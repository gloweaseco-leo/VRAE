"""Persistent bounded provider reservations, separate from synthetic Ledger and G1 jobs.

    Operator owns the DB path and retains it across restart; do not copy/restore an old
    checkpoint to retry. Lost/corrupt/mismatched quota fails closed. Unknown dispatch
    retains the full reservation. No background retry/refund or secret/body storage.
"""
from dataclasses import asdict
import json
import re
from pathlib import Path
import sqlite3

from .provider import INPUT_CAP, OUTPUT_RESERVE, digest, fail


class Quota:
    def __init__(self, path, *, create=False, batch=None):
        candidate = Path(path)
        if candidate.is_symlink() or (not create and not candidate.is_file()):
            fail('QUOTA_UNAVAILABLE')
        self.path = candidate.resolve()
        if batch is not None and (type(batch) is not str or
                not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{7,127}', batch)):
            fail('QUOTA_BATCH_INVALID')
        self.batch = batch
        if create:
            # Explicit exclusive initialization: never silently recreate a lost ledger.
            with self.path.open('xb'):
                pass
            with self._connect() as db:
                db.execute('CREATE TABLE policy (id INTEGER PRIMARY KEY CHECK(id=1), pin TEXT)')
                db.execute('CREATE TABLE calls (id TEXT PRIMARY KEY, intent TEXT, reserved INTEGER, '
                           'state TEXT, receipt TEXT, error TEXT)')
        if batch is not None:
            # Additive migration on the SAME operator-owned ledger. Existing
            # policy/calls are never replaced, reset or reclassified.
            with self._connect() as db:
                db.execute('CREATE TABLE IF NOT EXISTS authorization_batches '
                           '(id TEXT PRIMARY KEY, approval_ref TEXT UNIQUE NOT NULL, pin TEXT NOT NULL)')
                db.execute('CREATE TABLE IF NOT EXISTS call_batches '
                           '(call_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL)')

    def _owns(self, db, identity):
        if self.batch is not None and not db.execute(
                'SELECT 1 FROM call_batches WHERE call_id=? AND batch_id=?',
                (identity, self.batch)).fetchone():
            fail('QUOTA_BATCH_MISMATCH')

    def _connect(self):
        try:
            return sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=2)
        except Exception:
            fail('QUOTA_UNAVAILABLE')

    def reserve(self, identity, intent, *, config, permission, price, protocol_fake):
        policy = {**asdict(permission), 'expires_at': permission.expires_at.isoformat(),
                  'config': asdict(config), 'price': price.document, 'protocol_fake': protocol_fake}
        pin = digest(policy)
        amount = price.cost(INPUT_CAP, OUTPUT_RESERVE)
        try:
            with self._connect() as db:
                db.execute('BEGIN IMMEDIATE')
                held = (db.execute('SELECT pin FROM policy WHERE id=1').fetchone() if self.batch is None else
                        db.execute('SELECT pin FROM authorization_batches WHERE id=?', (self.batch,)).fetchone())
                if held is None:
                    if self.batch is None:
                        db.execute('INSERT INTO policy VALUES (1, ?)', (pin,))
                    else:
                        if db.execute('SELECT 1 FROM authorization_batches WHERE approval_ref=?',
                                      (permission.approval_ref,)).fetchone():
                            fail('BATCH_APPROVAL_ALREADY_USED')
                        db.execute('INSERT INTO authorization_batches VALUES (?, ?, ?)',
                                   (self.batch, permission.approval_ref, pin))
                elif held[0] != pin:
                    fail('QUOTA_POLICY_MISMATCH')
                if db.execute('SELECT 1 FROM calls WHERE id=?', (identity,)).fetchone():
                    fail('OPERATION_ALREADY_RESERVED')
                if self.batch is None:
                    count, spent = db.execute('SELECT count(*), coalesce(sum(reserved),0) FROM calls').fetchone()
                else:
                    count, spent = db.execute('SELECT count(*),coalesce(sum(c.reserved),0) FROM calls c '
                        'JOIN call_batches b ON b.call_id=c.id WHERE b.batch_id=?', (self.batch,)).fetchone()
                if count >= permission.max_calls or spent + amount > permission.cap_micros:
                    fail('BUDGET_REFUSED')
                db.execute('INSERT INTO calls VALUES (?, ?, ?, ?, NULL, NULL)',
                           (identity, intent, amount, 'DISPATCHED_USAGE_UNKNOWN'))
                if self.batch is not None:
                    db.execute('INSERT INTO call_batches VALUES (?, ?)', (identity, self.batch))
        except sqlite3.Error:
            fail('QUOTA_UNAVAILABLE')

    def settle(self, identity, intent, receipt):
        try:
            with self._connect() as db:
                self._owns(db, identity)
                cursor = db.execute('UPDATE calls SET reserved=?, state=?, receipt=? '
                    'WHERE id=? AND intent=? AND state=? AND reserved>=?',
                    (receipt['amount_micros'], 'USAGE_RECORDED', json.dumps(receipt), identity,
                     intent, 'DISPATCHED_USAGE_UNKNOWN', receipt['amount_micros']))
                if cursor.rowcount != 1:
                    fail('QUOTA_SETTLEMENT_REFUSED')
        except sqlite3.Error:
            fail('QUOTA_UNAVAILABLE')

    def unknown(self, identity, code):
        try:
            with self._connect() as db:
                self._owns(db, identity)
                db.execute('UPDATE calls SET error=? WHERE id=?', (code, identity))
        except sqlite3.Error:
            fail('QUOTA_UNAVAILABLE')

    def receipt(self, identity):
        try:
            with self._connect() as db:
                row = db.execute('SELECT receipt FROM calls WHERE id=?', (identity,)).fetchone()
                if row:
                    self._owns(db, identity)
                return json.loads(row[0]) if row and row[0] else None
        except sqlite3.Error:
            fail('QUOTA_UNAVAILABLE')

    def dispatched(self, identity):
        try:
            with self._connect() as db:
                found = db.execute('SELECT 1 FROM calls WHERE id=?', (identity,)).fetchone() is not None
                if found:
                    self._owns(db, identity)
                return found
        except sqlite3.Error:
            fail('QUOTA_UNAVAILABLE')

"""Persistent bounded provider reservations, separate from synthetic Ledger and G1 jobs.

    Operator owns the DB path and retains it across restart; do not copy/restore an old
    checkpoint to retry. Lost/corrupt/mismatched quota fails closed. Unknown dispatch
    retains the full reservation. No background retry/refund or secret/body storage.
"""
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3

from .provider import INPUT_CAP, OUTPUT_RESERVE, digest, fail


class Quota:
    def __init__(self, path, *, create=False):
        candidate = Path(path)
        if candidate.is_symlink() or (not create and not candidate.is_file()):
            fail('QUOTA_UNAVAILABLE')
        self.path = candidate.resolve()
        if create:
            # Explicit exclusive initialization: never silently recreate a lost ledger.
            with self.path.open('xb'):
                pass
            with self._connect() as db:
                db.execute('CREATE TABLE policy (id INTEGER PRIMARY KEY CHECK(id=1), pin TEXT)')
                db.execute('CREATE TABLE calls (id TEXT PRIMARY KEY, intent TEXT, reserved INTEGER, '
                           'state TEXT, receipt TEXT, error TEXT)')

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
                held = db.execute('SELECT pin FROM policy WHERE id=1').fetchone()
                if held is None:
                    db.execute('INSERT INTO policy VALUES (1, ?)', (pin,))
                elif held[0] != pin:
                    fail('QUOTA_POLICY_MISMATCH')
                if db.execute('SELECT 1 FROM calls WHERE id=?', (identity,)).fetchone():
                    fail('OPERATION_ALREADY_RESERVED')
                count, spent = db.execute('SELECT count(*), coalesce(sum(reserved),0) FROM calls').fetchone()
                if count >= permission.max_calls or spent + amount > permission.cap_micros:
                    fail('BUDGET_REFUSED')
                db.execute('INSERT INTO calls VALUES (?, ?, ?, ?, NULL, NULL)',
                           (identity, intent, amount, 'DISPATCHED_USAGE_UNKNOWN'))
        except sqlite3.Error:
            fail('QUOTA_UNAVAILABLE')

    def settle(self, identity, intent, receipt):
        try:
            with self._connect() as db:
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
                db.execute('UPDATE calls SET error=? WHERE id=?', (code, identity))
        except sqlite3.Error:
            fail('QUOTA_UNAVAILABLE')

    def receipt(self, identity):
        try:
            with self._connect() as db:
                row = db.execute('SELECT receipt FROM calls WHERE id=?', (identity,)).fetchone()
                return json.loads(row[0]) if row and row[0] else None
        except sqlite3.Error:
            fail('QUOTA_UNAVAILABLE')

    def dispatched(self, identity):
        try:
            with self._connect() as db:
                return db.execute('SELECT 1 FROM calls WHERE id=?', (identity,)).fetchone() is not None
        except sqlite3.Error:
            fail('QUOTA_UNAVAILABLE')

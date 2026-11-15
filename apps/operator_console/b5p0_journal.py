"""Private key-recovery bookkeeping. Business intents exist ONLY in PostgreSQL."""

import json
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from .contracts import refuse


class Journal:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS recovery(scope TEXT PRIMARY KEY, semantic TEXT NOT NULL, command BLOB NOT NULL, generation TEXT NOT NULL, receipt_sha TEXT)"
            )
        try:
            self.path.chmod(0o600)
        except OSError:
            raise ValueError("B5P0_PRIVATE_JOURNAL_REQUIRED") from None

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=3)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def read(self, scope):
        with self.connect() as c:
            row = c.execute(
                "SELECT semantic,command,generation,receipt_sha FROM recovery WHERE scope=?",
                (scope,),
            ).fetchone()
        return (
            None
            if row is None
            else {
                "semantic": row[0],
                "command": bytes(row[1]),
                "generation": row[2],
                "receipt_sha": row[3],
            }
        )

    def attempted(self, scope, semantic, command, generation):
        with self.connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO recovery VALUES(?,?,?,?,NULL)",
                (scope, semantic, command, generation),
            )
        row = self.read(scope)
        if row["semantic"] != semantic or row["command"] != command:
            refuse("B5P0_CONFLICT")
        return row

    def confirmed(self, scope, receipt_sha):
        with self.connect() as c:
            old = c.execute("SELECT receipt_sha FROM recovery WHERE scope=?", (scope,)).fetchone()
            if old is None or old[0] not in (None, receipt_sha):
                refuse("B5P0_CONFLICT")
            c.execute("UPDATE recovery SET receipt_sha=? WHERE scope=?", (receipt_sha, scope))

    def key(self, entry):
        return json.loads(entry["command"])["idempotency_key"]

"""Own the transaction and revalidate AFTER commit; never promise expiry rollback."""

import re

import psycopg

from vrae.persistence.private_bytes import Artifact, ByteGraph, Locator, locator, verify
from vrae.reviewing import ReviewTarget, validate_proposal
from vrae.reviewing.canonical import sha

from .contracts import Command, Denied, MODE, Receipt, Witness


def args(loc):
    return (loc.tenant, loc.ref_id, loc.source_run, loc.report, loc.version, loc.target_digest)


class IntentService:
    """Trusted local fixture supplies connection/provenance; HTTP supplies neither."""

    def __init__(self, connection, provenance, *, mode):
        if (
            mode != MODE
            or not connection.autocommit
            or connection.info.host != "127.0.0.1"
            or not re.fullmatch(r"vrae_p2b1_[0-9a-f]{12}", connection.info.dbname)
        ):
            raise Denied("B3_DISPOSABLE_LOOPBACK_REQUIRED")
        row = connection.execute(
            "SELECT session_user,current_user,current_setting('server_version_num')::int,"
            "rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,pg_has_role(session_user,'p2b1_review','MEMBER') "
            "FROM pg_roles WHERE rolname=session_user"
        ).fetchone()
        if (
            not row
            or row[0] != row[1]
            or not 160000 <= row[2] < 170000
            or any(row[3:7])
            or not row[7]
        ):
            raise Denied("B3_REVIEWER_SESSION_REQUIRED")
        self.connection = connection
        self.provenance = provenance
        self.actor = row[0]

    def _boundary(self, witness):
        if self.connection.info.transaction_status != 0:
            raise Denied("B3_OWNED_TRANSACTION_REQUIRED")
        if (
            type(witness) is not Witness
            or type(witness.location) is not Locator
            or witness.location != locator(self.provenance)
        ):
            raise Denied("B3_SERVER_WITNESS_LOCATOR_REQUIRED")

    def _validate_originals(self, loc, command):
        rows = self.connection.execute(
            "SELECT * FROM ra4a_review_test.load_target(%s,%s,%s,%s,%s,%s)", args(loc)
        ).fetchall()
        if not rows:
            raise Denied("B3_ORIGINAL_BYTES_REQUIRED")
        target, manifest = bytes(rows[0][0]), bytes(rows[0][1])
        artifacts = []
        for t, m, kind, key, raw, digest, length in rows:
            raw = bytes(raw)
            if (
                bytes(t) != target
                or bytes(m) != manifest
                or sha(raw) != digest
                or len(raw) != length
            ):
                raise Denied("B3_ORIGINAL_BYTES_INTEGRITY")
            artifacts.append(Artifact(kind, key, raw))
        graph = ByteGraph(loc.ref_id, target, tuple(artifacts), manifest, self.provenance.trust)
        verified = verify(graph, provenance=self.provenance)
        return validate_proposal(command.proposal(), ReviewTarget(verified.target))

    def submit(self, witness, command):
        self._boundary(witness)
        if type(command) is not Command:
            raise Denied("B3_COMMAND_REQUIRED")
        started_write = False
        try:
            with self.connection.transaction():
                digest = self._validate_originals(witness.location, command)
                started_write = True
                raw = bytes(
                    self.connection.execute(
                        "SELECT b3_p0.submit_test(%s,%s,%s,%s,%s,%s,%s,%s)",
                        (witness.token, *args(witness.location), command.payload),
                    ).fetchone()[0]
                )
                r = Receipt(raw).document
                if r["db_actor"] != self.actor or r["command_digest"] != digest:
                    raise Denied("B3_RECEIPT_BINDING")
            # Deferrable integrity/authority validation happened on real COMMIT.
            # A second transaction is necessary: physical COMMIT can cross expiry.
            checked = self.get_receipt(witness, r["idempotency_key"])
            if checked.payload != raw:
                raise Denied("B3_RECEIPT_CHANGED")
            return checked
        except (psycopg.OperationalError, psycopg.InterfaceError):
            raise Denied("UNKNOWN_COMMIT" if started_write else "B3_DATABASE_UNAVAILABLE") from None
        except psycopg.Error as exc:
            code = {
                "23505": "B3_IDEMPOTENCY_CONFLICT",
                "40001": "B3_STALE_CAS",
                "42501": "B3_AUTHORITY_DENIED",
                "P0002": "UNKNOWN_COMMIT",
            }.get(exc.sqlstate or "", "B3_SQL_DENIED")
            raise Denied(code) from None

    def get_receipt(self, witness, key):
        self._boundary(witness)
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{8,128}", key):
            raise Denied("B3_KEY_REQUIRED")
        try:
            with self.connection.transaction():
                raw = bytes(
                    self.connection.execute(
                        "SELECT b3_p0.get_receipt(%s,%s,%s,%s,%s,%s,%s,%s)",
                        (witness.token, *args(witness.location), key),
                    ).fetchone()[0]
                )
                r = Receipt(raw)
                if r.document["db_actor"] != self.actor:
                    raise Denied("B3_RECEIPT_BINDING")
            return r
        except (psycopg.OperationalError, psycopg.InterfaceError):
            raise Denied("UNKNOWN_COMMIT") from None
        except psycopg.Error as exc:
            raise Denied(
                "UNKNOWN_COMMIT" if exc.sqlstate == "P0002" else "B3_AUTHORITY_DENIED"
            ) from None

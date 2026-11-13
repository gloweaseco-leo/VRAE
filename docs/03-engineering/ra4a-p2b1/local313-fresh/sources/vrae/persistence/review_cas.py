"""Real atomic TEST_ONLY proposals, never a natural person's/native approval."""

import re
from dataclasses import dataclass

from vrae.reviewing import ReviewTarget, validate_proposal
from vrae.reviewing.canonical import COMMAND_LIMIT, canonical, parse, sha

from .contracts import PersistenceError
from .private_bytes import Artifact, ByteGraph, Locator, locator, verify

AUTHORITY = "TEST_ONLY_SYNTHETIC_DECISIONS_NOT_HUMAN_APPROVAL"
STATUSES = {
    "SIMULATED_APPROVE_CANDIDATE",
    "SIMULATED_CHANGES_REQUESTED",
    "SIMULATED_REJECTED",
    "SIMULATED_INTERNAL_SCOPE_ACK",
}


@dataclass(frozen=True)
class TestOnlyReviewReceipt:
    payload: bytes

    @property
    def document(self):
        return parse(self.payload, limit=262144)


def production_review_port(*args, **kwargs):
    raise PersistenceError("P2B1_REAL_IDENTITY_NATIVE_REVIEW_SHARE_DENIED")


class TestOnlyReviewCAS:
    """Caller supplies an existing isolated test DB connection, never an actor."""

    def __init__(self, connection, *, mode):
        if (
            mode != "TEST_ONLY_P2B1_REVIEW_CAS"
            or not connection.autocommit
            or connection.info.host not in ("127.0.0.1", "localhost")
            or not re.fullmatch(r"vrae_p2b1_[0-9a-f]{12}", connection.info.dbname)
        ):
            raise PersistenceError("P2B1_LOCAL_TEST_SESSION_REQUIRED")
        row = connection.execute(
            "SELECT session_user,current_setting('server_version_num')::int,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb "
            "FROM pg_roles WHERE rolname=session_user"
        ).fetchone()
        if row is None or not 160000 <= row[1] < 170000 or any(row[2:]):
            raise PersistenceError("P2B1_RUNTIME_ROLE_DENIED")
        self.connection = connection
        self.db_actor = row[0]

    def submit(self, location, proposal, *, provenance):
        if self.connection.info.transaction_status != 0:
            raise PersistenceError("P2B1_COMMIT_BOUNDARY_REQUIRED")
        if type(location) is not Locator or location != locator(provenance):
            raise PersistenceError("P2B1_EXACT_LOCATOR_REQUIRED")
        args = (
            location.tenant,
            location.ref_id,
            location.source_run,
            location.report,
            location.version,
            location.target_digest,
        )
        with self.connection.transaction():
            # Assignment/current-policy/version locks remain held through native
            # full byte replay, validate_proposal and the SQL CAS/commit.
            rows = self.connection.execute(
                "SELECT * FROM ra4a_review_test.load_target(%s,%s,%s,%s,%s,%s)", args
            ).fetchall()
            if not rows:
                raise PersistenceError("P2B1_ORIGINAL_BYTES_REQUIRED")
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
                    raise PersistenceError("P2B1_STORED_BYTES_INTEGRITY")
                artifacts.append(Artifact(kind, key, raw))
            candidate = ByteGraph(
                location.ref_id, target, tuple(artifacts), manifest, provenance.trust
            )
            verified = verify(candidate, provenance=provenance)
            command_digest = validate_proposal(proposal, ReviewTarget(verified.target))
            command = canonical(proposal.document, limit=COMMAND_LIMIT)
            raw_receipt = bytes(
                self.connection.execute(
                    "SELECT ra4a_review_test.submit(%s,%s,%s,%s,%s,%s,%s)", (*args, command)
                ).fetchone()[0]
            )
            receipt = TestOnlyReviewReceipt(raw_receipt)
            r = receipt.document
            if (
                r["authority"] != AUTHORITY
                or r["db_actor"] != self.db_actor
                or r["target_digest"] != location.target_digest
                or r["command_digest"] != command_digest
                or r["status"] not in STATUSES
                or r["review_seq"] != 1
                or r["report_event_seq"] < 1
                or r["native_decision"] is not None
                or r["native_approval"] is not None
                or r["share_grant"] is not None
                or r["external_visibility"] is not False
                or r["durable"] is not True
            ):
                raise PersistenceError("P2B1_INVALID_TEST_RECEIPT")
        # Return only after real commit; no approval permission is conveyed.
        return receipt

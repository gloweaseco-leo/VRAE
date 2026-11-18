"""Durable OFFLINE consumer fixture, not a deployed API/queue/CRM.

SQLite proves fixture commit/restart semantics only. No listener, collector,
provider, real ReviewDecision, real ShareGrant, email or VF call is present.
"""

from copy import deepcopy
from contextlib import contextmanager
import json
import sqlite3
from urllib.parse import urlsplit
from uuid import uuid4

from vrae.domain.access import require_access
from vrae.domain.business import advance_handoff
from vrae.domain.workflow import advance_run

from .contract import (
    VERSION,
    Refused,
    canonical,
    check_permission,
    digest,
    domain_call,
    status_view,
    validate,
)


class FixtureJournal:
    def __init__(self, path):
        if str(path) == ":memory:":
            raise ValueError("DURABLE_FIXTURE_PATH_REQUIRED")
        self.db = sqlite3.connect(path)
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS items(kind TEXT,tenant TEXT,id TEXT,idem TEXT,
            hash TEXT,document TEXT,withdrawn INTEGER DEFAULT 0,parent TEXT,
            PRIMARY KEY(kind,tenant,id),UNIQUE(kind,tenant,idem));
          CREATE TABLE IF NOT EXISTS outbox(tenant TEXT,audit TEXT,state TEXT,
            PRIMARY KEY(tenant,audit));
          CREATE TABLE IF NOT EXISTS events(tenant TEXT,event TEXT,hash TEXT,
            PRIMARY KEY(tenant,event));
        """)

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            yield

    def _read(self, kind, tenant, identity):
        row = self.db.execute(
            "SELECT document,withdrawn FROM items WHERE kind=? AND tenant=? AND id=?",
            (kind, tenant, identity),
        ).fetchone()
        if row is None or row[1]:
            raise Refused("FORBIDDEN_TENANT" if row is None else "POLICY_REVOKED")
        return json.loads(row[0])

    def _existing(self, kind, tenant, key, command):
        row = self.db.execute(
            "SELECT hash,document,withdrawn FROM items WHERE kind=? AND tenant=? AND idem=?",
            (kind, tenant, key),
        ).fetchone()
        if row and row[2]:
            raise Refused("POLICY_REVOKED")
        if row and row[0] != digest(command):
            raise Refused("IDEMPOTENCY_CONFLICT", 409)
        return json.loads(row[1]) if row else None

    def _write(self, kind, tenant, identity, document):
        self.db.execute(
            "UPDATE items SET document=? WHERE kind=? AND tenant=? AND id=?",
            (canonical(document).decode(), kind, tenant, identity),
        )

    def accept(
        self,
        command,
        header_key,
        caller,
        policy,
        verifier,
        now,
        *,
        queue_available=True,
        storage_available=True,
        capacity_available=True,
    ):
        check_permission(command, policy, caller, verifier, now)
        req = command["request"]
        if req["audit_mode"] == "L2":
            raise Refused("R0_L2_BRIDGE_NOT_AVAILABLE", 503)
        # .example is reserved fixture input; this stub never accepts live sites.
        if not (urlsplit(req["site_url"]).hostname or "").endswith(".example"):
            raise Refused("R0_FIXTURE_ONLY")
        if req["idempotency_key"] != header_key:
            raise Refused("IDEMPOTENCY_CONFLICT", 409)
        if not capacity_available:
            raise Refused("QUOTA_EXCEEDED", 429, True)
        if not storage_available:
            raise Refused("R0_STORAGE_UNAVAILABLE", 503, True)
        try:
            with self.transaction():
                stored = self._existing("audit", req["tenant_id"], header_key, command)
                if stored is None:
                    run = {
                        "schema_version": "1.0",
                        "tenant_id": req["tenant_id"],
                        "audit_id": req["audit_id"],
                        "request_id": req["request_id"],
                        "run_id": "run-" + uuid4().hex,
                        "status": "CREATED",
                        "attempt": 0,
                        "input_hash": digest(req),
                        "rule_version": "R0_NO_EXECUTION",
                        "started_at": None,
                        "finished_at": None,
                        "error_code": None,
                    }
                    stored = {"command": deepcopy(command), "run": run}
                    self.db.execute(
                        "INSERT INTO items(kind,tenant,id,idem,hash,document) VALUES(?,?,?,?,?,?)",
                        (
                            "audit",
                            req["tenant_id"],
                            req["audit_id"],
                            header_key,
                            digest(command),
                            canonical(stored).decode(),
                        ),
                    )
                    self.db.execute(
                        "INSERT INTO outbox VALUES(?,?,?)",
                        (req["tenant_id"], req["audit_id"], "PENDING_DISPATCH"),
                    )
        except sqlite3.IntegrityError:
            raise Refused("IDEMPOTENCY_CONFLICT", 409) from None
        except sqlite3.Error:
            raise Refused("R0_STORAGE_UNAVAILABLE", 503, True) from None
        if queue_available:
            self.dispatch(req["tenant_id"], req["audit_id"])
        state = self.db.execute(
            "SELECT state FROM outbox WHERE tenant=? AND audit=?",
            (req["tenant_id"], req["audit_id"]),
        ).fetchone()[0]
        body = {
            "contract_version": VERSION,
            "acceptance": {
                k: req[k] for k in ("schema_version", "tenant_id", "request_id", "audit_id")
            },
            "run_id": stored["run"]["run_id"],
            "durably_recorded": True,
            "queue_state": state,
            "diagnosis_complete": False,
        }
        body["acceptance"]["status"] = "CREATED"  # durable acceptance fact, not current run state
        validate("Accepted", body)
        return 202, body

    def dispatch(self, tenant, audit):
        """Fixture delivery of an atomically stored outbox; no actual queue."""
        with self.transaction():
            item = self._read("audit", tenant, audit)
            if item["run"]["status"] == "CREATED":
                item["run"]["status"] = domain_call(advance_run, "CREATED", "POLICY_CHECK")
                item["run"]["status"] = domain_call(advance_run, "POLICY_CHECK", "QUEUED")
                self._write("audit", tenant, audit, item)
                self.db.execute(
                    "UPDATE outbox SET state=? WHERE tenant=? AND audit=?",
                    ("DISPATCHED", tenant, audit),
                )

    def get_status(self, tenant, audit, caller, policy, verifier, now):
        item = self._read("audit", tenant, audit)
        check_permission(item["command"], policy, caller, verifier, now)
        return status_view(item["run"])

    def advance_fixture(self, tenant, audit, target):
        """Test-only producer of known V1 transitions; never an HTTP method."""
        with self.transaction():
            item = self._read("audit", tenant, audit)
            item["run"]["status"] = domain_call(advance_run, item["run"]["status"], target)
            self._write("audit", tenant, audit, item)

    def withdraw(self, tenant, audit, caller, policy, verifier, now):
        self.get_status(tenant, audit, caller, policy, verifier, now)
        with self.transaction():
            item = self._read("audit", tenant, audit)
            try:
                item["run"]["status"] = advance_run(item["run"]["status"], "CANCELLED")
            except ValueError:
                pass  # terminal review-ready is not rewritten to an illegal V1 state
            self._write("audit", tenant, audit, item)
            self.db.execute(
                "UPDATE items SET withdrawn=1 WHERE tenant=? AND ((kind=? AND id=?) OR (kind IN (?,?) AND parent=?))",
                (tenant, "audit", audit, "handoff", "grant", audit),
            )
        return status_view(item["run"], withdrawn=True)

    def request_handoff(self, command, caller, policy, verifier, now, *, current_report=None):
        validate("HandoffCommand", command)
        handoff = command["handoff"]
        tenant, identity = handoff["tenant_id"], handoff["handoff_id"]
        domain_call(require_access, caller, tenant, "handoff")
        status = self.get_status(tenant, handoff["audit_id"], caller, policy, verifier, now)
        from vrae.domain.contracts import validate_contract

        if current_report is None:
            raise Refused("REPORT_NOT_APPROVED")
        validate_contract("ReportVersion", current_report)
        if (
            status["run"]["status"] != "REVIEW_REQUIRED"
            or current_report["status"] != "APPROVED"
            or current_report["tenant_id"] != tenant
            or current_report["run_id"] != status["run"]["run_id"]
        ):
            raise Refused("REPORT_NOT_APPROVED")
        if current_report["report_version_id"] != handoff["report_version_id"]:
            raise Refused("REPORT_VERSION_STALE", 409)
        if handoff["stage"] != "HANDOFF_REQUESTED" or any(
            handoff[k] is not None
            for k in ("vf_receipt_ref", "inquiry_evidence_ref", "verified_by")
        ):
            raise Refused("BUSINESS_EVIDENCE_REQUIRED")
        with self.transaction():
            self._read("audit", tenant, handoff["audit_id"])
            old = self._existing("handoff", tenant, command["idempotency_key"], command)
            if old:
                return self._handoff_view(old)
            row = {
                "handoff": handoff,
                "request_sha256": digest(command),
                "delivery_state": "WAITING_ACK",
            }
            try:
                self.db.execute(
                    "INSERT INTO items(kind,tenant,id,idem,hash,document,parent) VALUES(?,?,?,?,?,?,?)",
                    (
                        "handoff",
                        tenant,
                        identity,
                        command["idempotency_key"],
                        digest(command),
                        canonical(row).decode(),
                        handoff["audit_id"],
                    ),
                )
            except sqlite3.IntegrityError:
                raise Refused("IDEMPOTENCY_CONFLICT", 409) from None
        return self._handoff_view(row)

    def register_grant_fixture(self, grant, proof, view, verifier, now):
        """A synthetic reference index, not a real ShareGrant issuance port."""
        from vrae.domain.contracts import validate_contract

        validate_contract("ShareGrant", grant)
        verifier.verify(
            proof, "share", {"grant": grant, "view_sha256": digest(view)}, grant["tenant_id"], now
        )
        doc = {"grant": grant, "view_sha256": digest(view)}
        with self.transaction():
            existing = self._existing("grant", grant["tenant_id"], grant["grant_id"], doc)
            if existing:
                return existing["grant"]
            self.db.execute(
                "INSERT INTO items(kind,tenant,id,idem,hash,document,parent) VALUES(?,?,?,?,?,?,?)",
                (
                    "grant",
                    grant["tenant_id"],
                    grant["grant_id"],
                    grant["grant_id"],
                    digest(doc),
                    canonical(doc).decode(),
                    view["audit_id"],
                ),
            )
        return grant

    def resolve_grant_fixture(self, tenant, grant_id):
        return self._read("grant", tenant, grant_id)

    def revoke_grant_fixture(self, tenant, grant_id, proof, verifier, now):
        verifier.verify(proof, "share", {"grant_id": grant_id, "action": "REVOKE"}, tenant, now)
        with self.transaction():
            self._read("grant", tenant, grant_id)
            self.db.execute(
                "UPDATE items SET withdrawn=1 WHERE kind=? AND tenant=? AND id=?",
                ("grant", tenant, grant_id),
            )

    @staticmethod
    def _handoff_view(row):
        body = {
            "contract_version": VERSION,
            "handoff": row["handoff"],
            "delivery_state": row["delivery_state"],
            "customer_approval": False,
            "counts_as_e2": False,
            "counts_as_e3": False,
            "quote_allowed": False,
        }
        validate("HandoffStatus", body)
        return body

    def receive(self, receipt, proof, verifier, now):
        validate("VFStorageReceipt", receipt)
        tenant, identity = receipt["tenant_id"], receipt["handoff_id"]
        with self.transaction():
            row = self._read("handoff", tenant, identity)
            h = row["handoff"]
            if (
                receipt["audit_id"] != h["audit_id"]
                or receipt["report_version_id"] != h["report_version_id"]
                or receipt["request_sha256"] != row["request_sha256"]
            ):
                raise Refused("BUSINESS_EVIDENCE_REQUIRED")
            verifier.verify(proof, "vf_storage", receipt, tenant, now)
            old = self.db.execute(
                "SELECT hash FROM events WHERE tenant=? AND event=?", (tenant, receipt["event_id"])
            ).fetchone()
            if old:
                if old[0] != digest(receipt):
                    raise Refused("IDEMPOTENCY_CONFLICT", 409)
                return self._handoff_view(row)
            h = {**h, "vf_receipt_ref": receipt["vf_receipt_ref"]}
            row["handoff"] = domain_call(
                advance_handoff,
                h,
                "VF_INQUIRY_RECORDED",
                {"tenant_id": tenant, "role": "SERVICE"},
                receipt_verified=True,
            )
            row["delivery_state"] = "ACKNOWLEDGED"
            self._write("handoff", tenant, identity, row)
            self.db.execute(
                "INSERT INTO events VALUES(?,?,?)", (tenant, receipt["event_id"], digest(receipt))
            )
        return self._handoff_view(row)

    def qualify(self, qualification, proof, verifier, now):
        validate("Qualification", qualification)
        q = qualification
        with self.transaction():
            row = self._read("handoff", q["tenant_id"], q["handoff_id"])
            key = verifier.verify(proof, "vf_qualification", q, q["tenant_id"], now)
            old = self.db.execute(
                "SELECT hash FROM events WHERE tenant=? AND event=?",
                (q["tenant_id"], q["event_id"]),
            ).fetchone()
            if old:
                if old[0] != digest(q):
                    raise Refused("IDEMPOTENCY_CONFLICT", 409)
                return self._handoff_view(row)
            if (
                q["verified_by"] != key.subject_ref
                or q["vf_receipt_ref"] != row["handoff"]["vf_receipt_ref"]
            ):
                raise Refused("BUSINESS_EVIDENCE_REQUIRED")
            h = {
                **row["handoff"],
                "verified_by": key.subject_ref,
                "inquiry_evidence_ref": q["inquiry_evidence_ref"],
            }
            row["handoff"] = domain_call(
                advance_handoff,
                h,
                "QUALIFIED_BY_HUMAN",
                {"tenant_id": q["tenant_id"], "role": key.role, "actor_id": key.subject_ref},
                qualification_confirmed=True,
            )
            self._write("handoff", q["tenant_id"], q["handoff_id"], row)
            self.db.execute(
                "INSERT INTO events VALUES(?,?,?)", (q["tenant_id"], q["event_id"], digest(q))
            )
        return self._handoff_view(row)

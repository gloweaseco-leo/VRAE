"""VF-B offline producer/consumer profile, not a web service or release gate.

All invitations, identities, return grants, sessions and publications are
synthetic fixtures. A future adapter must supply independently trusted current
resolvers. No client-provided role, release flag or latest version is trusted.
"""

from copy import deepcopy
import hashlib
import hmac
import json
import re
import sqlite3
from urllib.parse import urlsplit
from uuid import uuid4

from vrae.domain.policy import parse_time

from .contract import (
    Refused,
    canonical,
    check_permission,
    digest,
    simulate_report_read,
    validate,
)

VERSION = "vf-vrae-r0.1-vfb.1"
TASKS = ("DISCOVER", "UNDERSTAND", "TRUST", "INQUIRE", "SEARCH_TECHNICAL")
HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer"}
COOKIE_POLICY = {"HttpOnly": True, "Secure": True, "SameSite": "Strict", "Path": "/"}


def submission_document(submission):
    return {k: v for k, v in submission.items() if k != "submission_proof"}


def safe_error(error):
    """No existence, URL, evidence, token or caller input in safe error bodies."""
    status = error.status if error.status in {403, 409, 429, 503} else 403
    code = {403: "ACCESS_DENIED", 409: "CONFLICT", 429: "RATE_LIMITED", 503: "UNAVAILABLE"}[status]
    body = {
        "contract_version": VERSION,
        "http_status": status,
        "code": code,
        "retryable": status in {429, 503} and error.retryable,
        "retry_after_seconds": 60 if status == 429 else None,
    }
    validate("VFSafeError", body)
    return body


def vf_status(
    audit_ref, run, now, *, publication="UNPUBLISHED", version=None, access="ACTIVE", available=True
):
    """Trusted presentation helper. Expiry is access state, never AuditRun."""
    from vrae.domain.contracts import validate_contract

    validate_contract("AuditRun", run)
    if access != "ACTIVE":
        display = "expired" if access == "EXPIRED" else "access-ended"
    elif not available:
        display = "unavailable"
    elif publication == "WITHDRAWN":
        display = "access-ended"
    elif publication in {"APPROVED_FULL", "APPROVED_PARTIAL"}:
        if run["status"] != "REVIEW_REQUIRED" or not version:
            raise Refused("REPORT_NOT_APPROVED")
        display = "completed" if publication == "APPROVED_FULL" else "partial"
    elif run["status"] in {"CREATED", "POLICY_CHECK", "QUEUED"}:
        display = "accepted"
    elif run["status"] in {
        "POLICY_BLOCKED",
        "ACCESS_BLOCKED",
        "INSUFFICIENT_EVIDENCE",
        "MODEL_INVALID",
        "FAILED",
        "CANCELLED",
    }:
        display = "access-ended" if run["status"] == "CANCELLED" else "failed"
    else:
        display = "running"  # DRAFT_READY/REVIEW_REQUIRED are still unpublished
    body = {
        "contract_version": VERSION,
        "audit_ref": audit_ref,
        "task": {"status": run["status"], "run_id": run["run_id"], "progress_percent": None},
        "publication": {"state": publication, "report_version_id": version},
        "access": {"state": access},
        "display_state": display,
        "updated_at": now.isoformat(),
    }
    reasons = {
        "POLICY_BLOCKED": "SOURCE_POLICY_BLOCKED",
        "ACCESS_BLOCKED": "SOURCE_ACCESS_BLOCKED",
        "INSUFFICIENT_EVIDENCE": "NO_EVIDENCE",
        "MODEL_INVALID": "MODEL_INVALID",
        "FAILED": "TASK_FAILED",
        "CANCELLED": "WITHDRAWN",
        "DRAFT_READY": "PUBLICATION_PENDING",
        "REVIEW_REQUIRED": "PUBLICATION_PENDING",
    }
    reason = reasons.get(run["status"], "TASK_STAGE")
    if run["error_code"] == "QUOTA_EXCEEDED":
        reason = "RATE_LIMITED"
    if publication in {"APPROVED_FULL", "APPROVED_PARTIAL"}:
        reason = "APPROVED_PUBLICATION"
    elif publication == "WITHDRAWN":
        reason = "PUBLICATION_WITHDRAWN"
    if not available:
        reason = "DEPENDENCY_UNAVAILABLE"
    if access != "ACTIVE":
        reason = "ACCESS_EXPIRED" if access == "EXPIRED" else "ACCESS_ENDED"
    body["reason_code"] = reason
    body["retryable"] = reason == "RATE_LIMITED" and available and access == "ACTIVE"
    body["retry_after_seconds"] = 60 if body["retryable"] else None
    validate("VFStatus", body)
    return body


def validate_free_view(view, bundle):
    """Bind all projected facts/citations to independently approved originals.

    ISSUE is an explicit reviewed presentation label, never an inferred upgrade
    of a hypothesis. Owner's separate exact-view signature is checked by reader.
    """
    validate("FreePreDiagnosticView", view)
    original = bundle["view"]
    if (
        view["report_version_id"] != bundle["report"]["report_version_id"]
        or view["target_url"] != bundle["source_command"]["request"]["site_url"]
        or (original["citations"] and view["checked_at"] != original["citations"][0]["captured_at"])
    ):
        raise Refused("REPORT_VERSION_STALE", 409)
    if view["citations"] != original["citations"] or view["summary"] != original["summary"]:
        raise Refused("EVIDENCE_REFERENCE_INVALID")
    pages, coverage = view["pages"], view["coverage"]
    urls = [p["url"] for p in pages]
    successful = sum(p["outcome"] == "reviewed" for p in pages)
    if (
        len(set(urls)) != len(urls)
        or coverage["attempted"] != len(pages)
        or coverage["successful"] != successful
        or coverage["unknown"] != len(pages) - successful
        or not coverage["successful"] <= coverage["attempted"] <= coverage["authorized"]
        or coverage["authorized"] != original["coverage"]["authorized_pages"]
        or successful != original["coverage"]["observed_pages"]
    ):
        raise Refused("R0_COVERAGE_MISMATCH")
    citations = {c["citation_id"]: c for c in view["citations"]}
    originals = {f["finding_id"]: f for f in bundle["findings"]}
    ids, priorities, retained_originals = set(), set(), set()
    from vrae.collection.policy import canonical_url
    from vrae.collection.errors import CollectionError
    from vrae.domain.policy import authorize_source
    from .contract import domain_call

    for page in pages:
        try:
            canonical_url(page["url"])
        except CollectionError:
            raise Refused("SOURCE_NOT_ALLOWED") from None
        domain_call(
            authorize_source,
            {**bundle["source_command"]["request"], "site_url": page["url"]},
            bundle["source_policy"],
            parse_time(view["checked_at"]),
        )
        if page["outcome"] == "reviewed" and page["url"] not in {
            c["source_url"] for c in citations.values()
        }:
            raise Refused("EVIDENCE_REFERENCE_INVALID")
        if (page["outcome"] == "unknown") != (page["unknown_reason"] is not None):
            raise Refused("EVIDENCE_INSUFFICIENT")
    for task, facts in view["results"].items():
        for fact in facts:
            if fact["fact_id"] in ids or not set(fact["citation_ids"]) <= citations.keys():
                raise Refused("EVIDENCE_REFERENCE_INVALID")
            ids.add(fact["fact_id"])
            source = originals.get(fact["original_fact_ref"])
            if fact["status"] == "UNKNOWN" and (
                not fact["unknown_reason"] or not fact["next_check"]
            ):
                raise Refused("EVIDENCE_INSUFFICIENT")
            if fact["original_fact_ref"] is not None:
                if source is None:
                    raise Refused("EVIDENCE_REFERENCE_INVALID")
                retained_originals.add(fact["original_fact_ref"])
            if fact["kind"] == "UNKNOWN":
                if (
                    fact["status"] != "UNKNOWN"
                    or fact["citation_ids"]
                    or not fact["unknown_reason"]
                    or not fact["next_check"]
                ):
                    raise Refused("EVIDENCE_INSUFFICIENT")
                if source is not None and (
                    source["kind"] != "UNKNOWN"
                    or source["buyer_task"] != task
                    or source["statement"] != fact["statement"]["en"]
                ):
                    raise Refused("EVIDENCE_REFERENCE_INVALID")
            else:
                expected = "OBSERVATION" if fact["kind"] == "COUNTER_EVIDENCE" else fact["kind"]
                if (
                    source is None
                    or source["kind"] != expected
                    or source["buyer_task"] != task
                    or source["statement"] != fact["statement"]["en"]
                ):
                    raise Refused("EVIDENCE_REFERENCE_INVALID")
                if not fact["citation_ids"]:
                    raise Refused("EVIDENCE_INSUFFICIENT")
                if fact["kind"] in {"HYPOTHESIS", "RECOMMENDATION"} and fact["status"] != "UNKNOWN":
                    raise Refused("REPORT_NOT_APPROVED")
                if fact["status"] == "ISSUE":
                    if not fact["buyer_impact"] or not fact["rebuild"]:
                        raise Refused("EVIDENCE_INSUFFICIENT")
                    priorities.add(fact["fact_id"])
    if not set(view["priority"]) <= priorities:
        raise Refused("EVIDENCE_REFERENCE_INVALID")
    if retained_originals != originals.keys():
        raise Refused("EVIDENCE_REFERENCE_INVALID")
    if re.search(
        r"-----BEGIN|\bBearer\s|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.|[\w.+-]+@[\w.-]+",
        canonical(view).decode(),
    ):
        raise Refused("R0_PUBLIC_PROJECTION_DENIED")


class VFBCandidate:
    """Local fixture facade; adapters, live endpoints and real identity absent."""

    def __init__(self, journal, *, service_actor, invitations, publication_resolver):
        self.journal, self.db = journal, journal.db
        self.service_actor = service_actor
        self.invitations = invitations  # trusted current resolver stand-in
        self.publication_resolver = publication_resolver
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS vfb_refs(tenant TEXT,ref TEXT PRIMARY KEY,audit TEXT,
            hash TEXT,document TEXT,UNIQUE(tenant,audit));
          CREATE TABLE IF NOT EXISTS vfb_grants(ref TEXT PRIMARY KEY,document TEXT);
          CREATE TABLE IF NOT EXISTS vfb_sessions(hash TEXT PRIMARY KEY,ref TEXT,subject TEXT);
          CREATE TABLE IF NOT EXISTS vfb_exchanges(hash TEXT PRIMARY KEY);
          CREATE TABLE IF NOT EXISTS vfb_inquiries(tenant TEXT,idem TEXT,hash TEXT,
            PRIMARY KEY(tenant,idem));
        """)

    def _service(self, caller):
        if caller.get("actor_id") != self.service_actor or caller.get("role") != "SERVICE":
            raise Refused("FORBIDDEN_ROLE")

    @staticmethod
    def _response(body, status=200, **extra):
        return {"status": status, "headers": dict(HEADERS), "body": body, **extra}

    def _serve(self, function):
        try:
            return function()
        except Refused as error:
            body = safe_error(error)
            return self._response(body, body["http_status"])
        except sqlite3.Error:
            body = safe_error(Refused("R0_STORAGE_UNAVAILABLE", 503, True))
            return self._response(body, 503)

    def submit(self, submission, caller, policy, verifier, now, **faults):
        def execute():
            validate("VFSubmit", submission)
            self._service(caller)
            command = submission["command"]
            check_permission(command, policy, caller, verifier, now)
            invitation = self.invitations.get(submission["invitation_ref"])
            consent = submission["diagnosis_consent"]
            if (
                invitation is None
                or invitation["revoked"]
                or invitation["tenant_id"] != caller["tenant_id"]
                or invitation["subject_ref"] != submission["subject_ref"]
                or invitation["policy_sha256"] != digest(policy)
                or parse_time(invitation["expires_at"]) <= now
                or submission["normalized_host"]
                != urlsplit(command["request"]["site_url"]).hostname
                or consent["consent_version"] != command["permission_reference"]["consent_version"]
                or consent["text_sha256"] != command["permission_reference"]["consent_sha256"]
                or not parse_time(policy["created_at"]) <= parse_time(consent["accepted_at"]) <= now
            ):
                raise Refused("POLICY_REQUIRED")
            verifier.verify(
                submission["submission_proof"],
                "permission",
                submission_document(submission),
                caller["tenant_id"],
                now,
            )
            tenant, audit = caller["tenant_id"], command["request"]["audit_id"]
            old = self.db.execute(
                "SELECT ref,hash FROM vfb_refs WHERE tenant=? AND audit=?", (tenant, audit)
            ).fetchone()
            if old and old[1] != digest(submission):
                raise Refused("IDEMPOTENCY_CONFLICT", 409)
            _, accepted = self.journal.accept(
                command,
                command["request"]["idempotency_key"],
                caller,
                policy,
                verifier,
                now,
                **faults,
            )
            ref = old[0] if old else "aref-" + uuid4().hex
            if not old:
                with self.journal.transaction():
                    self.db.execute(
                        "INSERT INTO vfb_refs VALUES(?,?,?,?,?)",
                        (tenant, ref, audit, digest(submission), canonical(submission).decode()),
                    )
            body = {
                "contract_version": VERSION,
                "audit_ref": ref,
                "run_id": accepted["run_id"],
                "run_status": "CREATED",
                "diagnosis_complete": False,
                "poll_after_seconds": 10,
            }
            validate("VFAccepted", body)
            return self._response(body, 202)

        return self._serve(execute)

    def install_return_fixture(self, grant, proof, verifier, now):
        """Separate Owner-approved fixture issuance, never a browser endpoint."""
        validate("VFReturnGrant", grant)
        verifier.verify(proof, "share", grant, grant["tenant_id"], now)
        with self.journal.transaction():
            old = self.db.execute(
                "SELECT document FROM vfb_grants WHERE ref=?", (grant["audit_ref"],)
            ).fetchone()
            if old and json.loads(old[0]) != grant:
                raise Refused("IDEMPOTENCY_CONFLICT", 409)
            self.db.execute(
                "INSERT OR IGNORE INTO vfb_grants VALUES(?,?)",
                (grant["audit_ref"], canonical(grant).decode()),
            )

    def revoke_return_fixture(self, ref, proof, verifier, now):
        row = self.db.execute("SELECT document FROM vfb_grants WHERE ref=?", (ref,)).fetchone()
        if not row:
            raise Refused("FORBIDDEN_ROLE")
        grant = json.loads(row[0])
        verifier.verify(
            proof, "share", {"audit_ref": ref, "action": "REVOKE_RETURN"}, grant["tenant_id"], now
        )
        grant["revoked"] = True
        with self.journal.transaction():
            self.db.execute(
                "UPDATE vfb_grants SET document=? WHERE ref=?", (canonical(grant).decode(), ref)
            )

    def _resolve(self, ref, subject, caller, policy, verifier, now):
        self._service(caller)
        row = self.db.execute(
            "SELECT tenant,audit,document FROM vfb_refs WHERE ref=?", (ref,)
        ).fetchone()
        record = self.db.execute("SELECT document FROM vfb_grants WHERE ref=?", (ref,)).fetchone()
        if not row or not record:
            raise Refused("FORBIDDEN_ROLE")
        grant, submission = json.loads(record[0]), json.loads(row[2])
        if (
            row[0] != caller.get("tenant_id")
            or grant["tenant_id"] != row[0]
            or grant["subject_ref"] != subject
            or subject != submission["subject_ref"]
            or grant["revoked"]
            or parse_time(grant["expires_at"]) <= now
            or parse_time(grant["issued_at"]) > now
            or grant["policy_sha256"] != digest(policy)
        ):
            raise Refused("FORBIDDEN_ROLE")
        # Revalidate source authority for every task/report/citation/inquiry read.
        status = self.journal.get_status(row[0], row[1], caller, policy, verifier, now)
        invitation = self.invitations.get(submission["invitation_ref"])
        if (
            not invitation
            or invitation["revoked"]
            or parse_time(invitation["expires_at"]) <= now
            or invitation["tenant_id"] != row[0]
            or invitation["subject_ref"] != subject
            or invitation["policy_sha256"] != digest(policy)
        ):
            raise Refused("POLICY_REVOKED")
        return row[1], grant, status["run"]

    def exchange(self, ref, subject, return_token, caller, policy, verifier, now):
        def execute():
            _, grant, _ = self._resolve(ref, subject, caller, policy, verifier, now)
            hashed = hashlib.sha256(return_token.encode()).hexdigest()
            if not hmac.compare_digest(hashed, grant["token_sha256"]):
                raise Refused("FORBIDDEN_ROLE")
            cookie = "session-" + uuid4().hex
            try:
                with self.journal.transaction():
                    self.db.execute("INSERT INTO vfb_exchanges VALUES(?)", (hashed,))
                    self.db.execute(
                        "INSERT INTO vfb_sessions VALUES(?,?,?)",
                        (hashlib.sha256(cookie.encode()).hexdigest(), ref, subject),
                    )
            except sqlite3.IntegrityError:
                raise Refused("FORBIDDEN_ROLE") from None
            # Token travels only in a future Set-Cookie header; never JSON/URL.
            return self._response(
                {"restored": True},
                set_cookie={
                    "name": "__Host-vf-diagnosis",
                    "value": cookie,
                    **COOKIE_POLICY,
                    "Expires": grant["expires_at"],
                },
            )

        return self._serve(execute)

    def _session(self, ref, cookie, caller, policy, verifier, now):
        row = self.db.execute(
            "SELECT ref,subject FROM vfb_sessions WHERE hash=?",
            (hashlib.sha256(cookie.encode()).hexdigest(),),
        ).fetchone()
        if not row or row[0] != ref:
            raise Refused("FORBIDDEN_ROLE")
        return self._resolve(ref, row[1], caller, policy, verifier, now)

    def _publication(self, audit, ref, policy, verifier, now, subject):
        record = self.publication_resolver(audit)
        if record is None:
            return None
        bundle, view = record["bundle"], record["free_view"]
        if record["principal"]["subject_ref"] != subject:
            raise Refused("FORBIDDEN_ROLE")
        actual_run = self.journal._read("audit", bundle["report"]["tenant_id"], audit)["run"]
        if (
            actual_run["run_id"] != bundle["run"]["run_id"]
            or actual_run["status"] != "REVIEW_REQUIRED"
            or actual_run["input_hash"] != bundle["run"]["input_hash"]
            or bundle["source_policy"] != policy
        ):
            raise Refused("REPORT_NOT_APPROVED")
        simulate_report_read(
            bundle,
            record["principal"],
            record["server_bearer"],
            verifier,
            now,
            current_grant=record["current_grant"],
        )
        validate_free_view(view, bundle)
        if view["audit_ref"] != ref or bundle["view"]["audit_id"] != audit:
            raise Refused("FORBIDDEN_ROLE")
        verifier.verify(
            record["projection_proof"],
            "share",
            {
                "audit_ref": ref,
                "report_version_id": view["report_version_id"],
                "view_sha256": digest(view),
            },
            bundle["report"]["tenant_id"],
            now,
        )
        return record

    def read(self, operation, ref, cookie, caller, policy, verifier, now, *, citation_id=None):
        def execute():
            if operation not in {"status", "report", "citation"}:
                raise Refused("FORBIDDEN_ROLE")
            audit, grant, run = self._session(ref, cookie, caller, policy, verifier, now)
            record = self._publication(audit, ref, policy, verifier, now, grant["subject_ref"])
            if operation == "status":
                publication, version = "UNPUBLISHED", None
                if record:
                    view = record["free_view"]
                    publication = (
                        "APPROVED_PARTIAL" if view["coverage"]["unknown"] else "APPROVED_FULL"
                    )
                    version = view["report_version_id"]
                return self._response(
                    vf_status(ref, run, now, publication=publication, version=version)
                )
            if not record:
                raise Refused("REPORT_NOT_APPROVED")
            view = record["free_view"]
            if operation == "citation":
                found = [c for c in view["citations"] if c["citation_id"] == citation_id]
                if not found:
                    raise Refused("FORBIDDEN_ROLE")
                return self._response(deepcopy(found[0]))
            return self._response(deepcopy(view))

        return self._serve(execute)

    def inquiry(self, envelope, cookie, caller, policy, verifier, now):
        def execute():
            validate("VFInquiry", envelope)
            ref = envelope["audit_ref"]
            audit, grant, _ = self._session(ref, cookie, caller, policy, verifier, now)
            record = self._publication(audit, ref, policy, verifier, now, grant["subject_ref"])
            command, consent = envelope["command"], envelope["inquiry_consent"]
            if (
                record is None
                or envelope["report_version_id"] != record["bundle"]["report"]["report_version_id"]
                or command["handoff"]["audit_id"] != audit
                or command["handoff"]["report_version_id"] != envelope["report_version_id"]
                or consent["consent_version"] != "VF-INQUIRY-CONSENT-DRAFT-1"
                or consent["text_sha256"] != digest("SYNTHETIC separate inquiry consent")
                or not parse_time(policy["created_at"]) <= parse_time(consent["accepted_at"]) <= now
            ):
                raise Refused("BUSINESS_EVIDENCE_REQUIRED")
            old = self.db.execute(
                "SELECT hash FROM vfb_inquiries WHERE tenant=? AND idem=?",
                (caller["tenant_id"], command["idempotency_key"]),
            ).fetchone()
            if old and old[0] != digest(envelope):
                raise Refused("IDEMPOTENCY_CONFLICT", 409)
            body = self.journal.request_handoff(
                command, caller, policy, verifier, now, current_report=record["bundle"]["report"]
            )
            with self.journal.transaction():
                self.db.execute(
                    "INSERT OR IGNORE INTO vfb_inquiries VALUES(?,?,?)",
                    (caller["tenant_id"], command["idempotency_key"], digest(envelope)),
                )
            return self._response(body, 202)

        return self._serve(execute)


def safe_log_record(operation, code):
    """Only fixed low-cardinality labels may enter ordinary logs/analytics."""
    if operation not in {"submit", "status", "exchange", "report", "citation", "inquiry"}:
        raise Refused("FORBIDDEN_ROLE")
    allowed = {
        "ACCEPTED",
        "ACCESS_DENIED",
        "CONFLICT",
        "SOURCE_BLOCKED",
        "RATE_LIMITED",
        "NO_EVIDENCE",
        "MODEL_INVALID",
        "UNAVAILABLE",
    }
    if code not in allowed:
        raise Refused("FORBIDDEN_ROLE")
    return {"operation": operation, "code": code}

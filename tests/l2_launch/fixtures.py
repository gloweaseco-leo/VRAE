"""Public synthetic seeds/identities; none may sign real review/share/receipts."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import sqlite3

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from contracts.l2_launch.contract import (
    VERSION,
    FixtureVerifier,
    TrustedFixtureKey,
    canonical,
    digest,
    permission_document,
)
from vrae.domain.reviews import report_content_hash

NOW = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
ISSUED = "2026-11-18T11:00:00Z"
EXPIRES = "2026-11-19T12:00:00Z"
TENANT = "tenant-r0-fixture"
CALLER = {"tenant_id": TENANT, "actor_id": "vf-bff-fixture", "role": "SERVICE"}
BEARER = "fixture-recipient-token-not-a-live-credential"
PRINCIPAL = {
    "tenant_id": TENANT,
    "subject_ref": "recipient-fixture",
    "audience": "vrae-report",
    "expires_at": EXPIRES,
    "token_revoked": False,
}
IDENTITIES = {
    "permission": ("PERMISSION_AUTHORITY", "permission-fixture", 1),
    "review": ("REVIEWER", "reviewer-fixture", 2),
    "owner": ("OWNER", "owner-fixture", 3),
    "vf": ("VF_STORAGE_SERVICE", "vf-service-fixture", 4),
    "qualifier": ("OWNER", "human-commercial-fixture", 5),
}


def private_key(name):
    return Ed25519PrivateKey.from_private_bytes(bytes([IDENTITIES[name][2]]) * 32)


def verifier():
    return FixtureVerifier(
        {
            "key-" + name: TrustedFixtureKey(
                private_key(name).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw),
                TENANT,
                subject,
                role,
            )
            for name, (role, subject, _) in IDENTITIES.items()
        }
    )


def sign(name, purpose, document):
    unsigned = {
        "alg": "Ed25519",
        "key_id": "key-" + name,
        "claim": {
            "audience": "vrae-launch-r0-contract",
            "purpose": purpose,
            "tenant_id": TENANT,
            "subject_ref": IDENTITIES[name][1],
            "document_sha256": digest(document),
            "issued_at": ISSUED,
            "expires_at": EXPIRES,
        },
    }
    return {**unsigned, "signature": private_key(name).sign(canonical(unsigned)).hex()}


def audit_fixture():
    policy = {
        "schema_version": "1.0",
        "tenant_id": TENANT,
        "policy_id": "policy-fixture",
        "policy_version": 1,
        "mode": "OWNER_AUTHORIZED_DEEP",
        "permitted_hosts": ["legacy.example"],
        "scope_paths": ["/products"],
        "authorization_reference": "permission-ref-fixture",
        "expires_at": EXPIRES,
        "revoked_at": None,
        "created_at": ISSUED,
    }
    request = {
        "schema_version": "1.0",
        "tenant_id": TENANT,
        "request_id": "request-fixture",
        "audit_id": "audit-fixture",
        "site_url": "https://legacy.example/products/p40",
        "audit_mode": "L1",
        "source_policy_ref": "policy-fixture",
        "source_policy_version": 1,
        "source_system": "veyfront",
        "source_reference": "vf-source-fixture",
        "idempotency_key": "fixture-idempotency-01",
        "requested_at": ISSUED,
    }
    command = {
        "contract_version": VERSION,
        "request": request,
        "permission_reference": {
            "reference": "permission-ref-fixture",
            "consent_version": "VF-SCAN-CONSENT-DRAFT-1",
            "consent_sha256": digest("SYNTHETIC consent text, not legal authorization"),
        },
    }
    command["permission_reference"]["proof"] = sign(
        "permission", "permission", permission_document(command, policy)
    )
    return command, policy


def resign_permission(command, policy):
    command["permission_reference"]["proof"] = sign(
        "permission", "permission", permission_document(command, policy)
    )


def report_bundle(kind="PublicPreviewView", run_id="run-fixture"):
    mode = "L2" if kind == "ApprovedL2ReportView" else "L1"
    finding = {
        "schema_version": "1.0",
        "tenant_id": TENANT,
        "finding_id": "finding-fixture",
        "run_id": "run-fixture",
        "observation_id": "observation-fixture",
        "kind": "OBSERVATION",
        "evidence_ids": ["evidence-fixture"],
        "statement": "Synthetic bounded sample declares model P40; no live collection.",
        "buyer_task": "UNDERSTAND",
        "severity": None,
        "rule_version": "R0_FIXTURE_ONLY",
    }
    report = {
        "schema_version": "1.0",
        "tenant_id": TENANT,
        "report_id": "report-fixture",
        "report_version_id": "report-fixture.v1",
        "run_id": "run-fixture",
        "version": 1,
        "content_hash": "0" * 64,
        "status": "APPROVED",
        "finding_ids": ["finding-fixture"],
        "created_by": "producer-fixture",
        "created_at": ISSUED,
        "approved_by": "reviewer-fixture",
        "approved_at": ISSUED,
        "audit_mode": mode,
    }
    report["content_hash"] = report_content_hash(report, [finding])
    decision = {
        "schema_version": "1.0",
        "tenant_id": TENANT,
        "decision_id": "decision-fixture",
        "report_version_id": report["report_version_id"],
        "version": 1,
        "content_hash": report["content_hash"],
        "reviewer_id": "reviewer-fixture",
        "action": "APPROVE",
        "reason": "SYNTHETIC CONSUMER FIXTURE, never formal human review",
        "decided_at": ISSUED,
    }
    grant = {
        "schema_version": "1.0",
        "tenant_id": TENANT,
        "grant_id": "grant-fixture",
        "report_version_id": report["report_version_id"],
        "content_hash": report["content_hash"],
        "subject_ref": PRINCIPAL["subject_ref"],
        "token_hash": hashlib.sha256(BEARER.encode()).hexdigest(),
        "status": "ACTIVE",
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
        "revoked_at": None,
    }
    view = {
        "contract_version": VERSION,
        "view_type": kind,
        **{
            k: report[k]
            for k in (
                "tenant_id",
                "run_id",
                "report_id",
                "report_version_id",
                "version",
                "content_hash",
                "audit_mode",
            )
        },
        "audit_id": "audit-fixture",
        "audience": "AUTHORIZED_RECIPIENT",
        "anonymous_access": False,
        "summary": {
            "A": {
                "en": "Synthetic retained snippet declares model P40; no live collection.",
                "zh": "合成留存片段声明型号P40；未执行真实采集。",
                "basis": "OBSERVATION",
                "citation_ids": ["citation-fixture"],
            },
            "B": {
                "en": "Ask the supplier to verify operating conditions. Delivery and conversion are UNKNOWN.",
                "zh": "建议向供应商核对工况；送达及转化结果UNKNOWN。",
                "basis": "RECOMMENDATION",
                "citation_ids": ["citation-fixture"],
            },
        },
        "citations": [
            {
                "citation_id": "citation-fixture",
                "source_url": "https://legacy.example/products/p40",
                "captured_at": ISSUED,
                "locator": "synthetic-sample:paragraph-1",
                "excerpt": "Model P40 — synthetic reference only.",
            }
        ],
        "unknowns": ["FORM_SUBMISSION", "INQUIRY_DELIVERY", "CONVERSION", "WHOLE_SITE_COVERAGE"],
        "coverage": {"observed_pages": 1, "authorized_pages": 3, "whole_site_denominator": None},
    }
    source_command, source_policy = audit_fixture()
    source_command["request"]["audit_mode"] = mode
    resign_permission(source_command, source_policy)
    run = {
        "schema_version": "1.0",
        "tenant_id": TENANT,
        "audit_id": "audit-fixture",
        "request_id": "request-fixture",
        "run_id": "run-fixture",
        "status": "REVIEW_REQUIRED",
        "attempt": 1,
        "input_hash": digest(source_command["request"]),
        "rule_version": "R0_FIXTURE_ONLY",
        "started_at": ISSUED,
        "finished_at": ISSUED,
        "error_code": None,
    }
    if run_id != "run-fixture":
        report["run_id"] = finding["run_id"] = run["run_id"] = view["run_id"] = run_id
        report["content_hash"] = report_content_hash(report, [finding])
        decision["content_hash"] = grant["content_hash"] = view["content_hash"] = report[
            "content_hash"
        ]
    return {
        "report": report,
        "decision": decision,
        "grant": grant,
        "view": view,
        "findings": [finding],
        "source_command": source_command,
        "source_policy": source_policy,
        "source_caller": deepcopy(CALLER),
        "run": run,
        "latest_version": 1,
        "review_proof": sign("review", "review", decision),
        "share_proof": sign("owner", "share", {"grant": grant, "view_sha256": digest(view)}),
    }


def reseal_report(bundle):
    bundle["review_proof"] = sign("review", "review", bundle["decision"])
    bundle["share_proof"] = sign(
        "owner", "share", {"grant": bundle["grant"], "view_sha256": digest(bundle["view"])}
    )


def handoff_fixture(audit="audit-fixture", identity="handoff-fixture"):
    return {
        "contract_version": VERSION,
        "idempotency_key": identity + "-idempotency",
        "consent_reference": "vf-contact-consent-fixture",
        "handoff": {
            "schema_version": "1.0",
            "tenant_id": TENANT,
            "handoff_id": identity,
            "audit_id": audit,
            "report_version_id": "report-fixture.v1",
            "source_system": "vrae",
            "stage": "HANDOFF_REQUESTED",
            "vf_receipt_ref": None,
            "inquiry_evidence_ref": None,
            "verified_by": None,
            "created_at": ISSUED,
        },
    }


class FixtureVFStore:
    """Independent local storage issuer; no VF repository/client/contact API."""

    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY,hash TEXT,document TEXT)"
        )

    def record(self, command, *, storage_available=True):
        if not storage_available:
            raise OSError("SYNTHETIC_VF_STORAGE_FAILURE")
        h = command["handoff"]
        row = self.db.execute(
            "SELECT hash,document FROM receipts WHERE id=?", (h["handoff_id"],)
        ).fetchone()
        if row:
            if row[0] != digest(command):
                raise ValueError("VF_IDEMPOTENCY_CONFLICT")
            receipt = json_load(row[1])
        else:
            receipt = {
                "contract_version": VERSION,
                "event_id": "event-" + h["handoff_id"],
                "tenant_id": h["tenant_id"],
                "audit_id": h["audit_id"],
                "handoff_id": h["handoff_id"],
                "report_version_id": h["report_version_id"],
                "request_sha256": digest(command),
                "vf_receipt_ref": "VF-FIXTURE-" + h["handoff_id"],
                "storage_receipt_sha256": digest(
                    {"opaque_ref": h["handoff_id"], "fixture_storage": "COMMITTED"}
                ),
                "stored_at": ISSUED,
                "outcome": "STORED",
            }
            with self.db:
                self.db.execute(
                    "INSERT INTO receipts VALUES(?,?,?)",
                    (h["handoff_id"], digest(command), canonical(receipt).decode()),
                )
            assert (
                self.db.execute(
                    "SELECT document FROM receipts WHERE id=?", (h["handoff_id"],)
                ).fetchone()[0]
                == canonical(receipt).decode()
            )
        return deepcopy(receipt), sign("vf", "vf_storage", receipt)


def json_load(value):
    import json

    return json.loads(value)

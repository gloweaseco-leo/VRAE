"""Rebuild public synthetic JSON examples; no requests or live business writes."""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import UUID

from contracts.l2_launch.contract import (
    VERSION,
    Refused,
    availability,
    error_reply,
    status_view,
    validate,
)
from contracts.l2_launch.fixture_stub import FixtureJournal
from tests.l2_launch.fixtures import (
    CALLER,
    NOW,
    TENANT,
    FixtureVFStore,
    audit_fixture,
    handoff_fixture,
    report_bundle,
    sign,
    verifier,
)

ROOT = Path(__file__).resolve().parents[2]


def build():
    command, policy = audit_fixture()
    result = {
        "availability": ("Availability", availability()),
        "submission": ("AuditCommand", command),
    }
    for kind in ("PublicPreviewView", "ApprovedL2ReportView"):
        result[kind] = ("ReportView", report_bundle(kind)["view"])
    uncollected = deepcopy(result["PublicPreviewView"][1])
    uncollected["citations"] = []
    uncollected["coverage"]["observed_pages"] = 0
    uncollected["unknowns"].append("NO_CAPTURE")
    uncollected["summary"]["A"] = {
        "en": "No authorized capture retained. No site fault established.",
        "zh": "尚无获准采集留存；没有据此认定网站问题。",
        "basis": "UNKNOWN",
        "citation_ids": [],
    }
    uncollected["summary"]["B"]["citation_ids"] = []
    result["uncollected-unknown"] = ("ReportView", uncollected)
    for status, code, retryable in [
        (403, "REPORT_NOT_APPROVED", False),
        (409, "REPORT_VERSION_STALE", False),
        (429, "QUOTA_EXCEEDED", True),
        (503, "R0_STORAGE_UNAVAILABLE", True),
    ]:
        result["error-" + str(status)] = (
            "Error",
            error_reply(Refused(code, status, retryable), "request-fixture"),
        )
    with TemporaryDirectory(prefix="vrae-r0-contract-") as directory:
        journal = FixtureJournal(Path(directory) / "vrae.sqlite")
        vf = FixtureVFStore(Path(directory) / "vf.sqlite")
        try:
            with patch("contracts.l2_launch.fixture_stub.uuid4", return_value=UUID(int=1)):
                _, accepted = journal.accept(
                    command,
                    command["request"]["idempotency_key"],
                    CALLER,
                    policy,
                    verifier(),
                    NOW,
                    queue_available=False,
                )
            result["accepted-202-pending-dispatch"] = ("Accepted", accepted)
            result["status-created"] = (
                "AuditStatus",
                journal.get_status(TENANT, "audit-fixture", CALLER, policy, verifier(), NOW),
            )
            for state in ("POLICY_BLOCKED", "ACCESS_BLOCKED", "INSUFFICIENT_EVIDENCE", "FAILED"):
                run = deepcopy(report_bundle()["run"])
                run["status"] = state
                result["status-" + state.lower()] = ("AuditStatus", status_view(run))
            handoff = handoff_fixture()
            journal.dispatch(TENANT, "audit-fixture")
            for state in ("FETCHING", "EVIDENCE_READY", "RULED", "DRAFT_READY", "REVIEW_REQUIRED"):
                journal.advance_fixture(TENANT, "audit-fixture", state)
            result["handoff-waiting-ack"] = (
                "HandoffStatus",
                journal.request_handoff(
                    handoff,
                    CALLER,
                    policy,
                    verifier(),
                    NOW,
                    current_report=report_bundle(run_id=accepted["run_id"])["report"],
                ),
            )
            receipt, proof = vf.record(handoff)
            result["vf-storage-receipt"] = ("VFStorageReceipt", receipt)
            result["vf-storage-attestation"] = ("Attestation", proof)
            result["vf-inquiry-recorded"] = (
                "HandoffStatus",
                journal.receive(receipt, proof, verifier(), NOW),
            )
            q = {
                "contract_version": VERSION,
                "event_id": "qualification-event-fixture",
                "tenant_id": TENANT,
                "handoff_id": "handoff-fixture",
                "vf_receipt_ref": receipt["vf_receipt_ref"],
                "inquiry_evidence_ref": "inquiry-fixture",
                "verified_by": "human-commercial-fixture",
                "confirmed_at": NOW.isoformat(),
            }
            result["qualification"] = ("Qualification", q)
            result["qualified-by-human-fixture-only"] = (
                "HandoffStatus",
                journal.qualify(q, sign("qualifier", "vf_qualification", q), verifier(), NOW),
            )
            result["withdrawn"] = (
                "AuditStatus",
                journal.withdraw(TENANT, "audit-fixture", CALLER, policy, verifier(), NOW),
            )
        finally:
            journal.close()
            vf.db.close()
    return {
        name: {"scope": "SYNTHETIC_CONTRACT_FIXTURE_NOT_A_RELEASE", "type": kind, "body": body}
        for name, (kind, body) in result.items()
    }


def main():
    folder = ROOT / "contracts/l2_launch/examples"
    folder.mkdir(parents=True, exist_ok=True)
    examples = build()
    for name, sample in examples.items():
        validate(sample["type"], sample["body"])
        (folder / (name + ".json")).write_text(
            json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps({"examples": len(examples), "scope": "SYNTHETIC_CONTRACT_ONLY"}))


if __name__ == "__main__":
    main()

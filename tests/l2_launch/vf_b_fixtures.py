"""VF-B fixtures only: public fake consent, invitations and return secrets."""

from copy import deepcopy
import hashlib

from contracts.l2_launch.contract import digest
from contracts.l2_launch.vf_b import VERSION, TASKS, VFBCandidate, submission_document
from vrae.domain.reviews import report_content_hash
from .fixtures import (
    CALLER,
    PRINCIPAL,
    BEARER,
    TENANT,
    ISSUED,
    EXPIRES,
    audit_fixture,
    handoff_fixture,
    report_bundle,
    reseal_report,
    sign,
)

RETURN_TOKEN = "synthetic-return-exchange-only-never-live"


def submit_fixture():
    command, policy = audit_fixture()
    permission = command["permission_reference"]
    body = {
        "contract_version": VERSION,
        "command": command,
        "normalized_host": "legacy.example",
        "language": "zh",
        "subject_ref": PRINCIPAL["subject_ref"],
        "invitation_ref": "invitation-fixture",
        "diagnosis_consent": {
            "consent_version": permission["consent_version"],
            "accepted_at": ISSUED,
            "text_sha256": permission["consent_sha256"],
        },
    }
    body["submission_proof"] = sign("permission", "permission", submission_document(body))
    invitation = {
        "tenant_id": TENANT,
        "subject_ref": PRINCIPAL["subject_ref"],
        "policy_sha256": digest(policy),
        "expires_at": EXPIRES,
        "revoked": False,
    }
    return body, policy, {"invitation-fixture": invitation}


def facade_fixture(journal):
    submission, policy, invitations = submit_fixture()
    publications = {}
    adapter = VFBCandidate(
        journal,
        service_actor=CALLER["actor_id"],
        invitations=invitations,
        publication_resolver=publications.get,
    )
    return adapter, submission, policy, publications


def return_fixture(ref, policy):
    return {
        "contract_version": VERSION,
        "tenant_id": TENANT,
        "audit_ref": ref,
        "subject_ref": PRINCIPAL["subject_ref"],
        "audience": "vf-bff-return",
        "purpose": "DIAGNOSIS_RETURN_ONLY",
        "token_sha256": hashlib.sha256(RETURN_TOKEN.encode()).hexdigest(),
        "policy_sha256": digest(policy),
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
        "revoked": False,
    }


def text(en, zh="合成契约示例，未采集真实网站。"):
    return {"en": en, "zh": zh}


def free_publication_fixture(ref, run_id):
    bundle = report_bundle(run_id=run_id)
    finding = bundle["findings"][0]
    for suffix, kind, statement in [
        ("counter", "OBSERVATION", "Synthetic sample does not establish material suitability."),
        (
            "hypothesis",
            "HYPOTHESIS",
            "A buyer may need an engineering check; this is a hypothesis.",
        ),
        ("recommendation", "RECOMMENDATION", "Ask the supplier to verify operating conditions."),
    ]:
        bundle["findings"].append(
            {**finding, "finding_id": "finding-" + suffix, "kind": kind, "statement": statement}
        )
    report = bundle["report"]
    report["finding_ids"] = [f["finding_id"] for f in bundle["findings"]]
    report["content_hash"] = report_content_hash(report, bundle["findings"])
    for obj in (bundle["decision"], bundle["grant"], bundle["view"]):
        obj["content_hash"] = report["content_hash"]
    reseal_report(bundle)

    def unknown(task):
        return {
            "fact_id": "unknown-" + task.lower(),
            "original_fact_ref": None,
            "kind": "UNKNOWN",
            "status": "UNKNOWN",
            "statement": text("No observation retained for this task."),
            "citation_ids": [],
            "buyer_impact": None,
            "rebuild": None,
            "unknown_reason": "NOT_OBSERVED",
            "next_check": text("Verify within newly approved scope."),
        }

    results = {t: [unknown(t)] for t in TASKS}
    facts = []
    for index, original in enumerate(bundle["findings"]):
        kind = "COUNTER_EVIDENCE" if index == 1 else original["kind"]
        facts.append(
            {
                "fact_id": "projected-" + str(index),
                "original_fact_ref": original["finding_id"],
                "kind": kind,
                "status": "ISSUE" if index == 0 else "OBSERVED" if index == 1 else "UNKNOWN",
                "statement": text(original["statement"]),
                "citation_ids": ["citation-fixture"],
                "buyer_impact": text(
                    "Engineering suitability may remain uncertain; hypothesis only."
                )
                if index == 0
                else None,
                "rebuild": text(
                    "Add a verified operating-conditions reference; recommendation only."
                )
                if index == 0
                else None,
                "unknown_reason": "UNVERIFIED_INFERENCE" if index > 1 else None,
                "next_check": text("Verify with a qualified reviewer.") if index > 1 else None,
            }
        )
    results["UNDERSTAND"] = facts + results["UNDERSTAND"]
    view = {
        "contract_version": VERSION,
        "view_type": "FreePreDiagnosticView",
        "kind": "synthetic",
        "audience": "AUTHORIZED_RECIPIENT",
        "anonymous_access": False,
        "audit_ref": ref,
        "report_version_id": report["report_version_id"],
        "target_url": "https://legacy.example/products/p40",
        "checked_at": ISSUED,
        "source": "SYNTHETIC_CONTRACT_FIXTURE_NOT_A_RELEASE",
        "pages": [
            {
                "url": "https://legacy.example/products/p40",
                "label": "Synthetic product",
                "outcome": "reviewed",
                "unknown_reason": None,
            },
            {
                "url": "https://legacy.example/products/p41",
                "label": "Synthetic unavailable sample",
                "outcome": "unknown",
                "unknown_reason": "NO_CAPTURE",
            },
        ],
        "coverage": {
            "authorized": 3,
            "attempted": 2,
            "successful": 1,
            "unknown": 1,
            "whole_site_denominator": None,
        },
        "results": results,
        "priority": ["projected-0"],
        "summary": deepcopy(bundle["view"]["summary"]),
        "citations": deepcopy(bundle["view"]["citations"]),
        "limitations": [
            text(
                "Synthetic sample only. Form submission, inquiry delivery and conversion are UNKNOWN."
            )
        ],
    }
    return {
        "bundle": bundle,
        "free_view": view,
        "principal": deepcopy(PRINCIPAL),
        "server_bearer": BEARER,
        "current_grant": {
            "grant": deepcopy(bundle["grant"]),
            "view_sha256": digest(bundle["view"]),
        },
        "projection_proof": sign(
            "owner",
            "share",
            {
                "audit_ref": ref,
                "report_version_id": view["report_version_id"],
                "view_sha256": digest(view),
            },
        ),
    }


def inquiry_fixture(ref):
    return {
        "contract_version": VERSION,
        "audit_ref": ref,
        "report_version_id": "report-fixture.v1",
        "customer_requested": True,
        "inquiry_consent": {
            "consent_version": "VF-INQUIRY-CONSENT-DRAFT-1",
            "accepted_at": ISSUED,
            "text_sha256": digest("SYNTHETIC separate inquiry consent"),
        },
        "command": handoff_fixture(),
    }

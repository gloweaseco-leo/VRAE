"""Intended server-to-server provenance only. No transport or recipient exists."""

from .contracts import Candidate, IntendedEnvelope, canonical, deny, sha


def intended_envelope(candidate):
    if type(candidate) is not Candidate:
        deny()
    d = candidate.document
    p = d["pins"]
    correlation = "b6cor-" + sha(canonical([p["tenant_id"], p["report_id"],
                                           p["report_version"], d["content_digest"]]))
    doc = {
        "contract_version": "b6-vf-intended-envelope-v1", "status": "INTENDED_CONTRACT_ONLY",
        "authority": "TEST_ONLY_PRIVATE_PREVIEW", "approval_proven": False, "shareable": False,
        "delivery_allowed": False, "external_visibility": False, "native_decision": None,
        "real_recipient": None, "producer": "VRAE", "consumer": "VEYFRONT_INTENDED_ONLY",
        "ownership": {"evidence_and_report": "VRAE", "lead_customer_E2_E3": "VEYFRONT", "shared_database": False},
        "tenant_id": p["tenant_id"], "report_id": p["report_id"], "report_version": p["report_version"],
        "candidate_digest": d["content_digest"], "private_html_sha256": d["private_html_sha256"],
        "recipient_policy_sha256": sha(canonical(d["recipient_policy"])), "correlation_id": correlation,
        "consumer_idempotency_key": "b6p0-" + sha(canonical([correlation, d["content_digest"]])),
        "transfer_scope": ["SANITIZED_PRIVATE_CANDIDATE_DIGEST", "NO_ORIGINALS", "NO_CUSTOMER_DATA", "NO_SEND"],
        "recipient_binding": None, "owner_consent": None, "legal_authorization": None, "transport_endpoint": None,
        "expiry_revocation_contract": {"implemented": False, "max_future_ttl_seconds": 300,
                                       "issued_at": None, "expires_at": None, "lookup_before_every_access": True,
                                       "revocation_required": True, "lookup_endpoint": None, "missing_proof": "DENY"},
        "refusal_codes": ["B6_AUTHORITY_UNAVAILABLE", "B6_INPUT_DENIED", "B6_SOURCE_BINDING_DENIED", "B6_CURRENT_ACCESS_DENIED"],
    }
    return IntendedEnvelope(canonical(doc))

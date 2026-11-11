"""RA-0F adversarial cases; only synthetic documents, no external execution."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from vrae.domain.contracts import ROOT, validate_contract
from vrae.domain.errors import DomainError
from vrae.domain.policy import authorize_source
from vrae.domain.reviews import approve_version, check_share, validate_existing_grant
from vrae.domain.evidence import validate_ai_scoped_references
from vrae.domain.idempotency import accept_once

CASES = json.loads((Path(__file__).parent / "fixtures/contracts/valid.json").read_text())
NOW = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
OWNER = {"tenant_id": "tenant-example", "role": "OWNER", "actor_id": "owner-001"}
REVIEWER = {**OWNER, "role": "REVIEWER", "actor_id": "reviewer-001"}


def doc(name):
    return deepcopy(next(c["data"] for c in CASES if c["schema"] == name))


def bundle():
    r, d, g, f = (doc(n) for n in ("ReportVersion", "ReviewDecision", "ShareGrant", "Finding"))
    r["audit_mode"] = "L1"
    manifest = {k: v for k, v in r.items()
                if k not in {"content_hash", "status", "approved_by", "approved_at"}}
    digest = hashlib.sha256(json.dumps({"report": manifest, "findings": [f]},
                                      sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    for item in (r, d, g):
        item["content_hash"] = digest
    return r, d, g, f


def test_fixture_default_evidence_is_observed():
    from tests.test_domain import doc as original_doc
    assert original_doc("Evidence")["certainty"] == "OBSERVED"
    assert original_doc("PageSnapshot")["status"] == "FETCHED"


def test_future_existing_grant_is_refused():
    g = doc("ShareGrant")
    g["issued_at"] = "2026-11-11T00:00:00Z"
    with pytest.raises(DomainError):
        validate_existing_grant(g, NOW)


def test_future_policy_is_refused():
    p = doc("SourcePolicy")
    p["created_at"] = "2026-11-11T00:00:00Z"
    with pytest.raises(DomainError):
        authorize_source(doc("AuditRequest"), p, NOW)


@pytest.mark.parametrize("host", ["example.org/path", "example.org?query", "example.org#frag"])
def test_policy_hosts_cannot_smuggle_url_components(host):
    p = doc("SourcePolicy")
    p["permitted_hosts"] = [host]
    with pytest.raises(DomainError):
        authorize_source(doc("AuditRequest"), p, NOW)


@pytest.mark.parametrize("field", ["tenant_id", "run_id"])
def test_approval_requires_scoped_findings(field):
    r, d, _, f = bundle()
    f[field] = "other-scope"
    with pytest.raises(DomainError):
        approve_version(r, d, REVIEWER, 1, [f])


@pytest.mark.parametrize("change", ["finding_ids", "statement", "run_id", "reviewer", "approval_time"])
def test_changed_content_or_approval_cannot_share(change):
    r, d, g, f = bundle()
    r = approve_version(r, d, REVIEWER, 1, [f])
    if change == "finding_ids":
        r["finding_ids"] = ["find-other"]
    elif change == "statement":
        f["statement"] = "Changed after human review"
    elif change == "run_id":
        r["run_id"] = "run-other"
    elif change == "reviewer":
        r["approved_by"] = "unrelated-reviewer"
    else:
        r["approved_at"] = "2026-11-09T00:00:00Z"
    with pytest.raises(DomainError):
        check_share(r, d, g, OWNER, 1, NOW, "L1", findings=[f])


def test_ai_cannot_reference_unknown_evidence_as_validated():
    ai, obs, ev = (doc(n) for n in ("AIInterpretation", "Observation", "Evidence"))
    ai["status"] = "VALIDATED"
    ev["certainty"], ev["checksum"] = "UNKNOWN", None
    with pytest.raises(DomainError):
        validate_ai_scoped_references(ai, [obs], [ev])


def test_ai_observation_cannot_hide_unresolved_evidence():
    ai, obs, ev = (doc(n) for n in ("AIInterpretation", "Observation", "Evidence"))
    obs["evidence_ids"] = ["ev-fabricated"]
    with pytest.raises(DomainError):
        validate_ai_scoped_references(ai, [obs], [ev])


def test_idempotency_scope_has_no_delimiter_collision():
    records = {}
    assert accept_once(records, "tenant-a", "key:abcdefgh", {}, "req-one") == "req-one"
    assert accept_once(records, "tenant-a:key", "abcdefgh", {}, "req-two") == "req-two"


def test_health_contract_is_authenticated():
    spec = yaml.safe_load((ROOT / "openapi.yaml").read_text())
    health = spec["paths"]["/v1/health"]["get"]
    assert health.get("security", spec["security"])


@pytest.mark.parametrize("schema,field", [("UsageRecord", "amount")])
@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_non_json_numbers_are_rejected(schema, field, value):
    record = doc(schema)
    record.update(cost_status="RECONCILED", currency="CNY")
    record[field] = value
    with pytest.raises((ValueError, DomainError)):
        validate_contract(schema, record)


@pytest.mark.parametrize("status", ["ACCESS_BLOCKED", "UNKNOWN"])
def test_unobserved_snapshot_cannot_support_objective_failure(status):
    from vrae.domain.evidence import validate_evidence_graph
    s, e, o, f = (doc(n) for n in ("PageSnapshot", "Evidence", "Observation", "Finding"))
    s.update(status=status, sha256=None, final_url=None)
    o["result"] = "FAIL_WITH_EVIDENCE"
    with pytest.raises(DomainError):
        validate_evidence_graph(s, e, o, f)


def test_unknown_observation_does_not_become_failure():
    from vrae.domain.evidence import classify_rule, validate_evidence_graph
    assert classify_rule(None, ["ev-001"]) == "UNKNOWN"
    s, e, o, f = (doc(n) for n in ("PageSnapshot", "Evidence", "Observation", "Finding"))
    o.update(result="UNKNOWN", kind="UNKNOWN", evidence_ids=[])
    with pytest.raises(DomainError):
        validate_evidence_graph(s, e, o, f)


def test_qualification_cannot_impersonate_another_owner():
    from vrae.domain.business import advance_handoff
    h = doc("SalesHandoff")
    h.update(stage="VF_INQUIRY_RECORDED", vf_receipt_ref="receipt-001",
             inquiry_evidence_ref="inquiry-001", verified_by="another-owner")
    with pytest.raises(DomainError):
        advance_handoff(h, "QUALIFIED_BY_HUMAN", OWNER, qualification_confirmed=True)


@pytest.mark.parametrize("token", ["z" * 64, "A" * 64])
def test_share_rejects_non_hex_token_hash(token):
    r, d, g, f = bundle()
    r = approve_version(r, d, REVIEWER, 1, [f])
    g["token_hash"] = token
    with pytest.raises(DomainError):
        check_share(r, d, g, OWNER, 1, NOW, "L1", findings=[f])


def test_naive_share_clock_is_domain_refusal():
    r, d, g, f = bundle()
    r = approve_version(r, d, REVIEWER, 1, [f])
    with pytest.raises(DomainError):
        check_share(r, d, g, OWNER, 1, NOW.replace(tzinfo=None), "L1", findings=[f])


def test_l0_report_cannot_be_relabelled_by_share_caller():
    from vrae.domain.reviews import report_content_hash
    r, d, g, f = bundle()
    r["audit_mode"] = "L0"
    for item in (r, d, g):
        item["content_hash"] = report_content_hash(r, [f])
    r = approve_version(r, d, REVIEWER, 1, [f])
    with pytest.raises(DomainError):
        check_share(r, d, g, OWNER, 1, NOW, "L1", findings=[f])


@pytest.mark.parametrize("role", ["OPERATOR", "REVIEWER", "WORKER", "ANONYMOUS"])
def test_unauthorized_role_cannot_assert_business_verification(role):
    from vrae.domain.business import advance_handoff
    h = doc("SalesHandoff")
    h["vf_receipt_ref"] = "receipt-001"
    with pytest.raises(DomainError):
        advance_handoff(h, "VF_INQUIRY_RECORDED", {**OWNER, "role": role}, receipt_verified=True)


def test_all_contract_writes_require_idempotency_header():
    spec = yaml.safe_load((ROOT / "openapi.yaml").read_text())
    for path, operations in spec["paths"].items():
        if "post" not in operations:
            continue
        params = operations["post"].get("parameters", [])
        resolved = [spec["components"]["parameters"][p["$ref"].split("/")[-1]]
                    if "$ref" in p else p for p in params]
        assert any(p.get("name") == "Idempotency-Key" and p.get("required")
                   and p.get("in") == "header" for p in resolved), path

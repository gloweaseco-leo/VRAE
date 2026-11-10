"""Pure-domain unit tests, including explicit refusal and flow separation."""

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json

import pytest

from vrae.domain.access import require_access
from vrae.domain.budget import authorize_charge
from vrae.domain.business import advance_handoff
from vrae.domain.evidence import (
    classify_rule, validate_ai_references, validate_ai_scoped_references, validate_evidence_graph,
)
from vrae.domain.errors import DomainError
from vrae.domain.idempotency import accept_once
from vrae.domain.policy import authorize_source, syntax_host
from vrae.domain.reviews import approve_version, check_share, validate_existing_grant
from vrae.domain.workflow import advance_run, run_completed
from vrae.domain.contracts import load_schema

FX = Path(__file__).parent / "fixtures"
CASES = json.loads((FX / "security" / "url_cases.json").read_text())
VALID = {
    c["schema"]: c["data"]
    for c in json.loads((FX / "contracts" / "valid.json").read_text())
}
NOW = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
OWNER = {"tenant_id": "tenant-example", "role": "OWNER", "actor_id": "owner-001"}
REVIEWER = {"tenant_id": "tenant-example", "role": "REVIEWER", "actor_id": "reviewer-001"}


def doc(name: str) -> dict:
    return deepcopy(VALID[name])


def assert_error(code: str, fn, *args) -> None:
    with pytest.raises(DomainError) as exc:
        fn(*args)
    assert exc.value.code == code


@pytest.mark.parametrize("case", CASES, ids=lambda x: x["name"])
def test_url_syntax_only_cases(case: dict) -> None:
    if case["expected"] == "ACCEPT":
        assert syntax_host(case["url"]) == "example.org"
    else:
        assert_error(case["expected"], syntax_host, case["url"])


def test_l0_public_policy_valid() -> None:
    req = doc("AuditRequest")
    req["audit_mode"] = "L0"
    authorize_source(req, doc("SourcePolicy"), NOW)


def test_l1_public_policy_valid() -> None:
    authorize_source(doc("AuditRequest"), doc("SourcePolicy"), NOW)


def test_l2_owner_authorization_valid() -> None:
    req, pol = doc("AuditRequest"), doc("SourcePolicy")
    req["audit_mode"] = "L2"
    pol["mode"] = "OWNER_AUTHORIZED_DEEP"
    pol["authorization_reference"] = "owner-authorization-001"
    pol["expires_at"] = "2026-11-12T00:00:00Z"
    authorize_source(req, pol, NOW)


@pytest.mark.parametrize("which,code", [
    ("missing", "POLICY_REQUIRED"),
    ("revoked", "POLICY_REVOKED"),
    ("expired", "POLICY_EXPIRED"),
    ("tenant", "FORBIDDEN_TENANT"),
    ("version", "SOURCE_NOT_ALLOWED"),
    ("host", "SOURCE_NOT_ALLOWED"),
    ("path", "SOURCE_NOT_ALLOWED"),
    ("l2_public", "SOURCE_NOT_ALLOWED"),
    ("l2_no_consent", "SOURCE_NOT_ALLOWED"),
    ("l2_no_expiry", "SOURCE_NOT_ALLOWED"),
])
def test_policy_negative(which: str, code: str) -> None:
    req, pol = doc("AuditRequest"), doc("SourcePolicy")
    if which == "missing":
        pol = None
    elif which == "revoked":
        pol["revoked_at"] = "2026-11-09T00:00:00Z"
    elif which == "expired":
        pol["expires_at"] = "2026-11-09T00:00:00Z"
    elif which == "tenant":
        pol["tenant_id"] = "other-tenant"
    elif which == "version":
        req["source_policy_version"] = 2
    elif which == "host":
        req["site_url"] = "https://example.org.evil.example/"
    elif which == "path":
        pol["scope_paths"] = ["/products"]
    elif which == "l2_public":
        req["audit_mode"] = "L2"
    elif which == "l2_no_consent":
        req["audit_mode"] = "L2"
        pol["mode"] = "OWNER_AUTHORIZED_DEEP"
        pol["expires_at"] = "2026-11-12T00:00:00Z"
    elif which == "l2_no_expiry":
        req["audit_mode"] = "L2"
        pol["mode"] = "OWNER_AUTHORIZED_DEEP"
        pol["authorization_reference"] = "consent-001"
    assert_error(code, authorize_source, req, pol, NOW)


@pytest.mark.parametrize("status,next_status", [
    ("CREATED", "POLICY_CHECK"), ("POLICY_CHECK", "QUEUED"),
    ("QUEUED", "FETCHING"), ("FETCHING", "EVIDENCE_READY"),
    ("EVIDENCE_READY", "RULED"), ("RULED", "DRAFT_READY"),
    ("DRAFT_READY", "REVIEW_REQUIRED"),
])
def test_valid_audit_state_machine(status: str, next_status: str) -> None:
    assert advance_run(status, next_status) == next_status


@pytest.mark.parametrize("status,next_status", [
    ("CREATED", "APPROVED"), ("REVIEW_REQUIRED", "SHARE_GRANTED"),
    ("CANCELLED", "QUEUED"), ("FAILED", "FETCHING"),
    ("CREATED", "FETCHING"), ("UNKNOWN", "QUEUED"),
    ("QUEUED", "E3"), ("REVIEW_REQUIRED", "E2"),
])
def test_illegal_audit_state_machine(status: str, next_status: str) -> None:
    assert_error("INVALID_TRANSITION", advance_run, status, next_status)


def test_completed_is_not_approved_or_shared() -> None:
    assert run_completed("REVIEW_REQUIRED")
    assert not run_completed("RULED")
    assert_error("INVALID_TRANSITION", run_completed, "APPROVED")


@pytest.mark.parametrize("role,action", [
    ("OWNER", "share"), ("REVIEWER", "review"),
    ("OPERATOR", "submit"), ("WORKER", "read_evidence"),
    ("SERVICE", "submit"),
])
def test_role_allowlist(role: str, action: str) -> None:
    require_access({"tenant_id": "tenant-example", "role": role}, "tenant-example", action)


@pytest.mark.parametrize("role,action", [
    ("WORKER", "share"), ("OPERATOR", "review"),
    ("REVIEWER", "share"), ("SERVICE", "review"),
    ("ANONYMOUS", "submit"),
])
def test_role_denied(role: str, action: str) -> None:
    assert_error("FORBIDDEN_ROLE", require_access,
                 {"tenant_id": "tenant-example", "role": role}, "tenant-example", action)


def test_cross_tenant_permission_denied() -> None:
    assert_error("FORBIDDEN_TENANT", require_access, OWNER, "other-tenant", "share")


def test_valid_evidence_to_observation_finding() -> None:
    validate_evidence_graph(doc("PageSnapshot"), doc("Evidence"),
                            doc("Observation"), doc("Finding"))


@pytest.mark.parametrize("kind,code", [
    ("fake_id", "EVIDENCE_REFERENCE_INVALID"),
    ("no_objective_evidence", "EVIDENCE_INSUFFICIENT"),
    ("wrong_snapshot", "EVIDENCE_REFERENCE_INVALID"),
    ("wrong_tenant", "FORBIDDEN_TENANT"),
    ("wrong_run", "EVIDENCE_REFERENCE_INVALID"),
    ("wrong_observation", "EVIDENCE_REFERENCE_INVALID"),
    ("wrong_rule_version", "EVIDENCE_REFERENCE_INVALID"),
    ("unknown_as_fact", "EVIDENCE_INSUFFICIENT"),
])
def test_bad_evidence_graph(kind: str, code: str) -> None:
    s, e, o, f = (doc(x) for x in ("PageSnapshot", "Evidence", "Observation", "Finding"))
    if kind == "fake_id":
        f["evidence_ids"] = ["ev-forged"]
    elif kind == "no_objective_evidence":
        o["evidence_ids"] = []
    elif kind == "wrong_snapshot":
        e["snapshot_id"] = "snap-other"
    elif kind == "wrong_tenant":
        f["tenant_id"] = "other-tenant"
    elif kind == "wrong_run":
        f["run_id"] = "run-other"
    elif kind == "wrong_observation":
        f["observation_id"] = "obs-other"
    elif kind == "wrong_rule_version":
        f["rule_version"] = "2.0.0"
    elif kind == "unknown_as_fact":
        o["result"] = "UNKNOWN"
    assert_error(code, validate_evidence_graph, s, e, o, f)


def test_synthetic_rule_result_without_negative_assumption() -> None:
    assert classify_rule(True, ["ev-001"]) == "PASS"
    assert classify_rule(False, ["ev-001"]) == "FAIL_WITH_EVIDENCE"
    assert classify_rule(False, []) == "UNKNOWN"
    assert classify_rule(None, []) == "UNKNOWN"


def test_ai_valid_ids_and_fake_evidence_refused() -> None:
    ai = doc("AIInterpretation")
    validate_ai_references(ai, {"obs-001"}, {"ev-001"})
    ai["evidence_ids"] = ["ev-fabricated"]
    assert_error("EVIDENCE_REFERENCE_INVALID",
                 validate_ai_references, ai, {"obs-001"}, {"ev-001"})


def test_ai_cross_tenant_and_cross_run_blocked() -> None:
    ai, obs, evidence = (doc(x) for x in ("AIInterpretation", "Observation", "Evidence"))
    validate_ai_scoped_references(ai, [obs], [evidence])
    obs["tenant_id"] = "other-tenant"
    assert_error("FORBIDDEN_TENANT", validate_ai_scoped_references,
                 ai, [obs], [evidence])
    obs["tenant_id"] = ai["tenant_id"]
    evidence["run_id"] = "other-run"
    assert_error("EVIDENCE_REFERENCE_INVALID", validate_ai_scoped_references,
                 ai, [obs], [evidence])


def test_approve_then_issue_share_exact_version() -> None:
    report, decision, grant = (doc(x) for x in ("ReportVersion", "ReviewDecision", "ShareGrant"))
    approved = approve_version(report, decision, REVIEWER, 1, {"find-001"})
    assert approved["status"] == "APPROVED"
    assert report["status"] == "REVIEW_REQUIRED"
    check_share(approved, decision, grant, OWNER, 1, NOW)


@pytest.mark.parametrize("problem,code", [
    ("operator_approves", "FORBIDDEN_ROLE"),
    ("version_changed", "REPORT_VERSION_STALE"),
    ("hash_changed", "REPORT_VERSION_STALE"),
    ("cross_tenant", "FORBIDDEN_TENANT"),
])
def test_review_invalid(problem: str, code: str) -> None:
    r, d = doc("ReportVersion"), doc("ReviewDecision")
    actor, version = REVIEWER, 1
    if problem == "operator_approves":
        actor = {"tenant_id": "tenant-example", "role": "OPERATOR", "actor_id": "reviewer-001"}
    elif problem == "version_changed":
        version = 2
    elif problem == "hash_changed":
        d["content_hash"] = "b" * 64
    elif problem == "cross_tenant":
        d["tenant_id"] = "another-tenant"
    assert_error(code, approve_version, r, d, actor, version, {"find-001"})


@pytest.mark.parametrize("problem,code", [
    ("unapproved", "REPORT_NOT_APPROVED"),
    ("stale_version", "REPORT_VERSION_STALE"),
    ("changed_hash", "REPORT_VERSION_STALE"),
    ("expired_grant", "SHARE_EXPIRED"),
    ("revoked_grant", "SHARE_EXPIRED"),
    ("cross_tenant", "FORBIDDEN_TENANT"),
    ("reviewer_shares", "FORBIDDEN_ROLE"),
])
def test_share_invalid(problem: str, code: str) -> None:
    r, d, g = (doc(x) for x in ("ReportVersion", "ReviewDecision", "ShareGrant"))
    r["status"] = "APPROVED"
    actor, latest = OWNER, 1
    if problem == "unapproved":
        r["status"] = "REVIEW_REQUIRED"
    elif problem == "stale_version":
        latest = 2
    elif problem == "changed_hash":
        g["content_hash"] = "b" * 64
    elif problem == "expired_grant":
        g["expires_at"] = "2026-11-09T00:00:00Z"
    elif problem == "revoked_grant":
        g["revoked_at"] = "2026-11-10T01:00:00Z"
    elif problem == "cross_tenant":
        g["tenant_id"] = "another-tenant"
    elif problem == "reviewer_shares":
        actor = REVIEWER
    assert_error(code, check_share, r, d, g, actor, latest, NOW)


def test_revoked_existing_link_no_longer_works() -> None:
    g = doc("ShareGrant")
    validate_existing_grant(g, NOW)
    g["status"] = "REVOKED"
    assert_error("SHARE_EXPIRED", validate_existing_grant, g, NOW)


@pytest.mark.parametrize("level,limit,spent,amount,code", [
    ("L0", 0., 0., 0., "SOURCE_NOT_ALLOWED"),
    ("L1", None, 0., 1., "MODEL_COST_UNKNOWN"),
    ("L1", 2., None, 1., "MODEL_COST_UNKNOWN"),
    ("L1", 2., 0., None, "MODEL_COST_UNKNOWN"),
    ("L1", 2., 1.8, 0.3, "LIMIT_EXCEEDED"),
    ("L1", 2., -0.1, 0.2, "MODEL_COST_UNKNOWN"),
    ("L2", 2., 0., float("nan"), "MODEL_COST_UNKNOWN"),
])
def test_cost_blocking(level, limit, spent, amount, code) -> None:
    assert_error(code, authorize_charge, level, limit, spent, amount, "ESTIMATED")


def test_unknown_usage_status_hard_blocks_paid_calls() -> None:
    assert_error("MODEL_COST_UNKNOWN", authorize_charge,
                 "L1", 2.0, 0.0, 0.3, "UNKNOWN")


def test_approval_requires_verified_finding_ids() -> None:
    assert_error("EVIDENCE_INSUFFICIENT", approve_version,
                 doc("ReportVersion"), doc("ReviewDecision"), REVIEWER, 1, set())


def test_paid_budget_within_explicit_limit() -> None:
    authorize_charge("L1", 2.0, 1.0, 1.0, "ESTIMATED")


def test_idempotent_same_request_and_conflict() -> None:
    mem = {}
    payload = {"site_url": "https://example.org", "mode": "L1"}
    assert accept_once(mem, "tenant-example", "synthetic-key-001", payload, "req-001") == "req-001"
    assert accept_once(mem, "tenant-example", "synthetic-key-001", payload, "req-002") == "req-001"
    assert_error("IDEMPOTENCY_CONFLICT", accept_once,
                 mem, "tenant-example", "synthetic-key-001", {"mode": "L2"}, "req-003")
    assert accept_once(mem, "other-tenant", "synthetic-key-001", payload, "req-other") == "req-other"


def test_requested_handoff_is_not_e2_or_e3() -> None:
    h = doc("SalesHandoff")
    assert h["stage"] == "HANDOFF_REQUESTED"
    assert_error("BUSINESS_EVIDENCE_REQUIRED",
                 advance_handoff, h, "VF_INQUIRY_RECORDED", OWNER)
    assert_error("INVALID_TRANSITION", advance_handoff, h, "QUALIFIED_BY_HUMAN", OWNER)
    h["vf_receipt_ref"] = "vf-receipt-001"
    assert_error("BUSINESS_EVIDENCE_REQUIRED",
                 advance_handoff, h, "VF_INQUIRY_RECORDED", OWNER)
    h2 = advance_handoff(h, "VF_INQUIRY_RECORDED", OWNER, receipt_verified=True)
    assert h2["stage"] == "VF_INQUIRY_RECORDED"
    assert_error("BUSINESS_EVIDENCE_REQUIRED", advance_handoff, h2, "QUALIFIED_BY_HUMAN", OWNER)
    h2["inquiry_evidence_ref"] = "vf-inquiry-evidence-001"
    h2["verified_by"] = "sales-owner-001"
    assert_error("BUSINESS_EVIDENCE_REQUIRED",
                 advance_handoff, h2, "QUALIFIED_BY_HUMAN", OWNER)
    assert advance_handoff(
        h2, "QUALIFIED_BY_HUMAN", OWNER, qualification_confirmed=True
    )["stage"] == "QUALIFIED_BY_HUMAN"
    bad_actor = {**OWNER, "tenant_id": "another-tenant"}
    assert_error("FORBIDDEN_TENANT", advance_handoff,
                 h2, "QUALIFIED_BY_HUMAN", bad_actor)
    bad_role = {**OWNER, "role": "SERVICE"}
    assert_error("BUSINESS_EVIDENCE_REQUIRED", advance_handoff,
                 h2, "QUALIFIED_BY_HUMAN", bad_role)


def test_domain_error_codes_are_all_in_schema() -> None:
    contract_codes = set(load_schema("ErrorCode")["properties"]["code"]["enum"])
    import ast
    domain_path = Path(__file__).parents[1] / "vrae" / "domain"
    for source in domain_path.glob("*.py"):
        tree = ast.parse(source.read_text())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name) and node.func.id == "DomainError"):
                assert isinstance(node.args[0], ast.Constant)
                assert node.args[0].value in contract_codes, (source.name, node.args[0].value)


def test_no_network_or_unauthorized_framework_code() -> None:
    domain_path = Path(__file__).parents[1] / "vrae"
    banned = ("import requests", "import httpx", "import socket",
              "import playwright", "urllib.request", "subprocess.", "supabase")
    for source in domain_path.rglob("*.py"):
        data = source.read_text()
        assert all(word not in data for word in banned), source

"""Explicit R0 consumer suite; all identities/signatures/storage are synthetic."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import socket

from jsonschema import Draft202012Validator, ValidationError
import pytest

from contracts.l2_launch.contract import (
    VERSION,
    SCHEMA,
    STATE_MAP,
    Refused,
    availability,
    digest,
    error_reply,
    simulate_report_read,
    status_view,
    validate,
)
from contracts.l2_launch.fixture_stub import FixtureJournal
from vrae.domain.contracts import load_schema
from tests.l2_launch.fixtures import (
    NOW,
    TENANT,
    CALLER,
    PRINCIPAL,
    BEARER,
    FixtureVFStore,
    audit_fixture,
    handoff_fixture,
    report_bundle,
    reseal_report,
    resign_permission,
    sign,
    verifier,
)
from contracts.l2_launch.vf_b import (
    COOKIE_POLICY,
    HEADERS,
    VFBCandidate,
    safe_log_record,
    submission_document,
    validate_free_view,
    vf_status,
)
from tests.l2_launch.vf_b_fixtures import (
    RETURN_TOKEN,
    facade_fixture,
    free_publication_fixture,
    inquiry_fixture,
    return_fixture,
)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    calls = []

    def denied(*args, **kwargs):
        calls.append("forbidden_socket_or_dns")
        raise AssertionError("R0_NETWORK_FORBIDDEN")

    for name in ("socket", "create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, name, denied)
    yield
    assert calls == []


@pytest.fixture
def setup(tmp_path):
    command, policy = audit_fixture()
    db = FixtureJournal(tmp_path / "vrae-fixture.sqlite")
    vf = FixtureVFStore(tmp_path / "vf-fixture.sqlite")
    yield db, vf, command, policy, verifier(), tmp_path
    db.close()
    vf.db.close()


def accept(setup, **kwargs):
    db, _, command, policy, v, _ = setup
    return db.accept(
        command, command["request"]["idempotency_key"], CALLER, policy, v, NOW, **kwargs
    )


def requested(setup):
    db, _, _, policy, v, _ = setup
    _, accepted = accept(setup)
    for state in ("FETCHING", "EVIDENCE_READY", "RULED", "DRAFT_READY", "REVIEW_REQUIRED"):
        db.advance_fixture(TENANT, "audit-fixture", state)
    cmd = handoff_fixture()
    body = db.request_handoff(
        cmd,
        CALLER,
        policy,
        v,
        NOW,
        current_report=report_bundle(run_id=accepted["run_id"])["report"],
    )
    assert (
        body["handoff"]["stage"] == "HANDOFF_REQUESTED" and body["delivery_state"] == "WAITING_ACK"
    )
    return cmd


def read_fixture(bundle, v=None, principal=None, token=BEARER, current=None, now=NOW):
    return simulate_report_read(
        bundle,
        principal or PRINCIPAL,
        token,
        v or verifier(),
        now,
        current_grant={"grant": bundle["grant"], "view_sha256": digest(bundle["view"])}
        if current is None
        else current,
    )


def test_schema_and_default_frontend_unavailable():
    Draft202012Validator.check_schema(SCHEMA)
    validate("Availability", availability())
    assert not availability()["submit_enabled"] and not availability()["report_enabled"]
    assert set(STATE_MAP) == set(load_schema("AuditRun")["properties"]["status"]["enum"])
    assert STATE_MAP["REVIEW_REQUIRED"] == "REVIEW_PENDING"


def test_202_is_durable_reference_not_diagnosis_and_survives_restart(setup):
    db, _, command, policy, v, path = setup
    code, body = accept(setup, queue_available=False)
    assert code == 202 and body["acceptance"]["audit_id"] == command["request"]["audit_id"]
    assert body["queue_state"] == "PENDING_DISPATCH" and body["diagnosis_complete"] is False
    other = FixtureJournal(path / "vrae-fixture.sqlite")
    try:
        status = other.get_status(TENANT, "audit-fixture", CALLER, policy, v, NOW)
        assert status["run"]["run_id"] == body["run_id"] and status["run"]["status"] == "CREATED"
        assert status["presentation"]["progress_percent"] is None
        again = other.accept(
            command,
            command["request"]["idempotency_key"],
            CALLER,
            policy,
            v,
            NOW,
            queue_available=False,
        )
        assert again == (code, body)
        other.dispatch(TENANT, "audit-fixture")
        assert (
            other.get_status(TENANT, "audit-fixture", CALLER, policy, v, NOW)["run"]["status"]
            == "QUEUED"
        )
    finally:
        other.close()


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "revoked",
        "expired",
        "tenant",
        "path",
        "wrong_proof",
        "proof_replay",
        "unverified_checkbox",
        "L2_bridge",
    ],
)
def test_source_authority_refused_before_acceptance(setup, kind):
    db, _, command, policy, v, _ = setup
    if kind == "missing":
        policy = None
    elif kind == "revoked":
        policy["revoked_at"] = NOW.isoformat()
    elif kind == "expired":
        policy["expires_at"] = "2026-11-17T00:00:00Z"
    elif kind == "tenant":
        policy["tenant_id"] = "tenant-other"
    elif kind == "path":
        command["request"]["site_url"] = "https://legacy.example/private"
    elif kind == "wrong_proof":
        command["permission_reference"]["proof"]["signature"] = "0" * 128
    elif kind == "proof_replay":
        command["request"]["audit_id"] = "audit-other"
    elif kind == "unverified_checkbox":
        command["permission_reference"] = {"accepted": True}
    elif kind == "L2_bridge":
        command["request"]["audit_mode"] = "L2"
        resign_permission(command, policy)
    with pytest.raises(Refused) as e:
        db.accept(command, command["request"]["idempotency_key"], CALLER, policy, v, NOW)
    assert e.value.status in (400, 403, 503)
    assert db.db.execute("SELECT count(*) FROM items").fetchone()[0] == 0


@pytest.mark.parametrize(
    "kind",
    [
        "header",
        "different_body",
        "same_audit_new_key",
        "wrong_contract",
        "wrong_tenant",
        "storage",
        "quota",
        "query",
        "encoded_path",
    ],
)
def test_idempotency_errors_and_no_false_success(setup, kind):
    db, _, cmd, policy, v, _ = setup
    key = cmd["request"]["idempotency_key"]
    actor = deepcopy(CALLER)
    kwargs = {}
    if kind in ("different_body", "same_audit_new_key"):
        accept(setup)
    if kind == "header":
        key = "different-header-key"
    elif kind == "different_body":
        cmd["request"]["source_reference"] = "another-source"
    elif kind == "same_audit_new_key":
        key = cmd["request"]["idempotency_key"] = "another-idempotency-key"
    elif kind == "wrong_contract":
        cmd["contract_version"] = "v9"
    elif kind == "wrong_tenant":
        actor["tenant_id"] = "tenant-other"
    elif kind == "storage":
        kwargs["storage_available"] = False
    elif kind == "quota":
        kwargs["capacity_available"] = False
    elif kind == "query":
        cmd["request"]["site_url"] += "?token=not-a-real-token"
    elif kind == "encoded_path":
        cmd["request"]["site_url"] += "/%41"
    resign_permission(cmd, policy)
    with pytest.raises(Refused) as e:
        db.accept(cmd, key, actor, policy, v, NOW, **kwargs)
    error = error_reply(e.value, "request-fixture")
    assert error["http_status"] in (400, 403, 409, 429, 503)
    if kind in ("different_body", "same_audit_new_key", "header"):
        assert error["http_status"] == 409
    if kind == "quota":
        assert error["http_status"] == 429 and error["retry_after_seconds"] == 60
    if kind == "storage":
        assert error["http_status"] == 503


@pytest.mark.parametrize(
    "state",
    [
        "POLICY_BLOCKED",
        "ACCESS_BLOCKED",
        "INSUFFICIENT_EVIDENCE",
        "MODEL_INVALID",
        "FAILED",
        "CANCELLED",
    ],
)
def test_blocked_unknown_failure_are_not_site_faults(state):
    run = report_bundle()["run"]
    run["status"] = state
    dto = status_view(run)
    validate("AuditStatus", dto)
    assert dto["presentation"]["progress_percent"] is None
    assert dto["presentation"]["state"] in {"BLOCKED", "UNKNOWN", "FAILED", "CANCELLED"}
    run["status"] = "COMPLETE"
    with pytest.raises(ValidationError):
        status_view(run)


@pytest.mark.parametrize("kind", ["PublicPreviewView", "ApprovedL2ReportView"])
def test_approved_exact_projection_fixture_is_bilingual_minimal_and_recipient_bound(kind):
    bundle = report_bundle(kind)
    result = read_fixture(bundle)
    assert result["scope"] == "SYNTHETIC_CONTRACT_FIXTURE_NOT_A_RELEASE"
    assert result["view"]["anonymous_access"] is False
    assert result["view"]["summary"]["A"]["en"] and result["view"]["summary"]["B"]["zh"]
    assert (
        "findings" not in result["view"]
        and result["view"]["coverage"]["whole_site_denominator"] is None
    )


@pytest.mark.parametrize(
    "kind",
    [
        "DRAFT",
        "REVIEW_REQUIRED",
        "stale",
        "bad_token",
        "wrong_recipient",
        "wrong_audience",
        "token_expired",
        "token_revoked",
        "tenant",
        "source_revoked",
        "source_expired",
        "run_mismatch",
        "fake_review",
        "fake_owner",
        "changed_content",
        "changed_view",
        "expired_grant",
        "revoked_grant",
        "missing_current_grant",
        "anonymous",
        "private_field",
        "email",
        "citation_query",
        "citation_unresolved",
        "no_capture",
    ],
)
def test_reports_fail_closed_including_resealed_private_projection(kind):
    b = report_bundle()
    p, token, v, current, now = deepcopy(PRINCIPAL), BEARER, verifier(), None, NOW
    if kind in ("DRAFT", "REVIEW_REQUIRED"):
        b["report"]["status"] = kind
    elif kind == "stale":
        b["latest_version"] = 2
    elif kind == "bad_token":
        token = "wrong-fixture-token"
    elif kind == "wrong_recipient":
        p["subject_ref"] = "recipient-other"
    elif kind == "wrong_audience":
        p["audience"] = "vf-lead"
    elif kind == "token_expired":
        p["expires_at"] = "2026-11-17T00:00:00Z"
    elif kind == "token_revoked":
        p["token_revoked"] = True
    elif kind == "tenant":
        p["tenant_id"] = "tenant-other"
    elif kind == "source_revoked":
        b["source_policy"]["revoked_at"] = NOW.isoformat()
    elif kind == "source_expired":
        b["source_policy"]["expires_at"] = "2026-11-17T00:00:00Z"
    elif kind == "run_mismatch":
        b["run"]["audit_id"] = "audit-other"
    elif kind == "fake_review":
        b["review_proof"] = sign("vf", "review", b["decision"])
    elif kind == "fake_owner":
        b["share_proof"] = sign(
            "vf", "share", {"grant": b["grant"], "view_sha256": digest(b["view"])}
        )
    elif kind == "changed_content":
        b["findings"][0]["statement"] = "tampered"
    elif kind == "changed_view":
        b["view"]["summary"]["A"]["en"] = "unsupported new claim"
    elif kind == "expired_grant":
        b["grant"]["expires_at"] = "2026-11-17T00:00:00Z"
        reseal_report(b)
    elif kind == "revoked_grant":
        b["grant"]["status"] = "REVOKED"
        b["grant"]["revoked_at"] = NOW.isoformat()
        reseal_report(b)
    elif kind == "missing_current_grant":
        current = {}
    elif kind == "anonymous":
        b["view"]["anonymous_access"] = True
        reseal_report(b)
    elif kind == "private_field":
        b["view"]["evidence_pack"] = {"raw": "synthetic forbidden field"}
        reseal_report(b)
    elif kind == "email":
        b["view"]["citations"][0]["excerpt"] = "fixture-person@private.example"
        reseal_report(b)
    elif kind == "citation_query":
        b["view"]["citations"][0]["source_url"] += "?private=fixture"
        reseal_report(b)
    elif kind == "citation_unresolved":
        b["view"]["summary"]["A"]["citation_ids"] = ["missing-citation"]
        reseal_report(b)
    elif kind == "no_capture":
        b["view"]["coverage"]["observed_pages"] = 0
        reseal_report(b)
    with pytest.raises(Refused) as e:
        read_fixture(b, v, p, token, current, now)
    assert e.value.status in (400, 403, 409)


def test_grant_reference_idempotency_conflict_and_durable_revocation(setup):
    db, _, _, _, v, _ = setup
    b = report_bundle()
    grant = db.register_grant_fixture(b["grant"], b["share_proof"], b["view"], v, NOW)
    assert db.register_grant_fixture(b["grant"], b["share_proof"], b["view"], v, NOW) == grant
    changed = deepcopy(b)
    changed["grant"]["token_hash"] = "a" * 64
    reseal_report(changed)
    with pytest.raises(Refused) as e:
        db.register_grant_fixture(changed["grant"], changed["share_proof"], changed["view"], v, NOW)
    assert e.value.status == 409
    db.revoke_grant_fixture(
        TENANT,
        grant["grant_id"],
        sign("owner", "share", {"grant_id": grant["grant_id"], "action": "REVOKE"}),
        v,
        NOW,
    )
    with pytest.raises(Refused):
        db.resolve_grant_fixture(TENANT, grant["grant_id"])


@pytest.mark.parametrize("at_review_ready", [False, True])
def test_withdrawal_blocks_reads_callbacks_and_only_its_own_audit(setup, at_review_ready):
    db, vf, cmd, policy, v, _ = setup
    if at_review_ready:
        handoff = requested(setup)
    else:
        accept(setup)
        handoff = handoff_fixture()
    reply = db.withdraw(TENANT, "audit-fixture", CALLER, policy, v, NOW)
    assert reply["access_state"] == "WITHDRAWN"
    assert reply["run"]["status"] == ("REVIEW_REQUIRED" if at_review_ready else "CANCELLED")
    with pytest.raises(Refused):
        db.get_status(TENANT, "audit-fixture", CALLER, policy, v, NOW)
    receipt, proof = vf.record(handoff)
    with pytest.raises(Refused):
        db.receive(receipt, proof, v, NOW)
    other = deepcopy(cmd)
    other["request"].update(
        audit_id="audit-other", request_id="request-other", idempotency_key="other-fixture-key"
    )
    resign_permission(other, policy)
    assert db.accept(other, "other-fixture-key", CALLER, policy, v, NOW)[0] == 202


def test_real_storage_fixture_before_ack_retry_replay_and_restart(setup):
    db, vf, _, _, v, path = setup
    command = requested(setup)
    with pytest.raises(OSError):
        vf.record(command, storage_available=False)
    assert db._read("handoff", TENANT, "handoff-fixture")["delivery_state"] == "WAITING_ACK"
    receipt, proof = vf.record(command)  # committed independently; first transport ACK may be lost
    assert db._read("handoff", TENANT, "handoff-fixture")["handoff"]["stage"] == "HANDOFF_REQUESTED"
    assert vf.record(command) == (receipt, proof)
    body = db.receive(receipt, proof, v, NOW)
    assert body["handoff"]["stage"] == "VF_INQUIRY_RECORDED"
    assert db.receive(receipt, proof, v, NOW) == body
    other = FixtureJournal(path / "vrae-fixture.sqlite")
    try:
        assert other.receive(receipt, proof, v, NOW) == body
    finally:
        other.close()
    assert all(
        body[k] is False
        for k in ("counts_as_e2", "counts_as_e3", "customer_approval", "quote_allowed")
    )


@pytest.mark.parametrize(
    "kind",
    [
        "fake_ok",
        "unsigned",
        "wrong_tenant",
        "wrong_handoff",
        "wrong_request",
        "wrong_version",
        "wrong_key",
        "altered_event",
    ],
)
def test_fake_or_replayed_VF_ack_cannot_upgrade_business_state(setup, kind):
    db, vf, _, _, v, _ = setup
    cmd = requested(setup)
    receipt, proof = vf.record(cmd)
    if kind == "fake_ok":
        receipt = {"ok": True, "reference": "VF-FAKE"}
    elif kind == "unsigned":
        proof["signature"] = "0" * 128
    elif kind == "wrong_tenant":
        receipt["tenant_id"] = "tenant-other"
    elif kind == "wrong_handoff":
        receipt["handoff_id"] = "handoff-other"
    elif kind == "wrong_request":
        receipt["request_sha256"] = "f" * 64
    elif kind == "wrong_version":
        receipt["report_version_id"] = "report-fixture.v2"
    elif kind == "wrong_key":
        proof = sign("owner", "vf_storage", receipt)
    elif kind == "altered_event":
        db.receive(receipt, proof, v, NOW)
        receipt["vf_receipt_ref"] = "VF-CONFLICT"
        proof = sign("vf", "vf_storage", receipt)
    with pytest.raises(Refused):
        db.receive(receipt, proof, v, NOW)
    if kind != "altered_event":
        assert db._read("handoff", TENANT, "handoff-fixture")["delivery_state"] == "WAITING_ACK"


def test_independent_human_qualification_fixture_and_service_denial(setup):
    db, vf, _, _, v, _ = setup
    cmd = requested(setup)
    receipt, proof = vf.record(cmd)
    db.receive(receipt, proof, v, NOW)
    q = {
        "contract_version": VERSION,
        "event_id": "qualifier-event-fixture",
        "tenant_id": TENANT,
        "handoff_id": "handoff-fixture",
        "vf_receipt_ref": receipt["vf_receipt_ref"],
        "inquiry_evidence_ref": "inquiry-fixture",
        "verified_by": "human-commercial-fixture",
        "confirmed_at": NOW.isoformat(),
    }
    with pytest.raises(Refused):
        db.qualify(q, sign("vf", "vf_qualification", q), v, NOW)
    result = db.qualify(q, sign("qualifier", "vf_qualification", q), v, NOW)
    assert result["handoff"]["stage"] == "QUALIFIED_BY_HUMAN"
    assert not result["counts_as_e2"] and not result["counts_as_e3"] and not result["quote_allowed"]
    assert db.qualify(q, sign("qualifier", "vf_qualification", q), v, NOW) == result


def test_revoked_signing_key_and_expired_proof_are_refused(setup):
    _, _, cmd, policy, v, _ = setup
    v.keys["key-permission"] = replace(v.keys["key-permission"], revoked=True)
    from contracts.l2_launch.contract import check_permission

    with pytest.raises(Refused):
        check_permission(cmd, policy, CALLER, v, NOW)
    with pytest.raises(Refused):
        check_permission(cmd, policy, CALLER, verifier(), NOW + timedelta(days=3))


@pytest.mark.parametrize("kind", ["missing", "tenant", "run", "draft", "old_version"])
def test_handoff_requires_trusted_current_report_reference(setup, kind):
    db, _, _, policy, v, _ = setup
    command = requested(setup)
    report = report_bundle(run_id=db._read("audit", TENANT, "audit-fixture")["run"]["run_id"])[
        "report"
    ]
    if kind == "missing":
        report = None
    elif kind == "tenant":
        report["tenant_id"] = "tenant-other"
    elif kind == "run":
        report["run_id"] = "run-other"
    elif kind == "draft":
        report["status"] = "DRAFT"
    elif kind == "old_version":
        command["handoff"]["report_version_id"] = "report-fixture.v0"
    with pytest.raises(Refused):
        db.request_handoff(command, CALLER, policy, v, NOW, current_report=report)


def test_zero_capture_projection_stays_unknown():
    b = report_bundle()
    b["view"]["citations"] = []
    b["view"]["coverage"]["observed_pages"] = 0
    for summary in b["view"]["summary"].values():
        summary["basis"] = "UNKNOWN"
        summary["citation_ids"] = []
    b["view"]["unknowns"].append("NO_CAPTURE")
    reseal_report(b)
    assert "NO_CAPTURE" in read_fixture(b)["view"]["unknowns"]


@pytest.mark.parametrize("kind", ["other_host", "other_path", "future", "encoded_path"])
def test_owner_view_signature_does_not_expand_source_policy(kind):
    b = report_bundle()
    if kind == "other_host":
        b["view"]["citations"][0]["source_url"] = "https://other.example/products/p40"
    elif kind == "other_path":
        b["view"]["citations"][0]["source_url"] = "https://legacy.example/private"
    elif kind == "future":
        b["view"]["citations"][0]["captured_at"] = "2026-11-20T00:00:00Z"
    elif kind == "encoded_path":
        b["view"]["citations"][0]["source_url"] += "/%41"
    reseal_report(b)
    with pytest.raises(Refused):
        read_fixture(b)


def test_attestation_for_other_audience_is_not_source_permission(setup):
    db, _, cmd, policy, v, _ = setup
    cmd["permission_reference"]["proof"]["claim"]["audience"] = "some-other-service"
    with pytest.raises(Refused):
        db.accept(cmd, cmd["request"]["idempotency_key"], CALLER, policy, v, NOW)


def test_contract_examples_are_offline_validated():
    folder = Path(__file__).resolve().parents[2] / "contracts/l2_launch/examples"
    # Explicit paths are validated by the reproducible generator/evidence step.
    paths = sorted(folder.glob("*.json"))
    assert len(paths) >= 10
    for path in paths:
        sample = json.loads(path.read_text(encoding="utf-8"))
        assert sample["scope"] == "SYNTHETIC_CONTRACT_FIXTURE_NOT_A_RELEASE"
        validate(sample["type"], sample["body"])


@pytest.fixture
def vfb(setup):
    db, vf, _, _, v, directory = setup
    adapter, submission, policy, publications = facade_fixture(db)
    response = adapter.submit(submission, CALLER, policy, v, NOW, queue_available=False)
    assert response["status"] == 202
    ref = response["body"]["audit_ref"]
    grant = return_fixture(ref, policy)
    adapter.install_return_fixture(grant, sign("owner", "share", grant), v, NOW)
    restored = adapter.exchange(ref, PRINCIPAL["subject_ref"], RETURN_TOKEN, CALLER, policy, v, NOW)
    cookie = restored["set_cookie"]["value"]
    return adapter, submission, policy, publications, response, ref, cookie, v, vf, directory


def vfb_publish(vfb):
    adapter, _, _, publications, response, ref, *_ = vfb
    adapter.journal.dispatch(TENANT, "audit-fixture")
    for stage in ("FETCHING", "EVIDENCE_READY", "RULED", "DRAFT_READY", "REVIEW_REQUIRED"):
        adapter.journal.advance_fixture(TENANT, "audit-fixture", stage)
    publications["audit-fixture"] = free_publication_fixture(ref, response["body"]["run_id"])
    return publications["audit-fixture"]


def vfb_read(vfb, operation="status", **kwargs):
    adapter, _, policy, _, _, ref, cookie, v, *_ = vfb
    return adapter.read(
        operation,
        kwargs.pop("ref", ref),
        kwargs.pop("cookie", cookie),
        kwargs.pop("caller", CALLER),
        kwargs.pop("policy", policy),
        v,
        kwargs.pop("now", NOW),
        **kwargs,
    )


def test_vfb_producer_consumer_202_status_publication_return_and_VF_receipt(vfb):
    adapter, submission, policy, _, accepted, ref, cookie, v, vf, _ = vfb
    assert accepted["headers"] == HEADERS
    assert set(accepted["body"]) == {
        "contract_version",
        "audit_ref",
        "run_id",
        "run_status",
        "diagnosis_complete",
        "poll_after_seconds",
    }
    assert "audit-fixture" not in ref and not accepted["body"]["diagnosis_complete"]
    assert vfb_read(vfb)["body"]["display_state"] == "accepted"
    assert vfb_read(vfb, "report")["status"] == 403
    assert adapter.submit(submission, CALLER, policy, v, NOW)["body"]["audit_ref"] == ref
    record = vfb_publish(vfb)
    result = vfb_read(vfb)
    assert result["body"]["task"]["status"] == "REVIEW_REQUIRED"
    assert result["body"]["publication"]["state"] == "APPROVED_PARTIAL"
    assert result["body"]["display_state"] == "partial"
    view = vfb_read(vfb, "report")["body"]
    assert view["kind"] == "synthetic" and len(view["results"]["UNDERSTAND"]) == 5
    assert {f["kind"] for f in view["results"]["UNDERSTAND"]} == {
        "OBSERVATION",
        "COUNTER_EVIDENCE",
        "HYPOTHESIS",
        "RECOMMENDATION",
        "UNKNOWN",
    }
    assert view["coverage"] == {
        "authorized": 3,
        "attempted": 2,
        "successful": 1,
        "unknown": 1,
        "whole_site_denominator": None,
    }
    assert vfb_read(vfb, "citation", citation_id="citation-fixture")["body"] == view["citations"][0]
    inquiry = inquiry_fixture(ref)
    response = adapter.inquiry(inquiry, cookie, CALLER, policy, v, NOW)
    assert response["status"] == 202 and response["body"]["delivery_state"] == "WAITING_ACK"
    with pytest.raises(OSError):
        vf.record(inquiry["command"], storage_available=False)
    receipt, proof = vf.record(inquiry["command"])
    saved = adapter.journal.receive(receipt, proof, v, NOW)
    assert saved["handoff"]["stage"] == "VF_INQUIRY_RECORDED"
    assert not saved["counts_as_e2"] and not saved["counts_as_e3"]
    assert record["free_view"] == view


@pytest.mark.parametrize(
    "fault",
    [
        "missing-invitation",
        "revoked",
        "expired",
        "tenant",
        "subject",
        "scope",
        "host",
        "service",
        "language",
        "consent-time",
        "consent-version",
        "consent-body",
        "tamper-proof",
        "no-policy",
        "storage",
        "quota",
    ],
)
def test_vfb_submit_fail_closed_before_reference(setup, fault):
    db, _, _, _, v, _ = setup
    adapter, submission, policy, _ = facade_fixture(db)
    caller, kwargs = dict(CALLER), {}
    invitation = adapter.invitations["invitation-fixture"]
    if fault == "missing-invitation":
        adapter.invitations.clear()
    elif fault == "revoked":
        invitation["revoked"] = True
    elif fault == "expired":
        invitation["expires_at"] = "2026-11-18T10:00:00Z"
    elif fault == "tenant":
        invitation["tenant_id"] = "other-tenant"
    elif fault == "subject":
        submission["subject_ref"] = "other-subject"
    elif fault == "scope":
        invitation["policy_sha256"] = "0" * 64
    elif fault == "host":
        submission["normalized_host"] = "other.example"
    elif fault == "service":
        caller["actor_id"] = "untrusted-service"
    elif fault == "language":
        submission["language"] = "fr"
    elif fault == "consent-time":
        submission["diagnosis_consent"]["accepted_at"] = "2026-11-20T12:00:00Z"
    elif fault == "consent-version":
        submission["diagnosis_consent"]["consent_version"] = "other-consent"
    elif fault == "consent-body":
        submission["diagnosis_consent"]["text_sha256"] = "0" * 64
    elif fault == "tamper-proof":
        submission["submission_proof"]["signature"] = "0" * 128
    elif fault == "no-policy":
        policy = None
    elif fault == "storage":
        kwargs["storage_available"] = False
    elif fault == "quota":
        kwargs["capacity_available"] = False
    result = adapter.submit(submission, caller, policy, v, NOW, **kwargs)
    assert result["status"] == (503 if fault == "storage" else 429 if fault == "quota" else 403)
    assert result["headers"]["Cache-Control"] == "no-store" and "audit_ref" not in result["body"]
    assert db.db.execute("SELECT COUNT(*) FROM vfb_refs").fetchone()[0] == 0


def test_vfb_idempotency_binds_language_consent_and_subject(vfb):
    adapter, submission, policy, _, _, _, _, v, *_ = vfb
    changed = deepcopy(submission)
    changed["language"] = "en"
    changed["submission_proof"] = sign("permission", "permission", submission_document(changed))
    assert adapter.submit(changed, CALLER, policy, v, NOW)["status"] == 409


@pytest.mark.parametrize("operation", ["status", "report", "citation"])
@pytest.mark.parametrize(
    "fault",
    [
        "bare-ref",
        "nonexistent",
        "cross-tenant",
        "expired",
        "revoked",
        "source-revoked",
        "invitation-revoked",
    ],
)
def test_vfb_every_read_checks_session_current_source_and_permission(vfb, operation, fault):
    adapter, _, policy, _, _, ref, _, v, *_ = vfb
    vfb_publish(vfb)
    kwargs = {"citation_id": "citation-fixture"}
    if fault == "bare-ref":
        kwargs["cookie"] = ""
    elif fault == "nonexistent":
        kwargs["ref"] = "nonexistent-fixture"
    elif fault == "cross-tenant":
        kwargs["caller"] = {**CALLER, "tenant_id": "other-tenant"}
    elif fault == "expired":
        kwargs["now"] = NOW + timedelta(days=2)
    elif fault == "revoked":
        adapter.revoke_return_fixture(
            ref, sign("owner", "share", {"audit_ref": ref, "action": "REVOKE_RETURN"}), v, NOW
        )
    elif fault == "source-revoked":
        kwargs["policy"] = {**policy, "revoked_at": NOW.isoformat()}
    elif fault == "invitation-revoked":
        adapter.invitations["invitation-fixture"]["revoked"] = True
    denied = vfb_read(vfb, operation, **kwargs)
    missing = vfb_read(
        vfb, operation, ref="nonexistent-fixture", cookie="", citation_id="citation-fixture"
    )
    assert denied == missing and denied["status"] == 403
    assert set(denied["body"]) == {
        "contract_version",
        "http_status",
        "code",
        "retryable",
        "retry_after_seconds",
    }


def test_vfb_return_exchange_is_distinct_single_use_private_and_durable(vfb):
    adapter, _, policy, _, _, ref, cookie, v, _, directory = vfb
    assert COOKIE_POLICY == {"HttpOnly": True, "Secure": True, "SameSite": "Strict", "Path": "/"}
    again = adapter.exchange(ref, PRINCIPAL["subject_ref"], RETURN_TOKEN, CALLER, policy, v, NOW)
    assert again["status"] == 403
    assert (
        adapter.exchange(ref, "wrong-subject", RETURN_TOKEN, CALLER, policy, v, NOW)["status"]
        == 403
    )
    assert vfb_read(vfb, cookie=RETURN_TOKEN)["status"] == 403
    db = FixtureJournal(directory / "vrae-fixture.sqlite")
    restarted = VFBCandidate(
        db,
        service_actor=CALLER["actor_id"],
        invitations=adapter.invitations,
        publication_resolver=lambda _: None,
    )
    try:
        assert restarted.read("status", ref, cookie, CALLER, policy, v, NOW)["status"] == 200
        restored = restarted.exchange(
            ref, PRINCIPAL["subject_ref"], RETURN_TOKEN, CALLER, policy, v, NOW
        )
        assert restored["status"] == 403
    finally:
        db.close()


@pytest.mark.parametrize(
    "fault",
    [
        "draft",
        "old-version",
        "view-tamper",
        "counter-drop",
        "hypothesis-as-issue",
        "private",
        "false-coverage",
        "wrong-source",
        "four-priorities",
        "wrong-run",
        "released",
        "private-raw",
        "missing-task",
        "report-withdrawn",
        "unknown-without-reason",
    ],
)
def test_vfb_projection_or_publication_tamper_cannot_become_released(vfb, fault):
    record = vfb_publish(vfb)
    view, bundle = record["free_view"], record["bundle"]
    if fault == "draft":
        bundle["report"]["status"] = "DRAFT"
    elif fault == "old-version":
        bundle["latest_version"] = 2
    elif fault == "view-tamper":
        view["results"]["UNDERSTAND"][0]["status"] = "OBSERVED"
    elif fault == "counter-drop":
        view["results"]["UNDERSTAND"].pop(1)
    elif fault == "hypothesis-as-issue":
        view["results"]["UNDERSTAND"][2]["status"] = "ISSUE"
    elif fault == "private":
        view["limitations"][0]["en"] = "contact secret@example.com"
    elif fault == "false-coverage":
        view["coverage"]["successful"] = 2
    elif fault == "wrong-source":
        view["pages"][1]["url"] = "https://outside.example/private"
    elif fault == "four-priorities":
        view["priority"] = ["projected-0", "two", "three", "four"]
    elif fault == "wrong-run":
        bundle["run"]["run_id"] = "run-other"
    elif fault == "released":
        view["kind"] = "released"
    elif fault == "private-raw":
        view["evidence_pack"] = {"raw": "private text"}
    elif fault == "missing-task":
        del view["results"]["TRUST"]
    elif fault == "report-withdrawn":
        record["current_grant"]["grant"]["status"] = "REVOKED"
    elif fault == "unknown-without-reason":
        view["results"]["UNDERSTAND"][2]["unknown_reason"] = None
    if fault in {
        "counter-drop",
        "hypothesis-as-issue",
        "private",
        "false-coverage",
        "wrong-source",
        "four-priorities",
        "released",
        "private-raw",
        "missing-task",
        "unknown-without-reason",
    }:
        record["projection_proof"] = sign(
            "owner",
            "share",
            {
                "audit_ref": view["audit_ref"],
                "report_version_id": view["report_version_id"],
                "view_sha256": digest(view),
            },
        )
    denied = vfb_read(vfb, "report")
    assert denied["status"] in {403, 409} and denied["body"].get("kind") != "released"


@pytest.mark.parametrize("stage", list(STATE_MAP))
def test_vfb_status_never_publishes_from_run_status_alone(stage):
    run = report_bundle()["run"]
    run["status"] = stage
    body = vf_status("aref-fixture", run, NOW)
    assert body["display_state"] not in {"completed", "partial"}
    assert body["task"]["status"] == stage and body["task"]["progress_percent"] is None


def test_vfb_expiry_access_and_unavailability_are_independent_of_run():
    run = report_bundle()["run"]
    for access, available, expected in [
        ("EXPIRED", True, "expired"),
        ("ENDED", True, "access-ended"),
        ("ACTIVE", False, "unavailable"),
    ]:
        result = vf_status("aref-fixture", run, NOW, access=access, available=available)
        assert result["display_state"] == expected and result["task"]["status"] == "REVIEW_REQUIRED"
    assert (
        vf_status(
            "aref-fixture", run, NOW, publication="APPROVED_FULL", version="report-fixture.v1"
        )["display_state"]
        == "completed"
    )


@pytest.mark.parametrize(
    "fault",
    ["not-requested", "diagnosis-consent", "expired", "old-version", "no-publication", "withdrawn"],
)
def test_vfb_inquiry_requires_independent_active_access_and_consent(vfb, fault):
    adapter, _, policy, publications, _, ref, cookie, v, *_ = vfb
    vfb_publish(vfb)
    envelope, now = inquiry_fixture(ref), NOW
    if fault == "not-requested":
        envelope["customer_requested"] = False
    elif fault == "diagnosis-consent":
        envelope["inquiry_consent"]["consent_version"] = "VF-SCAN-CONSENT-DRAFT-1"
    elif fault == "expired":
        now += timedelta(days=2)
    elif fault == "old-version":
        envelope["report_version_id"] = "report-fixture.v0"
    elif fault == "no-publication":
        publications.clear()
    elif fault == "withdrawn":
        adapter.journal.withdraw(TENANT, "audit-fixture", CALLER, policy, v, NOW)
    response = adapter.inquiry(envelope, cookie, CALLER, policy, v, now)
    assert response["status"] == 403
    assert adapter.db.execute("SELECT COUNT(*) FROM items WHERE kind='handoff'").fetchone()[0] == 0


def test_vfb_projection_consumer_checks_all_facts_and_log_allowlist(vfb):
    record = vfb_publish(vfb)
    validate_free_view(record["free_view"], record["bundle"])
    assert safe_log_record("report", "ACCESS_DENIED") == {
        "operation": "report",
        "code": "ACCESS_DENIED",
    }
    for value in ("https://legacy.example/products/p40", RETURN_TOKEN, "cookie", "raw_excerpt"):
        with pytest.raises(Refused):
            safe_log_record("report", value)


@pytest.mark.parametrize(
    "stage,reason",
    [
        ("POLICY_BLOCKED", "SOURCE_POLICY_BLOCKED"),
        ("ACCESS_BLOCKED", "SOURCE_ACCESS_BLOCKED"),
        ("INSUFFICIENT_EVIDENCE", "NO_EVIDENCE"),
        ("MODEL_INVALID", "MODEL_INVALID"),
    ],
)
def test_vfb_blocked_unknown_model_reasons_are_safe_and_not_auto_retried(stage, reason):
    run = report_bundle()["run"]
    run["status"] = stage
    body = vf_status("aref-fixture", run, NOW)
    assert body["reason_code"] == reason and not body["retryable"]
    assert body["publication"]["report_version_id"] is None


def test_vfb_external_quota_and_report_withdrawal_have_bounded_semantics():
    run = report_bundle()["run"]
    run["status"], run["error_code"] = "FAILED", "QUOTA_EXCEEDED"
    body = vf_status("aref-fixture", run, NOW)
    assert body["reason_code"] == "RATE_LIMITED" and body["retry_after_seconds"] == 60
    ended = vf_status("aref-fixture", run, NOW, publication="WITHDRAWN")
    assert ended["display_state"] == "access-ended" and not ended["retryable"]

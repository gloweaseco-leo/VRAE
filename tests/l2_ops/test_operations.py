"""Synthetic adapter tests, not evidence of a completed real L2 Worker run."""

from dataclasses import replace

import pytest

from vrae.l2_ops.accounting import ActivityTimer, Measurement, total_cost
from vrae.l2_ops.briefs import BriefService
from vrae.l2_ops.sources import OperationsDenied
from vrae.reviewing.canonical import canonical, sha


@pytest.mark.parametrize("mode", ["OFFLINE_SYNTHETIC", "PUBLIC_READONLY_CAPTURE", "CLIENT_PROVIDED"])
def test_offline_depth_does_not_need_owner_access(bundle, mode):
    bundle = replace(bundle, access_mode=mode)
    result = bundle.document()
    assert result["diagnostic_level"] == "L2"
    assert result["network_requests"] == 0
    assert result["external_run_permission_reference"] is None
    assert result["inputs"][0]["synthetic"] is True
    assert "raw" not in result["inputs"][0]
    assert result["inputs"][0]["rebuild_asset_use"] == "PENDING_CONFIRMATION"
    with pytest.raises(OperationsDenied, match="EXTERNAL_EXECUTION"):
        replace(bundle, external_run_permission_reference="receipt-shaped-string").require_external_access()


def test_source_bytes_bind_identity_and_order(bundle):
    changed = replace(bundle.inputs[0], raw=b"different controlled source")
    assert replace(bundle, inputs=(changed,)).document()["content_sha256"] != bundle.document()["content_sha256"]
    with pytest.raises(OperationsDenied, match="DUPLICATE"):
        replace(bundle, inputs=bundle.inputs * 2)
    with pytest.raises(OperationsDenied, match="SYNTHETIC_LABEL"):
        replace(bundle, inputs=(replace(bundle.inputs[0], synthetic=False),))


@pytest.mark.parametrize("bad", ["", "  ", "newline\n", "\u202ehidden", "\ud800"])
def test_untrusted_reference_is_bounded(bundle, bad):
    with pytest.raises(OperationsDenied):
        replace(bundle.inputs[0], reference=bad)


def test_timer_measures_wall_not_human_or_cpu():
    timer = ActivityTimer("actual-test-runtime", "DIAGNOSIS_RUNTIME", "AUTOMATED_DEMO")
    row = timer.finish().priced()
    assert row["wall_ns"] >= 0 and row["cpu_ns"] is None
    assert row["amount_micros"] is None and row["cost_status"] == "UNKNOWN"
    assert row["human_labor_claim"] is False
    with pytest.raises(OperationsDenied, match="ALREADY_FINISHED"):
        timer.finish()


def test_unknown_cost_never_becomes_free_or_reconciled():
    row = Measurement("op", "REVIEW_ACTIVITY", 3_600_000_000_000, None, "HUMAN_ATTESTED", "synthetic-attestation-test-only")
    priced = row.priced(rate_micros_per_hour=100_000_000, currency="CNY")
    assert priced["amount_micros"] == 100_000_000
    assert priced["cost_status"] == "ESTIMATED" and not priced["invoice_reconciled"]
    assert total_cost([priced, row.priced()])["amount_micros"] is None
    assert total_cost([])["amount_micros"] is None
    assert total_cost([priced, row.priced(rate_micros_per_hour=1, currency="USD")])["amount_micros"] is None
    with pytest.raises(OperationsDenied, match="CURRENCY"):
        row.priced(currency="C1Y")
    with pytest.raises(OperationsDenied, match="COST_RECORD_CHANGED"):
        total_cost([{**priced, "amount_micros": 0}])


def test_internal_brief_is_not_customer_approval_or_vf_receipt(bundle, reader):
    service = BriefService(reader)
    result = service.prepare(bundle, brief_ref="brief-1", consultation_ref="unverified-user-reference")
    assert result["preparation_status"] == "INTERNAL_REVIEW_RECORDED"
    assert result["consultation"]["state"] == "UNVERIFIED_REFERENCE"
    assert not result["consultation"]["counts_as_e2"] and not result["consultation"]["counts_as_e3"]
    assert not result["external_delivery_allowed"] and not result["customer_approval"]
    assert all(c["status"] == "PENDING" for c in result["customer_confirmations"])
    assert result["cost_total"]["cost_status"] == "UNKNOWN"
    assert service.read_current(result) == result
    reader.allowed = False
    with pytest.raises(OperationsDenied, match="REVOKED"):
        service.read_current(result)


@pytest.mark.parametrize("kind", ["tenant", "source", "payload", "review", "blueprint", "L1"])
def test_cross_task_version_and_l1_cannot_form_deep_brief(bundle, reader, kind):
    current = reader.value
    if kind in {"tenant", "source"}:
        field, value = ("tenant_id", "another-tenant") if kind == "tenant" else ("source_bundle_sha256", "d" * 64)
        reader.value = replace(current, pins={**current.pins, field: value})
    elif kind == "payload":
        reader.value = replace(current, payload={**current.payload, "tampered": True})
    elif kind in {"review", "blueprint"}:
        reader.value = replace(current, **{kind: {**getattr(current, kind), "report_version": "other-version"}})
    else:
        payload = {**current.payload, "diagnostic_level": "L1"}
        reader.value = replace(current, payload=payload, pins={**current.pins, "payload_sha256": sha(canonical(payload))})
    with pytest.raises(OperationsDenied):
        BriefService(reader).prepare(bundle, brief_ref="denied")


def test_revised_or_rejected_review_does_not_become_approved(bundle, reader):
    for decision, state in [("REJECT_INTERNAL", "REJECTED"), ("REVISE_INTERNAL", "REVISION_REQUIRED")]:
        reader.value = replace(reader.value, review={**reader.value.review, "decision": decision})
        assert BriefService(reader).prepare(bundle, brief_ref="brief-1")["preparation_status"] == state


def test_current_recheck_and_immutable_payload(bundle, reader):
    service = BriefService(reader)
    document = service.prepare(bundle, brief_ref="brief-1")
    document["blueprint"]["items"][0]["proposal"] = "tampered"
    with pytest.raises(OperationsDenied, match="TAMPERED"):
        service.read_current(document)
    assert reader.value.blueprint["items"][0]["proposal"] != "tampered"
    document = service.prepare(bundle, brief_ref="brief-1")
    reader.value = replace(reader.value, pins={**reader.value.pins, "job_id": "another-job"})
    with pytest.raises(OperationsDenied, match="STALE_OR_CROSS_TASK"):
        service.read_current(document)


def test_human_labor_requires_explicit_attestation_reference():
    with pytest.raises(OperationsDenied):
        Measurement("op", "REVIEW_ACTIVITY", 1, None, "HUMAN_ATTESTED")
    with pytest.raises(OperationsDenied, match="ATTESTATION_ATTRIBUTION"):
        Measurement("op", "REVIEW_ACTIVITY", 1, None, "AUTOMATED_DEMO", "false-human-ref")

@pytest.mark.parametrize("tamper", ["e2", "approval", "price", "review_state", "confirmations"])
def test_rehash_does_not_create_business_authority(bundle, reader, tamper):
    service = BriefService(reader)
    document = service.prepare(bundle, brief_ref="brief-tamper")
    if tamper == "e2":
        document["consultation"]["counts_as_e2"] = True
    elif tamper == "approval":
        document["customer_approval"] = True
    elif tamper == "price":
        document["cost_total"]["amount_micros"] = 0
    elif tamper == "review_state":
        document["preparation_status"] = "APPROVED_FOR_CUSTOMER"
    else:
        document["customer_confirmations"][0]["status"] = "CONFIRMED"
    document["content_sha256"] = sha(canonical({k: v for k, v in document.items() if k != "content_sha256"}, limit=2_000_000))
    with pytest.raises(OperationsDenied):
        service.read_current(document)


def test_installer_refuses_using_existing_app_or_reviewer_role():
    from vrae.l2_ops.ledger import install
    for role in ("vrae_app", "vrae_reviewer", "postgres"):
        with pytest.raises(OperationsDenied, match="DEDICATED_RUNTIME_ROLE"):
            install(None, role)

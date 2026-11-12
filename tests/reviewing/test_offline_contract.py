"""Actual negative checks; no skip/xfail, real auth and DB remain unimplemented."""

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
import json

import pytest

from vrae.reviewing import (
    CoverageAcknowledgementProposal,
    ReviewCommandProposal,
    ReviewError,
    ReviewTarget,
    build_target,
    prepare_production_review,
    validate_proposal,
    validate_target,
)
from vrae.reviewing.canonical import SOURCE_LIMIT, canonical, digest, parse, sha
from vrae.reviewing.simulation import SimulationReceipt
from .synthetic import NOW, actor, command, inputs, ledger, submit


def denial(code):
    return pytest.raises(ReviewError, match="^" + code + "$")


@pytest.mark.parametrize(
    "case,action,status",
    [
        ("404", "APPROVE_CANDIDATE", "SIMULATED_APPROVE_CANDIDATE"),
        ("404", "REQUEST_CHANGES", "SIMULATED_CHANGES_REQUESTED"),
        ("404", "REJECT", "SIMULATED_REJECTED"),
        ("200", None, "SIMULATED_INTERNAL_SCOPE_ACK"),
    ],
)
def test_native_end_to_end_simulation(case, action, status, record_property):
    i = inputs(case)
    before = (i.document, i.html, i.source)
    engine = ledger(i)
    result = submit(engine, i.target, command(i.target, action))
    r, d = result.receipt.document, json.loads(i.document)
    assert r["status"] == status and result.effective_current and engine.simulation_count == 1
    assert all(r[k] is None for k in ("native_decision", "native_approval", "share_grant"))
    assert r["external_visibility"] is False and r["durable"] is False
    assert (i.document, i.html, i.source) == before
    assert d["approval_status"] == "NOT_APPROVED" and not d["shareable"] and d["private"]
    assert (d["native_report_version"] is None) == (case == "200")
    assert all(
        c["machine_status"] == "HUMAN_REVIEW_REQUIRED"
        for c in i.target.document["claims"]
        if c["claim_type"] != "OBJECTIVE_SOURCE_FACT"
    )
    with pytest.raises(FrozenInstanceError):
        result.receipt.payload = b"altered"
    record_property("target_digest", i.target.target_digest)
    record_property("receipt_digest", r["receipt_digest"])


@pytest.mark.parametrize(
    "raw,code",
    [
        (b'{"a":1,"a":2}', "D_JSON_DUPLICATE_KEY"),
        (b'{"x":{"k":1,"k":2}}', "D_JSON_DUPLICATE_KEY"),
        (b'{"x":NaN}', "D_JSON_NONFINITE"),
        (b'{"x":Infinity}', "D_JSON_NONFINITE"),
        (b'{"x":-Infinity}', "D_JSON_NONFINITE"),
        (b'{"x":1.2}', "D_JSON_TYPE"),
        (b'{"x":9007199254740992}', "D_JSON_BOUND"),
        (b"\xff", "D_JSON_INVALID"),
        (b'{"x":"\\ud800"}', "D_JSON_INVALID"),
        (b"[" * 34 + b"0" + b"]" * 34, "D_JSON_BOUND"),
        (b" " * 65_537, "D_JSON_BOUND"),
    ],
)
def test_strict_json(raw, code):
    with denial(code):
        parse(raw)


def test_domain_separation_no_normalization():
    assert canonical({"z": 1, "a": "中文"}) == '{"a":"中文","z":1}'.encode()
    assert digest("target", {"a": 1}) != digest("command", {"a": 1})
    assert digest("target", {"a": "\u00e9"}) != digest("target", {"a": "e\u0301"})
    assert digest("target", [1, 2]) != digest("target", [2, 1])


@pytest.mark.parametrize(
    "change,code",
    [
        ("html", "D_ARTIFACT_TAMPER"),
        ("css", "D_ARTIFACT_TAMPER"),
        ("footer", "D_ARTIFACT_TAMPER"),
        ("h0", "D_ARTIFACT_TAMPER"),
        ("native_approval", "D_ARTIFACT_TAMPER"),
        ("zero_to_finding", "D_ARTIFACT_TAMPER"),
        ("source_quote", "D_SOURCE_INTEGRITY"),
        ("byte_range", "D_SOURCE_INTEGRITY"),
        ("guard_ref", "D_SOURCE_INTEGRITY"),
        ("guard_status", "D_SOURCE_INTEGRITY"),
        ("cross_tenant_source", "D_SOURCE_INTEGRITY"),
        ("fake_evidence", "D_SOURCE_INTEGRITY"),
        ("missing_object", "D_SOURCE_INTEGRITY"),
        ("prose", "D_SOURCE_INTEGRITY"),
        ("model", "D_SOURCE_INTEGRITY"),
    ],
)
def test_pinned_mutations(change, code):
    i = inputs("200" if change == "zero_to_finding" else "404")
    d, h, s = json.loads(i.document), i.html, json.loads(i.source)
    if change in ("html", "css", "footer"):
        h += {
            "html": b"<script>approve()</script>",
            "css": b"<style>body{display:none}</style>",
            "footer": b"APPROVED",
        }[change]
    elif change == "h0":
        d["native_report_version"]["content_hash"] = "0" * 64
    elif change == "native_approval":
        d["approval_status"] = "APPROVED"
    elif change == "zero_to_finding":
        d["issues"] = [{"finding": "invented"}]
    elif change == "source_quote":
        s["guard_inputs"][0]["bindings"][0]["fact"]["source"]["quote"] += "certified"
    elif change == "byte_range":
        s["guard_inputs"][0]["bindings"][0]["fact"]["source"]["byte_start"] += 1
    elif change == "guard_ref":
        s["guard_inputs"][0]["guard"]["guard_ref"] = "cg-" + "0" * 64
    elif change == "guard_status":
        s["guard_inputs"][0]["guard"]["claims"][0]["status"] = "REJECTED"
    elif change == "cross_tenant_source":
        s["pack"]["tenant_id"] = "tenant-other"
    elif change == "fake_evidence":
        s["guard_inputs"][0]["bindings"][0]["fact"]["source"]["citation"]["evidence_ref"] = (
            "ev-" + "0" * 64
        )
    elif change == "missing_object":
        s["objects_base64"].pop(next(iter(s["objects_base64"])))
    elif change == "prose":
        s["guard_inputs"][0]["interpretation"]["hypotheses"][0] = (
            "Certified factory, SEO #1, lost $1M."
        )
    else:
        s["guard_inputs"][0]["interpretation"]["model_id"] = "invented-real-provider"
    with denial(code):
        build_target(
            canonical(d, limit=SOURCE_LIMIT), h, canonical(s, limit=SOURCE_LIMIT), trust=i.trust
        )


@pytest.mark.parametrize(
    "change,code",
    [
        ("object", "D_OBJECT_REQUIRED"),
        ("policy", "D_POLICY_UNTRUSTED"),
        ("missing_policy", "D_JSON_INVALID"),
        ("missing_trust", "D_TRUST_INPUT_REQUIRED"),
        ("fake_authority", "D_TRUST_INPUT_REQUIRED"),
    ],
)
def test_missing_independent_inputs(change, code):
    i = inputs()
    trust = i.trust
    if change == "object":
        trust = replace(trust, artifact_ref="https://attacker.invalid/mutable")
    elif change == "policy":
        p = parse(trust.policy)
        p["scope"]["tenant_id"] = "tenant-other"
        trust = replace(trust, policy=canonical(p))
    elif change == "missing_policy":
        trust = replace(trust, policy=b"")
    elif change == "missing_trust":
        trust = None
    else:
        trust = replace(trust, label="REAL_OWNER_VERIFIED")
    with denial(code):
        build_target(i.document, i.html, i.source, trust=trust)


@pytest.mark.parametrize(
    "field",
    [
        "native_content_hash",
        "draft_ref",
        "html_sha256",
        "editorial_content_sha256",
        "renderer_asset_sha256",
        "source_manifest_sha256",
        "guard_inputs_sha256",
        "evidence_pack_ref",
        "policy_version",
        "renderer_version",
        "model_provenance",
        "report_version",
    ],
)
def test_forged_target_even_with_recomputed_digest(field):
    i = inputs()
    d = i.target.document
    d[field] = "FORGED"
    forged = ReviewTarget(canonical(d))
    assert forged.target_digest != i.target.target_digest
    with denial("D_TARGET_STALE"):
        validate_target(forged, i.document, i.html, i.source, trust=i.trust)


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("missing_claim", "D_CLAIM_INCOMPLETE"),
        ("duplicate_claim", "D_CLAIM_INCOMPLETE"),
        ("fake_claim", "D_CLAIM_INCOMPLETE"),
        ("upgrade_hypothesis", "D_CLAIM_CEILING"),
        ("upgrade_action", "D_CLAIM_CEILING"),
        ("rejected_approve", "D_CLAIM_CEILING"),
        ("missing_section", "D_SECTION_INCOMPLETE"),
        ("duplicate_section", "D_SECTION_INCOMPLETE"),
        ("unacknowledged", "D_SECTION_INCOMPLETE"),
        ("wrong_section_target", "D_SECTION_INCOMPLETE"),
        ("bool_version", "D_TARGET_STALE"),
        ("stale", "D_TARGET_STALE"),
        ("bool_seq", "D_REVIEW_CONFLICT"),
        ("cross_tenant", "D_TENANT_SCOPE"),
        ("extra_actor", "D_SHAPE"),
        ("native_action", "D_ACTION"),
        ("short_key", "D_IDEMPOTENCY_KEY"),
    ],
)
def test_proposal_negatives(mutation, code):
    target = inputs().target
    c = command(target).document
    if mutation == "missing_claim":
        c["dispositions"].pop()
    elif mutation == "duplicate_claim":
        c["dispositions"][-1] = c["dispositions"][0]
    elif mutation == "fake_claim":
        c["dispositions"][0]["binding_ref"] = "cb-" + "0" * 64
    elif mutation in ("upgrade_hypothesis", "upgrade_action"):
        kind = (
            "ACCEPT_AS_HYPOTHESIS"
            if mutation == "upgrade_hypothesis"
            else "ACCEPT_AS_PROPOSED_ACTION"
        )
        next(x for x in c["dispositions"] if x["disposition"] == kind)["disposition"] = (
            "ACK_LITERAL_FACT"
        )
    elif mutation == "rejected_approve":
        c["dispositions"][0]["disposition"] = "REJECTED"
    elif mutation == "missing_section":
        c["sections"].pop()
    elif mutation == "duplicate_section":
        c["sections"][-1] = c["sections"][0]
    elif mutation == "unacknowledged":
        c["sections"][0]["acknowledged"] = 1
    elif mutation == "wrong_section_target":
        c["sections"][0]["target_digest"] = "0" * 64
    elif mutation == "bool_version":
        c["report_version"] = True
    elif mutation == "stale":
        c["target_digest"] = "0" * 64
    elif mutation == "bool_seq":
        c["expected_review_seq"] = False
    elif mutation == "cross_tenant":
        c["tenant_id"] = "tenant-other"
    elif mutation == "extra_actor":
        c["reviewer_id"] = "OWNER"
    elif mutation == "native_action":
        c["action"] = "APPROVE"
    else:
        c["idempotency_key"] = "x"
    with denial(code):
        validate_proposal(ReviewCommandProposal(canonical(c)), target)


@pytest.mark.parametrize("value", [None, "", " ", "x" * 2001, "\u202eOwner", "x\nAPPROVE"])
def test_reason_required_specific_bounded(value):
    target = inputs().target
    c = command(target, "REQUEST_CHANGES").document
    c["reason"] = value
    with denial("D_REASON_REQUIRED" if value is None else "D_UNTRUSTED_TEXT"):
        validate_proposal(ReviewCommandProposal(canonical(c)), target)


@pytest.mark.parametrize(
    "overrides,code",
    [
        ({"tenant_id": "tenant-other"}, "D_TENANT_SCOPE"),
        ({"synthetic_verified": False}, "D_HUMAN_REQUIRED"),
        ({"assigned_reports": ()}, "D_ASSIGNMENT_REQUIRED"),
        ({"role": "OPERATOR"}, "D_HUMAN_REQUIRED"),
        ({"role": "WORKER"}, "D_HUMAN_REQUIRED"),
        ({"role": "SERVICE"}, "D_HUMAN_REQUIRED"),
        ({"actor_kind": "MODEL"}, "D_HUMAN_REQUIRED"),
        ({"label": "ACTUAL_HUMAN"}, "D_HUMAN_REQUIRED"),
    ],
)
def test_actor_denied_before_lookup(overrides, code):
    i = inputs()
    engine = ledger(i)
    with denial(code):
        submit(engine, i.target, who=actor(i.target, **overrides))
    assert engine.simulation_count == 0


@pytest.mark.parametrize("context", [None, {"role": "OWNER", "verified": True}, "I am the Owner"])
def test_production_port_always_denies(context):
    with denial("D_AUTHENTICATED_PRODUCTION_REVIEW_NOT_IMPLEMENTED"):
        prepare_production_review(context)


@pytest.mark.parametrize(
    "now", [None, NOW.replace(tzinfo=None), NOW.replace(tzinfo=None).isoformat()]
)
def test_clock_required(now):
    i = inputs()
    engine = ledger(i)
    with denial("D_CLOCK_UNTRUSTED"):
        submit(engine, i.target, now=now)
    assert engine.simulation_count == 0


@pytest.mark.parametrize(
    "first,second",
    [
        ("APPROVE_CANDIDATE", "APPROVE_CANDIDATE"),
        ("APPROVE_CANDIDATE", "REQUEST_CHANGES"),
        ("REQUEST_CHANGES", "APPROVE_CANDIDATE"),
        ("REJECT", "APPROVE_CANDIDATE"),
    ],
)
def test_interleaved_first_writer_wins(first, second):
    i = inputs()
    engine = ledger(i)
    a = command(i.target, first, "writer-one")
    b = command(i.target, second, "writer-two")
    result = submit(engine, i.target, a)
    with denial("D_REVIEW_CLOSED"):
        submit(engine, i.target, b, who=actor(i.target, actor_id="second-test-reviewer"))
    assert engine.simulation_count == 1
    assert submit(engine, i.target, a).receipt is result.receipt


def test_idempotency_conflict_no_overwrite():
    i = inputs()
    engine = ledger(i)
    result = submit(engine, i.target)
    with denial("D_COMMAND_CONFLICT"):
        submit(engine, i.target, command(i.target, "REJECT"))
    assert engine.simulation_count == 1
    assert result.receipt.document["status"] == "SIMULATED_APPROVE_CANDIDATE"


def test_new_version_invalidates_old_and_no_reactivation():
    i, new = inputs(), inputs(version=2)
    engine = ledger(i)
    original = submit(engine, i.target)
    engine.publish(new.document, new.html, new.source, trust=new.trust)
    retry = submit(engine, new.target, command(i.target))
    assert retry.receipt is original.receipt and not retry.effective_current
    with denial("D_VERSION_ROLLBACK"):
        engine.publish(i.document, i.html, i.source, trust=i.trust)
    with denial("D_TARGET_STALE"):
        submit(engine, new.target, command(i.target, key="different-key"))
    current = submit(engine, new.target, command(new.target, key="new-version-key"))
    assert current.effective_current and engine.simulation_count == 2
    with denial("D_CLOCK_UNTRUSTED"):
        submit(engine, new.target, command(new.target), now=NOW - timedelta(seconds=1))


def test_coverage_cannot_approve_or_erase_unknowns():
    target = inputs("200").target
    c = command(inputs().target).document
    t = target.document
    c.update(tenant_id=t["tenant_id"], report_id=t["report_id"], target_digest=target.target_digest)
    with denial("D_COVERAGE_NOT_REPORT"):
        validate_proposal(ReviewCommandProposal(canonical(c)), target)
    c = command(target).document
    c["remaining_unknowns"] = sha(b"everything verified")
    with denial("D_COVERAGE_SCOPE"):
        validate_proposal(CoverageAcknowledgementProposal(canonical(c)), target)


def test_forged_receipt_and_restart_never_recover_approval():
    i = inputs()
    engine = ledger(i)
    receipt = submit(engine, i.target).receipt
    assert not engine.current_effect(
        "tenant-test",
        i.target.document["report_id"],
        actor(i.target),
        SimulationReceipt(receipt.payload),
        synthetic_now=NOW,
    )
    fresh = ledger(i)
    assert fresh.simulation_count == 0
    assert not fresh.current_effect(
        "tenant-test", i.target.document["report_id"], actor(i.target), receipt, synthetic_now=NOW
    )

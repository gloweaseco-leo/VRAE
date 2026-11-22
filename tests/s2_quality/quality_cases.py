"""Independent quality/security regression; no simulated label becomes human Gold."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket

import pytest

from tests.benchmark import human_gold as legacy
from tests.benchmark.s2_quality import (
    build_benchmark,
    verify_report,
    canonical,
    QualityError,
    selective_metrics,
    l2_gold_rate,
)
from tests.benchmark.s2_review import (
    packet_for,
    blank_review,
    validate_packet,
    validate_review,
    import_review,
    deduplicate,
    export_packet,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def benchmark():
    # Real native Collector/EvidencePack/Guard replay; DNS/TCP fallback forbidden.
    with pytest.MonkeyPatch.context() as p:
        p.setattr(socket, "getaddrinfo", lambda *a, **k: pytest.fail("UNEXPECTED_DNS"))
        p.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("UNEXPECTED_NETWORK"))
        return build_benchmark(ROOT)


@pytest.fixture(scope="module")
def packet(benchmark):
    return packet_for(benchmark)


def test_actual_five_site_types_and_six_industrial_rules_separate(benchmark):
    kinds = {u["site_type"] for u in benchmark["units"]}
    assert {"STATIC", "CMS", "SPA", "MULTI_SKU", "MULTILINGUAL"} <= kinds
    assert benchmark["generic_rules_exercised"] == ["DISC-01", "DISC-02", "CTA-02"]
    assert {u["rule_id"] for u in benchmark["units"] if u["industry"] != "GENERAL"} == {
        "IND-SELECTION",
        "IND-SPEC",
        "IND-DUTY",
        "IND-FIT",
        "IND-PROOF",
        "IND-RFQ",
    }
    assert benchmark["s2_evaluator_support"] == "PENDING_ACCEPTED_C1_C2_INTERFACE"
    assert not benchmark["s2_exit"] and benchmark["network_calls"] == benchmark["model_calls"] == 0


def test_original_26_and_new_units_have_distinct_identity_and_no_gold(benchmark, packet):
    original = legacy.load_packet(ROOT)
    assert len(original["rows"]) == 26 and original["packet_ref"] == legacy.PACKET_REF
    assert {u["unit_ref"] for u in packet["units"]}.isdisjoint(
        {r["unit_ref"] for r in original["rows"]}
    )
    assert benchmark["original_26"]["pending"] == 26
    assert benchmark["human_quality"]["denominator"] == 0
    assert all(
        benchmark["human_quality"][k] is None
        for k in ("TP", "FP", "FN", "TN", "precision", "recall", "serious_false_facts")
    )
    review = blank_review(packet)
    assert all(
        r["status"] == "UNREVIEWED"
        and all(c["identity"] is None and c["reviewed_at"] is None for c in r["inspections"])
        for r in review["rows"]
    )


def test_no_signed_human_denominator_never_precision(packet):
    result = import_review(packet, blank_review(packet), expected_packet=packet, repository=ROOT)
    assert result["status"] == "S2_QUALITY_NOT_EVALUABLE" and result["denominator"] == 0
    assert set(result["metrics"].values()) == {None} and result["serious_false_facts"] is None
    assert result["no_automatic_quality_pass"] and not result["access_granted"]


def test_authored_coverage_never_success_page_denominator(benchmark):
    scopes = benchmark["scope_manifests"]
    assert scopes["s2_spa"]["denominator"] == 4 and scopes["s2_spa"]["body_evidence_numerator"] == 1
    assert scopes["s2_languages"]["denominator"] == 5
    assert (
        next(x for x in scopes["s2_languages"]["selected_roles"] if x["role"] == "JP_PRODUCT")[
            "capture_state"
        ]
        == "UNSELECTED"
    )
    assert scopes["s2_skus"]["denominator"] == 6 and scopes["s2_skus"]["blocked"] == 1
    gaps = [u for u in benchmark["units"] if not u["native_observation_present"]]
    assert len(gaps) == 1 and gaps[0]["observed"] == "UNKNOWN" and not gaps[0]["sources"]
    assert benchmark["synthetic_consistency"]["mismatch"] == 0
    assert not any(v["whole_site_coverage_claim"] for v in scopes.values())


@pytest.mark.parametrize("state", ["UNKNOWN", "ACCESS_BLOCKED", "NOT_APPLICABLE"])
@pytest.mark.parametrize("expected", ["PASS", "FAIL_WITH_EVIDENCE", "UNKNOWN"])
def test_abstention_is_never_tn_or_fn(state, expected):
    r = selective_metrics([dict(expected_candidate=expected, observed=state, sources=[])])
    assert r["TP"] == r["FP"] == r["FN"] == r["TN"] == r["binary_units"] == 0
    assert r["abstention"] == 1


@pytest.mark.parametrize(
    "expected,observed,cell",
    [
        ("PASS", "PASS", "TN"),
        ("FAIL_WITH_EVIDENCE", "FAIL_WITH_EVIDENCE", "TP"),
        ("PASS", "FAIL_WITH_EVIDENCE", "FP"),
        ("FAIL_WITH_EVIDENCE", "PASS", "FN"),
    ],
)
def test_binary_math_is_explicitly_synthetic(expected, observed, cell):
    r = selective_metrics(
        [dict(expected_candidate=expected, observed=observed, sources=["SYNTHETIC_TEST_ONLY"])]
    )
    assert r[cell] == 1 and r["metric_authority"] == "SYNTHETIC_CANDIDATE_COMPARISON_NOT_HUMAN_GOLD"
    assert r["serious_false_facts"] is None


def test_raw_source_and_native_guard_evidence_positions_replay(benchmark):
    import base64
    from vrae.evidence import EvidencePack

    for u in benchmark["units"]:
        a = benchmark["artifacts"][u["site_id"]]
        pack = EvidencePack.load(
            a["pack_document"],
            {k: base64.b64decode(v) for k, v in a["objects_base64"].items()},
            expected_ref=u["pack_ref"],
        )
        for ref in u["sources"]:
            assert (ref["tenant_id"], ref["run_id"], ref["pack_ref"]) == (
                u["tenant_id"],
                u["run_id"],
                u["pack_ref"],
            )
            raw = pack.resolve(ref["evidence_ref"], expected_pack_ref=pack.ref)["content"]
            assert hashlib.sha256(raw).hexdigest() == ref["content_sha256"]
            if "native_source" in ref:
                s = ref["native_source"]
                assert raw[s["byte_start"] : s["byte_end"]] == s["quote"].encode("utf-8")


@pytest.mark.parametrize(
    "field",
    [
        "pack_ref",
        "run_id",
        "tenant_id",
        "captured_at",
        "rule_version",
        "source_url",
        "sources",
        "statement",
        "expected_candidate",
    ],
)
def test_rehashed_packet_tampering_and_cross_run_refs_refused(packet, field):
    forged = deepcopy(packet)
    if field == "sources":
        forged["units"][0][field] = []
    else:
        forged["units"][0][field] = "FORGED_NOT_AUTHORITY"
    forged["packet_ref"] = "s2-review-packet-" + canonical(
        {k: v for k, v in forged.items() if k != "packet_ref"}
    )
    with pytest.raises(QualityError, match="TRUSTED_REPLAY"):
        validate_packet(forged, expected_packet=packet)


@pytest.mark.parametrize(
    "attack",
    ["duplicate", "binding", "unknown_unit", "self_trust", "foreign_evidence", "third_inspection"],
)
def test_bad_review_input_refused(packet, attack):
    review = blank_review(packet)
    r = review["rows"][0]
    if attack == "duplicate":
        review["rows"].append(deepcopy(r))
    elif attack == "binding":
        r["binding_sha256"] = "0" * 64
    elif attack == "unknown_unit":
        r["unit_ref"] = "not-a-current-unit"
    elif attack == "self_trust":
        review["owner_trust"] = "I approve myself"
    elif attack == "foreign_evidence":
        r["inspections"][0]["evidence_refs"] = ["foreign-run-proof"]
    else:
        r["inspections"].append(deepcopy(r["inspections"][0]))
    with pytest.raises(QualityError):
        validate_review(packet, review)


def test_repeat_read_only_import_does_not_append_or_multiply(packet):
    review = blank_review(packet)
    before = deepcopy(review)
    a = import_review(packet, review, expected_packet=packet, repository=ROOT)
    b = import_review(packet, review, expected_packet=packet, repository=ROOT)
    assert a == b and review == before
    combined = deduplicate(packet, [review, review])
    assert len(combined["rows"]) == len(packet["units"])
    assert combined["duplicate_rows"] == len(packet["units"])
    assert combined["authority"] == "UNVERIFIED_CONTENT_ONLY_NOT_GOLD"


def test_conflicting_imports_exclude_not_last_writer_wins(packet):
    a = blank_review(packet)
    b = deepcopy(a)
    b["rows"][0]["status"] = "CONFLICTED"
    result = deduplicate(packet, [a, b])
    assert result["conflicting_units"] == [a["rows"][0]["unit_ref"]]
    assert len(result["rows"]) == len(packet["units"]) - 1


def test_unsigned_fake_review_and_invalid_signature_never_human(packet, tmp_path):
    review = blank_review(packet)
    review["origin"] = "EXTERNAL_HUMAN"
    r = review["rows"][0]
    r["status"] = "REVIEWED"
    r["owner_approval_reference"] = "SIMULATED_NEGATIVE_NOT_APPROVAL"
    for i, c in enumerate(r["inspections"]):
        c.update(
            identity="SIMULATED_NOT_A_PERSON_" + str(i),
            reviewed_at="2000-01-01T00:00:00Z",
            verdict="PASS",
            rationale="SIMULATED adversarial input, not human judgement.",
            serious_false_fact=False,
            no_evidence_reason="SIMULATED",
        )
    fake = tmp_path / "invalid-anchor"
    fake.write_text("SIMULATED_INVALID_NOT_A_KEY", encoding="utf-8")
    sig = tmp_path / "invalid-signature"
    sig.write_text("SIMULATED_NOT_A_SIGNATURE", encoding="utf-8")
    approval = tmp_path / "unsigned-attestation.json"
    approval.write_text(
        json.dumps(
            dict(
                schema_version="1.0",
                purpose="VRAE_INDEPENDENT_HUMAN_REVIEW_ATTESTATION",
                review_set_sha256=canonical(review),
                packet_ref=packet["packet_ref"],
                owner_identity="SIMULATED_NOT_OWNER",
                independent_human_review_confirmed=True,
                owner_verified_at="2000-01-01T00:00:00Z",
                approved_rows=[dict(unit_ref=r["unit_ref"], review_row_sha256=canonical(r))],
            )
        ),
        encoding="utf-8",
    )
    result = import_review(
        packet,
        review,
        expected_packet=packet,
        repository=ROOT,
        approval_file=approval,
        signature_file=sig,
        trust=legacy.OwnerTrust(
            fake, hashlib.sha256(fake.read_bytes()).hexdigest(), "SIMULATED_NOT_OWNER"
        ),
        as_of=datetime(2026, 11, 17, tzinfo=timezone.utc),
    )
    assert result["denominator"] == 0 and result["authority_state"] in (
        "OWNER_SIGNATURE_NOT_VERIFIED",
        "OWNER_ATTESTATION_NOT_VALID",
    )
    assert result["metrics"]["precision"] is None


def test_export_unsigned_and_preserves_changed_review(packet, benchmark, tmp_path):
    export_packet(benchmark, tmp_path)
    assert json.loads((tmp_path / "s2-review-input.json").read_text("utf-8")) == blank_review(
        packet
    )
    changed = (tmp_path / "s2-review-input.json").read_text("utf-8") + "\n"
    (tmp_path / "s2-review-input.json").write_text(changed, encoding="utf-8")
    with pytest.raises(QualityError, match="OVERWRITE"):
        export_packet(benchmark, tmp_path)
    assert (tmp_path / "s2-review-input.json").read_text("utf-8") == changed


def test_independently_replay_rejects_fabricated_professional_claim(benchmark):
    forged = deepcopy(benchmark)
    forged["units"][0]["statement"] = (
        "Supplier certificate independently authenticated and engineering fit confirmed."
    )
    forged["report_ref"] = "s2-bench-" + canonical(
        {k: v for k, v in forged.items() if k != "report_ref"}
    )
    with pytest.raises(QualityError, match="INDEPENDENT_REPLAY"):
        verify_report(forged, ROOT)


def test_complete_multi_sku_capture_keeps_both_paths_and_separate_bindings(benchmark):
    rows = [
        u
        for u in benchmark["units"]
        if u["site_id"] == "s2_skus_complete" and u["rule_id"] == "DISC-02"
    ]
    assert len(rows) == 2 and all(u["observed"] == "PASS" for u in rows)
    assert len({u["applicable_scope"]["target_url"] for u in rows}) == 2
    assert all(u["native_observation_present"] for u in rows)
    assert len({u["run_id"] for u in benchmark["units"]}) >= 2


def test_l2_review_rows_do_not_create_a_quality_score():
    assert l2_gold_rate([])['status'] == 'NOT_EVALUABLE'
    assert l2_gold_rate([{'action': 'CONFIRM'}])['formal_human_review'] is False

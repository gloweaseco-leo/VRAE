"""New L2 business semantics; no original acceptance suite or real network."""

from copy import deepcopy
import hashlib
import socket

import pytest

from integration.industry_l2.fixture import DIRECTORY, evidence_pack
from vrae.collection.manifest import document_hash
from vrae.evidence import EvidenceError
from vrae.industry.l2_v1 import diagnose, load, verify
from vrae.industry.l2_v1.contracts import validate_export
from vrae.industry.l2_v1.diagnose import quantity


def run(**kwargs):
    pack, bundle, transport = evidence_pack(**kwargs)
    result = diagnose(pack, expected_pack_ref=pack.ref, expected_industry_ref=load()["industry_ref"])
    return pack, bundle, transport, result


@pytest.fixture(scope="module")
def baseline():
    # Block real DNS/connect entry points; asyncio may create its internal local
    # wakeup socketpair (not an external website request), especially on Windows.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("UNEXPECTED_NETWORK"))
        patch.setattr(socket, "getaddrinfo", lambda *a, **k: pytest.fail("UNEXPECTED_DNS"))
        return run()


def rows(result, rule, model=None):
    return [a for a in result["assessments"] if a["observation"]["rule_id"] == rule and (model is None or a["model"] == model)]


def test_native_multipage_buyer_chain_and_all_guarded_sources(baseline):
    pack, bundle, transport, result = baseline
    assert len(bundle.manifest["pages"]) == 8
    assert all(p["http_status"] == 200 for p in bundle.manifest["pages"])
    assert len(transport.requests) == 9 and all(method == "GET" for method, _ in transport.requests)
    assert {a["model"] for a in result["assessments"]} == {"P40", "V25"}
    assert all(a["observation"]["result"] == "PASS" for a in rows(result, "IND-SELECTION"))
    assert all(a["details"]["native_path_observation_ids"] for a in rows(result, "IND-SELECTION"))
    assert all(p["contact_observation_ids"] for p in result["rfq_packets"])
    assert len(result["procurement_chains"]) == 2
    for chain in result["procurement_chains"]:
        assert [s["stage"] for s in chain["stages"]] == ["PRODUCT_DISCOVERY", "PRODUCT_AND_SPECIFICATION", "APPLICATION_REVIEW", "SUPPLIER_PROOF_CONTEXT", "CONTACT_AND_RFQ"]
        assert all(s["observation_ids"] for s in chain["stages"]) and chain["engineering_fit"] == "UNKNOWN"
    assert all(r["status"] == "EXECUTED" for r in result["industry_rule_coverage"])
    bindings = [b for group in result["source_guard_inputs"] for b in group["bindings"]]
    assert len(bindings) == len(result["source_facts"]) == 81
    assert {b["fact"]["fact_ref"] for b in bindings} == {f["fact_ref"] for f in result["source_facts"]}
    assert all(c["status"] == "SOURCE_FACT_BINDING_VERIFIED" for g in result["source_guard_inputs"] for c in g["guard"]["claims"])
    # Check exact source quotation, byte interval and hash on every distinct page.
    examples = {f["source"]["citation"]["url"]: f for f in result["source_facts"]}
    for fact in examples.values():
        source = fact["source"]
        raw = pack.resolve(source["citation"]["evidence_ref"], expected_pack_ref=pack.ref)["content"]
        assert raw[source["byte_start"]:source["byte_end"]] == source["quote"].encode()
        assert hashlib.sha256(raw).hexdigest() == source["citation"]["content_sha256"]
    validate_export(result)


def test_business_conflicts_do_not_become_fabricated_defects(baseline):
    result = baseline[3]
    for model, pressure in (("P40", "10 bar"), ("V25", "16 bar")):
        row = next(a for a in rows(result, "IND-DUTY", model) if a["details"].get("attribute") == "pressure")
        assert row["observation"]["result"] == "FAIL_WITH_EVIDENCE"
        assert pressure in row["observation"]["statement"] and "18 bar" in row["observation"]["statement"]
        sources = {f["source"]["citation"]["url"] for f in result["source_facts"] if f["fact_ref"] in row["source_fact_refs"]}
        assert "https://example.org/products/duty-selection" in sources and len(sources) == 2
    assert all(a["details"]["independent_authentication"] == "UNKNOWN" for a in rows(result, "IND-PROOF"))
    assert all(a["observation"]["result"] == "UNKNOWN" for a in rows(result, "IND-FIT"))
    assert all(a["possible_buyer_impact"]["finding"]["kind"] == "HYPOTHESIS" for a in result["assessments"])
    assert all(r["status"] == "HUMAN_REVIEW_REQUIRED" and r["finding"]["kind"] == "RECOMMENDATION" for a in result["assessments"] for r in a["recommendations"])
    assert all(p["missing_buyer_inputs"] == ["destination"] and not p["submission_performed"] for p in result["rfq_packets"])
    assert result["approval_status"] == "NOT_APPROVED" and not result["shareable"]
    assert result["native_report_draft_ref"] is None  # No second report engine.


@pytest.mark.parametrize("left,right,equal", [
    ("1.6 MPa", "1600 kPa", True), ("12 m3/h", "200 L/min", True),
    ("400 V", "400 V", True), ("10 bar", "18 bar", False),
])
def test_explicit_unit_comparisons(left, right, equal):
    profile = load()["profile"]
    a, b = quantity(left, profile), quantity(right, profile)
    assert a[0] == b[0] and (a[1] == b[1]) is equal


@pytest.mark.parametrize("value", [None, "PN16", "10-20 bar", "about 10 bar", "ten bar", "10 psi", "1e9 bar"])
def test_unresolved_units_and_ranges_remain_unknown(value):
    assert quantity(value, load()["profile"]) is None


def test_missing_attribute_and_pdf_alternative_do_not_prove_absence():
    raw = (DIRECTORY / "pump.html").read_bytes().replace(b"<tr><th>Motor power</th><td>2.2 kW</td></tr>", b"")
    raw = raw.replace(b"<nav>", b'<a href="/p40.pdf">More specifications in datasheet</a><nav>')
    result = run(overrides={"/products/pump-p40": raw})[3]
    row = rows(result, "IND-SPEC", "P40")[0]
    assert row["observation"]["result"] == "UNKNOWN" and row["details"]["not_observed"] == ["power"]
    assert row["finding"]["kind"] == "UNKNOWN" and row["finding"]["evidence_ids"] == []
    assert "does not establish absence" in row["observation"]["statement"]


def test_model_association_and_unsupported_pressure_are_not_guessed():
    app = (DIRECTORY / "application.html").read_bytes().replace(b"P40, V25", b"OTHER-MODEL")
    pump = (DIRECTORY / "pump.html").read_bytes().replace(b"10 bar", b"PN10")
    result = run(overrides={"/products/duty-selection": app, "/products/pump-p40": pump})[3]
    assert rows(result, "IND-SPEC", "P40")[0]["details"]["unusable_values"] == ["pressure"]
    assert all(a["observation"]["result"] in ("UNKNOWN", "NOT_APPLICABLE") for a in rows(result, "IND-DUTY"))
    assert all(a["observation"]["result"] == "UNKNOWN" for a in rows(result, "IND-RFQ"))


def test_no_retained_bodies_produce_unknown_not_failure():
    result = run(retain=False)[3]
    assert not result["source_facts"]
    assert {a["observation"]["result"] for a in result["assessments"]} == {"UNKNOWN"}
    assert sum(r["status"] == "UNKNOWN_INPUT_UNAVAILABLE" for r in result["industry_rule_coverage"]) == 5


def test_consumer_replay_rejects_forged_prose_even_with_rehashed_envelope(baseline):
    pack, _, _, result = baseline
    forged = deepcopy(result)
    forged["assessments"][0]["observation"]["statement"] = "The supplier is independently certified and the product is safe."
    forged["diagnosis_ref"] = "l2-" + document_hash({k: v for k, v in forged.items() if k != "diagnosis_ref"})
    with pytest.raises(EvidenceError, match="L2_INDUSTRY_INTEGRITY"):
        verify(forged, pack, expected_result_ref=forged["diagnosis_ref"], expected_pack_ref=pack.ref, expected_industry_ref=load()["industry_ref"])


def test_pins_and_tenant_bound_configuration_are_required(baseline):
    pack = baseline[0]
    with pytest.raises(EvidenceError):
        diagnose(pack, expected_pack_ref="ep-" + "0" * 64, expected_industry_ref=load()["industry_ref"])
    with pytest.raises(EvidenceError):
        diagnose(pack, expected_pack_ref=pack.ref, expected_industry_ref=load(tenant_id="tenant-other")["industry_ref"])


def test_pack_has_family_specific_applicability_and_not_a_universal_fit_score(baseline):
    result = baseline[3]
    valve_na = [a for a in rows(result, "IND-DUTY", "V25") if a["observation"]["result"] == "NOT_APPLICABLE"]
    assert len(valve_na) == 1 and valve_na[0]["observation"]["evidence_ids"] == []
    assert not any("motor" in q for q in load()["profile"]["families"]["valve"]["critical"])
    assert all(a["details"]["engineering_fit"] == "UNKNOWN" for a in rows(result, "IND-FIT"))

"""C3 read-only adaptation negatives; not a new Worker/browser/Gold run."""
import base64
from copy import deepcopy
import hashlib
import os
from pathlib import Path

import pytest

from integration.l2_ops.s2_quality_source_review import build_bundle, export_bundle
from tests.benchmark.s2_quality import canonical
from tests.benchmark.s2_review import validate_packet
from vrae.evidence import EvidenceError, EvidencePack
from vrae.rules.s2 import verify_s2_projection


@pytest.fixture(scope="module")
def bundle():
    return build_bundle(Path(__file__).resolve().parents[2],
                        Path(os.environ["C3_SOURCE_REVIEW_REPOSITORY"]))


def test_actual_accepted_source_replay_keeps_denominators_and_admission(bundle):
    assert bundle["source_manifest"]["accepted_main"] == "95ed55321775223e95cf0a1585220951cc692648"
    assert len(bundle["technical_runs"]) == 6
    assert all(r["independent_replay"] and not r["worker_or_browser_run"]
               for r in bundle["technical_runs"])
    assert {u["rule_id"] for u in bundle["packet"]["units"]} == {
        "DISC-03", "SEO-02", "TECH-01", "INFO-02", "TRUST-02", "TRUST-03"
    }
    for u in bundle["packet"]["units"]:
        assert u["producer_ref"].startswith("s2p-")
        assert not u["native_observation_present"] and u["projection_observation_present"]
        assert u["producer_kind"] == "S2P_READ_ONLY_NOT_RX_OR_GUARD"
    assert {u["observed"] for u in bundle["packet"]["units"]} == {"PASS", "UNKNOWN"}
    assert all(s["whole_site_denominator"] is None
               for s in bundle["report"]["scope_manifests"].values())


def test_each_review_quote_is_original_pack_bytes(bundle):
    for u in bundle["packet"]["units"]:
        artifact = bundle["report"]["artifacts"][u["site_id"]]
        for source in u["sources"]:
            cite = source["citation"]
            pack = EvidencePack.load(artifact["pack_document"],
                {k: base64.b64decode(v, validate=True) for k, v in artifact["objects_base64"].items()},
                expected_ref=u["pack_ref"])
            raw = pack.resolve(source["evidence_ref"], expected_pack_ref=pack.ref)["content"]
            assert hashlib.sha256(raw).hexdigest() == source["content_sha256"]
            assert raw[cite["byte_start"]:cite["byte_end"]].decode() == cite["quote"]


def test_existing_review_intake_stays_unsigned_and_not_evaluable(bundle):
    result = bundle["human_assessment"]
    assert result["denominator"] == 0 and result["status"] == "S2_QUALITY_NOT_EVALUABLE"
    assert all(v is None for v in result["metrics"].values())
    assert not result["formal_review"] and not result["access_granted"]
    for row in bundle["review_input"]["rows"]:
        assert row["status"] == "UNREVIEWED" and row["owner_approval_reference"] is None
        assert all(c["identity"] is c["reviewed_at"] is c["verdict"] is None
                   for c in row["inspections"])


@pytest.mark.parametrize("attack", ["result", "foreign_ev", "native_admission", "gold"])
def test_self_rehash_cannot_rebind_source_or_promote_authority(bundle, attack):
    changed = deepcopy(bundle["packet"])
    row = changed["units"][0]
    if attack == "result":
        row["observed"] = "FAIL_WITH_EVIDENCE"
    elif attack == "foreign_ev":
        row["sources"][0]["evidence_ref"] = "ev-" + "0" * 64
    elif attack == "native_admission":
        row["native_observation_present"] = True
    else:
        row["human_gold"] = True
    changed["packet_ref"] = "s2-review-packet-" + canonical(
        {k: v for k, v in changed.items() if k != "packet_ref"})
    with pytest.raises(ValueError, match="PACKET_TRUSTED_REPLAY_MISMATCH"):
        validate_packet(changed, expected_packet=bundle["packet"])


def test_accepted_c1_replay_rejects_unknown_promoted_to_pass(bundle):
    artifact = bundle["report"]["artifacts"]["batch2_no_pins"]
    out = deepcopy(artifact["producer"])
    pack = EvidencePack.load(artifact["pack_document"],
        {k: base64.b64decode(v, validate=True) for k, v in artifact["objects_base64"].items()},
        expected_ref=out["pack_ref"])
    out["industrial_projection"]["rows"][0]["observation"]["result"] = "PASS"
    out["projection_ref"] = "s2p-" + canonical({k: v for k, v in out.items() if k != "projection_ref"})
    with pytest.raises(EvidenceError):
        verify_s2_projection(out, pack, expected_pack_ref=pack.ref,
            trusted_scope=out["scope"], expected_projection_ref=out["projection_ref"],
            expected_projection_version=out["projection_version"])


def test_export_cannot_overwrite_a_prepared_or_human_edited_packet(bundle, tmp_path):
    export_bundle(bundle, tmp_path / "review")
    with pytest.raises(FileExistsError):
        export_bundle(bundle, tmp_path / "review")


def test_unverified_extra_snapshot_code_is_rejected():
    from integration.l2_ops.s2_quality_source_review import verify_source_root, SourceReviewError
    root = Path(__file__).resolve().parents[2]
    injected = root / "unverified_candidate_helper.py"
    assert not injected.exists()
    try:
        injected.write_text("raise RuntimeError('MUST_NOT_IMPORT')\n", encoding="utf-8")
        with pytest.raises(SourceReviewError, match="UNVERIFIED_SNAPSHOT_ENTRY"):
            verify_source_root(root, Path(os.environ["C3_SOURCE_REVIEW_REPOSITORY"]))
    finally:
        injected.unlink()

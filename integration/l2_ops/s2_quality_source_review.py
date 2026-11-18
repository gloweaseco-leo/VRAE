"""C3 local-only adaptation of accepted C1 source candidates to unsigned review."""
import argparse
from copy import deepcopy
import hashlib
import html
import importlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ACCEPTED = "95ed55321775223e95cf0a1585220951cc692648"
OVERLAYS = ("tests/benchmark/s2_quality.py", "tests/benchmark/s2_review.py",
            "tests/benchmark/s2_sites.py", "integration/l2_ops/s2_quality_source_review.py",
            "tests/s2_quality/source_review_cases.py")
TITLES = {
    "DISC-03": "应用路径能否到达本次采集的产品",
    "SEO-02": "产品页原文与静态站内链接，不评排名",
    "TECH-01": "本次记录的 HTTP 响应，不评实时可用性",
    "INFO-02": "来源声明的参数、单位、版本与工况",
    "TRUST-02": "型号相关证明的展示，不验证真伪或资格",
    "TRUST-03": "同一声明标识下的主体与联系原文对照",
}
STATIC_ROLES = [("HOME", "/"), ("APPLICATION", "/applications/water"),
                ("PRODUCT", "/products/p40"), ("PRODUCT", "/products/v25")]
INDUSTRIAL_ROLES = [("HOME", "/"), ("CATEGORY", "/products"),
                    ("PRODUCT", "/products/p40"), ("PRODUCT", "/products/v25"),
                    ("PROOF", "/products/proof"), ("ABOUT", "/about"), ("CONTACT", "/contact")]


class SourceReviewError(ValueError):
    """Fixed integrity error, never a permission or review decision."""


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def verify_source_root(root, repository):
    root, repository = Path(root).resolve(), Path(repository).resolve()
    if not root.is_relative_to(repository / "integration/l2_ops/.private"):
        raise SourceReviewError("OWNED_ACCEPTED_SNAPSHOT_REQUIRED")
    raw = subprocess.check_output(["git", "ls-tree", "-r", ACCEPTED, "--",
                                  "vrae", "tests", "contracts", "industry-packs",
                                  "integration/s2_contract", "pyproject.toml"], cwd=repository)
    expected = {}
    for line in raw.decode().splitlines():
        meta, name = line.split("\t")
        mode, kind, ref = meta.split()
        if kind != "blob" or mode not in ("100644", "100755"):
            raise SourceReviewError("SOURCE_ENTRY_TYPE")
        if name in OVERLAYS:
            continue
        content = (root / name).read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        if actual != ref:
            raise SourceReviewError("ACCEPTED_SOURCE_BYTES_CHANGED")
        expected[name] = ref
    actual_files = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual_files != set(expected) | set(OVERLAYS) or any(p.is_symlink() for p in root.rglob("*")):
        raise SourceReviewError("UNVERIFIED_SNAPSHOT_ENTRY")
    for name in OVERLAYS:
        if (root / name).read_bytes() != (repository / name).read_bytes():
            raise SourceReviewError("C3_REVIEW_OVERLAY_CHANGED")
    sys.path.insert(0, str(root))
    for name in ("vrae", "vrae.rules.s2", "tests.benchmark.s2_review",
                 "tests.s2_contract.batch2_fixtures"):
        module = importlib.import_module(name)
        if not Path(module.__file__).resolve().is_relative_to(root):
            raise SourceReviewError("MIXED_SOURCE_IMPORT_ROOT")
    return {"accepted_main": ACCEPTED, "accepted_git_blobs": expected,
            "own_overlay_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest()
                                   for p in OVERLAYS}}


def build_bundle(source_root, repository):
    manifest = verify_source_root(source_root, repository)
    # In-memory synthetic transport only; deny any accidental DNS/TCP fallback.
    with patch("socket.getaddrinfo", side_effect=SourceReviewError("DNS_FORBIDDEN")), patch(
        "socket.create_connection", side_effect=SourceReviewError("TCP_FORBIDDEN")
    ):
        return _build(Path(source_root), manifest)


def _build(root, manifest):
    from tests.benchmark import human_gold as legacy
    from tests.benchmark.s2_quality import canonical, unit, source_ref, archive
    from tests.benchmark.s2_review import packet_for, blank_review, validate_review, import_review
    from tests.s2_contract import p1_static_cases as batch1
    from tests.s2_contract.batch2_fixtures import fixture, identity, DIRECTORY
    from vrae.industry.l2_v1.pack import load_s2
    from vrae.rules.s2 import evaluate_s2, verify_s2_projection, IndustryPins

    static_rules = ("DISC-03", "SEO-02", "TECH-01")
    industry_rules = ("INFO-02", "TRUST-02", "TRUST-03")
    raw = (DIRECTORY / "pump.html").read_bytes().replace(b"10 bar", b"10 psi")
    raw = raw.replace(b"</table>", b"<tr><th>Data revision</th><td>R1</td></tr>"
                      b"<tr><th>Specification conditions</th><td>Water 20 degC</td></tr></table>")
    # Scope and selector expectations are authored BEFORE any capture.
    cases = [
        ("batch1_source", lambda: batch1.fixture(), "static_projection", static_rules, "PASS", True),
        ("batch1_no_raw", lambda: batch1.fixture(retain=False), "static_projection",
         static_rules, "UNKNOWN", True),
        ("batch2_source", lambda: fixture(), "industrial_projection", industry_rules, "PASS", True),
        ("batch2_literal_conflict", lambda: fixture(overrides={"/contact": identity(
            address="20 Other Demo Road")}), "industrial_projection", ("TRUST-03",), "UNKNOWN", True),
        ("batch2_unsupported_unit", lambda: fixture(overrides={"/products/p40": raw}),
         "industrial_projection", ("INFO-02",), "UNKNOWN", True),
        ("batch2_no_pins", lambda: fixture(), "industrial_projection", industry_rules, "UNKNOWN", False),
    ]
    units, artifacts, scopes, runs = [], {}, {}, []
    for case_id, capture, section, selected, expected, use_pins in cases:
        planned = [{"role": role, "url": "https://example.org" + path, "selected": True}
                   for role, path in (STATIC_ROLES if section == "static_projection" else INDUSTRIAL_ROLES)]
        pack = capture()
        scope = {k: pack.document[k] for k in ("tenant_id", "run_id", "policy_id", "policy_version")}
        held = None
        version = "s2-projection-1.1.0"
        if section == "industrial_projection":
            version = "s2-projection-1.2.0"
            if use_pins:
                config = load_s2(tenant_id=scope["tenant_id"])
                held = IndustryPins(config["industry_ref"], scope["tenant_id"])
        output = evaluate_s2(pack, expected_pack_ref=pack.ref, trusted_scope=scope,
                             projection_version=version, industry_pins=held)
        verify_s2_projection(output, pack, expected_pack_ref=pack.ref, trusted_scope=scope,
                             expected_projection_ref=output["projection_ref"],
                             expected_projection_version=version, industry_pins=held)
        scopes[case_id] = {"authored_before_capture": planned,
                          "whole_site_denominator": None, "scope_is_not_whole_site": True}
        artifacts[case_id] = archive(pack, output)
        snapshots = {s["snapshot_ref"]: s for s in pack.document["snapshots"]}
        for rule in selected:
            index, row = next((i, row) for i, row in enumerate(output[section]["rows"])
                              if row["observation"]["rule_id"] == rule)
            refs = []
            for citation in row["citations"]:
                source = source_ref(pack, citation["evidence_ref"])
                content = pack.resolve(citation["evidence_ref"], expected_pack_ref=pack.ref)["content"]
                if content[citation["byte_start"]:citation["byte_end"]].decode() != citation["quote"]:
                    raise SourceReviewError("SOURCE_QUOTE_BYTES_CHANGED")
                source.update(citation=deepcopy(citation),
                              url=snapshots[citation["snapshot_ref"]]["url"],
                              observed_at=snapshots[citation["snapshot_ref"]]["observed_at"])
                refs.append(source)
            snap = snapshots[row["citations"][0]["snapshot_ref"]] if refs else next(iter(snapshots.values()))
            obs = row["observation"]
            value = unit(pack, site=case_id, kind="STATIC" if section == "static_projection" else "INDUSTRIAL_MULTI_SKU",
                         rule=rule, version=obs["rule_version"], expected=expected, observed=obs["result"],
                         scope={"planned_roles": planned, "candidate_only": True},
                         source_url=snap["url"], captured_at=snap["observed_at"], references=refs,
                         producer_ref=output["projection_ref"], statement=obs["statement"],
                         rationale="Authored offline source expectation; not human Gold. " + row["reason"],
                         locator="/" + section + "/rows/" + str(index),
                         task="UNDERSTAND" if rule == "INFO-02" else "TRUST" if rule.startswith("TRUST") else "FIND",
                         industry="INDUSTRIAL" if section == "industrial_projection" else "GENERAL",
                         observed_in_native=False)
            value.update(producer_kind="S2P_READ_ONLY_NOT_RX_OR_GUARD",
                         source_projection_version=version, source_reason=row["reason"],
                         source_details=deepcopy(row.get("details", {})),
                         evidence_check="ORIGINAL_UTF8_SPANS_REPLAYED" if refs else "NO_QUOTE_EVIDENCE",
                         human_question=TITLES[rule], projection_observation_present=True)
            units.append(value)
        runs.append({"case_id": case_id, "scope_consistency_only": scope,
                     "pack_ref": pack.ref, "s2p_ref": output["projection_ref"],
                     "projection_version": version, "independent_replay": True,
                     "raw_citations_verified": True, "worker_or_browser_run": False})
    report = {"version": "c3-source-review-1.0.0", "accepted_main": ACCEPTED,
              "scope": "LOCAL_OFFLINE_SOURCE_REVIEW_PREPARATION_NOT_REPORT_OR_P2",
              "units": units, "scope_manifests": scopes, "artifacts": artifacts,
              "original_26": {"packet_ref": legacy.PACKET_REF, "pending": 26},
              "new_human_verified": 0, "quality_status": "S2_QUALITY_NOT_EVALUABLE",
              "runtime_worker_browser": False, "model_calls": 0, "external_network_calls": 0}
    report["report_ref"] = "c3-source-prep-" + canonical(report)
    packet = packet_for(report)
    review = blank_review(packet)
    validate_review(packet, review)
    assessment = import_review(packet, review, expected_packet=packet, repository=root)
    if assessment["denominator"] != 0 or any(v is not None for v in assessment["metrics"].values()):
        raise SourceReviewError("NO_HUMAN_GOLD_AUTHORITY")
    return {"report": report, "packet": packet, "review_input": review,
            "human_assessment": assessment, "technical_runs": runs, "source_manifest": manifest}


def verify_bundle(value, source_root, repository):
    expected = build_bundle(source_root, repository)
    if encode(value) != encode(expected):
        raise SourceReviewError("SOURCE_PREPARATION_REPLAY_MISMATCH")
    return expected


def export_bundle(value, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for name, obj in (("bundle.json", value), ("s2-packet.json", value["packet"]),
                      ("s2-review-input.json", value["review_input"]),
                      ("human-assessment.json", value["human_assessment"])):
        (output / name).write_bytes(encode(obj))
    lines = ["# 首批来源候选人工核对包（未审阅）", "",
             "仅离线合成来源；不是正式报告、人类Gold或权限许可。",
             "已实际运行：离线来源构造、EvidencePack验证、C1受限s2p及独立重放、原字节核对。",
             "未运行：真实Worker任务、浏览器、Controlled审核、Brief和整机P2。",
             "s2p不是原rx或Guard事实。PASS只指受限来源条件；工程适用性、证书真伪与主体资格未验证。",
             "两位真实独立审核人、第三人冲突裁决和Owner签名均由Owner另行安排；所有栏位空白。",
             "原0/26、新旧32单元与本包不合并计分；本包人审0，有效精度/召回率/严重事实虚构均未评估。", ""]
    for u in value["packet"]["units"]:
        lines += ["## " + u["human_question"] + " / " + u["site_id"],
                  "- 来源候选结果：" + u["observed"] + "；原因：" + u["source_reason"],
                  "- 范围：仅本次合成采集与已声明角色；不是全站分母。",
                  "- URL / 采集时间：" + u["source_url"] + " / " + u["captured_at"],
                  "- 来源投影：" + u["producer_ref"] + "，版本 " + u["source_projection_version"],
                  "- 包 / 规则版本：" + u["pack_ref"] + " / " + u["rule_version"],
                  "- 核对限制：缺数据不能判网站缺陷；冲突是人工待核，不是法律或资格结论。",
                  "- 审核人一：____；日期：____；意见与理由：____",
                  "- 审核人二：____；日期：____；意见与理由：____",
                  "- 冲突复核：____；Owner签署：____", ""]
        if not u["sources"]:
            lines.append("缺少可引用原文字节：保持不可评估，不制造ev-ref。")
        for source in u["sources"]:
            c = source["citation"]
            lines += ["原文：" + html.escape(c["quote"]),
                      "定位：" + source["url"] + " / " + c["locator"] +
                      " / bytes " + str(c["byte_start"]) + ":" + str(c["byte_end"]),
                      "原内容SHA256：" + source["content_sha256"], ""]
    (output / "reviewer-zh.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if bool(args.output) == bool(args.verify):
        parser.error("choose fresh output OR read-only verify")
    if args.verify:
        verify_source_root(args.source_root, args.repository)
        from tests.benchmark.s2_review import read_json
        verify_bundle(read_json(args.verify), args.source_root, args.repository)
        print("SOURCE_PREPARATION_REPLAY_VERIFIED_NOT_RUNTIME_OR_GOLD")
    else:
        value = build_bundle(args.source_root, args.repository)
        export_bundle(value, args.output)
        print(json.dumps({"units": len(value["packet"]["units"]), "technical_cases": 6,
                          "human_verified": 0, "status": "S2_QUALITY_NOT_EVALUABLE"}))


if __name__ == "__main__":
    main()

"""Execute industrial procurement analysis and export private synthetic data."""

import argparse
import base64
from collections import Counter
import json
from pathlib import Path

from vrae.industry.l2_v1 import diagnose, load
from .fixture import evidence_pack


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pack, bundle, transport = evidence_pack()
    result = diagnose(pack, expected_pack_ref=pack.ref, expected_industry_ref=load()["industry_ref"])
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "diagnosis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    source = {"pack": pack.document, "objects_base64": {k: base64.b64encode(v).decode() for k, v in pack.objects.items()}}
    (args.output / "source.json").write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
    counts = dict(Counter(a["observation"]["result"] for a in result["assessments"]))
    lines = ["# Synthetic industrial buyer-task execution", "", "Private NOT_APPROVED business data; not engineering approval or a shared report.", "", "- Source: eight local HTML pages; fixed recorded transport, no live domain request.", "- Models: P40 pump equipment and V25 industrial valve component.", "- Native refs: " + result["native_execution_ref"] + ", " + ", ".join(result["source_guard_refs"]), "- Diagnosis: " + result["diagnosis_ref"], "- Result counts: " + json.dumps(counts), "", "## Evidence-backed comparisons and unresolved questions", ""]
    for a in result["assessments"]:
        o = a["observation"]
        lines.append(f"- {a['model']} / {o['rule_id']} / {o['result']}: {o['statement']} [{o['observation_id']}]")
        if a["details"].get("not_observed"):
            lines.append("  - Not observed (not absence): " + ", ".join(a["details"]["not_observed"]))
        if a["details"].get("questions"):
            lines.append("  - Verify: " + "; ".join(a["details"]["questions"]))
    lines += ["", "## RFQ preparation (no submission)", ""]
    for packet in result["rfq_packets"]:
        lines.append("- " + packet["model"] + ": unresolved buyer inputs=" + ", ".join(packet["missing_buyer_inputs"]) + "; product-context GET paths=" + str(len(packet["contact_observation_ids"])))
    lines += ["", "Exact source quotations, byte positions, HTML-body SHA and capture times are in diagnosis.json -> source_facts; source.json replays the same native EvidencePack.", "Hypotheses and recommendations remain HUMAN_REVIEW_REQUIRED. Missing information, unsupported units and unverified engineering/certification remain UNKNOWN."]
    (args.output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"source": "SYNTHETIC_LOCAL_ONLY", "pages": len(bundle.manifest["pages"]), "get_requests": len(transport.requests), "source_guard_facts": len(result["source_facts"]), "assessments": counts, "diagnosis_ref": result["diagnosis_ref"]}))


if __name__ == "__main__":
    main()

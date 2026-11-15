"""Create private, replayed DISC HTML and native source-chain evidence offline."""

import base64
import hashlib
import json
from pathlib import Path

from integration.beta_disc_report import inputs
from vrae.reporting.disc_report_v1 import ReportDraft, build_draft


def main():
    root = Path(__file__).resolve().parents[2]
    out = root / "docs/03-engineering/beta-disc-report/.runtime/previews"
    out.mkdir(parents=True, exist_ok=True)
    receipts = []
    for rule in ("DISC-01", "DISC-02"):
        for status in (404, 410, 200, 403):
            pack, package, guards, metadata, pins = inputs(rule, status)
            draft = build_draft(pack, package, guards, metadata, **pins)
            ReportDraft.load(
                draft.document,
                draft.html_bytes,
                pack,
                package,
                guards,
                metadata,
                expected_draft_ref=draft.ref,
                **pins,
            )
            name = rule.lower() + "-" + str(status)
            (out / (name + ".html")).write_bytes(draft.html_bytes)
            evidence = {
                "pack": pack.document,
                "objects_base64": {
                    k: base64.b64encode(v).decode() for k, v in pack.objects.items()
                },
                "package": package.document,
                "guard_inputs": guards,
                "metadata": metadata,
                "pins": pins,
                "draft": draft.document,
            }
            raw = (
                json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
            ).encode()
            (out / (name + ".private.json")).write_bytes(raw)
            receipts.append(
                {
                    "case_id": name,
                    "pack_ref": pack.ref,
                    "package_ref": package.ref,
                    "execution_ref": pins["expected_execution_ref"],
                    "guard_refs": pins["expected_guard_refs"],
                    "draft_ref": draft.ref,
                    "issue_count": len(draft.document["issues"]),
                    "html_sha256": hashlib.sha256(draft.html_bytes).hexdigest(),
                    "private_chain_sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
    (out / "receipts.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "cases": len(receipts),
                "output": str(out),
                "private": True,
                "approval_status": "NOT_APPROVED",
                "network_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()

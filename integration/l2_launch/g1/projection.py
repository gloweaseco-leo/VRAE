"""Whitelist projection of current original C2 findings, not a report engine.

All native findings are retained. Citations group original source references by
retained page (<=8 actual pages), avoiding silent truncation of multi-fact rows.
"""

from copy import deepcopy
import hashlib

from contracts.l2_launch.contract import digest
from contracts.l2_launch.vf_b import VERSION, TASKS, validate_free_view


def text(en, zh):
    return {"en": en, "zh": zh}


def project(record, current):
    pack = current.evidence.pack
    document = pack.document
    view = current.view
    native = view.document
    citations = []
    by_url = {}
    pages = []
    evidence_by_snapshot = {
        e["snapshot_ref"]: e
        for e in document["evidence"]
        if e["kind"] == "HTTP_BODY" and e["blob_ref"]
    }
    for index, snapshot in enumerate(document["snapshots"]):
        raw_evidence = evidence_by_snapshot.get(snapshot["snapshot_ref"])
        successful = snapshot["status"] == "OBSERVED" and raw_evidence is not None
        pages.append(
            {
                "url": snapshot["url"],
                "label": "Recorded page " + str(index + 1),
                "outcome": "reviewed" if successful else "unknown",
                "unknown_reason": None if successful else snapshot["status"],
            }
        )
        if successful:
            raw = pack.resolve(raw_evidence["evidence_ref"], expected_pack_ref=pack.ref)["content"]
            excerpt = raw.decode("utf-8")[:200]
            citation = {
                "citation_id": "cite-"
                + hashlib.sha256(raw_evidence["evidence_ref"].encode()).hexdigest()[:32],
                "source_url": snapshot["url"],
                "captured_at": snapshot["observed_at"],
                "locator": raw_evidence["evidence_ref"]
                + "#sha256="
                + raw_evidence["content_sha256"],
                "excerpt": excerpt,
            }
            citations.append(citation)
            by_url[snapshot["url"]] = citation["citation_id"]
    evidence = {row["id"]: row for row in native["evidence"]}
    originals = view.findings
    rows_by_id = {row["id"]: row for row in native["findings"]}
    results = {task: [] for task in TASKS}
    for original in originals:
        row = rows_by_id[original["finding_id"]]
        task = original["buyer_task"]
        kind = original["kind"]
        if task not in results:
            raise ValueError("G1_UNMAPPED_ORIGINAL_TASK")
        if kind == "OBSERVATION" and row["native_result"] == "PASS":
            kind = "COUNTER_EVIDENCE"
        unknown = kind in ("UNKNOWN", "HYPOTHESIS", "RECOMMENDATION")
        urls = {
            evidence[ref]["url"]
            for ref in row["evidence_ids"]
            if ref in evidence and "url" in evidence[ref]
        }
        cids = sorted({by_url[url] for url in urls if url in by_url})
        fact = {
            "fact_id": row["id"],
            "original_fact_ref": original["finding_id"],
            "kind": kind,
            "status": "UNKNOWN" if unknown else "OBSERVED",
            "statement": text(original["statement"], row["statement"]),
            "citation_ids": [] if kind == "UNKNOWN" else cids,
            "buyer_impact": None,
            "rebuild": None,
            "unknown_reason": "HUMAN_REVIEW_REQUIRED" if unknown else None,
            "next_check": text(
                "Recheck the original retained evidence and ask the responsible engineer.",
                row["recheck"],
            )
            if unknown
            else None,
        }
        results[task].append(fact)
    for task, rows in results.items():
        if not rows:
            rows.append(
                {
                    "fact_id": "unknown-" + task.lower(),
                    "original_fact_ref": None,
                    "kind": "UNKNOWN",
                    "status": "UNKNOWN",
                    "statement": text(
                        "No supported original assessment for this task was produced in this bounded run.",
                        "本轮没有该维度的受支持原生评估；保持UNKNOWN。",
                    ),
                    "citation_ids": [],
                    "buyer_impact": None,
                    "rebuild": None,
                    "unknown_reason": "NOT_OBSERVED",
                    "next_check": text(
                        "Obtain separately authorized evidence before making a conclusion.",
                        "取得另行许可的证据后再判断。",
                    ),
                }
            )
    successful = sum(page["outcome"] == "reviewed" for page in pages)
    authorized = len(current.plan.native.pack.document["snapshots"])
    summary = {
        "A": {
            "en": f"This controlled synthetic run retained {successful} successful pages out of {len(pages)} attempted pages; {len(originals)} original assessments are preserved.",
            "zh": f"本轮受控合成任务尝试{len(pages)}页、成功留存{successful}页；保留{len(originals)}项原生评估。",
            "basis": "OBSERVATION",
            "citation_ids": [c["citation_id"] for c in citations],
        },
        "B": {
            "en": "Engineering fit, source authenticity, inquiry delivery and conversion remain UNKNOWN. Recheck the original evidence before any external use.",
            "zh": "工程适配、资料真实性、询价送达及转化仍UNKNOWN；对外使用前需复核原证据。",
            "basis": "RECOMMENDATION",
            "citation_ids": [c["citation_id"] for c in citations],
        },
    }
    result = {
        "contract_version": VERSION,
        "view_type": "FreePreDiagnosticView",
        "kind": "synthetic",
        "audience": "AUTHORIZED_RECIPIENT",
        "anonymous_access": False,
        "audit_ref": record["audit_ref"],
        "report_version_id": view.version["report_version_id"],
        "target_url": current.plan.audit["site_url"],
        "checked_at": citations[0]["captured_at"]
        if citations
        else document["snapshots"][0]["observed_at"],
        "source": "SYNTHETIC_CONTRACT_FIXTURE_NOT_A_RELEASE",
        "pages": pages,
        "coverage": {
            "authorized": authorized,
            "attempted": len(pages),
            "successful": successful,
            "unknown": len(pages) - successful,
            "whole_site_denominator": None,
        },
        "results": results,
        "priority": [],
        "summary": summary,
        "citations": citations,
        "limitations": [
            text(
                "OFFLINE_SYNTHETIC only. Source access is L1; diagnostic depth is separate. No live collection, real human approval, release, ShareGrant or VF business receipt.",
                "仅受控离线合成。采集许可L1与分析深度分离；无真实采集、真人批准、发行、ShareGrant或VF商务回执。",
            )
        ],
    }
    bundle = {
        "report": view.version,
        "source_command": record["submission"]["command"],
        "source_policy": current.plan.policy,
        "view": {
            "citations": deepcopy(citations),
            "summary": deepcopy(summary),
            "coverage": {"authorized_pages": authorized, "observed_pages": successful},
        },
        "findings": originals,
    }
    validate_free_view(result, bundle)
    assert {
        f["original_fact_ref"] for rows in results.values() for f in rows if f["original_fact_ref"]
    } == {f["finding_id"] for f in originals}
    return result, {
        "view_sha256": digest(result),
        "report_version_id": view.version["report_version_id"],
        "content_hash": view.version["content_hash"],
        "display_hash": view.display_hash,
        "pack_ref": pack.ref,
        "original_findings": len(originals),
        "blueprint_packages": len(native["blueprint"]),
    }

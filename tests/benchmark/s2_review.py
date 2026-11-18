"""Unsigned reviewer packets + read-only intake; reuse the original Owner verifier."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

from . import human_gold as legacy
from .s2_quality import canonical, fail, selective_metrics, strata, VERSION, RESULTS


def packet_for(report):
    value = dict(
        version=VERSION,
        report_ref=report["report_ref"],
        origin="UNREVIEWED_TEMPLATE",
        authority="NO_HUMAN_GOLD_NO_ACCESS_GRANT",
        units=deepcopy(report["units"]),
        source_artifacts={k: canonical(v) for k, v in report["artifacts"].items()},
        original_26_packet_ref=report["original_26"]["packet_ref"],
        required_reviewers=2,
        conflict_policy="INDEPENDENT_THIRD_PERSON_AND_OWNER_ATTESTATION",
    )
    value["packet_ref"] = "s2-review-packet-" + canonical(value)
    return value


def blank_review(packet):
    inspection = dict(
        identity=None,
        reviewed_at=None,
        verdict=None,
        rationale=None,
        evidence_refs=[],
        serious_false_fact=None,
        no_evidence_reason=None,
    )
    return dict(
        schema_version="s2-review-1.0",
        packet_ref=packet["packet_ref"],
        origin="UNREVIEWED_TEMPLATE",
        rows=[
            dict(
                unit_ref=u["unit_ref"],
                binding_sha256=canonical(u),
                status="UNREVIEWED",
                inspections=[deepcopy(inspection), deepcopy(inspection)],
                conflict_resolution=None,
                owner_approval_reference=None,
            )
            for u in packet["units"]
        ],
    )


def validate_packet(packet, *, expected_packet):
    if canonical(packet) != canonical(expected_packet):
        fail("PACKET_TRUSTED_REPLAY_MISMATCH")
    if packet["packet_ref"] != "s2-review-packet-" + canonical(
        {k: v for k, v in packet.items() if k != "packet_ref"}
    ):
        fail("PACKET_HASH_MISMATCH")


def validate_review(packet, review):
    expected = blank_review(packet)
    if len(json.dumps(review)) > 2_000_000 or set(review) != set(expected):
        fail("REVIEW_DOCUMENT_CONTRACT")
    if (
        review["schema_version"] != expected["schema_version"]
        or review["packet_ref"] != packet["packet_ref"]
        or review["origin"]
        not in ("UNREVIEWED_TEMPLATE", "SIMULATED_NOT_HUMAN_GOLD", "EXTERNAL_HUMAN")
    ):
        fail("REVIEW_SCOPE_OR_ORIGIN")
    if not isinstance(review["rows"], list) or len(review["rows"]) > len(packet["units"]):
        fail("REVIEW_ROWS_BOUND")
    units = {u["unit_ref"]: u for u in packet["units"]}
    seen = set()
    for row in review["rows"]:
        if (
            not isinstance(row, dict)
            or set(row) != set(expected["rows"][0])
            or row["unit_ref"] not in units
            or row["unit_ref"] in seen
        ):
            fail("DUPLICATE_OR_UNKNOWN_UNIT")
        seen.add(row["unit_ref"])
        if (
            row["binding_sha256"] != canonical(units[row["unit_ref"]])
            or row["status"] not in legacy.STATES
        ):
            fail("REVIEW_BINDING_OR_STATE")
        if not isinstance(row["inspections"], list) or len(row["inspections"]) != 2:
            fail("TWO_INSPECTIONS_REQUIRED")
        for check in row["inspections"]:
            if not isinstance(check, dict) or set(check) != set(
                expected["rows"][0]["inspections"][0]
            ):
                fail("INSPECTION_CONTRACT")
            if check["verdict"] not in (None, *RESULTS) or not isinstance(
                check["evidence_refs"], list
            ):
                fail("INSPECTION_VERDICT_OR_REFS")
            allowed = {s["evidence_ref"] for s in units[row["unit_ref"]]["sources"]}
            if any(not isinstance(r, str) or r not in allowed for r in check["evidence_refs"]):
                fail("REVIEW_FOREIGN_EVIDENCE")
            if (
                check["serious_false_fact"] is not None
                and type(check["serious_false_fact"]) is not bool
            ):
                fail("FALSE_FACT_CONTRACT")
            for field in ("identity", "reviewed_at", "rationale", "no_evidence_reason"):
                if check[field] is not None and (
                    not isinstance(check[field], str) or len(check[field]) > 2000
                ):
                    fail("INSPECTION_TEXT_BOUND")
        if row["owner_approval_reference"] is not None and not isinstance(
            row["owner_approval_reference"], str
        ):
            fail("OWNER_REFERENCE_CONTRACT")
        resolution = row["conflict_resolution"]
        if resolution is not None and (
            not isinstance(resolution, dict)
            or set(resolution) != {"identity", "reviewed_at", "verdict", "rationale"}
        ):
            fail("CONFLICT_RESOLUTION_CONTRACT")
    return review["rows"]


def _complete_inspection(check, captured_at, as_of):
    if any(
        not isinstance(check.get(k), str) or not check[k].strip()
        for k in ("identity", "reviewed_at", "rationale")
    ):
        return False
    if check["identity"].startswith("SIMULATED_") or check["verdict"] not in RESULTS:
        return False
    try:
        stamp = datetime.fromisoformat(check["reviewed_at"].replace("Z", "+00:00"))
        return (
            stamp.utcoffset() is not None and datetime.fromisoformat(captured_at) <= stamp <= as_of
        )
    except (ValueError, TypeError):
        return False


def import_review(
    packet,
    review,
    *,
    expected_packet,
    repository,
    approval_file=None,
    signature_file=None,
    trust=None,
    as_of=None,
):
    """Never signs, appends, mutates a packet, or accepts an in-document trust key."""
    validate_packet(packet, expected_packet=expected_packet)
    rows = validate_review(packet, review)
    approved, authority = legacy.verified_owner_rows(
        packet,
        review,
        repository=repository,
        approval_file=approval_file,
        signature_file=signature_file,
        trust=trust,
    )
    now = as_of or datetime.now(timezone.utc)
    if now.utcoffset() is None:
        fail("TRUSTED_NOW_TIMEZONE_REQUIRED")
    bindings = {u["unit_ref"]: u for u in packet["units"]}
    eligible = []
    serious = 0
    disagreements = 0
    for row in rows:
        u = bindings[row["unit_ref"]]
        checks = row["inspections"]
        if checks[0]["verdict"] != checks[1]["verdict"]:
            disagreements += 1
        if (
            row["unit_ref"] not in approved
            or review["origin"] != "EXTERNAL_HUMAN"
            or row["status"] != "REVIEWED"
            or not row["owner_approval_reference"]
            or row["owner_approval_reference"].startswith("SIMULATED_")
            or not all(_complete_inspection(c, u["captured_at"], now) for c in checks)
            or checks[0]["identity"] == checks[1]["identity"]
            or any(c["serious_false_fact"] is None for c in checks)
        ):
            continue
        if any(not c["evidence_refs"] and not c["no_evidence_reason"] for c in checks):
            continue
        verdict = checks[0]["verdict"]
        if verdict != checks[1]["verdict"]:
            r = row["conflict_resolution"]
            if (
                r is None
                or not _complete_inspection(r, u["captured_at"], now)
                or r["identity"] in {c["identity"] for c in checks}
            ):
                continue
            verdict = r["verdict"]
        # A label cannot turn absent source evidence into a binary-supported result.
        if verdict in ("PASS", "FAIL_WITH_EVIDENCE") and not u["sources"]:
            continue
        eligible.append(
            {
                **u,
                "expected_candidate": verdict,
                "human_serious_false_fact": any(c["serious_false_fact"] for c in checks),
            }
        )
        serious += any(c["serious_false_fact"] for c in checks)
    scores = selective_metrics(eligible)
    metrics = {
        k: scores[k] if scores["binary_units"] else None
        for k in ("TP", "FP", "FN", "TN", "precision", "recall")
    }
    return dict(
        status="S2_QUALITY_OWNER_DECISION_REQUIRED" if eligible else "S2_QUALITY_NOT_EVALUABLE",
        packet_ref=packet["packet_ref"],
        review_set_sha256=canonical(review),
        authority_state=authority,
        denominator=len(eligible),
        binary_denominator=scores["binary_units"],
        strata=[
            {
                **g,
                "metrics": {
                    **g["metrics"],
                    "metric_authority": "OWNER_ATTESTED_INDEPENDENT_HUMAN_ON_SYNTHETIC_SOURCE",
                    "serious_false_facts": sum(
                        u["human_serious_false_fact"]
                        for u in eligible
                        if all(u[k] == v for k, v in g["dimensions"].items())
                    ),
                    "serious_false_facts_status": "OWNER_ATTESTED_ROWS_ONLY",
                },
            }
            for g in strata(eligible)
        ],
        unknown=scores["unknown"] if eligible else None,
        blocked=scores["blocked"] if eligible else None,
        not_applicable=scores["not_applicable"] if eligible else None,
        pending=len(packet["units"]) - len(eligible),
        metrics=metrics,
        serious_false_facts=serious if eligible else None,
        abstention=scores["abstention"] if eligible else None,
        input_disagreements=disagreements,
        independent_inspection_slots=2,
        no_automatic_quality_pass=True,
        access_granted=False,
        formal_review=False,
        original_26_modified=False,
    )


def deduplicate(packet, reviews):
    """Content-only batch diagnostic; conflicts are excluded, no last-writer wins."""
    unique = {}
    conflicts = set()
    duplicates = 0
    for review in reviews:
        for row in validate_review(packet, review):
            ref = row["unit_ref"]
            if ref in unique:
                if canonical(row) == canonical(unique[ref]):
                    duplicates += 1
                else:
                    conflicts.add(ref)
            else:
                unique[ref] = row
    return dict(
        rows=[r for k, r in sorted(unique.items()) if k not in conflicts],
        duplicate_rows=duplicates,
        conflicting_units=sorted(conflicts),
        authority="UNVERIFIED_CONTENT_ONLY_NOT_GOLD",
    )


def export_packet(report, folder):
    packet = packet_for(report)
    files = {
        "s2-packet.json": packet,
        "s2-review-input.json": blank_review(packet),
        "benchmark.json": report,
    }
    content = {
        name: json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        for name, value in files.items()
    }
    checks = [
        "Inspect original bytes/hash/URL/locator and capture time; scope is not the whole site.",
        "Two real independent reviewers must supply identity, time, bounded verdict, rationale and serious-fact flag.",
        "A third independent person adjudicates disagreement; Owner signs exact rows out of band.",
        "Candidate expectations, names, dates and edited hashes confer no Gold or access authority.",
    ]
    lines = [
        "# S2-C3 PRIVATE unsigned reviewer packet",
        "",
        *checks,
        "",
        "| Unit | Rule / site | Source / time | Candidate (not authority) | Reviewers |",
        "| --- | --- | --- | --- | --- |",
    ]
    for u in packet["units"]:
        lines.append(
            f"| {u['unit_ref']} | {u['rule_id']} / {u['site_type']} | {u['source_url']} / {u['captured_at']} | {u['expected_candidate']} | UNREVIEWED / UNREVIEWED |"
        )
    for u in packet["units"]:
        lines += [
            "",
            "## " + u["rule_id"] + " / " + u["site_id"],
            "Native result: " + u["observed"] + ". " + u["statement"],
            "Candidate rationale (NOT human authority): " + u["candidate_rationale"],
            "Native observation present: " + str(u["native_observation_present"]),
            "Scope: " + json.dumps(u["applicable_scope"], sort_keys=True),
            "Original pack: " + u["pack_ref"],
            "Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.",
        ]
    content["reviewer.md"] = "\n".join(lines) + "\n"
    folder = Path(folder)
    for name, text in content.items():
        if (folder / name).exists() and (folder / name).read_text("utf-8") != text:
            fail("EXPORT_WOULD_OVERWRITE_REVIEW")
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in content.items():
        (folder / name).write_text(text, encoding="utf-8")
    return packet


def read_json(path):
    raw = Path(path).read_bytes()
    if len(raw) > 16_000_000:
        fail("INPUT_SIZE_BOUND")

    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                fail("DUPLICATE_JSON_KEY")
            value[key] = item
        return value

    def constant(value):
        fail("NONFINITE_JSON")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)

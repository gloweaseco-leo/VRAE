"""S2-C3 independent offline QA over accepted native producers (not an evaluator)."""

import asyncio
import base64
from copy import deepcopy
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import hashlib

from vrae.collection.collector import Collector
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Limits
from vrae.collection.policy import SourceAccess
from vrae.collection.manifest import document_hash
from vrae.evidence import build_pack
from vrae.findings import build_findings
from vrae.industry.l2_v1 import diagnose, load, verify
from vrae.rules import execute, verify_execution
from tests.collection.test_pipeline import FixedDNS
from .scenarios import StrictSyntheticTransport
from tests.collection.test_security import fixture
from . import human_gold as legacy
from .quality import (
    EVALUATOR,
    ENABLED,
    controlled_sample_ref,
    assess_sample,
    replay_sample,
    score_candidate,
)
from .scenarios import capture
from .s2_sites import VERSION, BASELINE, DIRECTORY, sites, industrial_cases

RESULTS = ("PASS", "FAIL_WITH_EVIDENCE", "UNKNOWN", "ACCESS_BLOCKED", "NOT_APPLICABLE")
BINARY = ("PASS", "FAIL_WITH_EVIDENCE")
NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)


class QualityError(ValueError):
    """No source content or identity data in integrity errors."""


def fail(reason):
    raise QualityError(reason)


def canonical(value):
    return document_hash(value)


def source_ref(pack, ref):
    resolved = pack.resolve(ref, expected_pack_ref=pack.ref)
    raw = resolved["content"]
    return dict(
        evidence_ref=ref,
        pack_ref=pack.ref,
        tenant_id=pack.document["tenant_id"],
        run_id=pack.document["run_id"],
        content_sha256=hashlib.sha256(raw).hexdigest(),
    )


def archive(pack, producer):
    return dict(
        pack_document=pack.document,
        objects_base64={k: base64.b64encode(v).decode("ascii") for k, v in pack.objects.items()},
        producer=producer,
    )


def coverage(plan, bundle):
    """Denominator fixed by authored plan, never reconstructed from successful pages."""
    observed = {p["snapshot"]["url"]: p for p in bundle.manifest["pages"]}
    rows = []
    for original in plan:
        row = deepcopy(original)
        p = observed.get(row["url"])
        if row["selection"] != "SELECTED":
            state = "UNSELECTED"
        elif not row["applicable"]:
            state = "NOT_APPLICABLE"
        elif p is None:
            state = "UNOBSERVED"
        elif p["http_status"] in (401, 403, 429):
            state = "ACCESS_BLOCKED"
        elif p["raw_retained"] and p["http_status"] == 200:
            state = "CAPTURED_BODY"
        else:
            state = "METADATA_ONLY"
        row.update(
            native_page_role=p["role"] if p else None,
            capture_state=state,
            http_status=p["http_status"] if p else None,
            body_sha256=p["snapshot"]["sha256"] if p else None,
        )
        rows.append(row)
    selected = [r for r in rows if r["selection"] == "SELECTED" and r["applicable"]]
    return dict(
        selected_roles=rows,
        denominator=len(selected),
        captured_response_numerator=sum(r["http_status"] is not None for r in selected),
        body_evidence_numerator=sum(r["capture_state"] == "CAPTURED_BODY" for r in selected),
        unknown=sum(r["capture_state"] in ("UNOBSERVED", "METADATA_ONLY") for r in selected),
        blocked=sum(r["capture_state"] == "ACCESS_BLOCKED" for r in selected),
        whole_site_coverage_claim=False,
    )


def unit(
    pack,
    *,
    site,
    kind,
    rule,
    version,
    expected,
    observed,
    scope,
    source_url,
    captured_at,
    references,
    producer_ref,
    statement,
    rationale,
    locator,
    task,
    industry,
    observed_in_native=True,
):
    if observed not in RESULTS or expected not in RESULTS:
        fail("OUTCOME_CONTRACT")
    if datetime.fromisoformat(captured_at).utcoffset() is None:
        fail("CAPTURE_TIME_ZONE_REQUIRED")
    if observed in BINARY and not references:
        fail("BINARY_WITHOUT_SOURCE")
    body = dict(
        rule_id=rule,
        rule_version=version,
        site_id=site,
        site_type=kind,
        source_origin="SYNTHETIC_OFFLINE",
        source_url=source_url,
        captured_at=captured_at,
        applicable_scope=scope,
        tenant_id=pack.document["tenant_id"],
        run_id=pack.document["run_id"],
        pack_ref=pack.ref,
        producer_ref=producer_ref,
        producer_locator=locator,
        expected_candidate=expected,
        observed=observed,
        statement=statement,
        candidate_rationale=rationale,
        sources=references,
        buyer_task=task,
        industry=industry,
        model_mode="NO_MODEL",
        human_gold=False,
        limited_to_captured_scope=True,
        native_observation_present=observed_in_native,
        capture_time_semantics="RECORDED_SYNTHETIC_RUN_WINDOW_NOT_PROOF_ALL_PLANNED_URLS_VISITED",
    )
    body["unit_ref"] = "s2-unit-" + canonical(
        {
            k: body[k]
            for k in (
                "rule_id",
                "rule_version",
                "site_id",
                "source_url",
                "captured_at",
                "applicable_scope",
                "tenant_id",
                "run_id",
                "pack_ref",
            )
        }
    )
    return body


def generic_site(case):
    bundle = capture(case)
    pack = build_pack([bundle])
    execution = execute(pack, expected_pack_ref=pack.ref, evaluator_version=EVALUATOR)
    verify_execution(
        execution, pack, expected_pack_ref=pack.ref, expected_evaluator_version=EVALUATOR
    )
    package = build_findings(
        pack,
        execution,
        expected_pack_ref=pack.ref,
        expected_execution_ref=execution["execution_ref"],
        expected_evaluator_version=EVALUATOR,
    )
    sample = dict(
        fixture={k: v for k, v in case.items() if k != "labels"},
        pins=dict(
            expected_pack_ref=pack.ref,
            expected_execution_ref=execution["execution_ref"],
            expected_evaluator_version=EVALUATOR,
            expected_package_ref=package.ref,
        ),
        evidence_document=pack.document,
        objects_base64={k: base64.b64encode(v).decode("ascii") for k, v in pack.objects.items()},
        finding_package=package.document,
        candidate_labels=deepcopy(case["labels"]),
    )
    sample["controlled_sample_sha256"] = controlled_sample_ref(sample)
    for label in sample["candidate_labels"]:
        label["controlled_sample_sha256"] = sample["controlled_sample_sha256"]
    replay_sample(sample)
    report = assess_sample(sample, execution)
    rows = []
    for todo in report["review_todos"]:
        identity = todo["unit"]
        refs = []
        for c in todo.get("citations", []):
            for key in ("evidence_ref", "target_evidence_ref"):
                if c.get(key):
                    refs.append({**source_ref(pack, c[key]), "native_citation": deepcopy(c)})
        rows.append(
            unit(
                pack,
                site=case["site_id"],
                kind=case["site_type"],
                rule=identity["rule_id"],
                version=identity["rule_version"],
                expected=todo["candidate_expected"],
                observed=todo["observed_result"] or "UNKNOWN",
                scope=dict(
                    source_url=identity["source_url"],
                    target_url=identity["target_url"],
                    anchor_index=identity["anchor_index"],
                    source_observed_at=(todo.get("source_page") or {}).get("observed_at"),
                ),
                source_url=identity["source_url"],
                captured_at=identity["source_observed_at"]
                or bundle.manifest["pages"][0]["evidence"]["observed_at"],
                references=refs,
                producer_ref=execution["execution_ref"],
                statement=next(
                    (
                        r["observation"]["statement"]
                        for e in execution["executions"]
                        for r in e["observations"]
                        if r["observation"]["observation_id"] == todo.get("observation_id")
                    ),
                    "No native observation exists for this planned scope; it remains an uncovered unit.",
                ),
                rationale=todo.get("candidate_rationale")
                or next(
                    label["rationale"]
                    for label in case["labels"]
                    if all(label[k] == v for k, v in identity.items())
                ),
                locator=todo.get("execution_locator"),
                task="INQUIRE" if identity["rule_id"].startswith("CTA") else "DISCOVER",
                industry="GENERAL",
                observed_in_native=todo.get("observation_id") is not None,
            )
        )
    if len(rows) != len(case["labels"]):
        fail("AUTHORED_UNIT_DENOMINATOR_MISMATCH")
    return (
        rows,
        coverage(case["selected_roles"], bundle),
        archive(pack, dict(execution=execution, package=package.document)),
    )


def industrial_capture(case):
    request, policy = fixture("AuditRequest"), fixture("SourcePolicy")
    request.update(
        audit_mode="L1", request_id="req-" + case["site_id"], audit_id="audit-" + case["site_id"]
    )
    access = SourceAccess(
        request, lambda: policy, terms_reference="synthetic-s2-quality-only", now=lambda: NOW
    )
    mapping = json.loads((DIRECTORY / "routes.json").read_text("utf-8"))
    bodies = {path: (DIRECTORY / name).read_bytes() for path, name in mapping.items()}
    bodies.update(case["overrides"])
    transport = StrictSyntheticTransport(
        {
            "https://example.org" + path: (
                200,
                {"content-type": "text/plain" if path == "/robots.txt" else "text/html"},
                raw,
            )
            for path, raw in bodies.items()
        }
    )
    bundle = asyncio.run(
        Collector(SafeFetcher(FixedDNS(), transport)).capture(
            "run-" + case["site_id"],
            access,
            limits=Limits(max_pages=8, interval_seconds=0.01),
            retain_raw_html=True,
        )
    )
    if any(call[1] != "GET" for call in transport.calls):
        fail("READ_ONLY_REQUIRED")
    return build_pack([bundle]), bundle


def industry_site(case):
    pack, bundle = industrial_capture(case)
    result = diagnose(
        pack, expected_pack_ref=pack.ref, expected_industry_ref=load()["industry_ref"]
    )
    verify(
        result,
        pack,
        expected_result_ref=result["diagnosis_ref"],
        expected_pack_ref=pack.ref,
        expected_industry_ref=load()["industry_ref"],
    )
    selected = [
        (i, a)
        for i, a in enumerate(result["assessments"])
        if a["observation"]["rule_id"] == case["rule"]
        and a["model"] == case["model"]
        and (case["attribute"] is None or a["details"].get("attribute") == case["attribute"])
    ]
    if len(selected) != (2 if case["site_id"] == "s2_model_collision" else 1):
        fail("AUTHORED_INDUSTRIAL_SCOPE_MISMATCH")
    facts = {f["fact_ref"]: f for f in result["source_facts"]}
    rows = []
    for i, a in selected:
        refs = []
        for ref in a["source_fact_refs"]:
            f = facts[ref]
            src = f["source"]
            c = src["citation"]
            raw = pack.resolve(c["evidence_ref"], expected_pack_ref=pack.ref)["content"]
            if raw[src["byte_start"] : src["byte_end"]] != src["quote"].encode("utf-8"):
                fail("RAW_SOURCE_LOCATOR_MISMATCH")
            refs.append(
                {
                    **source_ref(pack, c["evidence_ref"]),
                    "native_fact_ref": ref,
                    "native_source": deepcopy(src),
                }
            )
        o = a["observation"]
        rows.append(
            unit(
                pack,
                site=case["site_id"],
                kind=case["site_type"],
                rule=o["rule_id"],
                version=o["rule_version"],
                expected=case["expected"],
                observed=o["result"],
                scope=dict(
                    model=a["model"],
                    attribute=case["attribute"],
                    assessment_index=i,
                    source_observed_at=facts[a["source_fact_refs"][0]]["source"]["citation"][
                        "observed_at"
                    ]
                    if refs
                    else None,
                ),
                source_url=facts[a["source_fact_refs"][0]]["source"]["citation"]["url"]
                if refs
                else None,
                captured_at=bundle.manifest["pages"][0]["evidence"]["observed_at"],
                references=refs,
                producer_ref=result["diagnosis_ref"],
                statement=o["statement"],
                rationale=case["rationale"],
                locator="/assessments/" + str(i),
                task=a["finding"]["buyer_task"],
                industry="INDUSTRIAL_P40_V25",
            )
        )
    plan = [
        dict(role=role, url="https://example.org" + path, selection="SELECTED", applicable=True)
        for role, path in (
            ("HOME", "/"),
            ("CATALOG", "/products"),
            ("PUMP", "/products/pump-p40"),
            ("VALVE", "/products/valve-v25"),
            ("APPLICATION", "/products/duty-selection"),
            ("PROOF", "/products/supplier-proof"),
            ("RFQ_GUIDE", "/products/rfq-guide"),
            ("CONTACT", "/contact"),
        )
    ]
    # Fixed independent eight-page fixture budget/roles, not a production default.
    if len(plan) != 8:
        fail("INDUSTRIAL_EIGHT_ROLE_PLAN_MISMATCH")
    return (
        rows,
        coverage(plan, bundle),
        archive(
            pack,
            dict(
                projection="NATIVE_DIAGNOSIS_PIN_AND_ASSESSMENTS_REQUIRES_FULL_NATIVE_REPLAY",
                diagnosis_ref=result["diagnosis_ref"],
                industry_ref=result["industry_ref"],
                native_execution_ref=result["native_execution_ref"],
                native_package_ref=result["native_package_ref"],
                source_guard_refs=result["source_guard_refs"],
                assessments=result["assessments"],
                source_fact_count=len(result["source_facts"]),
            ),
        ),
    )


def selective_metrics(rows):
    counts = Counter(
        {
            k: 0
            for k in (
                "TP",
                "FP",
                "FN",
                "TN",
                "unresolved_expected_defects",
                "unsupported_defect",
                "unjustified_pass",
                "mismatch",
            )
        }
    )
    for row in rows:
        counts.update(score_candidate(row["expected_candidate"], row["observed"]))
    outcomes = Counter(row["observed"] for row in rows)
    binary = sum(counts[k] for k in ("TP", "FP", "FN", "TN"))
    total = len(rows)
    return dict(
        counts,
        units=total,
        binary_units=binary,
        precision=counts["TP"] / (counts["TP"] + counts["FP"])
        if counts["TP"] + counts["FP"]
        else None,
        recall=counts["TP"] / (counts["TP"] + counts["FN"])
        if counts["TP"] + counts["FN"]
        else None,
        abstention=total - binary,
        abstention_rate=(total - binary) / total if total else None,
        unknown=outcomes["UNKNOWN"],
        blocked=outcomes["ACCESS_BLOCKED"],
        not_applicable=outcomes["NOT_APPLICABLE"],
        applicability_denominator=total,
        applicable_units=total - outcomes["NOT_APPLICABLE"],
        evidence_units=sum(bool(row["sources"]) for row in rows),
        evidence_denominator=total,
        native_observed_units=sum(row.get("native_observation_present", True) for row in rows),
        unobserved_units=sum(not row.get("native_observation_present", True) for row in rows),
        serious_false_facts=None,
        serious_false_facts_status="HUMAN_GOLD_NOT_EVALUABLE",
        synthetic_unsupported_assertions=counts["unsupported_defect"] + counts["unjustified_pass"],
        metric_authority="SYNTHETIC_CANDIDATE_COMPARISON_NOT_HUMAN_GOLD",
    )


def strata(rows):
    fields = (
        "site_type",
        "industry",
        "buyer_task",
        "rule_id",
        "rule_version",
        "source_origin",
        "model_mode",
    )
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in fields)].append(row)
    return [
        dict(dimensions=dict(zip(fields, key)), metrics=selective_metrics(value))
        for key, value in sorted(groups.items())
    ]


def build_benchmark(root):
    original = legacy.load_packet(root)
    rows = []
    scopes = {}
    artifacts = {}
    for case in sites() + industrial_cases():
        new, scope, artifact = generic_site(case) if "routes" in case else industry_site(case)
        rows.extend(new)
        scopes[case["site_id"]] = scope
        artifacts[case["site_id"]] = artifact
    if len({row["unit_ref"] for row in rows}) != len(rows):
        fail("DUPLICATE_UNIT")
    result = dict(
        version=VERSION,
        accepted_baseline=BASELINE,
        scope="C3_P0_OFFLINE_QA_NOT_S2_E2E",
        source_origin="SYNTHETIC_OFFLINE",
        s2_evaluator_support="PENDING_ACCEPTED_C1_C2_INTERFACE",
        generic_rules_exercised=list(ENABLED),
        industrial_rules_separate=True,
        original_26=dict(
            packet_ref=original["packet_ref"], rows=26, verified_human_rows=0, pending=26
        ),
        units=rows,
        scope_manifests=scopes,
        artifacts=artifacts,
        synthetic_consistency=selective_metrics(rows),
        strata=strata(rows),
        human_quality=dict(
            status="S2_QUALITY_NOT_EVALUABLE",
            denominator=0,
            TP=None,
            FP=None,
            FN=None,
            TN=None,
            precision=None,
            recall=None,
            serious_false_facts=None,
        ),
        s2_exit=False,
        model_calls=0,
        network_calls=0,
        formal_review=False,
        external_delivery=False,
    )
    result["report_ref"] = "s2-bench-" + canonical(result)
    return result


def verify_report(report, root):
    fresh = build_benchmark(root)
    if canonical(report) != canonical(fresh):
        fail("BENCHMARK_INDEPENDENT_REPLAY_MISMATCH")
    return fresh

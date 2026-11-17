"""Prepare source-bound offline scenarios, never runtime or Gold acceptance."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from tests.benchmark.s2_sites import DIRECTORY, industrial_cases, sites
from tests.benchmark.s2_review import read_json

VERSION = "c3-s2-preparation-1.0.0"
IDENTITY_FIELDS = (
    "tenant_id", "request_id", "run_id", "job_id", "pack_ref",
    "diagnosis_sha", "report_id", "report_version", "report_hash",
    "review_receipt_hash", "brief_ref",
)


class PlanError(ValueError):
    """Fixed preparation errors do not disclose source content."""


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def build_plan():
    catalog = []
    for case in sites():
        catalog.append({
            "site_id": case["site_id"], "site_type": case["site_type"],
            "source_mode": "SYNTHETIC_OFFLINE",
            "scope_before_capture": deepcopy(case["selected_roles"]),
            "fixture_routes": [
                {"url": item["url"], "status": item["status"],
                 "body_sha256": digest(item["body"].encode("utf-8"))}
                for item in case["routes"]
            ],
            "authored_expectations_not_gold": [
                {k: deepcopy(row[k]) for k in (
                    "rule_id", "source_url", "target_url", "expected", "scope", "rationale"
                )}
                for row in case["labels"]
            ],
        })
    industrial = []
    for case in industrial_cases():
        item = {k: v for k, v in case.items() if k != "overrides"}
        item["fixture_override_sha256"] = {
            url: digest(raw) for url, raw in case["overrides"].items()
        }
        industrial.append(item)
    bindings = {
        p.relative_to(DIRECTORY).as_posix(): digest(p.read_bytes())
        for p in sorted(DIRECTORY.rglob("*")) if p.is_file()
    }
    attacks = [
        ("foreign_tenant", "Reject through original signed tenant authority."),
        ("foreign_run_or_pack", "Reject mixed run/pack through original replayers."),
        ("foreign_source_or_capture_time", "Reject source/time outside held pins."),
        ("stale_report_or_review_version", "Reject stale original report/review bindings."),
        ("rights_revoked_before_brief_commit", "Recheck BOTH authorities at real COMMIT."),
        ("authority_expired_before_brief_commit", "Use minimum original expiry; lease is not approval."),
        ("scope_dropped_after_capture", "Retain planned unobserved scope; never inflate coverage."),
        ("blocked_source_called_defect", "Keep ACCESS_BLOCKED distinct from site defect."),
        ("unknown_promoted_to_tn", "UNKNOWN contributes abstention, not human TN."),
        ("forged_human_review", "Reject through unchanged OwnerTrust/verified_owner_rows."),
        ("forged_engineering_or_certificate", "No fit/authenticity claim beyond original evidence."),
        ("unapproved_network_or_write", "Deny real collection, RFQ submission, sharing and models."),
    ]
    document = {
        "version": VERSION,
        "status": "PREPARATION_ONLY_RUNTIME_NOT_RUN",
        "authority": "NONE_NOT_EVIDENCEPACK_OR_REVIEW",
        "dependency_gate": {"pr124_owner_merge_required": True, "merge_permission": False},
        "future_lanes": [
            {"lane": lane, "fixture_site": site,
             "actual_runtime_identity": {k: None for k in IDENTITY_FIELDS}}
            for lane, site in (("A", "s2_static"), ("B", "s2_cms"))
        ],
        "future_runtime_requirements": {
            "lanes_must_have_distinct_real_run_and_pack": True,
            "single_original_app_worker_ssr_pg": True,
            "original_worker_lease_seconds": 30,
            "generic_rule_target": 16, "industrial_rule_target": 6,
            "new_ten_rules_implemented": False,
            "viewports": [1280, 390, 375, 320],
            "required_chain": [
                "APP202", "original Worker COMMIT", "same-run EvidencePack replay",
                "accepted C1 Port", "accepted C2 original workbench",
                "version-bound Controlled review", "Brief PG COMMIT",
                "PG restart and original report/hash/review/Brief readback",
            ],
            "actual_runtime_checks": "NOT_EXECUTED",
        },
        "catalog": catalog, "industrial_cases": industrial,
        "industrial_fixture_bytes_sha256": bindings,
        "adversarial_requirements": [{"id": k, "required_outcome": v, "observed": None}
                                     for k, v in attacks],
        "gold": {"legacy_verified": 0, "legacy_pending": 26, "new_verified": 0,
                 "quality_status": "S2_QUALITY_NOT_EVALUABLE"},
        "business": {k: "UNKNOWN" for k in (
            "real_consultation", "rate", "human_hours", "customer_approval", "E2", "E3"
        )},
        "resource_policy": {
            "cleanup": "EXACT_THIS_RUN_OWNERSHIP_ONLY",
            "historical_anonymous_volumes": "UNKNOWN_UNTOUCHED", "global_prune": False,
        },
        "collection_calls": 0, "model_calls": 0, "runtime_acceptance": False,
    }
    document["plan_ref"] = "c3-offline-plan-" + digest(canonical(document).encode("ascii"))
    return document


def verify_plan(value):
    # Only an integrity check against current authored fixtures, never a runtime verifier.
    if canonical(value) != canonical(build_plan()):
        raise PlanError("PREPARATION_PLAN_CHANGED")
    return {"status": "PLAN_INTEGRITY_ONLY_RUNTIME_NOT_RUN", "runtime_acceptance": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    output = verify_plan(read_json(args.verify)) if args.verify else build_plan()
    print(json.dumps(output, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

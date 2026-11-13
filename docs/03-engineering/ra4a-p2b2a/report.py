"""Aggregate actual native local JUnit and teardown without inferring CI success."""

import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def suite(path, *, legacy=False, allow_failures=False):
    raw = path.read_bytes()
    tree = ET.fromstring(raw)
    cases = tree.findall(".//testcase")
    counts = {"tests": len(cases), "failures": len(tree.findall(".//failure")),
              "errors": len(tree.findall(".//error")), "skipped": len(tree.findall(".//skipped"))}
    assert counts["tests"] > 0, str(path)
    if not allow_failures:
        assert counts["failures"] == counts["errors"] == 0, str(path)
    if legacy:
        for case in cases:
            if case.find("skipped") is not None:
                assert case.get("classname", "").startswith(
                    ("tests.browser.test_isolated_browser", "tests.collection.test_isolated")
                ), "UNEXPECTED_LEGACY_SKIP"
    else:
        assert counts["skipped"] == 0, "NEW_OR_PG_SKIP_DENIED"
    return {"path": path.relative_to(ROOT).as_posix(), **counts,
            "sha256": hashlib.sha256(raw).hexdigest()}


def corrected_legacy(path, correction):
    first = suite(path, legacy=True, allow_failures=True)
    rerun = suite(correction)
    original_cases = ET.parse(path).findall(".//testcase")
    corrected_cases = ET.parse(correction).findall(".//testcase")
    def key(case):
        return case.get("classname", "") + "::" + case.get("name", "")
    failures = {key(case) for case in original_cases
                if case.find("failure") is not None or case.find("error") is not None}
    allowed = {"tests.test_domain::test_no_network_or_unauthorized_framework_code",
               "tests.operator_console.test_proposal_http::test_real_preview_http_and_fresh_unsubmitted_get[200]"}
    assert failures <= allowed, "UNEXPECTED_LEGACY_FAILURE"
    assert failures <= {key(case) for case in corrected_cases}, "UNRESOLVED_LEGACY_FAILURE"
    return {"first_full_run": first, "corrective_utf8_rerun": rerun,
            "original_failed_ids": sorted(failures), "all_failed_ids_passed_on_rerun": True,
            "test_or_application_source_changes": False}


def main():
    rows = []
    db_evidence = []
    rehearsal = []
    for version in ("311", "313"):
        run = HERE / ("local" + version + "-pg-v3")
        execution = json.loads((run / "execution.json").read_text())
        assert all(c["exit"] == 0 for c in execution["commands"]), "FAILED_LOCAL_STAGE"
        assert execution["commands"][-1]["stage"] == "stop", "MISSING_TEARDOWN"
        assert execution["dependencies"]["cryptography"] == "50.0.2"
        for stage in ("crypto", "pg1", "pg2", "p2a", "p2b1", "identity-pg"):
            rows.append({"python": version, "stage": stage,
                         **suite(run / stage / "tests.xml")})
        assert rows[-2]["tests"] == 131, "P2B1_COUNT_CHANGED"
        cas = json.loads((run / "p2b1/p2b1-catalog-and-calls.json").read_text())
        assert len(cas["calls"]) == 131 and all(c["outcome"] == "passed" for c in cas["calls"])
        catalog_path = run / "identity-pg/p2b1-catalog-and-calls.json"
        catalog = json.loads(catalog_path.read_text())
        assert catalog["session_exit"] == 0 and catalog["server"].startswith("PostgreSQL 16.")
        db_evidence.append({"python": version, "server": catalog["server"],
                            "schema_sha256": catalog["schema_sha256"],
                            "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
                            "identity_tests": rows[-1]["tests"],
                            "counter_note": "Identity count is native JUnit; reused fixture hook counts only /p2b1/ paths"})
        teardown = json.loads((run / "stop/teardown.json").read_text())
        assert all(teardown[k] is True for k in
                   ("owned_container_removed", "owned_network_removed", "owned_volume_removed"))
        expected_sources = {p["path"]: p["lf_sha256"] for p in execution["source"]}
        for folder in ("vrae/identity", "tests/identity", "integration/ra4a/p2b2a"):
            for p in (ROOT / folder).rglob("*.py"):
                assert hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == expected_sources[p.relative_to(ROOT).as_posix()], "TESTED_SOURCE_DRIFT"
        profile = HERE / ("local-ci-3.11" if version == "311" else "local-ci-3.13")
        profile_execution = json.loads((profile / "execution.json").read_text())
        assert all(c["exit"] == 0 for c in profile_execution["commands"])
        assert profile_execution["commands"][-1]["stage"] == "stop"
        privacy = json.loads((profile / "credential-scan.json").read_text())
        assert privacy["publication_allowed"] is True and privacy["actual_lab_secret_count"] > 0
        rehearsal.append({"python": version, "mode": "Exact hosted identity-only entry",
                          "crypto": suite(profile / "crypto/tests.xml"),
                          "identity_pg": suite(profile / "identity-pg/tests.xml"),
                          "privacy": privacy})
    legacy = {"311": corrected_legacy(HERE / "legacy311/tests.xml", HERE / "corrective311.xml"),
              "313": corrected_legacy(HERE / "legacy313.xml", HERE / "corrective313.xml")}
    red = ET.parse(HERE / "final-red-tests.xml")
    assert len(red.findall(".//failure")) == 3 and len(red.findall(".//error")) == 0
    result = {"state": "LOCAL_ENGINEERING_CANDIDATE_WITH_CORRECTIVE_RERUNS_HOSTED_CI_PENDING",
              "base": "a17d02f16a16acd7214815fce02747509c31f7bd",
              "head_at_report": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
              "native_junit": rows, "red_control": {"deliberately_disabled_verifier": True,
                                                       "expected_failures": 3},
              "identity_db_evidence": db_evidence, "hosted_profile_rehearsal": rehearsal,
              "legacy_full_runs_and_corrections": legacy,
              "legacy_selection": "Accepted default tests selection, including RA3C QA V2; historical V1 reporting test remains excluded by unchanged pyproject addopts",
              "both_owned_pg_clusters_removed": True,
              "real_idp": False, "native_approval": False, "share_grant": False,
              "hosted_ci_claimed": False}
    (HERE / "LOCAL_RESULTS.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

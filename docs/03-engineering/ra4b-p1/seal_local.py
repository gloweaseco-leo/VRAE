"""Fail-closed final native local evidence seal; never changes a test outcome."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ACCEPTED = "4fd1ce15f4bc2e596111aa2e8fe86a2a46ba640d"
PREFIXES = ("apps/api/", "vrae/application/ra4b/", "worker/ra4b/", "integration/ra4b/",
            "tests/application/ra4b/", "docs/03-engineering/ra4b-p1/")
EXACT = {"db/migrations/0004_ra4b_test_only_api.sql", "requirements-ra4b-p1.lock", ".github/workflows/ra4b-p1.yml"}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode().strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(relative):
    return json.loads((HERE / relative).read_bytes())


def junit(relative, count=None, skips=0):
    root = ET.parse(HERE / relative).getroot()
    cases = list(root.iter("testcase"))
    value = {"path": relative, "sha256": sha(HERE / relative), "cases": len(cases),
             "failed": len(list(root.iter("failure"))), "errors": len(list(root.iter("error"))),
             "skipped": len(list(root.iter("skipped")))}
    assert not value["failed"] and not value["errors"] and value["skipped"] == skips, value
    if count is not None:
        assert value["cases"] == count, value
    return value


def main():
    assert git("merge-base", "--is-ancestor", ACCEPTED, "HEAD") == ""
    changed = set(git("diff", "--name-only", ACCEPTED).splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    forbidden = sorted(n for n in changed if n not in EXACT and not n.startswith(PREFIXES))
    assert not forbidden, forbidden
    suites, sources, cleanups = [], {}, []
    for minor in ("311", "313"):
        pg = "accepted-main-pg" + minor
        assert read(pg + "/result.json")["status"] == "PG_AND_FROZEN_PRELUDE_PASS_NOT_FINAL_RUNTIME_PASS"
        for stage, count in (("pg1", 54), ("pg2-before-0004", 54), ("p2a", 86), ("pg2-after-0004", 54),
                             ("p2b1", 131), ("identity-pg", 30), ("crypto", 73)):
            suites.append(junit(pg + "/" + stage + "/tests.xml", count))
        suites.append(junit(pg + "/b4-tests.xml", 46))
        catalog = read(pg + "/pg2-after-0004/pg-catalog-and-calls.json")
        assert len(catalog["roles"]) == 8 and len(catalog["policies"]) == 10
        assert len([r for r in catalog["tables"] if r[0] == "ra4a"]) == 8
        assert len(catalog["tables"]) == 11  # Eight public-schema + three private tables.
        assert read(pg + "/credential-scan.json")["matches"] == 0
        assert all(r["exit"] == 0 for r in read(pg + "/stages.json"))
        assert all(read(pg + "/teardown/teardown.json")[k] for k in
                   ("owned_container_removed", "owned_network_removed", "owned_volume_removed"))
        unit = "accepted-main-unit" + minor
        classified = read(unit + "/result.json")
        assert classified["status"] == "ORDINARY_PASS_SEPARATE_ISOLATED_GATES_REQUIRED"
        assert classified["frozen_qa_v2"] == 118 and classified["frozen_ra3d"] == 127
        suites.append(junit(unit + "/tests.xml", skips=25))
        assert read(unit + "/source-integrity.json")["before"] and read(unit + "/source-integrity.json")["after"]
        assert read(unit + "/teardown.json")["owned_volume_removed"]
        c3 = "accepted-main-c3" + minor + "-v2"
        assert read(c3 + "/result.json")["status"] == "PASS"
        suites.append(junit(c3 + "/tests.xml", 29))
        assert all(r["absent_after"] for r in read(c3 + "/teardown/teardown.json")["resources"])
        runtime = "accepted-main-runtime" + minor + "-v3"
        assert read(runtime + "/result.json")["status"] == "PASS"
        assert read(runtime + "/result.json")["actual_dump_restore_restart"]
        for phase, receipt in (("runtime", "runtime-result.json"), ("recovered", "recovery.json")):
            assert read(runtime + "/" + phase + "/" + receipt)["status"] == "PASS"
            assert read(runtime + "/" + phase + "/runtime-credential-scan.json")["matches"] == 0
        assert read(runtime + "/credential-scan.json")["matches"] == 0
        assert read(runtime + "/source-volume-cleanup.json")["absent"]
        assert all(read(runtime + "/teardown/teardown.json")[k] for k in
                   ("owned_container_removed", "owned_network_removed", "owned_volume_removed"))
        for name, rows in ((unit, read(unit + "/source.json")), (runtime, read(runtime + "/source.json")["source"])):
            for row in rows:
                path = ROOT / row["path"]
                assert hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == row["lf_sha256"], row["path"]
            sources[name] = {"manifest_sha256": sha(HERE / name / "source.json"), "all_recorded_sources_match_final_lf_bytes": True}
        cleanups.extend((pg, unit, c3, runtime))
    isolated = read("legacy-isolated-v1/result.json")
    assert isolated["status"] == "PASS" and isolated["original_browser_scenarios"] == 16
    suites.append(junit("legacy-isolated-v1/http24/tests.xml", 24))
    views = read("PUBLIC_EVIDENCE_VIEWS.json")
    for view in views["views"]:
        assert sha(HERE / view["public_path"]) == view["public_sha256"]
        assert sha(HERE / view["private_original"]) == view["original_sha256"]
    paths = []
    sensitive = []
    patterns = (r"password=[A-Za-z0-9_-]{24,}", r"Bearer [A-Za-z0-9_-]{32,}",
                r'"(?:password|admin_password|bearer)"\s*:\s*"[A-Za-z0-9_-]{24,}"',
                r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", r"eyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{20,}")
    for name in sorted(changed):
        path = ROOT / name
        if not path.is_file() or name.endswith("LOCAL_ACCEPTANCE.json"):
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8")
        except UnicodeError:
            text = ""
        if any(re.search(p, text) for p in patterns):
            sensitive.append(name)
        paths.append({"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)})
    assert not sensitive, sensitive
    result = {"status": "LOCAL_ALL_REQUIRED_GATES_PASS_AWAITING_REAL_CI_AND_INDEPENDENT_OWNER",
        "accepted_main": ACCEPTED, "local_head_before_feature_commit": git("rev-parse", "HEAD"),
        "head_ordered_parents": git("log", "-1", "--format=%H %P"),
        "protected_paths_unchanged": True, "forbidden_paths": forbidden,
        "native_junit": suites, "ordinary_25_deferred_each": "COVERED_BY_SEPARATE_HTTP24_AND_BROWSER16_NATIVE_GATES",
        "source_integrity": sources, "cleanup_verified": cleanups,
        "privacy_views": len(views["views"]), "public_sensitive_matches": 0, "publication_manifest": paths,
        "historical_red_retained": True, "real_human_approvals": 0, "share_grants": 0,
        "gate": "TEST_ONLY_PRIVATE_RUNTIME_CANDIDATE_G1_G2_G3_NO_GO", "pushed": False, "hosted_ci_claimed": False}
    (HERE / "LOCAL_ACCEPTANCE.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "native_suites": len(suites), "published_files": len(paths)}))


if __name__ == "__main__":
    main()

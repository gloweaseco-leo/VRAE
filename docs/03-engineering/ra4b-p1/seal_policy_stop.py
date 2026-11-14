"""Seal the distinct policy-count RED; preserve both earlier RED histories."""

import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ENTRY = "f9c64dacafffa08806890fcacf04f3da5723c040"


def main():
    prior = json.loads((HERE / "STOP_EVIDENCE.json").read_bytes())
    retained = []
    for row in prior["evidence"]:
        path = ROOT / row["path"]
        if row["path"].startswith("docs/03-engineering/ra4b-p1/"):
            assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"], row["path"]
            retained.append(row)
    protected = ("db/migrations/0001_ra4a_test_only.sql", "db/migrations/0002_ra4a_private_bytes.sql",
                 "db/migrations/0003_ra4a_test_review_cas.sql", "integration/ra4a", "vrae/persistence", ".github/workflows")
    assert subprocess.check_output(["git", "diff", ENTRY, "--", *protected], cwd=ROOT) == b""
    sql = (ROOT / "db/migrations/0004_ra4b_test_only_api.sql").read_text(encoding="utf-8")
    start = sql.index("CREATE POLICY b4_origin_app")
    end = sql.index("CREATE FUNCTION ra4b_test.require_actor")
    cause = sql[start:end]
    (HERE / "MINIMAL_POLICY_CAUSE.diff").write_text("".join(difflib.unified_diff([], cause.splitlines(True),
                                      fromfile="/dev/null", tofile="b/db/migrations/0004_ra4b_test_only_api.sql")), encoding="utf-8")
    out = HERE / "compat311-v1"
    catalog = json.loads((out / "pg2/pg-catalog-and-calls.json").read_bytes())
    assert len(catalog["roles"]) == 8 and len(catalog["policies"]) == 12
    assert len(catalog["calls"]) == 54 and sum(c["outcome"] == "passed" for c in catalog["calls"]) == 53
    suites = {}
    for name, passed, failed in (("tests.xml", 17, 0), ("pg2/tests.xml", 53, 1)):
        root = ET.parse(out / name).getroot()
        cases = list(root.iter("testcase"))
        failures = list(root.iter("failure"))
        assert len(cases) == passed + failed and len(failures) == failed
        assert not list(root.iter("skipped")) and not list(root.iter("error"))
        suites[name] = {"passed": passed, "failed": failed, "skipped": 0}
    error = ET.parse(out / "pg2/tests.xml").find(".//failure").text
    assert "assert len(rows) == 10" in error and "12 == 10" in error
    cleanup = json.loads((out / "teardown/teardown.json").read_bytes())
    assert all(cleanup[k] for k in ("owned_container_removed", "owned_network_removed", "owned_volume_removed"))
    files = [p for p in out.rglob("*") if p.is_file()]
    files += [HERE / "STOP_FROZEN_P1_POLICY_COUNT.md", HERE / "MINIMAL_POLICY_CAUSE.diff", HERE / "STOP_EVIDENCE.json"]
    files += [ROOT / n for n in ("db/migrations/0004_ra4b_test_only_api.sql", "vrae/application/ra4b/store.py",
                                "integration/ra4b/support.py", "integration/ra4b/security_cases.py")]
    receipt = {"status": "STOPPED_FROZEN_P1_POLICY_REGRESSION_NOT_ACCEPTED", "entry": ENTRY,
               "owner_decision": "RA4B_P1_ROLE_PREFIX_COMPAT_GO", "protected_diff": "EMPTY",
               "role_mapping": {"ra4a_test_b4_" + v: "ra4b_test_" + v for v in ("a_app", "b_app", "a_worker", "b_worker")},
               "actual_original_role_count": 8, "actual_original_policy_count": 12, "expected_original_policy_count": 10,
               "suites": suites, "retained_prior_evidence_files_verified": len(retained),
               "python313_hardening": "NOT_RUN", "runtime_http": "NOT_RUN", "push": False, "new_pr": False,
               "new_hosted_ci": False, "merge": False, "deployment": False,
               "evidence": [{"path": p.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)]}
    (HERE / "POLICY_STOP_EVIDENCE.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in receipt.items() if k != "evidence"}))


if __name__ == "__main__":
    main()

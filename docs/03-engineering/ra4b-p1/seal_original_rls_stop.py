"""Seal the original-policy runtime RED without modifying historical evidence."""

import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ENTRY = "f9c64dacafffa08806890fcacf04f3da5723c040"


def main():
    retained = set()
    for name in ("STOP_EVIDENCE.json", "POLICY_STOP_EVIDENCE.json"):
        ledger = json.loads((HERE / name).read_bytes())
        for row in ledger["evidence"]:
            if row["path"].startswith("docs/03-engineering/ra4b-p1/"):
                assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"], row["path"]
                retained.add(row["path"])
    protected = ("db/migrations/0001_ra4a_test_only.sql", "db/migrations/0002_ra4a_private_bytes.sql",
                 "db/migrations/0003_ra4a_test_review_cas.sql", "integration/ra4a", "vrae/persistence", ".github/workflows")
    assert subprocess.check_output(["git", "diff", ENTRY, "--", *protected], cwd=ROOT) == b""
    run, diag = HERE / "original-rls311-v1", HERE / "original-rls311-diagnostic"
    assert (run / "policies-before-0004.json").read_bytes() == (run / "policies-after-0004.json").read_bytes()
    assert len(json.loads((run / "policies-after-0004.json").read_bytes())) == 10
    suite_counts = {}
    for path, passed, failed in ((run / "p1-after-0004/tests.xml", 54, 0), (run / "b4-tests.xml", 6, 1)):
        root = ET.parse(path).getroot()
        assert len(list(root.iter("testcase"))) == passed + failed
        assert len(list(root.iter("failure"))) == failed
        assert not list(root.iter("error")) and not list(root.iter("skipped"))
        suite_counts[path.relative_to(HERE).as_posix()] = {"passed": passed, "failed": failed, "skipped": 0}
    error = json.loads((run / "actual-sql-failure.json").read_bytes())
    reproduced = json.loads((diag / "reproduced-failure.json").read_bytes())
    assert error["sqlstate"] == reproduced["failure"]["sqlstate"] == "42501"
    assert error["primary"] == reproduced["failure"]["primary"] == "RA4B_ORIGIN_APP_DENIED"
    assert reproduced["before_sha256"] == reproduced["after_sha256"] and reproduced["no_claim_advancement"]
    assert reproduced["jobs"] == [["tenant-test", "PENDING", 0, 0]]
    catalog = json.loads((diag / "catalog.json").read_bytes())
    assert catalog["legacy_role_count"] == 8
    for role, session in catalog["actual_sessions"].items():
        assert session[:2] == [role, role] and session[2] == "vrae_ra4a_p1" and session[3].startswith("16")
        assert not any(r[2] for r in catalog["grants"][role]["raw_table_privileges"])
        allowed = {"claim", "finish"} if role.endswith("worker") else {"admit", "status"}
        assert {(r[0], r[1]) for r in catalog["grants"][role]["function_executes"] if r[2]} == {("ra4b_test", n) for n in allowed}
    for name, owner, sd, search, acl in catalog["functions"]:
        assert owner == "ra4a_owner" and sd and search == ["search_path=pg_catalog, ra4b_test, pg_temp"]
        assert not any(v.startswith("=") for v in acl.strip("{}").split(","))
    for folder in (run, diag):
        cleanup = json.loads((folder / "teardown/teardown.json").read_bytes())
        assert all(cleanup[k] for k in ("owned_container_removed", "owned_network_removed", "owned_volume_removed"))
        assert json.loads((folder / "credential-scan.json").read_bytes())["matches"] == 0
    sql = (ROOT / "db/migrations/0004_ra4b_test_only_api.sql").read_text(encoding="utf-8")
    assert "CREATE POLICY" not in sql and "RA4B_ORIGIN_APP_DENIED" in sql
    excerpt = sql[sql.index("CREATE FUNCTION ra4b_test.require_run"):sql.index("CREATE FUNCTION ra4b_test.admit")]
    (HERE / "ORIGIN_AUTHORITY_CHECK.sql.txt").write_text(excerpt, encoding="utf-8")
    files = [p for folder in (run, diag) for p in folder.rglob("*") if p.is_file()]
    files += [HERE / n for n in ("STOP_ORIGINAL_RLS_ORIGIN_AUTHORITY.md", "ORIGIN_AUTHORITY_CHECK.sql.txt", "STOP_EVIDENCE.json", "POLICY_STOP_EVIDENCE.json")]
    files += [ROOT / n for n in ("db/migrations/0004_ra4b_test_only_api.sql", "vrae/application/ra4b/store.py", "integration/ra4b/support.py")]
    receipt = {"status": "STOPPED_ORIGINAL_RLS_ORIGIN_APP_AUTHORITY_NOT_ACCEPTED", "entry": ENTRY,
               "owner_decision": "RA4B_P1_RLS_POLICY_COMPAT_GO", "protected_diff": "EMPTY",
               "original_role_count": 8, "original_policy_count": 10, "original_policies_unchanged": True,
               "suites": suite_counts, "sqlstate": error["sqlstate"], "primary": error["primary"],
               "claim_transaction_rolled_back": True, "retained_historical_evidence_files_verified": len(retained),
               "python313": "NOT_RUN_AFTER_STOP", "full_regressions": "INCOMPLETE", "runtime_http": "NOT_RUN",
               "push": False, "new_pr": False, "new_hosted_ci": False, "merge": False, "deployment": False,
               "evidence": [{"path": p.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)]}
    (HERE / "ORIGINAL_RLS_STOP_EVIDENCE.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in receipt.items() if k != "evidence"}))


if __name__ == "__main__":
    main()

"""Read-only source/evidence verification and a deliberately unapplied repair diff."""

import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ENTRY = "f9c64dacafffa08806890fcacf04f3da5723c040"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    changed = ("db/migrations/0004_ra4b_test_only_api.sql", "vrae/application/ra4b/store.py",
               "integration/ra4b/support.py", "integration/ra4b/security_cases.py")
    diff = []
    for name in changed:
        before = (ROOT / name).read_text(encoding="utf-8")
        after = before.replace("ra4a_test_b4_", "ra4b_test_")
        assert after != before
        diff.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                        fromfile="a/" + name, tofile="b/" + name))
    (HERE / "PROPOSED_ROLE_NAMESPACE_FIX.diff").write_text("".join(diff), encoding="utf-8")
    protected = ("db/migrations/0001_ra4a_test_only.sql", "db/migrations/0002_ra4a_private_bytes.sql",
                 "db/migrations/0003_ra4a_test_review_cas.sql", "integration/ra4a", "vrae/persistence", ".github/workflows")
    assert git("diff", ENTRY, "--", *protected) == b""
    catalog = json.loads((HERE / "sql311-v4/pg2/pg-catalog-and-calls.json").read_bytes())
    assert len(catalog["roles"]) == 12 and len(catalog["calls"]) == 54
    assert sum(c["outcome"] == "passed" for c in catalog["calls"]) == 53
    assert catalog["session_exit"] == 1
    suites = {}
    for name, passed, failed in (("sql311-v4/tests.xml", 17, 0), ("sql311-v4/pg2/tests.xml", 53, 1)):
        root = ET.parse(HERE / name).getroot()
        cases = list(root.iter("testcase"))
        fails = [c.attrib["name"] for c in cases if c.find("failure") is not None]
        assert len(cases) == passed + failed and len(fails) == failed
        assert not list(root.iter("skipped")) and not list(root.iter("error"))
        suites[name] = {"passed": passed, "failed": failed, "skipped": 0, "failures": fails}
    for name in ("sql311-v4/teardown/teardown.json", "sql311-v2/cleanup-recheck/teardown.json"):
        cleanup = json.loads((HERE / name).read_bytes())
        assert all(cleanup[k] for k in ("owned_container_removed", "owned_network_removed", "owned_volume_removed"))
    paths = [p for name in ("actual-311", "actual-313", "sql311-v1", "sql311-v2", "sql311-v3", "sql311-v4")
             for p in (HERE / name).rglob("*") if p.is_file()]
    paths += [HERE / "STOP_FROZEN_P1_ROLE_COUNT.md", HERE / "PROPOSED_ROLE_NAMESPACE_FIX.diff"]
    paths += [ROOT / p for p in changed]
    ledger = [{"path": p.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
              for p in sorted(paths)]
    receipt = {"status": "STOPPED_FROZEN_P1_REGRESSION_NOT_ACCEPTED", "entry": ENTRY,
               "local_head": git("rev-parse", "HEAD").decode().strip(), "protected_diff": "EMPTY",
               "suites": suites, "post_0004_ra4a_role_count": 12, "frozen_expected_role_count": 8,
               "proposed_repair_applied": False, "python313_hardening_acceptance": "NOT_RUN",
               "http_runtime_acceptance": "NOT_RUN", "push": False, "new_pr": False,
               "new_hosted_ci": False, "merge": False, "deployment": False, "evidence": ledger}
    (HERE / "STOP_EVIDENCE.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in receipt.items() if k != "evidence"}))


if __name__ == "__main__":
    main()

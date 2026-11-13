"""Integrity receipt for the actual RED contract preflight; never a green runtime claim."""

import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXPECTED = "f9c64dacafffa08806890fcacf04f3da5723c040"


def main():
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    assert head == EXPECTED
    assert not subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT).strip()
    runs = []
    for version in ("311", "313"):
        run = HERE / ("actual-" + version)
        tree = ET.parse(run / "tests.xml")
        assert len(tree.findall(".//testcase")) == len(tree.findall(".//failure")) == 3
        assert not tree.findall(".//error") and not tree.findall(".//skipped")
        role = json.loads((run / "actual-worker-privileges.json").read_bytes())
        assert role["role"][0] == "ra4a_test_a_worker" and not any(role["role"][1:])
        assert all(role["select"].values())
        for state in ("revoked", "expired"):
            observation = json.loads((run / ("after-" + state + ".json")).read_bytes())
            assert observation["finish_denied"] is False
            assert observation["persisted_run_job"][:2] == ["TEST_ONLY_CONSUMED", "TEST_ONLY_DONE"]
        cleanup = json.loads((run / "teardown/teardown.json").read_bytes())
        assert all(cleanup[k] for k in ("owned_container_removed", "owned_network_removed", "owned_volume_removed"))
        scan = json.loads((run / "credential-scan.json").read_bytes())
        assert scan["matches"] == 0 and scan["all_owned_resources_removed"]
        receipt = json.loads((run / "receipt.json").read_bytes())
        assert receipt["pytest_exit"] == 1 and receipt["server"].startswith("PostgreSQL 16.")
        runs.append({"runtime": version, **receipt, "actual_credential_scan": scan})
    files = []
    for folder in (HERE, ROOT / "integration/ra4b"):
        for path in sorted(folder.rglob("*")):
            if (not path.is_file() or ".runtime" in path.parts or "__pycache__" in path.parts
                    or path.name == "PREFLIGHT_RECEIPT.json"):
                continue
            raw = path.read_bytes()
            files.append({"path": path.relative_to(ROOT).as_posix(),
                          "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
    report = {"state": "B4_P1_BLOCKED_BY_P1_CONTRACT_NOT_RUNTIME_CANDIDATE_NOT_B4_EXIT",
              "authorized_entry": EXPECTED, "actual_entry": head, "runs": runs,
              "existing_source_files_changed": 0, "api_worker_runtime_created": False,
              "migration_0004_applied": False, "pushed": False, "hosted_ci_triggered": False,
              "native_approval": False, "share_grant": False, "files": files}
    payload = (json.dumps(report, indent=2) + "\n").encode()
    (HERE / "PREFLIGHT_RECEIPT.json").write_bytes(payload)
    print(json.dumps({"state": report["state"], "dual_python": True,
                      "native_red_cases_each": 3, "owned_cleanup_verified": True,
                      "receipt_sha256": hashlib.sha256(payload).hexdigest()}))


if __name__ == "__main__":
    main()

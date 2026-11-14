"""Unmodified accepted C3 cases against a fresh PG16 including additive 0004.

Only the accepted lab's output root is redirected in memory to B4 evidence.
No original fixture, test assertion, role, policy or source file is edited.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))


def wire():
    from integration.ra4c3 import lab
    lab.OWN = HERE
    return lab


def main(label):
    lab = wire()
    out = (HERE / ".runtime/owner-review" if "--private-output" in sys.argv else HERE) / label
    out.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir(exist_ok=False)
    state = HERE / ".runtime" / (label + "-c3-state.json")
    profile = HERE / ".runtime" / (label + "-c3-profile.json")
    try:
        lab.start(state, out / "startup", option_a_local_trial=True)
        lab.seed(state, profile)
        # The immutable C3 seeder verifies ledger 1,2 and creates its private
        # original-bytes database at that accepted stage. B4 remains confined
        # to the canonical task database; coexistence must not migrate C3's DB.
        from integration.ra4b.support import migrate
        migrate()
        child = subprocess.run([sys.executable, str(Path(__file__)), "--child", str(out)], cwd=ROOT,
                env=dict(os.environ, RA4C3_STATE=str(state), RA4C3_PROFILE=str(profile)), capture_output=True)
        (out / "stdout.log").write_bytes(child.stdout)
        (out / "stderr.log").write_bytes(child.stderr)
        child.check_returncode()
        tests = ET.parse(out / "tests.xml").getroot()
        assert not any(list(tests.iter(k)) for k in ("failure", "error", "skipped"))
        (out / "result.json").write_text(json.dumps({"status": "PASS", "python": sys.version,
            "c3_cases": len(list(tests.iter("testcase"))), "canonical_task_db_migrations": [1, 2, 3, 4],
            "c3_private_bytes_db_migrations": [1, 2],
            "original_c3_sources_unchanged": True, "output_root_redirect_only": True}, indent=2))
    finally:
        if state.exists():
            held = json.loads(state.read_text())
            lab.stop(state, out / "teardown")
            secrets = [held["admin_password"], *held["runtime_passwords"].values()]
            assert not any(s.encode() in p.read_bytes() for p in out.rglob("*") if p.is_file() for s in secrets)
            (out / "credential-scan.json").write_text(json.dumps({"matches": 0, "actual_secret_count": len(secrets)}))
        if profile.exists():
            profile.unlink()


if __name__ == "__main__":
    if sys.argv[1] == "--child":
        wire()
        import pytest
        raise SystemExit(pytest.main(["-q", "--tb=short", "--import-mode=importlib",
            "integration/ra4c3/test_readside.py", "integration/ra4c3/test_lab_cleanup.py",
            "integration/ra4c3/test_restart_read.py", "--junitxml=" + str(Path(sys.argv[2]) / "tests.xml")]))
    main(sys.argv[1])

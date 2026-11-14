"""Actual local dual-Python PG check of 0004, separate from retained RED."""

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main(label):
    out = HERE / label
    out.mkdir(exist_ok="--cleanup-only" in sys.argv)
    from infra.ra4a import lab
    from integration.ra4a import support
    state = HERE / ".runtime" / (label + ".json")
    lab.STATE = support.STATE = state

    def bound(path):
        assert path.resolve().is_relative_to(HERE)
        return path.resolve()

    lab.output_path = bound
    if len(sys.argv) > 2 and sys.argv[2] == "--cleanup-only":
        lab.stop(out / "cleanup-recheck", out / "startup")
        return 0
    result = 2
    try:
        lab.start(out / "startup", 60)
        if "--full" in sys.argv:
            support.migrate()
            import subprocess
            dest = out / "pg1"
            dest.mkdir()
            child = subprocess.run([sys.executable, str(HERE / "regression.py"), "pg1", str(state), str(dest)], cwd=ROOT, capture_output=True)
            (dest / "stdout.log").write_bytes(child.stdout)
            (dest / "stderr.log").write_bytes(child.stderr)
            if child.returncode:
                return child.returncode
        from integration.ra4b.support import migrate
        migrate()
        import pytest
        os.environ["RA4B_EVIDENCE_DIR"] = str(out)
        result = pytest.main(["-q", "-x", "--tb=short", "--import-mode=importlib", "-o",
                              "consider_namespace_packages=true", "--confcutdir=integration/ra4b",
                              "integration/ra4b/security_cases.py", "integration/ra4b/epoch_cases.py",
                              "--junitxml=" + str(out / "tests.xml")])
        if result == 0 and "--post-p1" in sys.argv:
            import subprocess
            dest = out / "pg2-after-final-0004"
            dest.mkdir()
            child = subprocess.run([sys.executable, str(HERE / "regression.py"), "pg2", str(state), str(dest)], cwd=ROOT, capture_output=True)
            (dest / "stdout.log").write_bytes(child.stdout)
            (dest / "stderr.log").write_bytes(child.stderr)
            result = child.returncode
        if result == 0 and "--regressions" in sys.argv:
            import subprocess
            for name in ("pg2", "p2a", "p2b1", "identity-pg", "crypto"):
                dest = out / name
                dest.mkdir()
                child = subprocess.run([sys.executable, str(HERE / "regression.py"), name, str(state), str(dest)],
                                       cwd=ROOT, capture_output=True)
                (dest / "stdout.log").write_bytes(child.stdout)
                (dest / "stderr.log").write_bytes(child.stderr)
                print(name, child.returncode, flush=True)
                if child.returncode:
                    result = child.returncode
                    break
    finally:
        if state.exists():
            held = json.loads(state.read_bytes())
            secrets = [held["admin_password"], *held["runtime_passwords"].values()]
            lab.stop(out / "teardown", out / "startup")
            assert not any(secret.encode() in p.read_bytes() for p in out.rglob("*") if p.is_file() for secret in secrets)
    return result


if __name__ == "__main__":
    os.environ["PYTHONUTF8"] = "1"
    raise SystemExit(main(sys.argv[1]))

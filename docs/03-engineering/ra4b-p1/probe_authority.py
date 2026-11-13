"""Real isolated PG16 preflight. No HTTP/Worker runtime is authorized by RED."""

import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def main(label):
    assert label.replace("-", "").replace(".", "").isalnum()
    out = HERE / label
    out.mkdir(exist_ok=False)
    private = HERE / ".runtime"
    private.mkdir(exist_ok=True)
    from infra.ra4a import lab
    from integration.ra4a import support
    state = private / (label + ".json")
    lab.STATE = support.STATE = state

    def bounded(path):
        path = path.resolve()
        assert path.is_relative_to(HERE)
        return path

    lab.output_path = bounded
    os.environ["RA4B_AUTHORITY_EVIDENCE"] = str(out)
    result = 2
    try:
        lab.start(out / "startup", 60)
        from integration.ra4a.p2b1_support import migrate_p2b1
        migrate_p2b1()
        (out / "accepted-sources.json").write_text(json.dumps([
            {"path": str(p.relative_to(ROOT)).replace("\\", "/"),
             "lf_sha256": hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()}
            for p in sorted((ROOT / "db/migrations").glob("*.sql"))
        ], indent=2) + "\n", encoding="utf-8")
        with support.connect() as connection:
            server = connection.execute("SELECT version()").fetchone()[0]
        import pytest
        result = pytest.main(["-q", "--tb=short", "--import-mode=importlib", "-o",
                              "consider_namespace_packages=true", "--confcutdir=integration/ra4b",
                              "integration/ra4b/authority_cases.py",
                              "--junitxml=" + str(out / "tests.xml")])
        (out / "receipt.json").write_text(json.dumps({
            "state": "BLOCKED_CONTRACT_PREFLIGHT_RED" if result else "PREFLIGHT_INVARIANTS_PASS",
            "python": sys.version, "server": server, "pytest_exit": int(result),
            "api_worker_runtime_implemented": False, "hosted_ci_triggered": False,
            "network_scope": "Accepted P1 loopback-only SQL preflight; no API/Worker runtime or runtime egress claim",
        }, indent=2) + "\n", encoding="utf-8")
    finally:
        if state.exists():
            secret_state = json.loads(state.read_text())
            secrets = [secret_state["admin_password"], *secret_state["runtime_passwords"].values()]
            lab.stop(out / "teardown", out / "startup")
            for path in out.rglob("*"):
                if path.is_file():
                    assert not any(s.encode() in path.read_bytes() for s in secrets), "CREDENTIAL_LEAK_DENIED"
            (out / "credential-scan.json").write_text(json.dumps({
                "actual_secret_count": len(secrets), "matches": 0,
                "all_owned_resources_removed": True,
            }, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))

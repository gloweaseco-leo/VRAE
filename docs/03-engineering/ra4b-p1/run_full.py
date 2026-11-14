"""Accepted staged frozen prelude, then 0004 compatibility and B4 epoch matrix."""

import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))


def main(label):
    out = (HERE / ".runtime/owner-review" if "--private-output" in sys.argv else HERE) / label
    out.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir(exist_ok=False)
    from infra.ra4a import lab
    from integration.ra4a import support
    lab.STATE = support.STATE = HERE / ".runtime" / (label + ".json")
    lab.output_path = lambda p: p.resolve() if p.resolve().is_relative_to(HERE) else (_ for _ in ()).throw(ValueError("OUTPUT_BOUNDARY"))
    commands = []

    def stage(name, dest_name=None):
        dest = out / (dest_name or name)
        dest.mkdir()
        p = subprocess.run([sys.executable, str(HERE / "regression.py"), name, str(lab.STATE), str(dest)], cwd=ROOT, capture_output=True)
        (dest / "stdout.log").write_bytes(p.stdout)
        (dest / "stderr.log").write_bytes(p.stderr)
        commands.append({"stage": dest.name, "exit": p.returncode})
        print(json.dumps(commands[-1]), flush=True)
        (out / "stages.json").write_text(json.dumps(commands, indent=2))
        if p.returncode:
            raise RuntimeError("STOP_FROZEN_STAGE_" + name)

    try:
        lab.start(out / "startup", 60)
        if "--remaining" in sys.argv:
            from integration.ra4b.support import migrate
            migrate()
            for name in ("p2b1", "identity-pg", "crypto"):
                stage(name)
            (out / "result.json").write_text(json.dumps({"status": "REMAINING_FROZEN_PG_PASS", "python": sys.version,
                                                        "commands": commands}, indent=2))
            return 0
        support.migrate()
        stage("pg1")
        from integration.ra4a.p2a_support import migrate_p2a, schema_sha256
        migrate_p2a()
        stage("pg2", "pg2-before-0004")
        stage("p2a")  # Original verifier requires exactly ledger entries 1,2.
        from integration.ra4a.p2b1_support import migrate_p2b1
        migrate_p2b1()
        with support.connect() as c:
            baseline = c.execute("SELECT schemaname,tablename,policyname,qual,with_check FROM pg_policies "
                                 "WHERE schemaname IN ('ra4a','ra4a_private') ORDER BY 1,2,3").fetchall()
            old_bytes = schema_sha256(c)
        from integration.ra4b.support import migrate
        migrate()
        with support.connect() as c:
            assert schema_sha256(c) == old_bytes
            assert baseline == c.execute("SELECT schemaname,tablename,policyname,qual,with_check FROM pg_policies "
                                 "WHERE schemaname IN ('ra4a','ra4a_private') ORDER BY 1,2,3").fetchall()
            assert len(baseline) == 10
            assert c.execute("SELECT count(*) FROM ra4b_test.origin_epochs").fetchone() == (0,)
            (out / "migration-compat.json").write_text(json.dumps({"old_policies": baseline, "p2a_schema_sha256_unchanged": old_bytes,
                 "epoch_rows_at_fresh_bootstrap": 0, "initialization": "ACTUAL_APP_SCOPE_ONLY_AT_FIRST_ADMISSION"}, indent=2))
        stage("pg2", "pg2-after-0004")
        os.environ["RA4B_EVIDENCE_DIR"] = str(out)
        import pytest
        result = pytest.main(["-q", "-x", "--tb=short", "--import-mode=importlib", "-o", "consider_namespace_packages=true",
                              "--confcutdir=integration/ra4b", "integration/ra4b/security_cases.py", "integration/ra4b/epoch_cases.py",
                              "--junitxml=" + str(out / "b4-tests.xml")])
        if result:
            return result
        for name in ("p2b1", "identity-pg", "crypto"):
            stage(name)
        (out / "result.json").write_text(json.dumps({"status": "PG_AND_FROZEN_PRELUDE_PASS_NOT_FINAL_RUNTIME_PASS",
                         "python": sys.version, "commands": commands}, indent=2))
    finally:
        if lab.STATE.exists():
            state = json.loads(lab.STATE.read_bytes())
            lab.stop(out / "teardown", out / "startup")
            secrets = [state["admin_password"], *state["runtime_passwords"].values()]
            assert not any(s.encode() in p.read_bytes() for p in out.rglob("*") if p.is_file() for s in secrets)
            (out / "credential-scan.json").write_text(json.dumps({"actual_secret_count": len(secrets), "matches": 0}))
    return 0


if __name__ == "__main__":
    os.environ["PYTHONUTF8"] = "1"
    raise SystemExit(main(sys.argv[1]))

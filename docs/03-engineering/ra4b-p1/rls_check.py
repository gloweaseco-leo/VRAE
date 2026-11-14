"""Fresh PG16: exact original policy readback, frozen P1 then real B4 fail-fast."""

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def save(path, value):
    path.write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


def policies(c):
    return c.execute("SELECT schemaname,tablename,policyname,roles,cmd,permissive,qual,with_check "
                     "FROM pg_policies WHERE schemaname IN ('ra4a','ra4a_private') "
                     "ORDER BY schemaname,tablename,policyname").fetchall()


def main(label):
    out = HERE / label
    out.mkdir(exist_ok=False)
    from infra.ra4a import lab
    from integration.ra4a import support
    state = HERE / ".runtime" / (label + ".json")
    lab.STATE = support.STATE = state

    def bound(path):
        assert path.resolve().is_relative_to(HERE)
        return path.resolve()

    lab.output_path = bound
    held = None
    result = 2
    try:
        lab.start(out / "startup", 60)
        from integration.ra4a.p2b1_support import migrate_p2b1
        migrate_p2b1()
        with support.connect() as c:
            before = policies(c)
            assert len(before) == 10
            save(out / "policies-before-0004.json", before)
        from integration.ra4b.support import migrate
        migrate()
        with support.connect() as c:
            after = policies(c)
            assert after == before
            save(out / "policies-after-0004.json", after)
            assert c.execute("SELECT count(*) FROM pg_roles WHERE rolname LIKE 'ra4a_%'").fetchone() == (8,)
        dest = out / "p1-after-0004"
        dest.mkdir()
        child = subprocess.run([sys.executable, str(HERE / "regression.py"), "pg2", str(state), str(dest)],
                               cwd=ROOT, capture_output=True)
        (dest / "stdout.log").write_bytes(child.stdout)
        (dest / "stderr.log").write_bytes(child.stderr)
        print("FROZEN_P1_AFTER_0004_EXIT", child.returncode, flush=True)
        if child.returncode:
            return child.returncode
        import psycopg
        import pytest

        class FailureRecorder:
            def pytest_runtest_makereport(self, item, call):
                if call.excinfo is not None and isinstance(call.excinfo.value, psycopg.Error):
                    e = call.excinfo.value
                    save(out / "actual-sql-failure.json", {"nodeid": item.nodeid, "sqlstate": e.sqlstate,
                         "primary": e.diag.message_primary, "context": e.diag.context,
                         "exception": type(e).__name__})

        result = pytest.main(["-q", "-x", "--tb=short", "--import-mode=importlib", "-o",
                              "consider_namespace_packages=true", "--confcutdir=integration/ra4b",
                              "integration/ra4b/security_cases.py", "--junitxml=" + str(out / "b4-tests.xml")],
                             plugins=[FailureRecorder()])
        from integration.ra4b.support import config
        from vrae.application.ra4b import store
        actual_sessions = {}
        for kind in ("APP", "WORKER"):
            cfg = config(kind)
            with store.connect(cfg) as c:
                actual_sessions[kind] = c.execute("SELECT session_user,current_user,current_database(),"
                       "current_setting('server_version_num')").fetchone()
        with support.connect() as c:
            record = {
                "actual_runtime_connections": actual_sessions,
                "policies_unchanged": policies(c) == before,
                "roles": c.execute("SELECT rolname,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolcanlogin "
                      "FROM pg_roles WHERE rolname LIKE 'ra4b_%' ORDER BY rolname").fetchall(),
                "memberships": c.execute("SELECT member::regrole::text,roleid::regrole::text,inherit_option,set_option,admin_option "
                      "FROM pg_auth_members WHERE member IN (SELECT oid FROM pg_roles WHERE rolname LIKE 'ra4b_%') ORDER BY 1,2").fetchall(),
                "rls": c.execute("SELECT n.nspname,t.relname,pg_get_userbyid(t.relowner),t.relrowsecurity,t.relforcerowsecurity "
                      "FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname IN ('ra4a','ra4a_private') "
                      "AND t.relkind='r' ORDER BY 1,2").fetchall(),
                "functions": c.execute("SELECT proname,pg_get_userbyid(proowner),prosecdef,proconfig,proacl::text FROM pg_proc "
                      "WHERE pronamespace='ra4b_test'::regnamespace ORDER BY proname").fetchall(),
                "current_principals": c.execute("SELECT * FROM ra4a_private.principals WHERE db_role LIKE 'ra4b_%' ORDER BY db_role").fetchall(),
                "current_assignments": c.execute("SELECT * FROM ra4a_private.assignments WHERE db_role LIKE 'ra4b_%' ORDER BY db_role").fetchall(),
                "jobs": c.execute("SELECT tenant_id,job_id,state,lease_seq,attempts FROM ra4a.jobs ORDER BY tenant_id,job_id").fetchall(),
                "runs": c.execute("SELECT tenant_id,run_id,status FROM ra4a.runs ORDER BY tenant_id,run_id").fetchall(),
                "audit": c.execute("SELECT action,count(*) FROM ra4a.audit GROUP BY action ORDER BY action").fetchall(),
                "outbox": c.execute("SELECT kind,undelivered,count(*) FROM ra4a.outbox GROUP BY kind,undelivered ORDER BY kind").fetchall(),
            }
            save(out / "actual-b4-catalog-and-state.json", record)
    finally:
        if state.exists():
            held = json.loads(state.read_bytes())
            lab.stop(out / "teardown", out / "startup")
            secrets = [held["admin_password"], *held["runtime_passwords"].values()]
            assert not any(s.encode() in p.read_bytes() for p in out.rglob("*") if p.is_file() for s in secrets)
            save(out / "credential-scan.json", {"actual_secret_count": len(secrets), "matches": 0})
    save(out / "result.json", {"python": sys.version, "exit": int(result), "original_policy_count": 10,
                               "original_policies_unchanged": True, "gate": "NOT_ACCEPTED" if result else "PARTIAL"})
    return result


if __name__ == "__main__":
    os.environ["PYTHONUTF8"] = "1"
    raise SystemExit(main(sys.argv[1]))

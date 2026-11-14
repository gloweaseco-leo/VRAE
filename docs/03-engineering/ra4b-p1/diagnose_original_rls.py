"""Bounded reproduction of the stopped failure, not acceptance continuation."""

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))


def save(path, data):
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def original_policies(c):
    return c.execute("SELECT schemaname,tablename,policyname,roles,cmd,qual,with_check "
                     "FROM pg_policies WHERE schemaname IN ('ra4a','ra4a_private') "
                     "ORDER BY schemaname,tablename,policyname").fetchall()


def main(label):
    import psycopg
    from infra.ra4a import lab
    from integration.ra4a import support as old
    out = HERE / label
    out.mkdir(exist_ok=False)
    lab.STATE = old.STATE = HERE / ".runtime" / (label + ".json")

    def bound(path):
        assert path.resolve().is_relative_to(HERE)
        return path.resolve()

    lab.output_path = bound
    failure = None
    try:
        lab.start(out / "startup", 60)
        from integration.ra4a.p2b1_support import migrate_p2b1
        migrate_p2b1()
        with old.connect() as c:
            before_policies = original_policies(c)
        from integration.ra4b.support import ROLES, config, fingerprint, migrate, seed
        from vrae.application.ra4b import store
        migrate()
        seed()
        with old.connect() as admin:
            assert original_policies(admin) == before_policies and len(before_policies) == 10
            save(out / "original-policies.json", before_policies)
            roles = admin.execute("SELECT rolname,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolcanlogin "
                                  "FROM pg_roles WHERE rolname LIKE 'ra4b_%' ORDER BY rolname").fetchall()
            memberships = admin.execute("SELECT member::regrole::text,roleid::regrole::text,inherit_option,set_option,admin_option "
                                        "FROM pg_auth_members WHERE member IN (SELECT oid FROM pg_roles WHERE rolname LIKE 'ra4b_%') ORDER BY 1,2").fetchall()
            functions = admin.execute("SELECT proname,pg_get_userbyid(proowner),prosecdef,proconfig,proacl::text "
                                     "FROM pg_proc WHERE pronamespace='ra4b_test'::regnamespace ORDER BY proname").fetchall()
            grants = {}
            sessions = {}
            for role in ROLES:
                kind = "WORKER" if role.endswith("worker") else "APP"
                cfg = config(kind, "b" if "_b_" in role else "a")
                with store.connect(cfg) as c:
                    sessions[role] = c.execute("SELECT session_user,current_user,current_database(),current_setting('server_version_num')").fetchone()
                    grants[role] = {"raw_table_privileges": c.execute("SELECT n.nspname,t.relname,has_table_privilege(session_user,t.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE') "
                         "FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname IN ('ra4a','ra4a_private','ra4a_bytes','ra4a_review_test') "
                         "AND t.relkind='r' ORDER BY 1,2").fetchall(),
                         "function_executes": c.execute("SELECT n.nspname,p.proname,has_function_privilege(session_user,p.oid,'EXECUTE') "
                         "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname IN ('ra4a','ra4a_private','ra4a_bytes','ra4a_review_test','ra4b_test') ORDER BY 1,2").fetchall()}
                    assert all(not r[2] for r in grants[role]["raw_table_privileges"])
            catalog = {"python": sys.version, "roles": roles, "memberships": memberships, "functions": functions,
                       "actual_sessions": sessions, "grants": grants,
                       "legacy_role_count": admin.execute("SELECT count(*) FROM pg_roles WHERE rolname LIKE 'ra4a_%'").fetchone()[0],
                       "rls": admin.execute("SELECT n.nspname,t.relname,pg_get_userbyid(t.relowner),t.relrowsecurity,t.relforcerowsecurity "
                       "FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname IN ('ra4a','ra4a_private') AND t.relkind='r' ORDER BY 1,2").fetchall(),
                       "principals": admin.execute("SELECT * FROM ra4a_private.principals WHERE db_role LIKE 'ra4b_%' ORDER BY db_role").fetchall(),
                       "assignments": admin.execute("SELECT * FROM ra4a_private.assignments WHERE db_role LIKE 'ra4b_%' ORDER BY db_role").fetchall()}
            save(out / "catalog.json", catalog)
            app, worker = config(), config("WORKER")
            with store.connect(app) as c:
                receipt = store.admit(c, app, "rls-diagnostic-0001", "accepted-404")
                status = store.status(c, app, receipt["request_id"])
            assert status["status"] == "QUEUED"
            before = fingerprint(admin)
            with store.connect(worker) as c:
                try:
                    store.claim(c, worker, 10)
                except psycopg.Error as e:
                    failure = {"sqlstate": e.sqlstate, "primary": e.diag.message_primary,
                               "context": e.diag.context, "exception": type(e).__name__}
            assert failure and failure["sqlstate"] == "42501" and failure["primary"] == "RA4B_ORIGIN_APP_DENIED"
            after = fingerprint(admin)
            assert after == before
            save(out / "reproduced-failure.json", {"status": "REPRODUCED_RED_NOT_ACCEPTANCE_PASS", "failure": failure,
                  "app_admission": receipt, "app_status": status, "before_sha256": before, "after_sha256": after,
                  "no_claim_advancement": True,
                  "jobs": admin.execute("SELECT tenant_id,state,lease_seq,attempts FROM ra4a.jobs").fetchall(),
                  "runs": admin.execute("SELECT tenant_id,status FROM ra4a.runs").fetchall(),
                  "audit": admin.execute("SELECT action,count(*) FROM ra4a.audit GROUP BY action ORDER BY action").fetchall(),
                  "outbox": admin.execute("SELECT kind,undelivered,count(*) FROM ra4a.outbox GROUP BY kind,undelivered ORDER BY kind").fetchall()})
            save(out / "source.json", {"source": [{"path": name, "sha256": hashlib.sha256((ROOT / name).read_bytes()).hexdigest()}
                 for name in ("db/migrations/0004_ra4b_test_only_api.sql", "vrae/application/ra4b/store.py", "integration/ra4b/support.py")],
                 "claim_failure_preserved": True})
    finally:
        if lab.STATE.exists():
            state = json.loads(lab.STATE.read_bytes())
            lab.stop(out / "teardown", out / "startup")
            secrets = [state["admin_password"], *state["runtime_passwords"].values()]
            assert not any(s.encode() in p.read_bytes() for p in out.rglob("*") if p.is_file() for s in secrets)
            save(out / "credential-scan.json", {"actual_secret_count": len(secrets), "matches": 0})
    print(json.dumps({"status": "STOP_CONFIRMED_NOT_ACCEPTED", "failure": failure}), flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))

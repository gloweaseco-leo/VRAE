"""Real PostgreSQL fixture. Missing PG is ERROR, never skip/xfail."""

import pytest
import json
import os
from pathlib import Path

from .support import connect, migrate, reset


@pytest.fixture(scope="session", autouse=True)
def actual_migration():
    migrate()


@pytest.fixture
def db():
    with connect() as admin:
        reset(admin)
        yield admin


_calls = []


def pytest_runtest_logreport(report):
    if report.when == "call" and "integration/ra4a/" in report.nodeid:
        _calls.append({"id": report.nodeid, "outcome": report.outcome})


def pytest_sessionfinish(session, exitstatus):
    output = Path(os.environ["RA4A_EVIDENCE_DIR"])
    with connect() as c:
        record = {
            "migrations": c.execute(
                "SELECT version,sha256 FROM ra4a_private.migrations ORDER BY version"
            ).fetchall(),
            "server_version": c.execute("SELECT version()").fetchone()[0],
            "roles": c.execute(
                "SELECT rolname,rolsuper,rolbypassrls,rolcanlogin,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname LIKE 'ra4a_%' ORDER BY rolname"
            ).fetchall(),
            "tables": c.execute(
                "SELECT n.nspname,c.relname,r.rolname,c.relrowsecurity,c.relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_roles r ON r.oid=c.relowner WHERE n.nspname IN ('ra4a','ra4a_private') AND c.relkind='r' ORDER BY n.nspname,c.relname"
            ).fetchall(),
            "policies": c.execute(
                "SELECT schemaname,tablename,policyname,qual,with_check FROM pg_policies WHERE schemaname IN ('ra4a','ra4a_private') ORDER BY schemaname,tablename"
            ).fetchall(),
            "grants": c.execute(
                "SELECT grantee,table_schema,table_name,privilege_type FROM information_schema.role_table_grants WHERE grantee IN ('ra4a_app','ra4a_worker') ORDER BY grantee,table_name,privilege_type"
            ).fetchall(),
            "functions": c.execute(
                "SELECT p.proname,r.rolname,p.prosecdef,p.proconfig,p.proacl::text FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_roles r ON r.oid=p.proowner WHERE n.nspname IN ('ra4a','ra4a_private') ORDER BY p.proname"
            ).fetchall(),
            "calls": _calls,
            "session_exit": int(exitstatus),
            "github_checkout": os.environ.get("GITHUB_SHA"),
            "synthetic_authority_only": True,
            "actual_human_approvals": 0,
            "share_grants": 0,
        }
    (output / "pg-catalog-and-calls.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    tr = session.config.pluginmanager.getplugin("terminalreporter")
    tr.write_line(
        "RA4A_P1_REAL_PG_RECEIPT="
        + json.dumps(
            {
                "server_version": record["server_version"],
                "calls": len(_calls),
                "passed": sum(x["outcome"] == "passed" for x in _calls),
                "session_exit": int(exitstatus),
                "checkout": record["github_checkout"],
            },
            sort_keys=True,
        )
    )

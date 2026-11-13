"""Explicit P2B1-only real database fixtures and actual executed call evidence."""

import json
import os
import uuid
from pathlib import Path

import pytest
from psycopg import sql

from .p2b1_support import connect, graph, migrate_p2b1, register_graph, schema_sha256, seed_base

_calls = []


@pytest.fixture(scope="session", autouse=True)
def actual_v3():
    migrate_p2b1()
    migrate_p2b1()


@pytest.fixture
def isolated():
    seed_base()
    name = "vrae_p2b1_" + uuid.uuid4().hex[:12]
    with connect(dbname="postgres") as c:
        c.execute(sql.SQL("CREATE DATABASE {} TEMPLATE vrae_ra4a_p1").format(sql.Identifier(name)))
    try:
        with connect(dbname=name) as c:
            c.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(name)))
            c.execute(
                sql.SQL(
                    "GRANT CONNECT ON DATABASE {} TO ra4a_app,ra4a_worker,p2a_fixture_writer,p2b1_review"
                ).format(sql.Identifier(name))
            )
        register_graph(name, graph("404"))
        register_graph(name, graph("200"))
        with connect(dbname=name) as c:
            yield name, c
    finally:
        with connect(dbname="postgres") as c:
            c.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def pytest_runtest_logreport(report):
    if report.when == "call" and "/p2b1/" in report.nodeid:
        row = {"id": report.nodeid, "outcome": report.outcome}
        _calls.append(row)
        with (Path(os.environ["RA4A_P2B1_EVIDENCE_DIR"]) / "actual-calls.jsonl").open(
            "a", encoding="utf-8"
        ) as stream:
            stream.write(json.dumps(row) + "\n")


def pytest_sessionfinish(session, exitstatus):
    out = Path(os.environ["RA4A_P2B1_EVIDENCE_DIR"])
    with connect() as c:
        record = {
            "checkout": os.environ.get("GITHUB_SHA"),
            "session_exit": int(exitstatus),
            "calls": _calls,
            "server": c.execute("SELECT version()").fetchone()[0],
            "schema_sha256": schema_sha256(c),
            "migrations": c.execute(
                "SELECT version,sha256 FROM ra4a_private.migrations ORDER BY version"
            ).fetchall(),
            "roles": c.execute(
                "SELECT rolname,rolsuper,rolbypassrls,rolcanlogin,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname LIKE 'p2b1_%' OR rolname='ra4a_owner' ORDER BY rolname"
            ).fetchall(),
            "tables": c.execute(
                "SELECT relname,relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner) FROM pg_class WHERE relnamespace='ra4a_review_test'::regnamespace AND relkind='r' ORDER BY relname"
            ).fetchall(),
            "policies": c.execute(
                "SELECT tablename,qual,with_check FROM pg_policies WHERE schemaname='ra4a_review_test' ORDER BY tablename"
            ).fetchall(),
            "grants": c.execute(
                "SELECT grantee,table_name,privilege_type FROM information_schema.role_table_grants WHERE table_schema='ra4a_review_test' ORDER BY grantee,table_name,privilege_type"
            ).fetchall(),
            "constraints": c.execute(
                "SELECT conrelid::regclass::text,contype,pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace='ra4a_review_test'::regnamespace ORDER BY conname"
            ).fetchall(),
            "triggers": c.execute(
                "SELECT tgrelid::regclass::text,tgname,tgdeferrable,tginitdeferred FROM pg_trigger WHERE NOT tgisinternal AND tgrelid IN (SELECT oid FROM pg_class WHERE relnamespace='ra4a_review_test'::regnamespace) ORDER BY tgname"
            ).fetchall(),
            "functions": c.execute(
                "SELECT proname,prosecdef,pg_get_userbyid(proowner),proconfig,proacl::text FROM pg_proc WHERE pronamespace='ra4a_review_test'::regnamespace ORDER BY proname"
            ).fetchall(),
            "authority": "TEST_ONLY_SYNTHETIC_DECISIONS_NOT_HUMAN_APPROVAL",
            "native_human_approvals": 0,
            "share_grants": 0,
        }
    (out / "p2b1-catalog-and-calls.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    session.config.pluginmanager.getplugin("terminalreporter").write_line(
        "RA4A_P2B1_ACTUAL_RECEIPT="
        + json.dumps(
            {
                "calls": len(_calls),
                "passed": sum(c["outcome"] == "passed" for c in _calls),
                "session_exit": int(exitstatus),
                "checkout": record["checkout"],
                "native_approvals": 0,
                "share_grants": 0,
            }
        )
    )

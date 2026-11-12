"""Explicit P2A-only plugin; P1 collection and fixtures stay byte-for-byte."""

import json
import os
from pathlib import Path
import uuid

import pytest
from psycopg import sql

from .p2a_support import connect, migrate_p2a, seed_base

_calls = []


@pytest.fixture(scope="session", autouse=True)
def p2a_migration():
    migrate_p2a()
    migrate_p2a()
    from .p2a_support import graph
    import hashlib

    out = Path(os.environ["RA4A_P2A_EVIDENCE_DIR"]) / "independently-held"
    for case, version in [("404", 1), ("200", 1), ("404", 2)]:
        g = graph(case, version)
        folder = out / (case + "-v" + str(version))
        folder.mkdir(parents=True, exist_ok=False)
        (folder / "held.json").write_bytes(g.trust.held)
        (folder / "policy.json").write_bytes(g.trust.policy)
        (folder / "manifest.json").write_bytes(g.manifest)
        for artifact in g.artifacts:
            (folder / (artifact.kind + "-" + artifact.key + ".bin")).write_bytes(artifact.raw)
        fixture = (
            Path(__file__).resolve().parents[2] / "tests/reviewing/fixtures" / (case + ".json")
        )
        (folder / "fixture-provenance.json").write_text(
            json.dumps(
                {
                    "fixture": fixture.relative_to(Path(__file__).resolve().parents[2]).as_posix(),
                    "original_accepted_main": "e9ec1bd7f36a0446af14f04b66b71e4d45ebfb97",
                    "fixture_file_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
                    "version_2": "explicit synthetic new version via accepted native producer"
                    if version == 2
                    else None,
                    "artifact_ref": g.trust.artifact_ref,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


@pytest.fixture
def isolated():
    seed_base()
    name = "vrae_p2a_" + uuid.uuid4().hex[:12]
    with connect(dbname="postgres") as c:
        c.execute(sql.SQL("CREATE DATABASE {} TEMPLATE vrae_ra4a_p1").format(sql.Identifier(name)))
    try:
        with connect(dbname=name) as c:
            c.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(name)))
            c.execute(
                sql.SQL(
                    "GRANT CONNECT ON DATABASE {} TO ra4a_app,ra4a_worker,p2a_fixture_writer"
                ).format(sql.Identifier(name))
            )
            yield name, c
    finally:
        with connect(dbname="postgres") as c:
            c.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def pytest_runtest_logreport(report):
    if report.when == "call" and "/p2a/" in report.nodeid:
        _calls.append({"id": report.nodeid, "outcome": report.outcome})
        with (Path(os.environ["RA4A_P2A_EVIDENCE_DIR"]) / "actual-calls.jsonl").open(
            "a", encoding="utf-8"
        ) as stream:
            stream.write(json.dumps(_calls[-1]) + "\n")


def pytest_sessionfinish(session, exitstatus):
    out = Path(os.environ["RA4A_P2A_EVIDENCE_DIR"])
    with connect() as c:
        data = {
            "actual_calls": _calls,
            "session_exit": int(exitstatus),
            "checkout": os.environ.get("GITHUB_SHA"),
            "server": c.execute("SELECT version()").fetchone()[0],
            "migrations": c.execute(
                "SELECT * FROM ra4a_private.migrations ORDER BY version"
            ).fetchall(),
            "roles": c.execute(
                "SELECT rolname,rolsuper,rolbypassrls,rolcanlogin,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname LIKE 'p2a_%' OR rolname='ra4a_owner' ORDER BY rolname"
            ).fetchall(),
            "tables": c.execute(
                "SELECT relname,relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner) FROM pg_class JOIN pg_namespace n ON n.oid=relnamespace WHERE n.nspname='ra4a_bytes' AND relkind='r' ORDER BY relname"
            ).fetchall(),
            "policies": c.execute(
                "SELECT tablename,qual,with_check FROM pg_policies WHERE schemaname='ra4a_bytes' ORDER BY tablename"
            ).fetchall(),
            "constraints": c.execute(
                "SELECT conrelid::regclass::text,contype,pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace='ra4a_bytes'::regnamespace ORDER BY conname"
            ).fetchall(),
            "triggers": c.execute(
                "SELECT tgrelid::regclass::text,tgname,tgdeferrable,tginitdeferred FROM pg_trigger WHERE tgrelid IN (SELECT oid FROM pg_class WHERE relnamespace='ra4a_bytes'::regnamespace) AND NOT tgisinternal ORDER BY tgname"
            ).fetchall(),
            "grants": c.execute(
                "SELECT grantee,table_name,privilege_type FROM information_schema.role_table_grants WHERE table_schema='ra4a_bytes' ORDER BY grantee,table_name,privilege_type"
            ).fetchall(),
            "functions": c.execute(
                "SELECT proname,prosecdef,pg_get_userbyid(proowner),proconfig,proacl::text FROM pg_proc WHERE pronamespace='ra4a_bytes'::regnamespace ORDER BY proname"
            ).fetchall(),
            "native_approvals": 0,
            "share_grants": 0,
            "production_authority": False,
            "schema_sha256": __import__(
                "integration.ra4a.p2a_support", fromlist=["schema_sha256"]
            ).schema_sha256(c),
        }
    (out / "p2a-catalog-and-calls.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    session.config.pluginmanager.getplugin("terminalreporter").write_line(
        "RA4A_P2A_ACTUAL_CALLS="
        + json.dumps(
            {
                "calls": len(_calls),
                "passed": sum(r["outcome"] == "passed" for r in _calls),
                "session_exit": int(exitstatus),
                "checkout": data["checkout"],
            }
        )
    )

"""Real local P2B1 migrations, independent accepted byte graphs and fixture identities."""

import hashlib
import json
import secrets

from psycopg import sql

from tests.reviewing.synthetic import command
from vrae.persistence.private_bytes import locator, verify
from vrae.persistence.review_cas import TestOnlyReviewCAS

from .p2a_support import (
    graph,
    migrate_p2a,
    raw_args,
)
from .p2a_support import (
    schema_sha256 as p2a_schema_sha,
)
from .p2a_support import (
    seed_base as seed_p2a,
)
from .support import ROOT, STATE, connect

SCHEMA = "ra4a_review_test"
TABLES = ("states", "proposals", "claims", "sections", "audit", "outbox")
ROLES = ("p2b1_test_a_reviewer", "p2b1_test_a_peer", "p2b1_test_b_reviewer")
SQL3 = ROOT / "db/migrations/0003_ra4a_test_review_cas.sql"


def schema_sha256(c):
    queries = (
        "SELECT proname,pg_get_functiondef(oid),proacl::text FROM pg_proc WHERE pronamespace='ra4a_review_test'::regnamespace ORDER BY proname",
        "SELECT relname,relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner) FROM pg_class WHERE relnamespace='ra4a_review_test'::regnamespace AND relkind='r' ORDER BY relname",
        "SELECT conrelid::regclass::text,conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace='ra4a_review_test'::regnamespace ORDER BY conname",
        "SELECT pg_get_triggerdef(oid) FROM pg_trigger WHERE NOT tgisinternal AND tgrelid IN (SELECT oid FROM pg_class WHERE relnamespace='ra4a_review_test'::regnamespace) ORDER BY tgrelid::regclass::text,tgname",
        "SELECT tablename,qual,with_check FROM pg_policies WHERE schemaname='ra4a_review_test' ORDER BY tablename",
        "SELECT grantee,table_name,privilege_type FROM information_schema.role_table_grants WHERE table_schema='ra4a_review_test' ORDER BY grantee,table_name,privilege_type",
        "SELECT c.relname,a.attname,pg_get_expr(d.adbin,d.adrelid) FROM pg_attrdef d JOIN pg_attribute a ON a.attrelid=d.adrelid AND a.attnum=d.adnum JOIN pg_class c ON c.oid=d.adrelid WHERE c.relnamespace='ra4a_review_test'::regnamespace ORDER BY c.relname,a.attname",
    )
    return hashlib.sha256(
        json.dumps(
            [c.execute(q).fetchall() for q in queries], sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def verify_migrations(c):
    expected = [
        (
            v,
            hashlib.sha256(
                (ROOT / "db/migrations" / name).read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest(),
        )
        for v, name in (
            (1, "0001_ra4a_test_only.sql"),
            (2, "0002_ra4a_private_bytes.sql"),
            (3, "0003_ra4a_test_review_cas.sql"),
        )
    ]
    assert (
        c.execute("SELECT version,sha256 FROM ra4a_private.migrations ORDER BY version").fetchall()
        == expected
    ), "P2B1_MIGRATION_DRIFT"
    held = json.loads(STATE.read_text())
    assert p2a_schema_sha(c) == held["p2a_schema_sha256"], "P2B1_P2A_SCHEMA_DRIFT"
    assert schema_sha256(c) == held.get("p2b1_schema_sha256"), "P2B1_SCHEMA_DRIFT"


def migrate_p2b1():
    with connect() as c:
        present = c.execute("SELECT to_regclass('ra4a_private.migrations')").fetchone()[0]
        if (
            present
            and c.execute("SELECT 1 FROM ra4a_private.migrations WHERE version=3").fetchone()
        ):
            verify_migrations(c)
            return
    migrate_p2a()
    raw = SQL3.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(raw).hexdigest()
    state = json.loads(STATE.read_text())
    with connect() as c, c.transaction():
        c.execute(raw.decode())
        c.execute("INSERT INTO ra4a_private.migrations VALUES(3,%s)", (digest,))
        for role in ROLES:
            password = secrets.token_urlsafe(24)
            c.execute(
                sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
            state["runtime_passwords"][role] = password
        assert p2a_schema_sha(c) == state["p2a_schema_sha256"], "P2B1_CHANGED_P2A_SCHEMA"
        state["p2b1_schema_sha256"] = schema_sha256(c)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("P2B1_MIGRATION_0003_COMMITTED sha256=" + digest)


def seed_base():
    seed_p2a()
    with connect() as c:
        for role in ROLES:
            tenant = "tenant-beta" if role == "p2b1_test_b_reviewer" else "tenant-test"
            c.execute(
                "INSERT INTO ra4a_private.principals VALUES(%s,%s,'APP',true,'TEST_ONLY')",
                (role, tenant),
            )
            c.execute("INSERT INTO ra4a_private.assignments VALUES(%s,%s,true)", (role, tenant))
            for case in ("404", "200"):
                c.execute(
                    "INSERT INTO ra4a_review_test.assignments VALUES(%s,%s,%s,true,'TEST_ONLY')",
                    (tenant, locator(graph(case)).report, role),
                )


def register_graph(name, g):
    verify(g, provenance=g)
    with connect("p2a_test_a_writer", dbname=name) as c:
        c.execute("SELECT ra4a_bytes.register(%s,%s,%s,%s,%s,%s,%s)", raw_args(g))


def proposal(g=None, action="APPROVE_CANDIDATE", key="review-key-0001"):
    from vrae.reviewing import ReviewTarget

    return command(ReviewTarget((g or graph()).target), action=action, key=key)


def port(name, role="p2b1_test_a_reviewer"):
    c = connect(role, dbname=name)
    return c, TestOnlyReviewCAS(c, mode="TEST_ONLY_P2B1_REVIEW_CAS")


def submit(name, g=None, cmd=None, role="p2b1_test_a_reviewer"):
    g = graph() if g is None else g
    c, api = port(name, role)
    with c:
        return api.submit(locator(g), proposal(g) if cmd is None else cmd, provenance=g)


def args(g, cmd):
    from vrae.reviewing.canonical import COMMAND_LIMIT, canonical

    loc = locator(g)
    return (
        loc.tenant,
        loc.ref_id,
        loc.source_run,
        loc.report,
        loc.version,
        loc.target_digest,
        canonical(cmd.document, limit=COMMAND_LIMIT),
    )


def raw_submit(c, g, cmd):
    return bytes(
        c.execute("SELECT ra4a_review_test.submit(%s,%s,%s,%s,%s,%s,%s)", args(g, cmd)).fetchone()[
            0
        ]
    )


def counts(c):
    return {
        t: c.execute("SELECT count(*) FROM ra4a_review_test." + t).fetchone()[0] for t in TABLES
    }


def fingerprint(c):
    rows = {
        t: c.execute(
            "SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY to_jsonb(x)::text),'[]'::jsonb) FROM ra4a_review_test."
            + t
            + " x"
        ).fetchone()[0]
        for t in TABLES
    }
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


if __name__ == "__main__":
    migrate_p2b1()

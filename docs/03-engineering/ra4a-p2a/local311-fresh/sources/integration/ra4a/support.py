"""Test-only local PG connections, migration and independently replayed fixtures."""

from functools import lru_cache
import hashlib
import json
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from vrae.persistence.contracts import frozen_reference

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "infra/ra4a/.venv/lab-state.json"
SQL = ROOT / "db/migrations/0001_ra4a_test_only.sql"
TABLES = ("audit", "outbox", "jobs", "runs", "requests", "references", "policies", "tenants")


def connect(role="postgres", *, dbname=None):
    s = json.loads(STATE.read_text())
    assert s["host"] == "127.0.0.1" and s["dbname"] == "vrae_ra4a_p1"
    return psycopg.connect(
        host=s["host"],
        port=s["port"],
        dbname=dbname or s["dbname"],
        user=role,
        password=s["admin_password"] if role == "postgres" else s["runtime_passwords"][role],
        autocommit=True,
        connect_timeout=5,
    )


def migrate():
    raw = SQL.read_bytes().replace(b"\r\n", b"\n")
    sha = hashlib.sha256(raw).hexdigest()
    with connect() as c, c.transaction():
        present = c.execute("SELECT to_regclass('ra4a_private.migrations')").fetchone()[0]
        if present:
            assert c.execute(
                "SELECT sha256 FROM ra4a_private.migrations WHERE version=1"
            ).fetchone() == (sha,), "MIGRATION_DRIFT"
            return
        c.execute(raw.decode("utf-8"))
        c.execute("INSERT INTO ra4a_private.migrations VALUES(1,%s)", (sha,))
        s = json.loads(STATE.read_text())
        for role, password in s["runtime_passwords"].items():
            c.execute(
                sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
    print("REAL_PG16_MIGRATION_0001_COMMITTED sha256=" + sha)


@lru_cache(maxsize=1)
def references():
    # Merged accepted synthetic fixtures only; original source/Guard/HTML pins are
    # replayed, not rewritten or inferred from client-provided metadata.
    from tests.reviewing.synthetic import inputs

    result = []
    for case in ("404", "200"):
        i = inputs(case)
        result.append(
            frozen_reference("accepted-" + case, i.document, i.html, i.source, trust=i.trust)
        )
    return result


def reset(c):
    with c.transaction():
        c.execute("TRUNCATE " + ",".join("ra4a." + t for t in TABLES) + " CASCADE")
        c.execute("TRUNCATE ra4a_private.assignments,ra4a_private.principals CASCADE")
        for tenant in ("tenant-test", "tenant-beta"):
            c.execute("INSERT INTO ra4a.tenants(tenant_id) VALUES(%s)", (tenant,))
            c.execute(
                "INSERT INTO ra4a.policies VALUES(%s,'pol-001',1,'ALLOWED',clock_timestamp()+interval '1 day','SYNTHETIC_INTERNAL_ONLY')",
                (tenant,),
            )
        for suffix, tenant in [("a", "tenant-test"), ("b", "tenant-beta")]:
            for kind in ("app", "worker"):
                role = f"ra4a_test_{suffix}_{kind}"
                c.execute(
                    "INSERT INTO ra4a_private.principals VALUES(%s,%s,%s,true,'TEST_ONLY')",
                    (role, tenant, kind.upper()),
                )
                c.execute("INSERT INTO ra4a_private.assignments VALUES(%s,%s,true)", (role, tenant))
        c.execute(
            "INSERT INTO ra4a_private.principals VALUES('ra4a_test_unassigned','tenant-test','APP',true,'TEST_ONLY')"
        )
        for ref in references():
            keys = list(ref)
            values = [Jsonb(ref[k]) if k == "metadata" else ref[k] for k in keys]
            c.execute(
                sql.SQL("INSERT INTO ra4a.references ({}) VALUES ({})").format(
                    sql.SQL(",").join(map(sql.Identifier, keys)),
                    sql.SQL(",").join(sql.Placeholder() for _ in keys),
                ),
                values,
            )


if __name__ == "__main__":
    migrate()
    with connect() as connection:
        reset(connection)
        print(
            json.dumps(
                {
                    "real_server": connection.execute("SELECT version()").fetchone()[0],
                    "reference_target_digests": [r["target_digest"] for r in references()],
                }
            )
        )

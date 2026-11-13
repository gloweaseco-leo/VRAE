"""Only local isolated DBs; original main fixtures are held outside stored records."""

import hashlib
import json
import secrets

from psycopg import sql
from psycopg.types.json import Jsonb

from .support import connect, migrate, reset, STATE, ROOT
from vrae.persistence.contracts import frozen_reference
from vrae.persistence.private_bytes import assemble
from vrae.persistence.private_postgres import TestOnlyPrivateBytes
from tests.reviewing.synthetic import inputs

MIGRATION = ROOT / "db/migrations/0002_ra4a_private_bytes.sql"


def migrate_p2a():
    migrate()
    raw = MIGRATION.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(raw).hexdigest()
    state = json.loads(STATE.read_text())
    with connect() as c, c.transaction():
        previous = c.execute(
            "SELECT sha256 FROM ra4a_private.migrations WHERE version=2"
        ).fetchone()
        if previous:
            assert previous == (digest,), "P2A_MIGRATION_DRIFT"
            return
        c.execute(raw.decode())
        c.execute("INSERT INTO ra4a_private.migrations VALUES(2,%s)", (digest,))
        for role in ("p2a_test_a_writer", "p2a_test_b_writer"):
            password = secrets.token_urlsafe(24)
            c.execute(
                sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
            state["runtime_passwords"][role] = password
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("P2A_MIGRATION_0002_COMMITTED sha256=" + digest)


def graph(case="404", version=1):
    i = inputs(case, version)
    ref = "accepted-" + case + ("" if version == 1 else "-v" + str(version))
    return assemble(ref, i.document, i.html, i.source, trust=i.trust)


def seed_base():
    with connect() as c:
        reset(c)
        for role, tenant in (
            ("p2a_test_a_writer", "tenant-test"),
            ("p2a_test_b_writer", "tenant-beta"),
        ):
            c.execute(
                "INSERT INTO ra4a_private.principals VALUES(%s,%s,'APP',true,'TEST_ONLY')",
                (role, tenant),
            )
            c.execute("INSERT INTO ra4a_private.assignments VALUES(%s,%s,true)", (role, tenant))


def add_reference(c, case="404", version=2):
    i = inputs(case, version)
    ref = frozen_reference(graph(case, version).ref_id, i.document, i.html, i.source, trust=i.trust)
    keys = list(ref)
    c.execute(
        sql.SQL("INSERT INTO ra4a.references ({}) VALUES ({})").format(
            sql.SQL(",").join(map(sql.Identifier, keys)),
            sql.SQL(",").join(sql.Placeholder() for _ in keys),
        ),
        [Jsonb(ref[k]) if k == "metadata" else ref[k] for k in keys],
    )
    return graph(case, version)


def port(dbname, role):
    c = connect(role, dbname=dbname)
    return c, TestOnlyPrivateBytes(c, mode="TEST_ONLY_PRIVATE_BYTES_PG16")


def register(dbname, g=None):
    g = graph() if g is None else g
    c, api = port(dbname, "p2a_test_a_writer")
    with c:
        return api.register(g, provenance=g)


def read(dbname, g=None, role="ra4a_test_a_app"):
    from vrae.persistence.private_bytes import locator

    g = graph() if g is None else g
    c, api = port(dbname, role)
    with c:
        return api.read(locator(g), provenance=g)


def raw_args(g):
    from vrae.persistence.private_bytes import locator

    return (
        locator(g).tenant,
        g.ref_id,
        g.target,
        g.manifest,
        [a.kind for a in g.artifacts],
        [a.key for a in g.artifacts],
        [a.raw for a in g.artifacts],
    )


def counts(c):
    return tuple(
        c.execute("SELECT count(*) FROM ra4a_bytes." + t).fetchone()[0]
        for t in ("graphs", "objects", "events")
    )


if __name__ == "__main__":
    migrate_p2a()

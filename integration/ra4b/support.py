"""Trusted disposable bootstrap only; never imported by API or Worker."""

import json
from pathlib import Path
import secrets

from psycopg import sql

from integration.ra4a import support as old

ROOT = Path(__file__).resolve().parents[2]
ROLES = ("ra4b_test_a_app", "ra4b_test_b_app", "ra4b_test_a_worker", "ra4b_test_b_worker")


def migrate():
    from integration.ra4a.p2b1_support import migrate_p2b1
    migrate_p2b1()
    state = json.loads(old.STATE.read_bytes())
    with old.connect() as c, c.transaction():
        assert c.execute("SELECT to_regnamespace('ra4b_test')").fetchone()[0] is None
        c.execute((ROOT / "db/migrations/0004_ra4b_test_only_api.sql").read_text(encoding="utf-8"))
        for role in ROLES:
            password = secrets.token_urlsafe(32)
            c.execute(sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(role), sql.Literal(password)))
            state["runtime_passwords"][role] = password
    old.STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def seed():
    from integration.ra4a.p2b1_support import seed_base
    seed_base()
    with old.connect() as c:
        for role in ROLES:
            tenant = "tenant-beta" if "_b_" in role else "tenant-test"
            kind = "WORKER" if role.endswith("worker") else "APP"
            c.execute("INSERT INTO ra4a_private.principals VALUES(%s,%s,%s,true,'TEST_ONLY')", (role, tenant, kind))
            c.execute("INSERT INTO ra4a_private.assignments VALUES(%s,%s,true)", (role, tenant))


def config(kind="APP", suffix="a"):
    state = json.loads(old.STATE.read_bytes())
    role = "ra4b_test_" + suffix + "_" + kind.lower()
    return {"mode": "TEST_ONLY_RA4B_P1", "kind": kind, "role": role,
            "host": "127.0.0.1", "port": state["port"], "dbname": "vrae_ra4a_p1",
            "password": state["runtime_passwords"][role],
            "tenant": "tenant-beta" if suffix == "b" else "tenant-test",
            "sources": {r["ref_id"]: {"sha256": r["ref_sha256"], "policy_id": r["policy_id"],
                                       "policy_version": r["policy_version"]} for r in old.references()}}


def fingerprint(c):
    import hashlib
    data = [c.execute("SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]'::jsonb) FROM ra4a." + name + " t").fetchone()[0]
            for name in ("requests", "runs", "jobs", "audit", "outbox")]
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

"""Narrow function-only port into the ORIGINAL PG queue and target bindings."""

import json
from pathlib import Path
import os
import psycopg
from contracts.l2_launch.contract import Refused


def config(path, kind):
    p = Path(path)
    s = p.stat()
    if s.st_mode & 0o077 or s.st_uid != os.geteuid():
        raise ValueError("PRIVATE_CONFIG_REQUIRED")
    c = json.loads(p.read_bytes())
    if c["kind"] != kind or c["authority"] != "AUTHORIZED_TARGET_V1":
        raise ValueError("TARGET_CONFIG_REQUIRED")
    return c


def connect(binding):
    c = psycopg.connect(
        host="127.0.0.1",
        port=5432,
        dbname="vrae_ra4a_p1",
        user=binding["role"],
        password=binding["password"],
        autocommit=True,
        connect_timeout=2,
        options="-c statement_timeout=3000 -c lock_timeout=1500",
    )
    row = c.execute(
        "SELECT session_user,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,ra4a.scope() FROM pg_roles WHERE rolname=session_user"
    ).fetchone()
    if row != (binding["role"], False, False, False, False, binding["tenant_id"]):
        c.close()
        raise Refused("FORBIDDEN_ROLE")
    # Dynamic tenant roles get only their versioned function group, never raw
    # queue, source, artifact or original fixture writer table privileges.
    raw = c.execute(
        "SELECT count(*) FROM pg_class r JOIN pg_namespace n ON n.oid=r.relnamespace WHERE n.nspname IN ('ra4a','ra4a_private','target_v1') AND r.relkind='r' AND has_table_privilege(session_user,r.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE')"
    ).fetchone()[0]
    if raw:
        c.close()
        raise Refused("FORBIDDEN_ROLE")
    return c


def invoke(binding, name, *values):
    signatures = {
        "automatic_session": 3,
        "automatic_retry": 4,
        "submission_plan": 5,
        "source_context": 4,
        "readiness": 1,
        "make_return": 6,
        "exchange_return": 4,
        "exchange": 4,
        "session": 3,
        "plan": 4,
        "admit": 5,
        "status": 4,
        "load": 4,
        "commit": 5,
    }
    if name not in signatures or len(values) != signatures[name]:
        raise ValueError("NARROW_TARGET_PORT")
    with connect(binding) as c, c.transaction():
        if name == 'submission_plan' and not c.execute(
            "SELECT to_regprocedure('target_v1.submission_plan(text,text,text,text,text)') IS NOT NULL"
        ).fetchone()[0]:
            # Older controlled drills keep their accepted single-origin schema.
            name, values = 'plan', values[:4]
        return c.execute(
            "SELECT target_v1." + name + "(" + ",".join("%s" for _ in values) + ")", values
        ).fetchone()[0]


def claim(binding):
    with connect(binding) as c, c.transaction():
        return c.execute("SELECT * FROM ra4a.claim(%s,30)", (binding["tenant_id"],)).fetchone()


class WorkerPort:
    """One authenticated connection; each check sees a new committed snapshot."""

    def __init__(self, binding):
        self.binding = binding
        self.connection = connect(binding)

    def call(self, name, *values):
        if name not in ("load", "commit", "capture_failure"):
            raise ValueError("NARROW_WORKER_PORT")
        with self.connection.transaction():
            return self.connection.execute(
                "SELECT target_v1." + name + "(" + ",".join("%s" for _ in values) + ")", values
            ).fetchone()[0]

    def claim(self):
        with self.connection.transaction():
            return self.connection.execute(
                "SELECT * FROM ra4a.claim(%s,30)", (self.binding["tenant_id"],)
            ).fetchone()

    def close(self):
        self.connection.close()

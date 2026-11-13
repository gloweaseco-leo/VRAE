"""Trusted fixed-role connections to the additive, guarded B4 SQL seam."""

import json
import os
from pathlib import Path

import psycopg

from vrae.persistence.contracts import admission_payload

MODE = "TEST_ONLY_RA4B_P1"
AUTHORITY = "TEST_ONLY_PRIVATE_RUNTIME_NOT_HUMAN_APPROVAL"
ROLES = {"APP": {"ra4b_test_a_app", "ra4b_test_b_app"},
         "WORKER": {"ra4b_test_a_worker", "ra4b_test_b_worker"}}


def validate_binding(c):
    kind = c.get("kind")
    role = c.get("role")
    expected_tenant = "tenant-beta" if isinstance(role, str) and "_b_" in role else "tenant-test"
    if (c.get("mode") != MODE or kind not in ROLES or role not in ROLES[kind]
            or c.get("host") != "127.0.0.1" or c.get("dbname") != "vrae_ra4a_p1"
            or c.get("tenant") != expected_tenant or type(c.get("port")) is not int
            or not 1 <= c["port"] <= 65535
            or not isinstance(c.get("password"), str) or len(c["password"]) < 24):
        raise ValueError("RA4B_FIXED_TEST_PROVISIONING_REQUIRED")


def load_config(path, kind):
    path = Path(path)
    st = path.stat()
    if (os.environ.get("VRAE_RA4B_TEST_ONLY") != "1" or st.st_mode & 0o077
            or (hasattr(os, "geteuid") and st.st_uid != os.geteuid())):
        raise ValueError("RA4B_PRIVATE_TEST_CONFIG_REQUIRED")
    c = json.loads(path.read_bytes())
    validate_binding(c)
    if c["kind"] != kind:
        raise ValueError("RA4B_FIXED_TEST_PROVISIONING_REQUIRED")
    return c


def connect(config):
    validate_binding(config)
    c = psycopg.connect(host="127.0.0.1", port=config["port"], dbname="vrae_ra4a_p1",
                         user=config["role"], password=config["password"], autocommit=True,
                         connect_timeout=2, options="-c statement_timeout=2000 -c lock_timeout=1500")
    row = c.execute("SELECT session_user,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,"
                    "pg_has_role(session_user,'ra4a_app','MEMBER'),"
                    "pg_has_role(session_user,'ra4a_worker','MEMBER'),"
                    "current_setting('server_version_num')::int FROM pg_roles WHERE rolname=session_user").fetchone()
    if row is None or row[0] != config["role"] or any(row[1:7]) or not 160000 <= row[7] < 170000:
        c.close()
        raise ValueError("RA4B_RUNTIME_ROLE_DENIED")
    try:
        memberships = c.execute("SELECT rolname FROM pg_roles WHERE rolname<>session_user "
                                "AND pg_has_role(session_user,oid,'MEMBER') ORDER BY rolname").fetchall()
        if memberships != [("ra4b_" + config["kind"].lower(),)]:
            raise ValueError("RA4B_INHERITED_ROLE_DENIED")
        raw_row = c.execute("SELECT count(*) FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace "
                        "WHERE n.nspname IN ('ra4a','ra4a_private','ra4a_bytes','ra4a_review_test','ra4b_test') "
                        "AND t.relkind IN ('r','p','v','m','f') AND "
                        "has_table_privilege(session_user,t.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')").fetchone()
        if raw_row is None:
            raise ValueError("RA4B_RUNTIME_CATALOG_REQUIRED")
        raw = raw_row[0]
        allowed = {"APP": {"admit", "status"}, "WORKER": {"claim", "finish"}}[config["kind"]]
        functions = c.execute("SELECT n.nspname,p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                              "WHERE n.nspname IN ('ra4a','ra4a_private','ra4a_bytes','ra4a_review_test','ra4b_test') "
                              "AND has_function_privilege(session_user,p.oid,'EXECUTE')").fetchall()
        if raw or set(functions) != {("ra4b_test", name) for name in allowed}:
            raise ValueError("RA4B_RUNTIME_ACL_DENIED")
    except BaseException:
        c.close()
        raise
    return c


def admit(c, config, key, source_ref):
    binding = config["sources"].get(source_ref)
    if binding is None:
        raise ValueError("RA4B_SYNTHETIC_SOURCE_REQUIRED")
    raw, digest = admission_payload(source_ref, binding["sha256"])
    with c.transaction():
        row = c.execute("SELECT * FROM ra4b_test.admit(%s,%s,%s,%s,%s,%s)",
                        (config["tenant"], binding["policy_id"], binding["policy_version"],
                         key, digest, raw)).fetchone()
    return {"request_id": str(row[0]), "run_id": str(row[1]), "job_id": str(row[2]),
            "event_id": str(row[3]), "authority": AUTHORITY}


def status(c, config, request_id):
    with c.transaction():
        cursor = c.execute("SELECT * FROM ra4b_test.status(%s,%s)", (config["tenant"], request_id))
        row = cursor.fetchone()
        if row is None:
            return None
        result = {col.name: (str(value) if col.type_code == 2950 else value)
                  for col, value in zip(cursor.description, row)}
    return dict(result, authority=AUTHORITY, native_approval=None, share_grant=None)


def claim(c, config, seconds):
    with c.transaction():
        return c.execute("SELECT * FROM ra4b_test.claim(%s,%s)", (config["tenant"], seconds)).fetchone()


def finish(c, config, lease):
    with c.transaction():
        return c.execute("SELECT ra4b_test.finish(%s,%s,%s,%s)",
                         (config["tenant"], lease[0], lease[2], lease[3])).fetchone()[0]

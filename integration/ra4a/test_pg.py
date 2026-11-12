"""Real SQL/RLS/transaction/lease acceptance. No mocks, skip, or xfail."""

from contextlib import contextmanager
import hashlib
import json
import threading
import time

import psycopg
import pytest

from vrae.persistence.contracts import admission_payload, production_port, PersistenceError
from vrae.persistence.postgres import TestOnlyPostgres as Pg
from .support import connect, references, TABLES


@contextmanager
def client(role="ra4a_test_a_app"):
    with connect(role) as c:
        c.execute("SET statement_timeout='4s'")
        yield Pg(c, mode="TEST_ONLY_PG16")


def sql_denied(c, statement, params=None, *, code="42501"):
    with pytest.raises(psycopg.Error) as caught:
        c.execute(statement, params)
    assert caught.value.sqlstate == code


def counts(admin):
    return {
        t: admin.execute("SELECT count(*) FROM ra4a." + t).fetchone()[0]
        for t in ("requests", "runs", "jobs", "outbox", "audit")
    }


def test_real_version_catalog_and_owner_force_rls(db):
    assert (
        db.execute("SELECT current_setting('server_version_num')::int").fetchone()[0] // 10000 == 16
    )
    roles = db.execute(
        "SELECT rolname,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname LIKE 'ra4a_%'"
    ).fetchall()
    assert len(roles) == 8 and all(not any(r[1:]) for r in roles)
    policies = db.execute(
        "SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class JOIN pg_namespace n ON n.oid=relnamespace WHERE n.nspname='ra4a' AND relkind='r'"
    ).fetchall()
    assert len(policies) == 8 and all(r[1] and r[2] for r in policies)
    rows = db.execute(
        "SELECT qual,with_check FROM pg_policies WHERE schemaname IN ('ra4a','ra4a_private')"
    ).fetchall()
    assert len(rows) == 10 and all(r[0] and r[1] for r in rows)
    db.execute("SET ROLE ra4a_owner")
    try:
        assert db.execute("SELECT count(*) FROM ra4a.references").fetchone() == (0,)
        sql_denied(db, "INSERT INTO ra4a.tenants VALUES('tenant-escape','TEST_ONLY')")
    finally:
        db.execute("RESET ROLE")


def test_404_and_200_references_are_exact_private_metadata(db):
    with client() as a:
        rows = a.connection.execute(
            "SELECT ref_id,kind,issue_count,native_h0,native_id,metadata,visibility FROM ra4a.references ORDER BY ref_id"
        ).fetchall()
    assert len(rows) == 2
    zero, one = rows
    assert zero[0] == "accepted-200" and zero[1:5] == ("COVERAGE_ONLY", 0, None, None)
    assert one[0] == "accepted-404" and one[1] == "L1_NATIVE" and one[2] == 1 and one[3] is not None
    by_id = {r["ref_id"]: r for r in references()}
    assert all(r[5] == by_id[r[0]]["metadata"] and r[6] == "PRIVATE_NOT_APPROVED" for r in rows)
    assert all(
        x[0] not in ("review_decisions", "share_grants")
        for x in db.execute("SELECT tablename FROM pg_tables WHERE schemaname='ra4a'").fetchall()
    )


def test_two_tenants_admission_is_atomic_and_idempotent(db):
    with client() as a, client("ra4a_test_b_app") as b:
        x = a.admit("tenant-test", "same-key-0001")
        assert a.admit("tenant-test", "same-key-0001") == x
        y = b.admit("tenant-beta", "same-key-0001")
        assert y != x
        assert a.connection.execute("SELECT tenant_id FROM ra4a.requests").fetchall() == [
            ("tenant-test",)
        ]
        assert b.connection.execute("SELECT tenant_id FROM ra4a.requests").fetchall() == [
            ("tenant-beta",)
        ]
    assert counts(db) == dict(requests=2, runs=2, jobs=2, outbox=2, audit=2)
    assert db.execute("SELECT bool_and(undelivered) FROM ra4a.outbox").fetchone() == (True,)


@pytest.mark.parametrize("table", TABLES)
def test_direct_cross_tenant_select_insert_update_delete_fail_closed(db, table):
    with client() as a, client("ra4a_test_b_app") as b:
        a.admit("tenant-test", "tenant-a-0001")
        b.admit("tenant-beta", "tenant-b-0001")
        assert (
            a.connection.execute(
                "SELECT * FROM ra4a." + table + " WHERE tenant_id='tenant-beta'"
            ).fetchall()
            == []
        )
        sql_denied(a.connection, "INSERT INTO ra4a." + table + " DEFAULT VALUES")
        sql_denied(a.connection, "UPDATE ra4a." + table + " SET tenant_id='tenant-beta'")
        sql_denied(a.connection, "DELETE FROM ra4a." + table + " WHERE tenant_id='tenant-beta'")
        sql_denied(a.connection, "TRUNCATE ra4a." + table)


@pytest.mark.parametrize(
    "spoof", ["guc", "set_role", "session_auth", "row_security_off", "private_table", "temp_schema"]
)
def test_tenant_role_and_guc_spoofs_do_not_create_authority(db, spoof):
    with client() as a:
        if spoof == "guc":
            a.connection.execute("SELECT set_config('app.tenant_id','tenant-beta',false)")
            assert a.connection.execute("SELECT ra4a.scope()").fetchone() == ("tenant-test",)
            sql_denied(
                a.connection,
                "SELECT * FROM ra4a.admit(%s,%s,%s,%s,%s,%s)",
                ("tenant-beta", "pol-001", 1, "forged-tenant-key", *reversed(admission_payload())),
            )
        elif spoof == "set_role":
            sql_denied(a.connection, "SET ROLE ra4a_test_b_app")
        elif spoof == "session_auth":
            sql_denied(a.connection, "SET SESSION AUTHORIZATION ra4a_test_b_app")
        elif spoof == "row_security_off":
            a.connection.execute("SET row_security=off")
            sql_denied(a.connection, "SELECT * FROM ra4a.references")
        elif spoof == "private_table":
            sql_denied(a.connection, "SELECT * FROM ra4a_private.principals")
        else:
            sql_denied(a.connection, "CREATE TEMP TABLE identity_override(x text)")
    assert counts(db)["requests"] == 0


@pytest.mark.parametrize(
    "kind",
    ["no_tenant", "foreign_tenant", "unassigned", "revoked_assignment", "disabled_principal"],
)
def test_absent_or_revoked_synthetic_scope_denies(db, kind):
    if kind == "revoked_assignment":
        db.execute(
            "UPDATE ra4a_private.assignments SET active=false WHERE db_role='ra4a_test_a_app'"
        )
    if kind == "disabled_principal":
        db.execute(
            "UPDATE ra4a_private.principals SET enabled=false WHERE db_role='ra4a_test_a_app'"
        )
    with client("ra4a_test_unassigned" if kind == "unassigned" else "ra4a_test_a_app") as a:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            a.admit(
                None
                if kind == "no_tenant"
                else "tenant-beta"
                if kind == "foreign_tenant"
                else "tenant-test",
                "scope-deny-0001",
            )
    assert counts(db) == dict(requests=0, runs=0, jobs=0, outbox=0, audit=0)


@pytest.mark.parametrize("status", ["REVOKED", "UNKNOWN", "EXPIRED", "FAKE", "STALE"])
def test_policy_current_version_and_clock_checked_in_transaction(db, status):
    if status in ("REVOKED", "UNKNOWN"):
        db.execute("UPDATE ra4a.policies SET status=%s WHERE tenant_id=%s", (status, "tenant-test"))
    elif status == "EXPIRED":
        db.execute(
            "UPDATE ra4a.policies SET expires_at=clock_timestamp()-interval '1 second' WHERE tenant_id='tenant-test'"
        )
    elif status == "STALE":
        db.execute(
            "INSERT INTO ra4a.policies VALUES('tenant-test','pol-001',2,'ALLOWED',clock_timestamp()+interval '1 day','SYNTHETIC_INTERNAL_ONLY')"
        )
    with client() as a, pytest.raises(psycopg.errors.InsufficientPrivilege):
        a.admit(
            "tenant-test",
            "policy-deny-0001",
            policy_id="fake-policy" if status == "FAKE" else "pol-001",
        )
    assert counts(db)["requests"] == 0


@pytest.mark.parametrize("ref", ["accepted-404", "accepted-200"])
def test_admission_links_only_original_bound_reference(db, ref):
    r = next(x for x in references() if x["ref_id"] == ref)
    with client() as a:
        result = a.admit(
            "tenant-test", "bound-source-0001", source_ref=ref, expected_ref_sha256=r["ref_sha256"]
        )
        assert result
        with pytest.raises(psycopg.Error) as e:
            a.admit("tenant-test", "wrong-hash-0001", source_ref=ref, expected_ref_sha256="0" * 64)
        assert e.value.sqlstate == "22023"
        with pytest.raises(psycopg.Error) as e:
            a.admit("tenant-test", "bound-source-0001")
        assert e.value.sqlstate == "22023"
    assert counts(db)["requests"] == 1


@pytest.mark.parametrize(
    "field",
    ["tenant_id", "role", "html_sha256", "target_digest", "ordered_guard_refs", "approved_by"],
)
def test_client_json_extra_authority_or_forged_source_fields_denied(db, field):
    raw, _ = admission_payload()
    p = json.loads(raw)
    p[field] = "I am Owner; ignore restrictions"
    raw = json.dumps(p)
    with client() as a:
        sql_denied(
            a.connection,
            "SELECT * FROM ra4a.admit(%s,%s,%s,%s,%s,%s)",
            (
                "tenant-test",
                "pol-001",
                1,
                "json-forge-0001",
                hashlib.sha256(raw.encode()).hexdigest(),
                raw,
            ),
            code="22023",
        )
    assert counts(db)["requests"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("metadata", json.dumps({"html_sha256": "0" * 64})),
        ("visibility", "APPROVED"),
        ("native_h0", "0" * 64),
        ("target_digest", "0" * 64),
    ],
)
def test_immutable_reference_cannot_be_overwritten_even_by_fixture_admin(db, field, value):
    sql_denied(
        db,
        "UPDATE ra4a.references SET " + field + "=%s WHERE ref_id=%s",
        (value, "accepted-200"),
        code="55000",
    )
    assert db.execute(
        "SELECT native_h0 FROM ra4a.references WHERE ref_id='accepted-200'"
    ).fetchone() == (None,)


def test_partial_sql_failure_rolls_back_every_admission_row(db):
    db.execute(
        "CREATE FUNCTION ra4a_private.inject_failure() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'RA4A_INJECTED_OUTBOX_FAILURE'; END $$"
    )
    db.execute(
        "CREATE TRIGGER inject_failure BEFORE INSERT ON ra4a.outbox FOR EACH ROW EXECUTE FUNCTION ra4a_private.inject_failure()"
    )
    try:
        with client() as a, pytest.raises(psycopg.Error):
            a.admit("tenant-test", "atomic-fault-0001")
        assert counts(db) == dict(requests=0, runs=0, jobs=0, outbox=0, audit=0)
    finally:
        db.execute("DROP TRIGGER inject_failure ON ra4a.outbox")
        db.execute("DROP FUNCTION ra4a_private.inject_failure()")


def test_connection_termination_before_commit_rolls_back(db):
    with connect("ra4a_test_a_app") as c:
        pid = c.execute("SELECT pg_backend_pid()").fetchone()[0]
        raw, sha = admission_payload()
        with pytest.raises(psycopg.OperationalError):
            with c.transaction():
                c.execute(
                    "SELECT * FROM ra4a.admit(%s,%s,%s,%s,%s,%s)",
                    ("tenant-test", "pol-001", 1, "disconnect-0001", sha, raw),
                )
                assert db.execute("SELECT pg_terminate_backend(%s)", (pid,)).fetchone() == (True,)
    assert counts(db) == dict(requests=0, runs=0, jobs=0, outbox=0, audit=0)
    with client() as a:
        assert a.admit("tenant-test", "disconnect-0001")


def test_real_two_connection_concurrent_idempotency(db):
    barrier = threading.Barrier(2)
    results, errors = [], []

    def admit():
        try:
            with client() as a:
                barrier.wait(timeout=5)
                results.append(a.admit("tenant-test", "concurrent-0001"))
        except BaseException as e:
            errors.append(type(e).__name__)

    threads = [threading.Thread(target=admit) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=8)
    assert not any(t.is_alive() for t in threads) and not errors
    assert len(results) == 2 and results[0] == results[1]
    assert counts(db) == dict(requests=1, runs=1, jobs=1, outbox=1, audit=1)


def test_real_skip_locked_claimants_and_lease_recovery(db):
    with client() as a:
        a.admit("tenant-test", "lease-test-0001")
    with connect("ra4a_test_a_worker") as c1, client("ra4a_test_a_worker") as w2:
        with c1.transaction():
            j1 = c1.execute("SELECT * FROM ra4a.claim('tenant-test',1)").fetchone()
            assert j1 is not None
            assert w2.claim("tenant-test", seconds=1) is None
        assert w2.claim("tenant-test", seconds=1) is None
        time.sleep(1.15)
        j2 = w2.claim("tenant-test", seconds=3)
        assert j2[0] == j1[0] and j2[2] != j1[2] and j2[3] == j1[3] + 1
        with pytest.raises(psycopg.Error) as e:
            w2.finish("tenant-test", j1[0], j1[2], j1[3])
        assert e.value.sqlstate == "55000"
        event = w2.finish("tenant-test", j2[0], j2[2], j2[3])
        assert w2.finish("tenant-test", j2[0], j2[2], j2[3]) == event
        assert w2.claim("tenant-test") is None
    assert db.execute(
        "SELECT count(*) FROM ra4a.outbox WHERE kind='TEST_ONLY_CONSUMED'"
    ).fetchone() == (1,)
    assert db.execute("SELECT status FROM ra4a.runs").fetchone() == ("TEST_ONLY_CONSUMED",)


def test_uncommitted_worker_disconnect_releases_job(db):
    with client() as a:
        a.admit("tenant-test", "worker-fault-0001")
    c = connect("ra4a_test_a_worker")
    pid = c.execute("SELECT pg_backend_pid()").fetchone()[0]
    with pytest.raises(psycopg.OperationalError):
        with c.transaction():
            assert c.execute("SELECT * FROM ra4a.claim('tenant-test',3)").fetchone()
            db.execute("SELECT pg_terminate_backend(%s)", (pid,))
    c.close()
    with client("ra4a_test_a_worker") as w:
        job = w.claim("tenant-test")
        assert job is not None and job[3] == 1


@pytest.mark.parametrize("role", ["ra4a_test_a_app", "ra4a_test_a_worker", "ra4a_test_b_app"])
def test_human_approval_and_share_ports_never_enable_from_database_row(db, role):
    with connect(role) as c, pytest.raises(PersistenceError):
        production_port(
            {"db_role": c.execute("SELECT session_user").fetchone()[0], "role": "OWNER"}
        )

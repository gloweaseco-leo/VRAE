"""Additional byte-seal, provenance and mid-transaction attack probes."""

import json
import threading
import time

import psycopg
import pytest

from .cases import change, denied, raw_register
from ..p2a_support import connect, counts, graph, read, register
from vrae.persistence.contracts import PersistenceError
from vrae.persistence.private_bytes import verify
from vrae.reviewing import ReviewError
from vrae.reviewing.canonical import SOURCE_LIMIT, canonical


@pytest.mark.parametrize(
    "attack", ["quote", "byte_range", "renderer_version", "extra_claim", "APPROVED", "zero_finding"]
)
def test_semantic_forgery_rejected_by_full_provenance_and_sql(isolated, attack):
    name, admin = isolated
    g = graph("200" if attack == "zero_finding" else "404")

    def alter(raw):
        d = json.loads(raw)
        if attack == "quote":
            d["issues"][0]["fact_claim"]["fact"]["source"]["quote"] = (
                "Forged ISO 9001 certification"
            )
        elif attack == "byte_range":
            d["issues"][0]["fact_claim"]["fact"]["source"]["byte_start"] += 1
        elif attack == "renderer_version":
            d["renderer_version"] = "forged-renderer"
        elif attack == "extra_claim":
            d["positive_source_claims"].append({"fictional_sales_loss": 100000})
        elif attack == "APPROVED":
            d["approval_status"] = "APPROVED"
        else:
            d["issues"] = [{"fictional_finding": True}]
        return canonical(d, limit=SOURCE_LIMIT)

    bad = change(g, "DRAFT", alter)
    with pytest.raises((PersistenceError, ReviewError)):
        verify(bad, provenance=g)
    with connect("p2a_test_a_writer", dbname=name) as c, pytest.raises(psycopg.Error):
        raw_register(c, bad)
    assert counts(admin) == (0, 0, 0)


def test_sealed_graph_cannot_append_and_fk_is_tenant_bound(isolated):
    name, admin = isolated
    register(name)
    denied(
        admin,
        "INSERT INTO ra4a_bytes.objects(tenant_id,source_run_id,report_id,report_version,kind,object_key,raw) "
        "VALUES('tenant-test','run-ra3b-404base','report-ra3c-404',1,'SOURCE_OBJECT','extra',decode('00','hex'))",
        code="55000",
    )
    denied(
        admin,
        "INSERT INTO ra4a_bytes.objects(tenant_id,source_run_id,report_id,report_version,kind,object_key,raw) "
        "VALUES('tenant-beta','run-ra3b-404base','report-ra3c-404',1,'SOURCE_OBJECT','extra',decode('00','hex'))",
        code="23503",
    )
    admin.execute("SET ROLE ra4a_owner")
    try:
        assert admin.execute("SELECT count(*) FROM ra4a_bytes.objects").fetchone() == (0,)
    finally:
        admin.execute("RESET ROLE")
    assert read(name) == graph()


@pytest.mark.parametrize("drift", ["migration_hash", "schema_function"])
def test_migration_reapply_refuses_ledger_and_real_schema_drift(isolated, drift):
    from ..p2a_support import verify_migrations

    _, admin = isolated
    verify_migrations(admin)
    if drift == "migration_hash":
        admin.execute("UPDATE ra4a_private.migrations SET sha256='0' WHERE version=2")
    else:
        admin.execute(
            "ALTER FUNCTION ra4a_bytes.read_graph(text,text,text,text,integer,text) SET search_path=public"
        )
    with pytest.raises(AssertionError, match="P2A_.*DRIFT"):
        verify_migrations(admin)


def test_no_native_approval_share_export_or_production_role(isolated):
    from vrae.persistence.private_bytes import production_store_port

    name, admin = isolated
    register(name, graph("200"))
    with connect("ra4a_test_a_app", dbname=name) as c:
        denied(c, "SELECT ra4a_bytes.approve_version()", code="42883")
        denied(c, "SELECT ra4a_bytes.check_share()", code="42883")
        denied(c, "SELECT ra4a_bytes.export()", code="42883")
        denied(c, "UPDATE ra4a_bytes.graphs SET visibility='APPROVED'")
        denied(c, "CREATE ROLE actual_reviewer")
    with pytest.raises(PersistenceError):
        production_store_port(actor={"db_role": "p2a_test_a_writer"}, operation="APPROVE")
    assert counts(admin)[0] == counts(admin)[2] == 1
    with connect("p2a_test_b_writer", dbname=name) as c, pytest.raises(psycopg.Error):
        raw_register(c, graph())


def test_connection_death_mid_multi_object_function_leaves_no_partial_target(isolated):
    name, admin = isolated
    admin.execute(
        "CREATE FUNCTION ra4a_bytes.fault_pause() RETURNS trigger LANGUAGE plpgsql AS $$"
        "BEGIN IF NEW.kind='HTML' THEN PERFORM pg_sleep(20); END IF; RETURN NEW; END $$"
    )
    admin.execute(
        "CREATE TRIGGER fault_pause BEFORE INSERT ON ra4a_bytes.objects FOR EACH ROW "
        "EXECUTE FUNCTION ra4a_bytes.fault_pause()"
    )
    ready = threading.Event()
    result = []
    pid = []

    def write():
        try:
            with connect("p2a_test_a_writer", dbname=name) as c:
                pid.append(c.execute("SELECT pg_backend_pid()").fetchone()[0])
                ready.set()
                raw_register(c, graph())
            result.append("UNEXPECTED_COMMIT")
        except psycopg.Error:
            result.append("terminated")

    thread = threading.Thread(target=write, daemon=True)
    thread.start()
    assert ready.wait(10)
    try:
        for _ in range(100):
            state = admin.execute(
                "SELECT wait_event FROM pg_stat_activity WHERE pid=%s", (pid[0],)
            ).fetchone()
            if state and state[0] == "PgSleep":
                break
            time.sleep(0.05)
        else:
            raise AssertionError("No actual mid-object pause observed")
        assert counts(admin) == (0, 0, 0)
    finally:
        admin.execute("SELECT pg_terminate_backend(%s)", (pid[0],))
        thread.join(10)
    assert result == ["terminated"] and not thread.is_alive()
    assert counts(admin) == (0, 0, 0)
    admin.execute("DROP TRIGGER fault_pause ON ra4a_bytes.objects")
    register(name)
    assert read(name) == graph()

"""Actual source-authority epochs and two-connection lock/commit interleavings."""

import hashlib
import json
import os
from pathlib import Path
import threading
import time

import psycopg
import pytest

from integration.ra4a import support as old
from integration.ra4b.security_cases import admitted, leased
from integration.ra4b.support import config, fingerprint, seed
from vrae.application.ra4b import store

APP = "ra4b_test_a_app"


@pytest.fixture
def db():
    seed()
    with old.connect() as c:
        yield c


def version(c):
    return c.execute("SELECT epoch FROM ra4b_test.origin_epochs WHERE tenant_id='tenant-test' AND origin_role=%s", (APP,)).fetchone()[0]


def source_fingerprint(c):
    rows = [c.execute("SELECT * FROM ra4a_private.principals WHERE db_role=%s", (APP,)).fetchall(),
            c.execute("SELECT * FROM ra4a_private.assignments WHERE db_role=%s", (APP,)).fetchall()]
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def change(c, mutation):
    if mutation in ("disabled", "cycle"):
        c.execute("UPDATE ra4a_private.principals SET enabled=false WHERE db_role=%s", (APP,))
        if mutation == "cycle":
            c.execute("UPDATE ra4a_private.principals SET enabled=true WHERE db_role=%s", (APP,))
    elif mutation == "assignment":
        c.execute("UPDATE ra4a_private.assignments SET active=false WHERE db_role=%s", (APP,))
    elif mutation == "tenant":
        c.execute("UPDATE ra4a_private.assignments SET tenant_id='tenant-beta' WHERE db_role=%s", (APP,))
    elif mutation == "replacement":
        c.execute("DELETE FROM ra4a_private.assignments WHERE db_role=%s", (APP,))
        c.execute("DELETE FROM ra4a_private.principals WHERE db_role=%s", (APP,))
        c.execute("INSERT INTO ra4a_private.principals VALUES(%s,'tenant-test','APP',true,'TEST_ONLY')", (APP,))
        c.execute("INSERT INTO ra4a_private.assignments VALUES(%s,'tenant-test',true)", (APP,))
    else:
        c.execute("TRUNCATE ra4a_private.assignments")
        # Re-enable only Worker. Origin APP remains unassigned: old work must deny.
        c.execute("INSERT INTO ra4a_private.assignments VALUES('ra4b_test_a_worker','tenant-test',true)")


@pytest.mark.parametrize("stage", ["claim", "finish"])
@pytest.mark.parametrize("mutation", ["disabled", "cycle", "assignment", "tenant", "replacement", "truncate"])
def test_origin_changes_invalidate_old_task(db, stage, mutation):
    if stage == "claim":
        cfg, receipt = admitted()
        worker, lease = config("WORKER"), None
    else:
        cfg, receipt, worker, lease = leased()
    original = version(db)
    change(db, mutation)
    current = version(db)
    assert current > original
    before = fingerprint(db)
    with store.connect(worker) as c, pytest.raises(psycopg.errors.InsufficientPrivilege) as caught:
        store.claim(c, worker, 5) if stage == "claim" else store.finish(c, worker, lease)
    assert caught.value.sqlstate == "42501" and fingerprint(db) == before and version(db) == current
    if mutation in ("cycle", "replacement"):
        # Current APP is valid again, but retry cannot overwrite the immutable
        # original binding. A new admission obtains only the new version.
        with store.connect(cfg) as c:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                store.admit(c, cfg, "b4-key-0001", "accepted-404")
            fresh = store.admit(c, cfg, "b4-regrant-new-0001", "accepted-404")
        assert fresh["request_id"] != receipt["request_id"]
        assert db.execute("SELECT epoch FROM ra4b_test.request_origins WHERE request_id=%s", (fresh["request_id"],)).fetchone()[0] == current


def wait_blocked(admin, pid, blocker):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if blocker in admin.execute("SELECT pg_blocking_pids(%s)", (pid,)).fetchone()[0]:
            return
        time.sleep(0.02)
    raise AssertionError("ACTUAL_PG_LOCK_WAIT_NOT_OBSERVED")


@pytest.mark.parametrize("stage", ["claim", "finish"])
@pytest.mark.parametrize("first,rollback", [("worker", False), ("admin", False), ("admin", True)])
def test_actual_origin_revoke_serial_order(db, stage, first, rollback):
    if stage == "claim":
        admitted()
        worker, lease = config("WORKER"), None
    else:
        _, _, worker, lease = leased()
    initial = version(db)
    initial_source = source_fingerprint(db)
    baseline = fingerprint(db)
    worker_conn = store.connect(worker)
    admin = old.connect()
    worker_pid, admin_pid = worker_conn.info.backend_pid, admin.info.backend_pid
    events, errors, ready = [], [], threading.Event()

    def operation():
        return store.claim(worker_conn, worker, 10) if stage == "claim" else store.finish(worker_conn, worker, lease)

    def other():
        ready.set()
        try:
            if first == "worker":
                change(admin, "disabled")
                events.append("admin_commit")
            else:
                operation()
                events.append("worker_commit")
        except psycopg.Error as e:
            errors.append(e.sqlstate)

    try:
        if first == "worker":
            with worker_conn.transaction():
                committed_receipt = operation()
                thread = threading.Thread(target=other)
                thread.start()
                assert ready.wait(3)
                wait_blocked(db, admin_pid, worker_pid)
                assert not events and not errors
            events.append("worker_commit")
            thread.join(5)
            # The marker append races with the unlocked admin thread; actual
            # blocking established the commit order, not Python list timing.
            assert "admin_commit" in events and not errors
            assert version(db) > initial
            after_revoke = fingerprint(db)
            if stage == "claim":
                # An already-held lease has no eligible second claim. The
                # authority boundary is finishing that committed original lease.
                assert operation() is None
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    store.finish(worker_conn, worker, committed_receipt)
            else:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    operation()
            assert fingerprint(db) == after_revoke
        else:
            try:
                with admin.transaction():
                    change(admin, "disabled")
                    thread = threading.Thread(target=other)
                    thread.start()
                    assert ready.wait(3)
                    wait_blocked(db, worker_pid, admin_pid)
                    assert not events and not errors
                    if rollback:
                        raise RuntimeError("TEST_ADMIN_ROLLBACK")
                events.append("admin_commit")
            except RuntimeError as e:
                assert rollback and str(e) == "TEST_ADMIN_ROLLBACK"
                events.append("admin_rollback")
            thread.join(5)
            if rollback:
                assert not errors and "worker_commit" in events and version(db) == initial
                assert db.execute("SELECT enabled FROM ra4a_private.principals WHERE db_role=%s", (APP,)).fetchone() == (True,)
            else:
                assert errors == ["42501"] and version(db) > initial
                assert fingerprint(db) == baseline
        assert not thread.is_alive()
        path = Path(os.environ["RA4B_EVIDENCE_DIR"])
        (path / f"epoch-order-{stage}-{first}-{rollback}.json").write_text(json.dumps({
            "first_lock_holder": first, "stage": stage, "admin_rollback": rollback,
            "actual_pg_blocking_pids_observed": True, "events": events, "sqlstates": errors,
            "before_epoch": initial, "after_epoch": version(db),
            "before_source_sha256": initial_source, "after_source_sha256": source_fingerprint(db),
            "denied_worker_left_business_unchanged": fingerprint(db) == baseline if first == "admin" and not rollback else None}, indent=2))
    finally:
        worker_conn.close()
        admin.close()


def test_epoch_initialization_monotonicity_and_no_runtime_projection_writes(db):
    cfg, receipt = admitted()
    start = version(db)
    with store.connect(cfg) as c:
        assert store.admit(c, cfg, "b4-key-0001", "accepted-404")["request_id"] == receipt["request_id"]
    assert version(db) == start
    for query in ("DELETE FROM ra4b_test.origin_epochs", "TRUNCATE ra4b_test.origin_epochs",
                  "UPDATE ra4b_test.origin_epochs SET epoch=epoch-1"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute(query)
    assert version(db) == start
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        db.execute("UPDATE ra4b_test.request_origins SET epoch=epoch+1")


def test_source_and_epoch_rollback_are_one_transaction(db):
    admitted()
    original = version(db)
    with pytest.raises(RuntimeError):
        with db.transaction():
            change(db, "cycle")
            assert version(db) > original
            raise RuntimeError("ROLLBACK_SOURCE_AND_EPOCH")
    assert version(db) == original
    with store.connect(config("WORKER")) as c:
        assert store.claim(c, config("WORKER"), 5)


@pytest.mark.parametrize("missing", [True, False])
def test_privileged_malformed_origin_fixture_cannot_be_consumed(db, missing):
    _, receipt, worker, lease = leased()
    with store.connect(worker) as c:
        store.finish(c, worker, lease)
    # Explicit privileged corruption fixture, never an authenticated admission.
    request = db.execute("INSERT INTO ra4a.requests(tenant_id,principal,idempotency_key,payload_hash,canonical_payload,policy_id,policy_version,source_ref) "
                         "SELECT tenant_id,principal,'corrupt-origin-0001',payload_hash,canonical_payload,policy_id,policy_version,source_ref "
                         "FROM ra4a.requests WHERE request_id=%s RETURNING tenant_id,request_id", (receipt["request_id"],)).fetchone()
    run = db.execute("INSERT INTO ra4a.runs(tenant_id,request_id,status) VALUES(%s,%s,'QUEUED') RETURNING run_id", request).fetchone()[0]
    db.execute("INSERT INTO ra4a.jobs(tenant_id,run_id) VALUES(%s,%s)", (request[0], run))
    if not missing:
        db.execute("INSERT INTO ra4b_test.request_origins VALUES(%s,%s,%s,%s)", (*request, APP, version(db) + 100))
    before = fingerprint(db)
    with store.connect(worker) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
        store.claim(c, worker, 5)
    assert fingerprint(db) == before


@pytest.mark.parametrize("stage", ["claim", "finish"])
def test_disabled_worker_cannot_use_epoch_projection(db, stage):
    if stage == "claim":
        admitted()
        worker, lease = config("WORKER"), None
    else:
        _, _, worker, lease = leased()
    db.execute("UPDATE ra4a_private.principals SET enabled=false WHERE db_role=%s", (worker["role"],))
    before = fingerprint(db)
    with store.connect(worker) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
        store.claim(c, worker, 5) if stage == "claim" else store.finish(c, worker, lease)
    assert fingerprint(db) == before


def test_guc_and_role_spoof_do_not_change_session_scope(db):
    admitted()
    worker = config("WORKER")
    with store.connect(worker) as c:
        c.execute("SET app.tenant_id='tenant-beta'")
        c.execute("SET app.role='postgres'")
        assert c.execute("SELECT session_user").fetchone() == (worker["role"],)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("SET ROLE ra4a_owner")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("SELECT * FROM ra4b_test.claim('tenant-beta',5)")
        assert store.claim(c, worker, 5)


@pytest.mark.parametrize("phase", ["claim", "finish"])
def test_two_workers_concurrent_claim_or_exact_finish(db, phase):
    if phase == "claim":
        admitted()
        worker, lease = config("WORKER"), None
    else:
        _, _, worker, lease = leased()
    connections = [store.connect(worker), store.connect(worker)]
    pids = [c.info.backend_pid for c in connections]
    results, errors, graph = [], [], {}

    def run(c):
        try:
            results.append(store.claim(c, worker, 10) if phase == "claim" else store.finish(c, worker, lease))
        except psycopg.Error as e:
            errors.append(e.sqlstate)

    try:
        with old.connect() as gate, gate.transaction():
            gate.execute("SELECT 1 FROM ra4a.tenants WHERE tenant_id='tenant-test' FOR UPDATE")
            threads = [threading.Thread(target=run, args=(c,)) for c in connections]
            for thread in threads:
                thread.start()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                waiting = db.execute("SELECT pid,wait_event_type,pg_blocking_pids(pid) FROM pg_stat_activity WHERE pid=ANY(%s)", (pids,)).fetchall()
                if len(waiting) == 2 and all(r[1] == "Lock" and r[2] for r in waiting):
                    graph = {str(r[0]): r[2] for r in waiting}
                    break
                time.sleep(0.02)
            assert graph and not results and not errors
        for thread in threads:
            thread.join(5)
            assert not thread.is_alive()
        assert not errors and len(results) == 2
        if phase == "claim":
            assert sum(result is None for result in results) == 1
            assert db.execute("SELECT attempts,lease_seq,state FROM ra4a.jobs").fetchone() == (1, 1, "LEASED")
        else:
            assert results[0] == results[1]
            assert db.execute("SELECT count(*) FROM ra4a.outbox WHERE kind='TEST_ONLY_CONSUMED'").fetchone() == (1,)
            assert db.execute("SELECT count(*) FROM ra4a.audit WHERE action='TEST_ONLY_CONSUMED'").fetchone() == (1,)
        (Path(os.environ["RA4B_EVIDENCE_DIR"]) / ("two-workers-" + phase + ".json")).write_text(json.dumps({
            "phase": phase, "distinct_actual_worker_backends": pids, "actual_lock_graph": graph,
            "sqlstates": errors, "source_sha256": source_fingerprint(db), "epoch": version(db),
            "one_lease_or_exact_same_finish_receipt": True}, indent=2))
    finally:
        for c in connections:
            c.close()


@pytest.mark.parametrize("legacy_state", ["pending", "exhausted"])
def test_b4_cannot_advance_legacy_queue_rows(db, legacy_state):
    from vrae.persistence.postgres import TestOnlyPostgres as Legacy
    # Controller-only legacy fixtures; B4 API/Worker never receive these credentials.
    with old.connect("ra4a_test_a_app") as c:
        Legacy(c, mode="TEST_ONLY_PG16").admit("tenant-test", "legacy-boundary-0001")
    if legacy_state == "exhausted":
        with old.connect("ra4a_test_a_worker") as c:
            old_worker = Legacy(c, mode="TEST_ONLY_PG16")
            for _ in range(3):
                assert old_worker.claim("tenant-test", seconds=1)
                time.sleep(1.1)
    before = fingerprint(db)
    worker = config("WORKER")
    with store.connect(worker) as c, pytest.raises(psycopg.errors.InsufficientPrivilege) as caught:
        store.claim(c, worker, 5)
    assert caught.value.sqlstate == "42501" and fingerprint(db) == before

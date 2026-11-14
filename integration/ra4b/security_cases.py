"""Actual PG current-authority, narrow ACL and commit-bound regression matrix."""

import threading
import time

import psycopg
import pytest

from integration.ra4a import support as old
from integration.ra4b.support import ROLES, config, fingerprint, seed
from vrae.application.ra4b import store
from vrae.persistence.contracts import admission_payload


@pytest.fixture
def db():
    seed()
    with old.connect() as c:
        yield c


def admitted():
    cfg = config()
    with store.connect(cfg) as c:
        receipt = store.admit(c, cfg, "b4-key-0001", "accepted-404")
    return cfg, receipt


def leased(seconds=10):
    cfg, receipt = admitted()
    worker = config("WORKER")
    with store.connect(worker) as c:
        lease = store.claim(c, worker, seconds)
    assert lease is not None
    return cfg, receipt, worker, lease


@pytest.mark.parametrize("role", ROLES)
def test_narrow_catalog_and_real_raw_denials(db, role):
    kind = "WORKER" if role.endswith("worker") else "APP"
    cfg = config(kind, "b" if "_b_" in role else "a")
    with store.connect(cfg) as c:
        for table in ("ra4a.requests", "ra4a.jobs", "ra4a.policies", "ra4a.references",
                      "ra4a_private.principals", "ra4a_bytes.graphs", "ra4a_review_test.proposals",
                      "ra4b_test.origin_epochs", "ra4b_test.request_origins"):
            oid = db.execute("SELECT %s::regclass::oid", (table,)).fetchone()[0]
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                assert c.execute("SELECT has_table_privilege(session_user,%s::oid,%s)", (oid, privilege)).fetchone()[0] is False
            for query in ("SELECT * FROM " + table, "DELETE FROM " + table,
                          "UPDATE " + table + " SET tenant_id=tenant_id", "TRUNCATE " + table):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    c.execute(query)
        oid = db.execute("SELECT 'ra4a.finish(text,uuid,uuid,integer)'::regprocedure::oid").fetchone()[0]
        assert not c.execute("SELECT has_function_privilege(session_user,%s::oid,'EXECUTE')", (oid,)).fetchone()[0]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("SELECT ra4a.finish('tenant-test',gen_random_uuid(),gen_random_uuid(),1)")
    # Owner explicitly retained this legacy debt, not globally hardened it.
    assert db.execute("SELECT has_table_privilege('ra4a_test_a_worker','ra4a.jobs','SELECT')").fetchone()[0]


@pytest.mark.parametrize("ref,count", [("accepted-404", 1), ("accepted-200", 0)])
def test_durable_receipt_status_and_idempotency(db, ref, count):
    cfg = config()
    with store.connect(cfg) as c:
        receipt = store.admit(c, cfg, "same-key-0001", ref)
        assert store.admit(c, cfg, "same-key-0001", ref) == receipt
        row = store.status(c, cfg, receipt["request_id"])
        assert row["issue_count"] == count and row["status"] == "QUEUED"
        assert row["native_approval"] is row["share_grant"] is None
        before = fingerprint(db)
        other = "accepted-200" if count else "accepted-404"
        with pytest.raises(psycopg.errors.InvalidParameterValue):
            store.admit(c, cfg, "same-key-0001", other)
        assert fingerprint(db) == before
    assert db.execute("SELECT count(*) FROM ra4a.requests").fetchone()[0] == 1


@pytest.mark.parametrize("mutation", ["revoked", "expired", "version", "source", "worker", "origin"])
def test_finish_current_authority_denied_without_advancement(db, mutation):
    _, _, worker, lease = leased()
    if mutation == "revoked":
        db.execute("UPDATE ra4a.policies SET status='REVOKED'")
    elif mutation == "expired":
        db.execute("UPDATE ra4a.policies SET expires_at=clock_timestamp()-interval '1 second'")
    elif mutation == "version":
        db.execute("INSERT INTO ra4a.policies VALUES('tenant-test','pol-001',2,'ALLOWED',clock_timestamp()+interval '1 day','SYNTHETIC_INTERNAL_ONLY')")
    elif mutation == "source":
        from integration.ra4a.p2a_support import add_reference
        add_reference(db, "404", 2)
    elif mutation == "worker":
        db.execute("UPDATE ra4a_private.assignments SET active=false WHERE db_role='ra4b_test_a_worker'")
    else:
        db.execute("UPDATE ra4a_private.principals SET enabled=false WHERE db_role='ra4b_test_a_app'")
    before = fingerprint(db)
    with store.connect(worker) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
        store.finish(c, worker, lease)
    assert fingerprint(db) == before


def test_expiry_during_open_finish_transaction_rolls_back(db):
    _, _, worker, lease = leased()
    db.execute("UPDATE ra4a.policies SET expires_at=clock_timestamp()+interval '700 milliseconds'")
    before = fingerprint(db)
    with store.connect(worker) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with c.transaction():
                assert store.finish(c, worker, lease)
                time.sleep(0.9)
    assert fingerprint(db) == before


def test_expiry_during_open_admission_transaction_rolls_back(db):
    cfg = config()
    db.execute("UPDATE ra4a.policies SET expires_at=clock_timestamp()+interval '700 milliseconds'")
    before = fingerprint(db)
    with store.connect(cfg) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
        with c.transaction():
            store.admit(c, cfg, "b4-expiring-0001", "accepted-404")
            time.sleep(0.9)
    assert fingerprint(db) == before


def test_stale_lease_and_valid_exact_retry(db):
    _, _, worker, first = leased(1)
    time.sleep(1.15)
    with store.connect(worker) as c:
        second = store.claim(c, worker, 5)
        assert second and second[3] == first[3] + 1
        before = fingerprint(db)
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            store.finish(c, worker, first)
        assert fingerprint(db) == before
        receipt = store.finish(c, worker, second)
        before = fingerprint(db)
        assert store.finish(c, worker, second) == receipt
        assert fingerprint(db) == before


def test_actual_two_transaction_revoke_order(db):
    _, _, worker, lease = leased()
    started, committed = threading.Event(), threading.Event()
    errors = []

    def revoke():
        try:
            with old.connect() as admin:
                started.set()
                admin.execute("UPDATE ra4a.policies SET status='REVOKED' WHERE tenant_id='tenant-test'")
                committed.set()
        except Exception as e:
            errors.append(type(e).__name__)

    with store.connect(worker) as c:
        with c.transaction():
            store.finish(c, worker, lease)
            thread = threading.Thread(target=revoke)
            thread.start()
            assert started.wait(3) and not committed.wait(0.15)
        thread.join(5)
    assert committed.is_set() and not errors
    before = fingerprint(db)
    with store.connect(worker) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
        store.finish(c, worker, lease)
    assert fingerprint(db) == before


def test_wrong_source_cross_tenant_and_legacy_bypass(db):
    cfg, receipt = admitted()
    beta = config(suffix="b")
    with store.connect(beta) as c:
        assert store.status(c, beta, receipt["request_id"]) is None
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("SELECT * FROM ra4b_test.status('tenant-test',%s)", (receipt["request_id"],))
    raw, digest = admission_payload("accepted-404", "f" * 64)
    with store.connect(cfg) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
        c.execute("SELECT * FROM ra4b_test.admit(%s,'pol-001',1,'bad-source-0001',%s,%s)", (cfg["tenant"], digest, raw))
    before = fingerprint(db)
    with old.connect("ra4a_test_a_worker") as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
        with c.transaction():
            c.execute("SELECT * FROM ra4a.claim('tenant-test',5)").fetchone()
    assert fingerprint(db) == before

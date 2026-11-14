"""Required RA4B authority invariants against unchanged P1, expected RED if absent."""

import json
import os
from pathlib import Path

import psycopg
import pytest

from integration.ra4a import support
from vrae.persistence.postgres import TestOnlyPostgres as Queue

OUT = Path(os.environ["RA4B_AUTHORITY_EVIDENCE"])


@pytest.fixture
def accepted():
    from integration.ra4a.p2b1_support import seed_base

    seed_base()
    with support.connect() as admin:
        yield admin


def record(name, value):
    (OUT / (name + ".json")).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def test_worker_has_no_direct_raw_table_select(accepted):
    with support.connect("ra4a_test_a_worker") as connection:
        role = connection.execute(
            "SELECT session_user,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb "
            "FROM pg_roles WHERE rolname=session_user"
        ).fetchone()
        privileges = {table: connection.execute(
            "SELECT has_table_privilege(session_user,%s,'SELECT')", ("ra4a." + table,)
        ).fetchone()[0] for table in ("requests", "jobs", "policies", "references")}
    record("actual-worker-privileges", {"role": role, "select": privileges})
    assert not any(privileges.values()), "ISSUE78_REQUIRES_NO_RAW_SELECT"


@pytest.mark.parametrize("policy_state", ["REVOKED", "EXPIRED"])
def test_current_policy_must_deny_finish_after_committed_claim(accepted, policy_state):
    admin = accepted
    ref = support.references()[0]
    with support.connect("ra4a_test_a_app") as app_connection:
        app = Queue(app_connection, mode="TEST_ONLY_PG16")
        receipt = app.admit("tenant-test", "ra4b-preflight-" + policy_state.lower(),
                            source_ref=ref["ref_id"], expected_ref_sha256=ref["ref_sha256"])
    with support.connect("ra4a_test_a_worker") as worker_connection:
        worker = Queue(worker_connection, mode="TEST_ONLY_PG16")
        lease = worker.claim("tenant-test", seconds=30)
        assert lease is not None
        if policy_state == "REVOKED":
            admin.execute("UPDATE ra4a.policies SET status='REVOKED' WHERE tenant_id='tenant-test'")
        else:
            admin.execute("UPDATE ra4a.policies SET expires_at=clock_timestamp()-interval '1 second' WHERE tenant_id='tenant-test'")
        # Genuine second connection has committed policy invalidation before finish.
        fresh_claim = worker.claim("tenant-test", seconds=30)
        denied = False
        try:
            worker.finish("tenant-test", lease[0], lease[2], lease[3])
        except psycopg.Error:
            denied = True
        row = admin.execute(
            "SELECT s.status,j.state,j.attempts FROM ra4a.runs s JOIN ra4a.jobs j "
            "USING(tenant_id,run_id) WHERE s.run_id=%s", (receipt[1],)
        ).fetchone()
        events = admin.execute(
            "SELECT kind,undelivered FROM ra4a.outbox WHERE run_id=%s ORDER BY kind", (receipt[1],)
        ).fetchall()
        record("after-" + policy_state.lower(), {
            "separate_app_worker_and_admin_connections": True,
            "policy_invalidation_committed_before_finish": True,
            "fresh_claim_denied": fresh_claim is None, "finish_denied": denied,
            "persisted_run_job": row, "private_outbox": events,
            "authority": "TEST_ONLY_CONTRACT_PREFLIGHT_NOT_RUNTIME_ACCEPTANCE",
            "native_approval": False, "external_delivery": False,
        })
        assert denied, "ISSUE78_REQUIRES_CURRENT_POLICY_FAIL_CLOSED_AT_FINISH"

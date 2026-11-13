"""Real connections serialize local policy publication/admission."""

import threading

import psycopg
import pytest

from vrae.persistence.contracts import admission_payload
from .support import connect
from .test_pg import client


def test_current_policy_publication_waits_for_admission_commit(db):
    started, completed = threading.Event(), threading.Event()
    errors = []

    def publish():
        try:
            with connect() as admin:
                started.set()
                admin.execute(
                    "INSERT INTO ra4a.policies VALUES('tenant-test','pol-001',2,'ALLOWED',clock_timestamp()+interval '1 day','SYNTHETIC_INTERNAL_ONLY')"
                )
                completed.set()
        except BaseException as error:
            errors.append(type(error).__name__)

    with connect("ra4a_test_a_app") as a:
        with a.transaction():
            raw, sha = admission_payload()
            assert a.execute(
                "SELECT * FROM ra4a.admit(%s,%s,%s,%s,%s,%s)",
                ("tenant-test", "pol-001", 1, "policy-race-0001", sha, raw),
            ).fetchone()
            thread = threading.Thread(target=publish)
            thread.start()
            assert started.wait(3)
            assert not completed.wait(0.2)
            with client("ra4a_test_b_app") as b:
                assert b.admit("tenant-beta", "other-tenant-0001")
        thread.join(timeout=5)
        assert not thread.is_alive() and completed.is_set() and not errors
    with client() as a, pytest.raises(psycopg.errors.InsufficientPrivilege):
        a.admit("tenant-test", "policy-race-0001")

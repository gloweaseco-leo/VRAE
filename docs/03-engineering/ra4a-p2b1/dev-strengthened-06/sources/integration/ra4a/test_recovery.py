"""Actual pg_dump/pg_restore, expiry and source-version refusal evidence."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import psycopg
import pytest
from psycopg.types.json import Jsonb

from vrae.persistence.contracts import admission_payload, frozen_reference
from .support import connect, STATE, TABLES
from .test_pg import client, sql_denied


def data_snapshot(c):
    return {
        table: c.execute(
            "SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]'::jsonb) FROM ra4a."
            + table
            + " t"
        ).fetchone()[0]
        for table in TABLES
    }


def data_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def test_pg_dump_restore_retains_data_owners_rls_and_idempotency(db):
    output = Path(os.environ["RA4A_EVIDENCE_DIR"])
    state = json.loads(STATE.read_text())
    with client() as a, client("ra4a_test_b_app") as b:
        admitted = a.admit("tenant-test", "backup-a-0001")
        b.admit("tenant-beta", "backup-b-0001")
    original = data_snapshot(db)
    dump_cmd = [
        "docker",
        "exec",
        state["container"],
        "pg_dump",
        "-U",
        "postgres",
        "-d",
        "vrae_ra4a_p1",
        "-Fc",
    ]
    dump = subprocess.run(dump_cmd, capture_output=True, check=True).stdout
    (output / "synthetic-metadata.dump").write_bytes(dump)
    db.execute("CREATE DATABASE vrae_ra4a_restore TEMPLATE template0")
    try:
        restore_cmd = [
            "docker",
            "exec",
            "-i",
            state["container"],
            "pg_restore",
            "-U",
            "postgres",
            "-d",
            "vrae_ra4a_restore",
            "--exit-on-error",
        ]
        subprocess.run(restore_cmd, input=dump, capture_output=True, check=True)
        with connect(dbname="vrae_ra4a_restore") as restored:
            assert data_snapshot(restored) == original
            owners = restored.execute(
                "SELECT p.proname,r.rolname,r.rolsuper,r.rolbypassrls FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_roles r ON r.oid=p.proowner WHERE n.nspname='ra4a' AND p.prosecdef"
            ).fetchall()
            assert len(owners) == 5 and all(r[1] == "ra4a_owner" and not any(r[2:]) for r in owners)
            restored.execute("REVOKE ALL ON DATABASE vrae_ra4a_restore FROM PUBLIC")
            restored.execute("GRANT CONNECT ON DATABASE vrae_ra4a_restore TO ra4a_app,ra4a_worker")
        with connect("ra4a_test_a_app", dbname="vrae_ra4a_restore") as a:
            assert a.execute("SELECT tenant_id FROM ra4a.requests").fetchall() == [("tenant-test",)]
            assert (
                a.execute("SELECT * FROM ra4a.requests WHERE tenant_id='tenant-beta'").fetchall()
                == []
            )
            sql_denied(a, "UPDATE ra4a.references SET visibility='APPROVED'")
            raw, sha = admission_payload()
            replay = a.execute(
                "SELECT * FROM ra4a.admit(%s,%s,%s,%s,%s,%s)",
                ("tenant-test", "pol-001", 1, "backup-a-0001", sha, raw),
            ).fetchone()
            assert replay == admitted
        with connect(dbname="vrae_ra4a_restore") as restored:
            assert data_snapshot(restored) == original
        proof = {
            "dump_command": dump_cmd,
            "restore_command": restore_cmd,
            "dump_sha256": hashlib.sha256(dump).hexdigest(),
            "dump_bytes": len(dump),
            "source_data_sha256": data_hash(original),
            "restored_data_sha256": data_hash(original),
            "data_equal_before_and_after_idempotent_replay": True,
            "nonprivileged_function_owners": owners,
            "restored_tenant_isolation_and_write_denial": True,
        }
        (output / "backup-restore.json").write_text(
            json.dumps(proof, indent=2) + "\n", encoding="utf-8"
        )
    finally:
        db.execute("DROP DATABASE vrae_ra4a_restore WITH (FORCE)")


def test_expired_unreclaimed_lease_cannot_finish(db):
    with client() as a:
        a.admit("tenant-test", "lease-expiry-001")
    with client("ra4a_test_a_worker") as w:
        job = w.claim("tenant-test", seconds=1)
        time.sleep(1.15)
        with pytest.raises(psycopg.Error) as exc:
            w.finish("tenant-test", job[0], job[2], job[3])
        assert exc.value.sqlstate == "55000"


def test_attempt_cap_is_real_dead_letter_not_exactly_once(db):
    with client() as a:
        a.admit("tenant-test", "lease-cap-0001")
    with client("ra4a_test_a_worker") as w:
        for seq in (1, 2, 3):
            job = w.claim("tenant-test", seconds=1)
            assert job[3] == seq
            time.sleep(1.15)
        assert w.claim("tenant-test") is None
    assert db.execute("SELECT state,attempts FROM ra4a.jobs").fetchone() == ("DEAD_LETTER", 3)


def test_legitimate_new_synthetic_version_does_not_reactivate_old_ref(db):
    from tests.reviewing.synthetic import inputs

    i = inputs("404", version=2)
    ref = frozen_reference("accepted-404-v2", i.document, i.html, i.source, trust=i.trust)
    keys = list(ref)
    from psycopg import sql

    db.execute(
        sql.SQL("INSERT INTO ra4a.references ({}) VALUES ({})").format(
            sql.SQL(",").join(map(sql.Identifier, keys)),
            sql.SQL(",").join(sql.Placeholder() for _ in keys),
        ),
        [Jsonb(ref[k]) if k == "metadata" else ref[k] for k in keys],
    )
    old = db.execute(
        "SELECT ref_sha256 FROM ra4a.references WHERE ref_id='accepted-404'"
    ).fetchone()[0]
    with client() as a:
        with pytest.raises(psycopg.Error) as exc:
            a.admit(
                "tenant-test",
                "stale-source-001",
                source_ref="accepted-404",
                expected_ref_sha256=old,
            )
        assert exc.value.sqlstate == "22023"
        assert a.admit(
            "tenant-test",
            "fresh-source-001",
            source_ref=ref["ref_id"],
            expected_ref_sha256=ref["ref_sha256"],
        )


def test_admin_connection_is_not_a_synthetic_runtime_client(db):
    from vrae.persistence.postgres import TestOnlyPostgres
    from vrae.persistence.contracts import PersistenceError

    with pytest.raises(PersistenceError, match="RA4A_RUNTIME_ROLE_DENIED"):
        TestOnlyPostgres(db, mode="TEST_ONLY_PG16")

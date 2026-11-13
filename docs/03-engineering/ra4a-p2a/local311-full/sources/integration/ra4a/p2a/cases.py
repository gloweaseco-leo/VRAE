"""Real database adversarial contracts; no skips, mocks, xfails or live data."""

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import uuid

import psycopg
from psycopg import sql
import pytest

from vrae.persistence.contracts import PersistenceError
from vrae.persistence.private_bytes import Artifact, descriptors, locator, verify
from vrae.reviewing import ReviewError
from vrae.reviewing.canonical import canonical, SOURCE_LIMIT
from ..p2a_support import (
    add_reference,
    connect,
    counts,
    graph,
    port,
    raw_args,
    read,
    register,
    STATE,
)


def denied(c, query, args=None, code="42501"):
    with pytest.raises(psycopg.Error) as exc:
        c.execute(query, args)
    assert exc.value.sqlstate == code


def raw_register(c, g):
    return c.execute("SELECT ra4a_bytes.register(%s,%s,%s,%s,%s,%s,%s)", raw_args(g)).fetchone()


def change(g, kind, transform, *, omit=False):
    items = tuple(
        Artifact(a.kind, a.key, transform(a.raw)) if a.kind == kind else a
        for a in g.artifacts
        if not (omit and a.kind == kind)
    )
    return replace(g, artifacts=items, manifest=canonical(descriptors(items), limit=SOURCE_LIMIT))


@pytest.mark.parametrize("case", ["404", "200"])
def test_exact_complete_native_bytes_and_idempotent_registration(isolated, case):
    name, admin = isolated
    g = graph(case)
    first = register(name, g)
    assert register(name, g) == first == locator(g)
    assert counts(admin) == (1, len(g.artifacts), 1)
    assert read(name, g) == g
    d = json.loads(next(a.raw for a in g.artifacts if a.kind == "DRAFT"))
    assert d["private"] and not d["shareable"] and d["approval_status"] == "NOT_APPROVED"
    assert len(d["issues"]) == (1 if case == "404" else 0)
    assert (d["native_report_version"] is None) == (case == "200")
    for a in g.artifacts:
        row = admin.execute(
            "SELECT raw,content_sha256,length_bytes FROM ra4a_bytes.objects WHERE kind=%s AND object_key=%s",
            (a.kind, a.key),
        ).fetchone()
        assert (
            bytes(row[0]) == a.raw
            and row[1] == hashlib.sha256(a.raw).hexdigest()
            and row[2] == len(a.raw)
        )


@pytest.mark.parametrize(
    "role", ["ra4a_test_a_app", "ra4a_test_b_app", "ra4a_test_unassigned", "ra4a_test_a_worker"]
)
@pytest.mark.parametrize("verb", ["SELECT raw FROM", "INSERT INTO", "UPDATE", "DELETE FROM"])
def test_no_direct_raw_table_authority(isolated, role, verb):
    name, _ = isolated
    register(name)
    statement = {
        "SELECT raw FROM": "SELECT raw FROM ra4a_bytes.objects",
        "INSERT INTO": "INSERT INTO ra4a_bytes.objects DEFAULT VALUES",
        "UPDATE": "UPDATE ra4a_bytes.objects SET raw=decode('00','hex')",
        "DELETE FROM": "DELETE FROM ra4a_bytes.objects",
    }[verb]
    with connect(role, dbname=name) as c:
        denied(c, statement)


@pytest.mark.parametrize("role", ["ra4a_test_b_app", "ra4a_test_unassigned", "p2a_test_b_writer"])
def test_cross_tenant_and_unassigned_gated_reads_refused(isolated, role):
    name, _ = isolated
    register(name)
    c, api = port(name, role)
    with c, pytest.raises(psycopg.Error) as exc:
        api.read(locator(graph()), provenance=graph())
    assert exc.value.sqlstate == "42501"


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant", "tenant-beta"),
        ("source_run", "foreign-run"),
        ("report", "foreign-report"),
        ("version", 2),
        ("target_digest", "0" * 64),
        ("ref_id", "accepted-200"),
    ],
)
def test_exact_locator_not_just_naked_digest(isolated, field, value):
    name, _ = isolated
    register(name)
    bad = replace(locator(graph()), **{field: value})
    c, api = port(name, "ra4a_test_a_app")
    with c, pytest.raises(PersistenceError):
        api.read(bad, provenance=graph())
    with connect("ra4a_test_a_app", dbname=name) as c:
        denied(
            c,
            "SELECT * FROM ra4a_bytes.read_graph(%s,%s,%s,%s,%s,%s)",
            (bad.tenant, bad.ref_id, bad.source_run, bad.report, bad.version, bad.target_digest),
        )


@pytest.mark.parametrize("spoof", ["tenant_guc", "actor_guc", "set_role", "owner", "writer"])
def test_spoofs_do_not_grant_store_authority(isolated, spoof):
    name, _ = isolated
    register(name)
    with connect("ra4a_test_b_app", dbname=name) as c:
        if spoof.endswith("guc"):
            c.execute(
                "SELECT set_config(%s,%s,false)",
                ("app.tenant_id" if spoof == "tenant_guc" else "app.actor", "tenant-test"),
            )
            denied(
                c,
                "SELECT * FROM ra4a_bytes.read_graph(%s,%s,%s,%s,%s,%s)",
                (
                    "tenant-test",
                    "accepted-404",
                    "run-ra3b-404base",
                    "report-ra3c-404",
                    1,
                    locator(graph()).target_digest,
                ),
            )
        else:
            denied(
                c,
                "SET ROLE "
                + {
                    "set_role": "ra4a_test_a_app",
                    "owner": "ra4a_owner",
                    "writer": "p2a_test_a_writer",
                }[spoof],
            )


@pytest.mark.parametrize("operation", ["read", "write"])
def test_revoked_assignment_and_policy_lock_fail_closed(isolated, operation):
    name, admin = isolated
    register(name)
    role = "ra4a_test_a_app" if operation == "read" else "p2a_test_a_writer"
    admin.execute("UPDATE ra4a_private.assignments SET active=false WHERE db_role=%s", (role,))
    with pytest.raises(psycopg.Error):
        read(name) if operation == "read" else register(name)


@pytest.mark.parametrize(
    "column,value", [("status", "REVOKED"), ("status", "UNKNOWN"), ("expires_at", "2000-01-01")]
)
def test_policy_denial_for_registered_bytes(isolated, column, value):
    name, admin = isolated
    register(name)
    admin.execute(
        sql.SQL("UPDATE ra4a.policies SET {}=%s WHERE tenant_id='tenant-test'").format(
            sql.Identifier(column)
        ),
        (value,),
    )
    with pytest.raises(psycopg.Error):
        read(name)


@pytest.mark.parametrize(
    "kind",
    [
        "DRAFT",
        "HTML",
        "SOURCE",
        "PACK",
        "PACKAGE",
        "GUARD",
        "METADATA",
        "CSS",
        "SOURCE_OBJECT",
        "TARGET",
    ],
)
def test_altered_content_with_recomputed_outer_manifest_refused(isolated, kind):
    name, admin = isolated
    bad = change(graph(), kind, lambda raw: raw + b" ")
    with pytest.raises((PersistenceError, ReviewError)):
        verify(bad, provenance=graph())
    with connect("p2a_test_a_writer", dbname=name) as c, pytest.raises(psycopg.Error):
        raw_register(c, bad)
    assert counts(admin) == (0, 0, 0)


@pytest.mark.parametrize("kind", ["HTML", "CSS", "SOURCE_OBJECT", "GUARD"])
def test_incomplete_or_truncated_graph_is_not_readable(isolated, kind):
    name, admin = isolated
    bad = change(graph(), kind, lambda raw: raw, omit=True)
    with connect("p2a_test_a_writer", dbname=name) as c, pytest.raises(psycopg.Error):
        raw_register(c, bad)
    assert counts(admin) == (0, 0, 0)


@pytest.mark.parametrize("kind", ["HTML", "TARGET"])
def test_database_rejects_overlarge_bytes_before_insert(isolated, kind):
    name, admin = isolated
    bad = change(graph(), kind, lambda raw: b"x" * (8_000_001 if kind == "HTML" else 65_537))
    with connect("p2a_test_a_writer", dbname=name) as c:
        denied(c, "SELECT ra4a_bytes.register(%s,%s,%s,%s,%s,%s,%s)", raw_args(bad), "22023")
    assert counts(admin) == (0, 0, 0)


@pytest.mark.parametrize("table", ["graphs", "objects", "events"])
@pytest.mark.parametrize("verb", ["UPDATE", "DELETE", "TRUNCATE"])
def test_ordinary_fixture_admin_cannot_overwrite_delete_or_truncate(isolated, table, verb):
    name, admin = isolated
    register(name)
    query = {
        "UPDATE": "UPDATE ra4a_bytes." + table + " SET tenant_id=tenant_id",
        "DELETE": "DELETE FROM ra4a_bytes." + table,
        "TRUNCATE": "TRUNCATE ra4a_bytes." + table + " CASCADE",
    }[verb]
    denied(admin, query, code="55000")
    assert read(name) == graph()


def test_sha_and_length_are_generated_not_client_attestation(isolated):
    name, admin = isolated
    register(name)
    denied(admin, "UPDATE ra4a_bytes.objects SET content_sha256='0'", code="428C9")
    denied(admin, "UPDATE ra4a_bytes.objects SET length_bytes=0", code="428C9")


def test_stale_version_does_not_resurrect_old_review(isolated):
    name, admin = isolated
    register(name)
    newer = add_reference(admin, version=2)
    register(name, newer)
    assert read(name, newer) == newer
    with pytest.raises(psycopg.Error):
        read(name)
    assert counts(admin)[0] == counts(admin)[2] == 2


def test_registration_rollback_and_connection_termination_leave_no_graph(isolated):
    name, admin = isolated
    with connect("p2a_test_a_writer", dbname=name) as c:
        c.execute("BEGIN")
        raw_register(c, graph())
        assert counts(admin) == (0, 0, 0)
        reader, api = port(name, "ra4a_test_a_app")
        with reader:
            reader.execute("SET lock_timeout='150ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                api.read(locator(graph()), provenance=graph())
        c.execute("ROLLBACK")
    assert counts(admin) == (0, 0, 0)
    c = connect("p2a_test_a_writer", dbname=name)
    try:
        c.execute("BEGIN")
        raw_register(c, graph())
        pid = c.execute("SELECT pg_backend_pid()").fetchone()[0]
        assert admin.execute("SELECT pg_terminate_backend(%s)", (pid,)).fetchone()[0]
        with pytest.raises(psycopg.OperationalError):
            c.execute("SELECT 1")
    finally:
        c.close()
    assert counts(admin) == (0, 0, 0)
    register(name)
    assert read(name) == graph()


@pytest.mark.parametrize("variant", [False, True])
def test_two_connections_race_consistent_commit(isolated, variant):
    name, admin = isolated
    barrier = threading.Barrier(2)
    results = []

    def writer(bad):
        try:
            with connect("p2a_test_a_writer", dbname=name) as c:
                barrier.wait(timeout=10)
                raw_register(c, change(graph(), "HTML", lambda b: b + b"!") if bad else graph())
            results.append("commit")
        except psycopg.Error:
            results.append("refused")

    threads = [
        threading.Thread(target=writer, args=(False,)),
        threading.Thread(target=writer, args=(variant,)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    assert all(not t.is_alive() for t in threads)
    assert sorted(results) == (["commit", "refused"] if variant else ["commit", "commit"])
    assert counts(admin) == (1, len(graph().artifacts), 1)
    assert read(name) == graph()


@pytest.mark.parametrize("kind", ["HTML", "CSS", "SOURCE_OBJECT", "GUARD", "TARGET"])
def test_privileged_corruption_recomputed_db_hash_still_refused(isolated, kind):
    name, admin = isolated
    register(name)
    # Isolated fault injection, outside normal fixture/runtime authority:
    # cluster superuser disables the trigger. Never a claimed write-once API.
    admin.execute("ALTER TABLE ra4a_bytes.objects DISABLE TRIGGER immutable_bytes")
    admin.execute(
        "UPDATE ra4a_bytes.objects SET raw=raw||decode('20','hex') WHERE kind=%s", (kind,)
    )
    admin.execute("ALTER TABLE ra4a_bytes.objects ENABLE TRIGGER immutable_bytes")
    with pytest.raises((PersistenceError, ReviewError)):
        read(name)


def test_404_200_substitution_and_illegal_writer(isolated):
    name, admin = isolated
    c, api = port(name, "ra4a_test_a_app")
    with c, pytest.raises(psycopg.Error):
        api.register(graph(), provenance=graph())
    bad = replace(graph(), target=graph("200").target)
    with connect("p2a_test_a_writer", dbname=name) as c, pytest.raises(psycopg.Error):
        raw_register(c, bad)
    assert counts(admin) == (0, 0, 0)


def test_current_version_publication_serializes_with_read_transaction(isolated):
    name, admin = isolated
    register(name)
    reader = connect("ra4a_test_a_app", dbname=name)
    reader.execute("BEGIN")
    reader.execute(
        "SELECT * FROM ra4a_bytes.read_graph(%s,%s,%s,%s,%s,%s)",
        (
            "tenant-test",
            "accepted-404",
            "run-ra3b-404base",
            "report-ra3c-404",
            1,
            locator(graph()).target_digest,
        ),
    ).fetchall()
    admin.execute("SET lock_timeout='150ms'")
    with pytest.raises(psycopg.errors.LockNotAvailable):
        add_reference(admin, version=2)
    reader.execute("COMMIT")
    reader.close()
    admin.execute("SET lock_timeout='5s'")
    newer = add_reference(admin, version=2)
    register(name, newer)
    with pytest.raises(psycopg.Error):
        read(name)


def test_real_dump_restore_and_volume_restart_original_bytes_latest_version(isolated):
    name, admin = isolated
    register(name)
    zero = graph("200")
    register(name, zero)
    newer = add_reference(admin, version=2)
    register(name, newer)
    state = json.loads(STATE.read_text())
    out = Path(os.environ["RA4A_P2A_EVIDENCE_DIR"])
    dump_cmd = [
        "docker",
        "exec",
        state["container"],
        "pg_dump",
        "-U",
        "postgres",
        "-d",
        name,
        "-Fc",
    ]
    dump = subprocess.run(dump_cmd, capture_output=True, check=True).stdout
    (out / "private-bytes.dump").write_bytes(dump)
    restored = "vrae_p2a_" + uuid.uuid4().hex[:12]
    with connect(dbname="postgres") as c:
        c.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(restored)))
    try:
        subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                state["container"],
                "pg_restore",
                "-U",
                "postgres",
                "-d",
                restored,
                "--exit-on-error",
            ],
            input=dump,
            capture_output=True,
            check=True,
        )
        with connect(dbname=restored) as c:
            c.execute(
                sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(restored))
            )
            c.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO ra4a_app,p2a_fixture_writer").format(
                    sql.Identifier(restored)
                )
            )
        for dbname in (name, restored):
            assert read(dbname, newer) == newer and read(dbname, zero) == zero
            with pytest.raises(psycopg.Error):
                read(dbname)
            with pytest.raises(psycopg.Error):
                read(dbname, newer, role="ra4a_test_b_app")
        admin.close()
        subprocess.run(
            ["docker", "restart", "--time", "1", state["container"]],
            capture_output=True,
            check=True,
        )
        binding = (
            subprocess.check_output(["docker", "port", state["container"], "5432/tcp"])
            .decode()
            .strip()
        )
        assert binding.startswith("127.0.0.1:") and "\n" not in binding
        state["port"] = int(binding.rsplit(":", 1)[1])
        STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
        import time

        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                with connect(dbname=name) as c:
                    c.execute("SELECT 1")
                break
            except psycopg.OperationalError:
                time.sleep(0.25)
        else:
            raise AssertionError("Actual restart did not become ready")
        for dbname in (name, restored):
            assert read(dbname, newer) == newer and read(dbname, zero) == zero
            with pytest.raises(psycopg.Error):
                read(dbname)
            with pytest.raises(psycopg.Error):
                read(dbname, newer, role="ra4a_test_b_app")
        proof = {
            "dump_sha256": hashlib.sha256(dump).hexdigest(),
            "dump_bytes": len(dump),
            "actual_volume_restart": True,
            "restored_original_bytes_exact": True,
            "cross_tenant_and_stale_denied_after_both_recoveries": True,
            "held_expected_artifacts": descriptors(newer.artifacts) + descriptors(zero.artifacts),
        }
        (out / "p2a-recovery.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    finally:
        with connect(dbname="postgres") as c:
            c.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(restored)))

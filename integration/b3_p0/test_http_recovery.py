"""Real loopback HTTP, durable lost response, restart and independent restore."""

import http.client
import json
import socket
import time
import uuid

import psycopg
from psycopg import sql
import pytest

from integration.ra4a.p2b1_support import proposal
from vrae.b3_p0.contracts import Denied
from vrae.b3_p0.http import Sessions, serve
from vrae.reviewing.canonical import canonical

from .lab import Lab, docker
from .support import Case, counts, protected, sha, snapshot


def post(server, token, raw, path="/test-only/intents", **extra):
    c = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
    try:
        headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"} | extra
        c.request("POST", path, raw, headers)
        r = c.getresponse()
        return r.status, r.read()
    finally:
        c.close()


@pytest.mark.parametrize("which", ["404", "200"])
def test_http_real_submit_and_receipt(case, which):
    w = case.witness(which)
    sessions = Sessions()
    token = sessions.provision(w)
    cmd = proposal(case.graphs[which]).payload
    with serve(case.service, sessions) as server:
        status, first = post(server, token, cmd)
        assert status == 200
        assert post(server, token, cmd) == (200, first)
        assert post(
            server, token, canonical({"idempotency_key": "review-key-0001"}), "/test-only/receipts"
        ) == (200, first)
    assert counts(case.admin)["outbox"] == 1


@pytest.mark.parametrize(
    "bad",
    [
        "missing_session",
        "forged_subject",
        "forged_role",
        "forged_tenant",
        "origin",
        "host",
        "production_review",
        "share",
        "extra_receipt",
        "expired_session",
        "missing_receipt",
    ],
)
def test_http_negatives_never_change_rows(case, bad):
    w = case.witness()
    sessions = Sessions()
    token = sessions.provision(w, ttl=0.01 if bad == "expired_session" else 120)
    raw = proposal(case.graphs["404"]).payload
    path = "/test-only/intents"
    extra = {}
    if bad == "missing_session":
        token = "A" * 43
    if bad.startswith("forged_"):
        d = json.loads(raw)
        d[bad[7:]] = "owner"
        raw = canonical(d, limit=131072)
    if bad == "origin":
        extra["Origin"] = "https://untrusted.invalid"
    if bad == "host":
        extra["Host"] = "untrusted.invalid"
    if bad == "production_review":
        path = "/v1/review-decisions"
    if bad == "share":
        path = "/v1/share-grants"
    if bad in {"extra_receipt", "missing_receipt"}:
        path = "/test-only/receipts"
        raw = canonical(
            {"idempotency_key": "never-committed-key"}
            | ({"subject": "forged"} if bad == "extra_receipt" else {})
        )
    if bad == "expired_session":
        time.sleep(0.02)
    before = snapshot(case.admin)
    with serve(case.service, sessions) as server:
        status, body = post(server, token, raw, path, **extra)
        assert status in {403, 409} and set(json.loads(body)) == {"error"}
    assert snapshot(case.admin) == before


def test_lost_http_response_retry_exact_then_restart_server_invalidates_session(case):
    w = case.witness()
    sessions = Sessions()
    token = sessions.provision(w)
    cmd = proposal(case.graphs["404"]).payload
    with serve(case.service, sessions) as server:
        # Real request: caller closes before reading response. Wait for durable SQL fact.
        with socket.create_connection(("127.0.0.1", server.server_port), timeout=10) as s:
            headers = (
                f"POST /test-only/intents HTTP/1.0\r\nHost: 127.0.0.1:{server.server_port}\r\n"
                f"Authorization: Bearer {token}\r\nContent-Type: application/json\r\nContent-Length: {len(cmd)}\r\n\r\n"
            )
            s.sendall(headers.encode() + cmd)
        deadline = time.monotonic() + 20
        while counts(case.admin)["intents"] != 1:
            assert time.monotonic() < deadline
            time.sleep(0.05)
        original = bytes(case.admin.execute("SELECT receipt FROM b3_p0.intents").fetchone()[0])
        assert post(server, token, cmd) == (200, original)
    new_sessions = Sessions()
    with serve(case.service, new_sessions) as server:
        assert post(server, token, cmd)[0] == 403
        fresh_token = new_sessions.provision(case.witness())
        assert post(server, fresh_token, cmd) == (200, original)
    assert counts(case.admin)["audit"] == counts(case.admin)["outbox"] == 1


def test_unknown_commit_lookup_does_not_resubmit(case):
    w = case.witness()
    with case.service(w) as service, pytest.raises(Denied, match="UNKNOWN_COMMIT"):
        service.get_receipt(w, "never-committed-key")
    assert all(v == 0 for v in counts(case.admin).values())


def test_real_database_down_restart_retains_receipt(case):
    w = case.witness(ttl=120)
    original = case.submit(w).payload
    held = protected(case.admin)
    with case.service(w) as service:
        docker("stop", "--time", "2", case.lab.name)
        try:
            with pytest.raises(Denied, match="UNKNOWN_COMMIT"):
                service.get_receipt(w, "review-key-0001")
        finally:
            docker("start", case.lab.name)
            case.lab.refresh_port()
            deadline = time.monotonic() + 30
            while True:
                try:
                    with case.lab.connect(dbname=case.dbname):
                        break
                except psycopg.OperationalError:
                    assert time.monotonic() < deadline
                    time.sleep(0.1)
    # Old connection is dead. The restarted server uses new sessions/witnesses.
    with case.lab.connect(dbname=case.dbname) as admin:
        resumed = Case(case.lab, case.dbname, admin)
        admin.execute("UPDATE b3_p0.authority SET epoch=epoch+1")
        with resumed.service(w) as service, pytest.raises(Denied):
            service.get_receipt(w, "review-key-0001")
        fresh = resumed.witness(epoch=2)
        with resumed.service(fresh) as service:
            assert service.get_receipt(fresh, "review-key-0001").payload == original
        assert protected(admin) == held


def test_independent_custom_format_cross_environment_restore(case, tmp_path):
    w = case.witness()
    original = case.submit(w).payload
    fingerprint = snapshot(case.admin, schema=True)
    from .evidence import raw_acl, record

    original_new_acl = raw_acl(case.admin)
    from .support import encode

    (tmp_path / "source-facts.json").write_bytes(
        encode(snapshot(case.admin, schema=True, details=True))
    )
    from integration.ra4e.manifest import capture

    old, old_acl = capture(case.lab, case.dbname)
    archive = docker(
        "exec",
        case.lab.name,
        "pg_dump",
        "-U",
        "postgres",
        "--format=custom",
        "--dbname=" + case.dbname,
    )
    assert archive.startswith(b"PGDMP")
    # Raw archive stays private; public evidence only holds SHA and observations.
    (tmp_path / "private.dump").write_bytes(archive)
    destination = Lab("restore-" + uuid.uuid4().hex[:12])
    try:
        destination.start()
        name = "vrae_p2b1_" + uuid.uuid4().hex[:12]
        with destination.connect(dbname="postgres") as admin:
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name))
            )
        import subprocess

        p = subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                destination.name,
                "pg_restore",
                "-U",
                "postgres",
                "--exit-on-error",
                "--dbname=" + name,
            ],
            input=archive,
            capture_output=True,
            timeout=60,
        )
        assert p.returncode == 0, "B3_REAL_CUSTOM_RESTORE_FAILED"
        with destination.connect(dbname=name) as admin:
            (tmp_path / "destination-facts.json").write_bytes(
                encode(snapshot(admin, schema=True, details=True))
            )
            assert snapshot(admin, schema=True) == fingerprint
            restored_old, restored_old_acl = capture(destination, name)
            assert restored_old == old
            from integration.ra4e.manifest import verify_sources

            verified = verify_sources(destination, name, destination.graphs)
            record(
                "restore-catalog-and-originals",
                {
                    "b3_schema_data_security_source_sha256": fingerprint,
                    "b3_schema_data_security_restored_sha256": snapshot(admin, schema=True),
                    "accepted_manifest_source": old,
                    "accepted_manifest_restored": restored_old,
                    "b3_raw_acl_source": original_new_acl,
                    "b3_raw_acl_restored": raw_acl(admin),
                    "accepted_raw_acl_source": old_acl["raw_table_acl_evidence"],
                    "accepted_raw_acl_restored": restored_old_acl["raw_table_acl_evidence"],
                    "custom_archive_sha256": sha(archive),
                    "restored_originals": verified,
                },
            )
            restored = Case(destination, name, admin)
            # Restored witnesses are NOT current authority: explicit restore ceremony rotates epoch
            # before any server session can be issued. No runtime/admin mixing.
            admin.execute("UPDATE b3_p0.authority SET epoch=epoch+1")
            with restored.service(w) as service, pytest.raises(Denied):
                service.get_receipt(w, "review-key-0001")
            fresh = restored.witness(epoch=2)
            assert restored.submit(fresh).payload == original
            assert counts(admin)["outbox"] == counts(admin)["audit"] == 1
            # At-least-once INTERNAL test consumer deduplicates the stable durable event ID.
            event = admin.execute(
                "SELECT event_id,receipt_sha256,internal_only FROM b3_p0.outbox"
            ).fetchone()
            import sqlite3

            consumed = tmp_path / "private-test-consumer.sqlite"
            with sqlite3.connect(consumed) as ledger:
                ledger.execute(
                    "CREATE TABLE seen(event_id TEXT PRIMARY KEY, receipt_sha256 TEXT NOT NULL)"
                )
                ledger.execute("INSERT INTO seen VALUES(?,?)", (str(event[0]), event[1]))
            with sqlite3.connect(consumed) as restarted_consumer:
                restarted_consumer.execute(
                    "INSERT OR IGNORE INTO seen VALUES(?,?)", (str(event[0]), event[1])
                )
                assert restarted_consumer.execute("SELECT count(*) FROM seen").fetchone() == (1,)
            assert event[2] is True and event[1] == sha(original)
            with restored.connect() as reviewer, pytest.raises(psycopg.Error) as caught:
                reviewer.execute("SELECT * FROM b3_p0.outbox")
            assert caught.value.sqlstate == "42501"
        # A truncated custom archive is an actual restore failure in another empty database.
        broken = "vrae_p2b1_" + uuid.uuid4().hex[:12]
        with destination.connect(dbname="postgres") as admin:
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(broken))
            )
        bad = subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                destination.name,
                "pg_restore",
                "-U",
                "postgres",
                "--exit-on-error",
                "--single-transaction",
                "--dbname=" + broken,
            ],
            input=archive[: len(archive) // 2],
            capture_output=True,
            timeout=60,
        )
        assert bad.returncode != 0
        with destination.connect(dbname=broken) as admin:
            assert admin.execute("SELECT to_regclass('b3_p0.intents')").fetchone() == (None,)
    finally:
        destination.stop()

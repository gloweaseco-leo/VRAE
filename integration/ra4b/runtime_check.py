"""Linux supervisor: actual separate unprivileged API/Worker, actual PG and HTTP.

Run only in an owned --network container:<network-none-PG> namespace. Admin
bootstrap is supplied on stdin; neither child gets it, host files or Docker.
"""

import http.client
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time

from integration.ra4a import support as old
from integration.ra4b.support import config, fingerprint, seed
from vrae.application.ra4b.store import connect as store_connection

OUT = Path("/evidence")
PRIVATE = Path("/tmp/b4-supervisor")
CHILDREN = []
LOGS = []
SECRET_VALUES = []


def publish(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, default=str) + "\n")


def wait_for(predicate, seconds=8):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("BOUNDED_RUNTIME_WAIT_FAILED")


def provision(kind, uid):
    directory = Path("/tmp/b4-" + kind.lower())
    directory.mkdir(mode=0o700)
    path = directory / "config.json"
    cfg = config(kind)
    if kind == "APP":
        cfg["bearer"] = secrets.token_urlsafe(40)
        SECRET_VALUES.append(cfg["bearer"])
    path.write_text(json.dumps(cfg))
    path.chmod(0o600)
    os.chown(path, uid, uid)
    os.chown(directory, uid, uid)
    return path, cfg


def spawn(kind, path, *args):
    uid = 10001 if kind == "APP" else 10002
    name = "apps.api.ra4b" if kind == "APP" else "worker.ra4b.main"
    log = OUT / (kind.lower() + "-" + str(len(CHILDREN)) + ".log")
    stream = log.open("wb")
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONPATH": "/work",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1",
           "VRAE_RA4B_TEST_ONLY": "1", "HOME": "/tmp"}
    assert not any(secret in "\0".join(env.values()) for secret in SECRET_VALUES)
    child = subprocess.Popen([sys.executable, "-m", name, "--config", str(path), *args],
                             env=env, cwd="/work", stdin=subprocess.DEVNULL,
                             stdout=stream, stderr=stream, user=uid, group=uid, extra_groups=[])
    stream.close()
    CHILDREN.append(child)
    child.b4_uid = uid
    LOGS.append(log)
    return child, log


def signal_child(child, number):
    if child.poll() is not None:
        return
    # Same-UID signal helper; the supervisor needs no CAP_KILL or ptrace.
    subprocess.run([sys.executable, "-c", "import os,sys; os.kill(int(sys.argv[1]),int(sys.argv[2]))",
                    str(child.pid), str(int(number))], user=child.b4_uid, group=child.b4_uid,
                   extra_groups=[], stdin=subprocess.DEVNULL, capture_output=True, check=True,
                   env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})


def request(cfg, method="POST", path="/v1/audit-requests", payload=None, key="runtime-key-0001", overrides=None):
    headers = {"Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:8765",
               "Authorization": "Bearer " + cfg["bearer"], "Content-Type": "application/json",
               "Idempotency-Key": key}
    headers.update(overrides or {})
    body = json.dumps(payload or {"source_ref": "accepted-404"}) if method == "POST" and not path.endswith("cancel") else None
    conn = http.client.HTTPConnection("127.0.0.1", 8765, timeout=5)
    try:
        conn.request(method, path, body, headers)
        r = conn.getresponse()
        response = json.loads(r.read())
        with (OUT / "http-calls.jsonl").open("a") as stream:
            stream.write(json.dumps({"method": method, "path": path, "key": key, "status": r.status, "response": response}) + "\n")
        return r.status, response
    finally:
        conn.close()


def row(c):
    return c.execute("SELECT state,lease_seq,attempts,job_id FROM ra4a.jobs").fetchone()


def catalog(c):
    rows = c.execute("SELECT p.proname,pg_get_userbyid(p.proowner),p.prosecdef,p.proconfig,p.proacl::text "
                     "FROM pg_proc p WHERE pronamespace='ra4b_test'::regnamespace ORDER BY proname").fetchall()
    assert len(rows) == 10
    for name, owner, sd, search, acl in rows:
        assert owner == "ra4a_owner" and sd and search == ["search_path=pg_catalog, ra4b_test, pg_temp"]
        assert not any(item.startswith("=") for item in (acl or "{}").strip("{}").split(","))
    trigger = c.execute("SELECT t.tgname,t.tgdeferrable,t.tginitdeferred,pg_get_userbyid(p.proowner) "
                        "FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid WHERE t.tgname='ra4b_current_at_commit'").fetchall()
    assert trigger == [("ra4b_current_at_commit", True, True, "ra4a_owner")]
    original = c.execute("SELECT schemaname,tablename,policyname,qual,with_check FROM pg_policies "
                         "WHERE schemaname IN ('ra4a','ra4a_private') ORDER BY 1,2,3").fetchall()
    assert len(original) == 10
    roles = c.execute("SELECT rolname,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolcanlogin "
                      "FROM pg_roles WHERE rolname LIKE 'ra4b_%' ORDER BY rolname").fetchall()
    assert all(not any(r[1:5]) for r in roles)
    projections = c.execute("SELECT relname,relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner) "
                            "FROM pg_class WHERE relnamespace='ra4b_test'::regnamespace AND relkind='r' ORDER BY relname").fetchall()
    assert len(projections) == 2 and all(r[1:3] == (True, True) and r[3] == 'ra4a_owner' for r in projections)
    sessions, acl = {}, {}
    for kind in ("APP", "WORKER"):
        for suffix in ("a", "b"):
            cfg = config(kind, suffix)
            with store_connection(cfg) as connection:
                sessions[cfg["role"]] = connection.execute("SELECT session_user,current_user,current_database(),current_setting('server_version_num')").fetchone()
                acl[cfg["role"]] = connection.execute("SELECT n.nspname,t.relname,has_table_privilege(session_user,t.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE') "
                         "FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname IN ('ra4a','ra4a_private','ra4a_bytes','ra4a_review_test','ra4b_test') "
                         "AND t.relkind='r' ORDER BY 1,2").fetchall()
                assert all(not r[2] for r in acl[cfg["role"]])
    publish("b4-catalog.json", {"functions": rows, "triggers": trigger,
                               "original_policies": original, "roles": roles, "projection_rls": projections,
                               "actual_sessions": sessions, "raw_table_acl": acl,
                               "memberships": c.execute("SELECT member::regrole::text,roleid::regrole::text,inherit_option,set_option,admin_option "
                                "FROM pg_auth_members WHERE member IN (SELECT oid FROM pg_roles WHERE rolname LIKE 'ra4b_%') ORDER BY 1,2").fetchall(),
                               "legacy_raw_select_debt": "G1_HARD_NO_GO"})


def main():
    assert os.geteuid() == 0
    assert sorted(p.name for p in Path("/sys/class/net").iterdir()) == ["lo"]
    assert len(Path("/proc/net/route").read_text().strip().splitlines()) == 1
    assert not Path("/var/run/docker.sock").exists()
    publish("network.json", {"interfaces": ["lo"], "external_routes": 0, "docker_socket": False})
    PRIVATE.mkdir(mode=0o700)
    state = json.load(sys.stdin)
    state["port"] = 5432
    old.STATE = PRIVATE / "state.json"
    old.STATE.write_text(json.dumps(state))
    old.STATE.chmod(0o600)
    SECRET_VALUES.extend([state["admin_password"], *state["runtime_passwords"].values()])
    recovered = "--recovered" in sys.argv
    if not recovered:
        seed()
    app_path, app = provision("APP", 10001)
    worker_path, _ = provision("WORKER", 10002)
    api, log = spawn("APP", app_path)
    wait_for(lambda: b"RA4B_LOOPBACK_TEST_ONLY_READY" in log.read_bytes(), 30)
    assert api.poll() is None
    for child in (api,):
        status = Path(f"/proc/{child.pid}/status").read_text()
        assert "CapEff:\t0000000000000000" in status
    # Actual UID-isolated read denial, not just absence from argv.
    denied = subprocess.run([sys.executable, "-c", "from pathlib import Path; Path('/tmp/b4-app/config.json').read_bytes()"],
                            user=10002, group=10002, extra_groups=[], capture_output=True)
    assert denied.returncode and b"PermissionError" in denied.stderr
    with old.connect() as admin:
        catalog(admin)
        if recovered:
            before = fingerprint(admin)
            for key, expected in state["expected_receipts"].items():
                source = "accepted-404" if key.endswith("0001") else "accepted-200"
                assert request(app, payload={"source_ref": source}, key=key) == (202, expected)
                code, status = request(app, "GET", "/v1/audit-requests/" + expected["request_id"])
                assert code == 200 and status["status"] == "TEST_ONLY_CONSUMED"
            assert fingerprint(admin) == before
            publish("recovery.json", {"status": "PASS", "exact_receipts_after_dump_restore_restart": True,
                                      "zero_new_business_rows": True})
            return
        early = fingerprint(admin)
        admin.execute("UPDATE ra4a_private.principals SET enabled=false WHERE db_role='ra4b_test_a_app'")
        assert request(app, key="http-disabled-0001")[0] == 403 and fingerprint(admin) == early
        admin.execute("UPDATE ra4a_private.principals SET enabled=true WHERE db_role='ra4b_test_a_app'")
        admin.execute("UPDATE ra4a_private.assignments SET active=false WHERE db_role='ra4b_test_a_app'")
        assert request(app, key="http-unassigned-0001")[0] == 403 and fingerprint(admin) == early
        admin.execute("UPDATE ra4a_private.assignments SET active=true WHERE db_role='ra4b_test_a_app'")
        admin.execute("UPDATE ra4a.policies SET status='REVOKED' WHERE tenant_id='tenant-test'")
        assert request(app, key="http-revoked-0001")[0] == 403 and fingerprint(admin) == early
        admin.execute("UPDATE ra4a.policies SET status='ALLOWED',expires_at=clock_timestamp()-interval '1 second' WHERE tenant_id='tenant-test'")
        assert request(app, key="http-expired-0001")[0] == 403 and fingerprint(admin) == early
        admin.execute("UPDATE ra4a.policies SET expires_at=clock_timestamp()+interval '1 day' WHERE tenant_id='tenant-test'")
        assert admin.execute("SELECT count(*) FROM ra4b_test.origin_epochs").fetchone() == (0,)
        publish("http-authority-negatives.json", {"disabled_app": 403, "revoked_policy": 403, "expired_policy": 403,
                                                  "business_and_failed_admission_epoch_unchanged": True})
        # Real commit latency fixture, never a skipped/replaced authority guard.
        # Observe this actual APP backend in COMMIT/PgSleep before expiry.
        admin.execute("CREATE FUNCTION ra4b_test.fixture_commit_delay() RETURNS trigger LANGUAGE plpgsql "
                      "SET search_path=pg_catalog AS $$ BEGIN PERFORM pg_sleep(1); RETURN NULL; END $$")
        admin.execute("REVOKE ALL ON FUNCTION ra4b_test.fixture_commit_delay() FROM PUBLIC")
        admin.execute("CREATE CONSTRAINT TRIGGER ra4b_0_fixture_delay AFTER INSERT ON ra4a.jobs "
                      "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ra4b_test.fixture_commit_delay()")
        delayed = []
        try:
            admin.execute("UPDATE ra4a.policies SET expires_at=clock_timestamp()+interval '700 milliseconds' WHERE tenant_id='tenant-test'")
            thread = threading.Thread(target=lambda: delayed.append(request(app, key="http-expiry-at-commit-0001")))
            thread.start()
            wait_for(lambda: admin.execute("SELECT count(*) FROM pg_stat_activity WHERE usename='ra4b_test_a_app' "
                                           "AND query='COMMIT' AND wait_event='PgSleep'").fetchone()[0] > 0)
            assert admin.execute("SELECT bool_and(expires_at>clock_timestamp()) FROM ra4a.policies WHERE tenant_id='tenant-test'").fetchone() == (True,)
            thread.join(5)
            assert delayed and delayed[0][0] == 403 and fingerprint(admin) == early
            assert admin.execute("SELECT count(*) FROM ra4b_test.origin_epochs").fetchone() == (0,)
            publish("http-commit-expiry.json", {"actual_app_commit_sleep_observed_before_expiry": True,
                                                "response": 403, "all_admission_rows_rolled_back": True})
        finally:
            admin.execute("DROP TRIGGER ra4b_0_fixture_delay ON ra4a.jobs")
            admin.execute("DROP FUNCTION ra4b_test.fixture_commit_delay()")
            admin.execute("UPDATE ra4a.policies SET expires_at=clock_timestamp()+interval '1 day' WHERE tenant_id='tenant-test'")
        # Block admission at tenant lock. No receipt/row exists while it cannot commit.
        gate = old.connect()
        answers = []
        with gate.transaction():
            gate.execute("SELECT 1 FROM ra4a.tenants WHERE tenant_id='tenant-test' FOR UPDATE")
            thread = threading.Thread(target=lambda: answers.append(request(app)))
            thread.start()
            wait_for(lambda: admin.execute("SELECT count(*) FROM pg_stat_activity WHERE usename='ra4b_test_a_app' "
                                           "AND wait_event_type='Lock' AND query LIKE '%%ra4b_test.admit%%'").fetchone()[0] > 0)
            assert thread.is_alive() and not answers
            assert admin.execute("SELECT count(*) FROM ra4a.requests").fetchone() == (0,)
        gate.close()
        thread.join(5)
        assert answers and answers[0][0] == 202
        receipt = answers[0][1]
        assert row(admin)[0] == "PENDING"
        assert request(app)[1] == receipt
        path = "/v1/audit-requests/" + receipt["request_id"]
        assert request(app, "GET", path)[1]["issue_count"] == 1
        before = fingerprint(admin)
        assert request(app, payload={"source_ref": "accepted-200"})[0] == 409 and fingerprint(admin) == before
        assert request(app, "POST", path + "/cancel")[0] == 501
        assert fingerprint(admin) == before
        checks = [(401, {"Authorization": "Bearer wrong"}), (403, {"Host": "evil.invalid"}),
                  (403, {"Origin": "https://evil.invalid"}), (400, {"Cookie": "session=forged"}),
                  (400, {"X-Tenant-ID": "tenant-beta"}), (400, {"X-Role": "postgres"})]
        for code, headers in checks:
            assert request(app, overrides=headers)[0] == code
            assert fingerprint(admin) == before
        for payload in ({"source_ref": "https://example.invalid/"}, {"source_ref": "accepted-404", "tenant_id": "tenant-beta"},
                        {"source_ref": "accepted-404", "dsn": "arbitrary"}, {"source_ref": []},
                        {"source_ref": "accepted-404", "epoch": 999}):
            assert request(app, payload=payload)[0] == 422
            assert fingerprint(admin) == before
        assert request(app, payload={"source_ref": "x" * 1100})[0] == 413
        assert request(app, overrides={"Content-Type": "text/plain"})[0] == 415
        assert request(app, key="tiny")[0] == 422
        for raw_body in (b'{"source_ref":"accepted-404","source_ref":"accepted-200"}', b'{'):
            header = ("POST /v1/audit-requests HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nOrigin: http://127.0.0.1:8765\r\n"
                      "Authorization: Bearer " + app["bearer"] + "\r\nIdempotency-Key: boundary-json-0001\r\n"
                      "Content-Type: application/json\r\nContent-Length: " + str(len(raw_body)) + "\r\n\r\n").encode()
            with socket.create_connection(("127.0.0.1", 8765), timeout=5) as sock:
                sock.sendall(header + raw_body)
                assert b" 400 " in sock.recv(2048).split(b"\r\n", 1)[0]
        with socket.create_connection(("127.0.0.1", 8765), timeout=5) as sock:
            sock.sendall(b"POST /v1/audit-requests HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nUser-Agent: " + b"x" * 9000 + b"\r\n\r\n")
            assert b" 431 " in sock.recv(2048).split(b"\r\n", 1)[0]
        with socket.create_connection(("127.0.0.1", 8765), timeout=5) as sock:
            sock.sendall(("POST /v1/audit-requests HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nOrigin: http://127.0.0.1:8765\r\n"
                          "Authorization: Bearer " + app["bearer"] + "\r\nContent-Length: 10\r\n\r\n{").encode())
            assert b" 400 " in sock.recv(2048).split(b"\r\n", 1)[0]
        assert fingerprint(admin) == before
        publish("http-parser-bounds.json", {"oversized_body": 413, "oversized_headers": 431,
                 "duplicate_or_malformed_json": 400, "incomplete_body_deadline": 400, "unexpected_epoch": 422,
                 "idempotency_conflict": 409, "no_business_advancement": True})
        # Duplicate headers, pipelining and chunked transfer all denied before DB.
        for extra in (b"Content-Length: 2\r\nContent-Length: 2\r\n", b"Transfer-Encoding: chunked\r\n"):
            with socket.create_connection(("127.0.0.1", 8765), timeout=3) as sock:
                sock.sendall(b"POST /v1/audit-requests HTTP/1.1\r\nHost: 127.0.0.1:8765\r\n" + extra + b"\r\n{}")
                assert b" 400 " in sock.recv(2048).split(b"\r\n", 1)[0]
            assert fingerprint(admin) == before
        # Truly independent process, committed lease, SIGKILL and new process recovery.
        first, first_log = spawn("WORKER", worker_path, "--once", "--lease-seconds", "1", "--hold-seconds", "20")
        wait_for(lambda: b'"LEASED"' in first_log.read_bytes())
        assert "CapEff:\t0000000000000000" in Path(f"/proc/{first.pid}/status").read_text()
        original = row(admin)
        assert original[:3] == ("LEASED", 1, 1)
        signal_child(first, signal.SIGKILL)
        assert first.wait(3) == -signal.SIGKILL
        assert row(admin) == original
        time.sleep(1.1)
        second, _ = spawn("WORKER", worker_path, "--once", "--lease-seconds", "5")
        assert second.wait(8) == 0
        assert row(admin)[:3] == ("TEST_ONLY_DONE", 2, 2)
        done = request(app, "GET", path)
        assert done[0] == 200 and done[1]["status"] == "TEST_ONLY_CONSUMED"
        before = fingerprint(admin)
        assert request(app)[1] == receipt and fingerprint(admin) == before
        assert admin.execute("SELECT count(*) FROM ra4a.outbox WHERE NOT undelivered").fetchone() == (0,)
        publish("durable-runtime.json", {"receipt": receipt, "final": done[1], "independent_worker_sigkill": True,
                                         "reclaimed_sequence": 2, "202_waited_for_commit": True,
                                         "negative_state_unchanged": True, "cancel": 501})
        # Persist one no-finding source as independent admission, consume it.
        code, empty = request(app, payload={"source_ref": "accepted-200"}, key="runtime-key-0002")
        assert code == 202
        third, _ = spawn("WORKER", worker_path, "--once")
        assert third.wait(8) == 0
        empty_status = request(app, "GET", "/v1/audit-requests/" + empty["request_id"])[1]
        assert empty_status["issue_count"] == 0 and empty_status["status"] == "TEST_ONLY_CONSUMED"
        publish("accepted-sources-runtime.json", {"404": done[1], "200": empty_status})
        publish("receipts.json", {"runtime-key-0001": receipt, "runtime-key-0002": empty})
        code, exhausted = request(app, key="runtime-deadletter-0003")
        assert code == 202
        for attempt in range(1, 4):
            process, process_log = spawn("WORKER", worker_path, "--once", "--lease-seconds", "1", "--hold-seconds", "20")
            wait_for(lambda: b'"LEASED"' in process_log.read_bytes())
            observed = admin.execute("SELECT state,attempts,lease_seq FROM ra4a.jobs WHERE job_id=%s", (exhausted["job_id"],)).fetchone()
            assert observed == ("LEASED", attempt, attempt)
            signal_child(process, signal.SIGKILL)
            assert process.wait(3) == -signal.SIGKILL
            time.sleep(1.1)
        final, _ = spawn("WORKER", worker_path, "--once")
        assert final.wait(8) == 0
        assert request(app, "GET", "/v1/audit-requests/" + exhausted["request_id"])[1]["status"] == "DEAD_LETTER"
        assert admin.execute("SELECT count(*) FROM ra4a.outbox WHERE run_id=%s AND kind='TEST_ONLY_CONSUMED'", (exhausted["run_id"],)).fetchone() == (0,)
        publish("dead-letter.json", {"three_actual_sigkills": True, "attempts": 3, "state": "DEAD_LETTER", "consumed_outbox": 0})
        # The first response is deliberately discarded. Only independently read
        # persisted IDs establish the subsequent real HTTP retry's identity.
        raw_body = b'{"source_ref":"accepted-200"}'
        raw = ("POST /v1/audit-requests HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nOrigin: http://127.0.0.1:8765\r\n"
               "Authorization: Bearer " + app["bearer"] + "\r\nIdempotency-Key: runtime-lost-0004\r\n"
               "Content-Type: application/json\r\nContent-Length: " + str(len(raw_body)) + "\r\n\r\n").encode() + raw_body
        with socket.create_connection(("127.0.0.1", 8765), timeout=3) as sock:
            sock.sendall(raw)
        def persisted_lost():
            return admin.execute("SELECT q.request_id,s.run_id,j.job_id,e.event_id FROM ra4a.requests q "
                                 "JOIN ra4a.runs s USING(tenant_id,request_id) JOIN ra4a.jobs j USING(tenant_id,run_id) "
                                 "JOIN ra4a.outbox e USING(tenant_id,run_id) WHERE q.idempotency_key='runtime-lost-0004' AND e.kind='TEST_ONLY_ADMITTED'").fetchone()
        durable = wait_for(persisted_lost)
        before = fingerprint(admin)
        code, lost = request(app, key="runtime-lost-0004", payload={"source_ref": "accepted-200"})
        assert code == 202 and tuple(lost[k] for k in ("request_id", "run_id", "job_id", "event_id")) == tuple(map(str, durable))
        assert fingerprint(admin) == before
        consume, _ = spawn("WORKER", worker_path, "--once")
        assert consume.wait(8) == 0
        publish("lost-response.json", {"status": "PASS", "response_discarded": True, "retry_receipt": lost,
                                       "retry_created_no_new_business_rows": True})
        before_outage = fingerprint(admin)
        publish("db-down-ready.json", {"ready": True})
        wait_for(lambda: (OUT / "pg-paused.json").exists(), 30)
        started = time.monotonic()
        code, error = request(app, key="runtime-dbdown-0005")
        assert code == 503 and error == {"error": "DURABLE_STORE_UNAVAILABLE"}
        publish("db-down-result.json", {"status": code, "seconds": time.monotonic() - started,
                                        "no_sql_or_credentials_in_response": True})
        wait_for(lambda: (OUT / "pg-resumed.json").exists(), 30)
        assert fingerprint(admin) == before_outage
        assert request(app, "GET", path)[0] == 200
    publish("runtime-result.json", {"python": sys.version, "status": "PASS", "authority": "TEST_ONLY",
                                    "gate": "B4_P1_CANDIDATE_NOT_G1_EXIT"})


if __name__ == "__main__":
    try:
        main()
    finally:
        for child in reversed(CHILDREN):
            if child.poll() is None:
                signal_child(child, signal.SIGTERM)
                try:
                    child.wait(3)
                except subprocess.TimeoutExpired:
                    signal_child(child, signal.SIGKILL)
                    child.wait(3)
        assert not any(secret.encode() in p.read_bytes() for p in OUT.rglob("*") if p.is_file() for secret in SECRET_VALUES)
        publish("runtime-credential-scan.json", {"actual_secret_count": len(SECRET_VALUES), "matches": 0,
                                                 "child_processes_stopped": all(p.poll() is not None for p in CHILDREN)})

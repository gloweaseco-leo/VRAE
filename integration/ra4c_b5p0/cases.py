"""Actual Ed25519 -> B5A original read -> B3 COMMIT -> same SSR receipt."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import socket
import time
from urllib.parse import urlencode

import pytest

from .support import Client


def submit(c, path, fields, headers=None):
    return c.request(
        "POST",
        path,
        urlencode(fields).encode(),
        {"Content-Type": "application/x-www-form-urlencoded", **(headers or {})},
    )


@pytest.mark.parametrize("case", ["404", "200"])
def test_real_signed_ssr_atomic_journey(runtime, case):
    c = runtime.client()
    assert c.login(runtime.issuer, "task-" + case)[0][0] == 303
    runtime.original_descriptors = [runtime.original_facts(case)]
    before = runtime.roots()
    path, f, body = runtime.form(c, case)
    assert b"NOT APPROVED" in body and "保存内部演练记录（非审批）".encode() in body
    status, body, _ = submit(c, path, f)
    assert status == 200, body[:300]
    assert b"TEST_ONLY_REVIEW_INTENT" in body and b"NOT APPROVED" in body
    assert (
        b"COVERAGE_ACK_TEST_ONLY" in body if case == "200" else b"REVIEW_INTENT_TEST_ONLY" in body
    )
    assert b"witness" not in body.lower() and b"idempotency_key" not in body
    counts = runtime.data()
    assert counts["intents"] == counts["audit"] == counts["outbox"] == 1
    assert counts["claims"] == (6 if case == "404" else 3)
    assert runtime.roots() == before
    assert c.request("GET", path + "/receipt")[1] == body
    assert submit(c, path, f)[1] == body
    assert runtime.data() == counts


@pytest.mark.parametrize(
    "field",
    [
        "role",
        "db_role",
        "dsn",
        "tenant_id",
        "subject",
        "issuer",
        "epoch",
        "witness",
        "idempotency_key",
        "_csrf",
        "_ticket",
        "target",
        "version",
        "guard.0",
        "section.coverage.v1",
    ],
)
def test_forged_fields_zero_business_effect(runtime, field):
    c = runtime.client()
    assert c.login(runtime.issuer)[0][0] == 303
    path, f, _ = runtime.form(c)
    f[field] = "forged"
    assert submit(c, path, f)[0] in (403, 409)
    assert all(v == 0 for v in runtime.data().values())


@pytest.mark.parametrize(
    "bad",
    [
        "origin",
        "host",
        "cookie",
        "anchor",
        "assignment",
        "epoch",
        "witness",
        "cross-subject",
        "cross-issuer",
        "cross-tenant",
        "cross-version",
    ],
)
def test_current_authority_refused(runtime, bad):
    c = runtime.client()
    assert c.login(runtime.issuer)[0][0] == 303
    path, f, _ = runtime.form(c)
    h = {}
    if bad == "origin":
        h["Origin"] = "https://untrusted.invalid"
    elif bad == "host":
        h["Host"] = "untrusted.invalid"
    elif bad == "cookie":
        c.cookies["b5a_session"] = "A" * 43
    elif bad == "anchor":
        runtime.store.rotate(
            replace(runtime.store.boundary.anchor, available=False), runtime.bindings.values()
        )
    elif bad == "assignment":
        with runtime.lab.connect() as a:
            a.execute(
                "UPDATE ra4a_review_test.assignments SET active=false WHERE db_role='p2b1_test_a_reviewer'"
            )
    elif bad == "epoch":
        with runtime.lab.connect() as a:
            a.execute("UPDATE b3_p0.authority SET epoch=epoch+1")
    elif bad == "witness":
        from uuid import uuid4

        b = runtime.links["task-404"]
        runtime.app.bindings["task-404"] = replace(b, witness=replace(b.witness, token=uuid4()))
    else:
        b = runtime.app.bindings["task-404"]
        if bad == "cross-subject":
            runtime.store.boundary.assignments = (
                replace(runtime.bindings["task-404"], subject="other"),
            )
        elif bad == "cross-issuer":
            runtime.store.boundary.anchor = replace(runtime.store.boundary.anchor, issuer="other")
        else:
            runtime.store.boundary.assignments = (
                replace(
                    runtime.bindings["task-404"],
                    location=replace(
                        b.witness.location,
                        **({"tenant": "tenant-beta"} if bad == "cross-tenant" else {"version": 2}),
                    ),
                ),
            )
    assert submit(c, path, f, h)[0] in (403, 409)
    assert all(v == 0 for v in runtime.data().values())


@pytest.mark.parametrize("conflict", [False, True])
def test_actual_double_click_same_or_conflicted(runtime, conflict):
    c = runtime.client()
    assert c.login(runtime.issuer)[0][0] == 303
    path, f, _ = runtime.form(c)
    other = dict(f)
    if conflict:
        other["reason"] = "Different canonical proposal"

    def click(fields):
        clone = Client(runtime.origin)
        clone.cookies = dict(c.cookies)
        return submit(clone, path, fields)

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(click, [f, other]))
    assert sorted(x[0] for x in results) == ([200, 409] if conflict else [200, 200])
    assert runtime.data()["intents"] == runtime.data()["audit"] == runtime.data()["outbox"] == 1
    if not conflict:
        assert results[0][1] == results[1][1]


def test_b5_anchor_revoked_at_actual_commit_entry_rolls_back(runtime):
    c = runtime.client()
    assert c.login(runtime.issuer)[0][0] == 303
    path, f, _ = runtime.form(c)

    def revoke(event):
        if event["event"] == "intent_attempt":

            def at_entry(e):
                if e["event"] == "commit_entry":
                    runtime.store.rotate(
                        replace(runtime.store.boundary.anchor, available=False),
                        runtime.bindings.values(),
                    )

            runtime.hook = at_entry

    runtime.hook = revoke
    assert submit(c, path, f)[0] in (403, 409)
    assert all(v == 0 for v in runtime.data().values())


def test_lost_response_new_authenticated_lookup_after_session_restart(runtime):
    c = runtime.client()
    assert c.login(runtime.issuer)[0][0] == 303
    path, f, _ = runtime.form(c)
    raw = urlencode(f).encode()
    with socket.create_connection(("127.0.0.1", runtime.http.server_port), timeout=10) as s:
        request = (
            f"POST {path} HTTP/1.0\r\nHost: 127.0.0.1:{runtime.http.server_port}\r\nOrigin: {runtime.origin}\r\n"
            f"Cookie: b5a_session={c.cookies['b5a_session']}\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: {len(raw)}\r\n\r\n"
        ).encode() + raw
        s.sendall(request)
    deadline = time.monotonic() + 30
    while runtime.data()["intents"] != 1:
        assert time.monotonic() < deadline
        time.sleep(0.05)
    runtime.store.rotate(runtime.store.boundary.anchor, runtime.bindings.values())
    assert c.request("GET", path + "/receipt")[0] == 403
    fresh = runtime.client()
    assert fresh.login(runtime.issuer)[0][0] == 303
    status, body, _ = fresh.request("GET", path + "/receipt")
    assert status == 200 and b"NOT APPROVED" in body
    assert runtime.data()["outbox"] == 1


@pytest.mark.parametrize(
    "path",
    [
        "/v1/review",
        "/v1/review-decisions",
        "/v1/share-grants",
        "/b5a/tasks/task-404/approve",
        "/b5a/tasks/task-404/share",
    ],
)
def test_effective_ports_always_denied(runtime, path):
    c = runtime.client()
    assert c.login(runtime.issuer)[0][0] == 303
    assert c.request("POST", path, b"{}", {"Content-Type": "application/json"})[0] in (
        400,
        403,
        501,
    )
    assert all(v == 0 for v in runtime.data().values())


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE ra4a_private.principals SET enabled=false WHERE db_role='p2b1_test_a_reviewer'",
        "UPDATE ra4a_private.assignments SET active=false WHERE db_role='p2b1_test_a_reviewer'",
        "UPDATE b3_p0.authority SET anchor_active=false",
        "UPDATE b3_p0.authority SET anchor_expires=clock_timestamp()-interval '1 second'",
    ],
)
def test_revoked_scope_or_b3_anchor(runtime, sql):
    c = runtime.client()
    assert c.login(runtime.issuer)[0][0] == 303
    path, f, _ = runtime.form(c)
    with runtime.lab.connect() as a:
        a.execute(sql)
    assert submit(c, path, f)[0] in (403, 409)
    assert all(v == 0 for v in runtime.data().values())


def test_real_session_expiry_after_candidate_before_commit(runtime):
    c = runtime.client()
    assert c.login(runtime.issuer, changes={"exp": int(time.time()) + 60})[0][0] == 303
    path, f, _ = runtime.form(c)
    expires = next(iter(runtime.store.sessions.values())).expires
    observed = []

    def phase(event):
        if event["event"] == "intent_attempt":

            def delay(entry):
                if entry["event"] == "commit_entry":
                    observed.append("actual_candidate_before_driver_commit")
                    time.sleep(max(0, expires - time.time()) + 0.1)

            runtime.hook = delay

    runtime.hook = phase
    from http.client import HTTPConnection

    actual = HTTPConnection("127.0.0.1", c.port, timeout=90)
    try:
        actual.request(
            "POST",
            path,
            urlencode(f).encode(),
            {
                "Origin": runtime.origin,
                "Cookie": "b5a_session=" + c.cookies["b5a_session"],
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        response = actual.getresponse()
        response.read()
        assert response.status in (403, 409)
    finally:
        actual.close()
    assert observed and all(v == 0 for v in runtime.data().values())


def test_revision_race_after_original_read_before_submit(runtime):
    from integration.ra4a.p2a_support import add_reference, raw_args

    c = runtime.client()
    assert c.login(runtime.issuer)[0][0] == 303
    path, f, _ = runtime.form(c)

    def replace_revision(event):
        if event["event"] == "intent_attempt":
            runtime.hook = None
            with runtime.lab.connect() as admin:
                graph = add_reference(admin, version=2)
            with runtime.lab.connect("p2a_test_a_writer") as writer:
                writer.execute("SELECT ra4a_bytes.register(%s,%s,%s,%s,%s,%s,%s)", raw_args(graph))

    runtime.hook = replace_revision
    assert submit(c, path, f)[0] in (403, 409)
    assert all(v == 0 for v in runtime.data().values())


def test_actual_low_role_cannot_read_business_tables(runtime):
    import psycopg

    tables = [
        "b3_p0.intents",
        "b3_p0.claims",
        "b3_p0.sections",
        "b3_p0.audit",
        "b3_p0.outbox",
        "ra4a_bytes.objects",
        "ra4a_review_test.proposals",
        "ra4a_private.principals",
    ]
    with runtime.reader.settings.connect() as role:
        assert role.execute(
            "SELECT session_user,current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=session_user"
        ).fetchone() == ("p2b1_test_a_reviewer", "p2b1_test_a_reviewer", False, False)
        for table in tables:
            with pytest.raises(psycopg.Error) as caught:
                role.execute("SELECT * FROM " + table)
            assert caught.value.sqlstate == "42501"
            runtime.event(
                {
                    "event": "actual_raw_select_denied",
                    "sqlstate": caught.value.sqlstate,
                    "table": table,
                }
            )


def test_database_down_is_not_witness_authority(runtime):
    from .lab import docker
    import psycopg

    c = runtime.client()
    assert c.login(runtime.issuer)[0][0] == 303
    path, f, _ = runtime.form(c)
    docker("stop", "--time", "2", runtime.lab.name)
    try:
        assert submit(c, path, f)[0] in (403, 409)
    finally:
        docker("start", runtime.lab.name)
        runtime.lab.refresh_port()
        deadline = time.monotonic() + 30
        while True:
            try:
                with runtime.lab.connect():
                    break
            except psycopg.OperationalError:
                assert time.monotonic() < deadline
                time.sleep(0.1)
    assert all(v == 0 for v in runtime.data().values())


def test_wrong_b3_subject_candidate_is_rejected_before_commit(runtime):
    from uuid import uuid4

    c = runtime.client()
    assert c.login(runtime.issuer)[0][0] == 303
    path, f, _ = runtime.form(c)
    b = runtime.links["task-404"]
    loc = b.witness.location
    token = uuid4()
    with runtime.lab.connect() as a:
        a.execute(
            "INSERT INTO b3_p0.witnesses VALUES(%s,%s,%s,'TEST_ONLY_other',1,clock_timestamp()+interval '10 minutes',%s,%s,%s,%s,%s)",
            (
                loc.tenant,
                token,
                b.role,
                loc.ref_id,
                loc.source_run,
                loc.report,
                loc.version,
                loc.target_digest,
            ),
        )
    runtime.app.bindings["task-404"] = replace(b, witness=replace(b.witness, token=token))
    assert submit(c, path, f)[0] == 403
    assert all(v == 0 for v in runtime.data().values())


def test_real_child_process_restart_and_lost_response(runtime):
    import os
    import subprocess
    import sys
    from pathlib import Path

    runtime.http.shutdown()
    runtime.http.server_close()
    runtime.thread.join(timeout=10)
    profile = runtime.lab.private / "reviewer.json"
    bridge = runtime.lab.private / "bridge.json"
    profile.write_text(json.dumps(runtime.profile()), encoding="utf-8")
    bridge.write_text(json.dumps(runtime.bridge_profile()), encoding="utf-8")
    audit = runtime.lab.private / "child-audit.jsonl"
    root = Path(__file__).resolve().parents[2]
    stderr = (runtime.lab.private / "child-stderr.log").open("wb")

    def launch():
        p = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-m",
                "integration.ra4c_b5p0.http_server",
                "--profile",
                str(profile),
                "--bridge",
                str(bridge),
                "--audit",
                str(audit),
            ],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=stderr,
            env=dict(os.environ, PYTHONUTF8="1"),
        )
        return p, json.loads(p.stdout.readline())["url"].removesuffix("/b5a/login")

    child = None
    try:
        child, origin = launch()
        c = Client(origin)
        assert c.login(runtime.issuer)[0][0] == 303
        old_origin = runtime.origin
        runtime.origin = origin
        path, f, _ = runtime.form(c)
        raw = urlencode(f).encode()
        with socket.create_connection(("127.0.0.1", c.port), timeout=10) as s:
            head = (
                f"POST {path} HTTP/1.0\r\nHost: 127.0.0.1:{c.port}\r\nOrigin: {origin}\r\nCookie: b5a_session={c.cookies['b5a_session']}\r\n"
                f"Content-Type: application/x-www-form-urlencoded\r\nContent-Length: {len(raw)}\r\n\r\n"
            )
            s.sendall(head.encode() + raw)
        deadline = time.monotonic() + 30
        while runtime.data()["intents"] != 1:
            assert time.monotonic() < deadline
            time.sleep(0.05)
        child.terminate()
        child.wait(timeout=15)
        child, origin = launch()
        fresh = Client(origin)
        fresh.cookies = dict(c.cookies)
        assert fresh.request("GET", path + "/receipt")[0] == 403
        assert fresh.login(runtime.issuer)[0][0] == 303
        status, body, _ = fresh.request("GET", path + "/receipt")
        assert status == 200 and b"NOT APPROVED" in body
        assert runtime.data()["intents"] == runtime.data()["audit"] == runtime.data()["outbox"] == 1
        runtime.origin = old_origin
    finally:
        if child and child.poll() is None:
            child.terminate()
            child.wait(timeout=15)
        stderr.close()


@pytest.mark.parametrize("change", ["witness-expired", "wrong-actor", "stale-form"])
def test_additional_exact_binding_denials(runtime, change):
    c = runtime.client()
    assert c.login(runtime.issuer)[0][0] == 303
    path, fields, _ = runtime.form(c)
    if change == "witness-expired":
        from uuid import uuid4

        b = runtime.links["task-404"]
        loc = b.witness.location
        token = uuid4()
        with runtime.lab.connect() as admin:
            admin.execute(
                "INSERT INTO b3_p0.witnesses VALUES(%s,%s,%s,%s,1,clock_timestamp()-interval '1 second',%s,%s,%s,%s,%s)",
                (
                    loc.tenant,
                    token,
                    b.role,
                    b.b3_subject,
                    loc.ref_id,
                    loc.source_run,
                    loc.report,
                    loc.version,
                    loc.target_digest,
                ),
            )
        runtime.app.bindings["task-404"] = replace(b, witness=replace(b.witness, token=token))
        assert c.request("GET", path)[0] == 403
    elif change == "wrong-actor":
        b = runtime.bindings["task-404"]
        runtime.store.boundary.assignments = (replace(b, db_role="p2b1_test_a_peer"),)
        assert c.request("GET", path)[0] == 403
    else:
        assert c.login(runtime.issuer)[0][0] == 303
    assert submit(c, path, fields)[0] == 403
    assert all(value == 0 for value in runtime.data().values())


@pytest.mark.parametrize("boundary", ["b5a", "b3"])
def test_revoked_receipt_and_preview_never_reveal_persisted_result(runtime, boundary):
    c = runtime.client()
    assert c.login(runtime.issuer)[0][0] == 303
    path, fields, _ = runtime.form(c)
    assert submit(c, path, fields)[0] == 200
    before = runtime.data()
    if boundary == "b5a":
        runtime.store.rotate(
            replace(runtime.store.boundary.anchor, available=False), runtime.bindings.values()
        )
    else:
        with runtime.lab.connect() as admin:
            admin.execute("UPDATE b3_p0.authority SET epoch=epoch+1")
    for url in (path, path + "/receipt", "/b5a/tasks/task-404/compose"):
        status, body, _ = c.request("GET", url)
        assert status == 403 and b"rehearsal-receipt" not in body
        assert b"NOT APPROVED" in body
    assert runtime.data() == before


def test_actual_role_widening_and_raw_dml_denied(runtime):
    import psycopg

    with runtime.reader.settings.connect() as role:
        for query in (
            "SET ROLE postgres",
            "SET ROLE ra4a_test_a_app",
            "DELETE FROM b3_p0.intents",
            "UPDATE b3_p0.authority SET epoch=epoch+1",
        ):
            with pytest.raises(psycopg.Error) as caught:
                role.execute(query)
            assert caught.value.sqlstate == "42501"
            runtime.event({"event": "actual_role_or_dml_denied", "sqlstate": caught.value.sqlstate})
        assert role.execute("SELECT session_user=current_user").fetchone()[0] is True
    assert all(value == 0 for value in runtime.data().values())

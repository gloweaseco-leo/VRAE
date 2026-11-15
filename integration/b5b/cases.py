"""Real signed PG/HTTP B5B boundary tests; never seed a generated-job report."""

from dataclasses import replace
import hashlib
import time
from urllib.parse import urlencode
import pytest
from integration.ra4c_b5a.support import Forms
from integration.ra4c_b5p0.cases import submit
from vrae.b6_p0.delivery import OPERATIONS


def path(case="404", action="private-preview"):
    return "/b5a/tasks/task-" + case + "/b5b/" + action


@pytest.mark.parametrize("case", ["404", "200"])
def test_same_signed_workspace_preview_original_document_and_durable_receipt(runtime, case):
    c = runtime.client()
    assert c.login(runtime.issuer, "task-" + case)[0][0] == 303
    home = c.request("GET", "/b5a/")
    assert home[0] == 200 and b"BLOCKED_NO_ACCEPTED_LEASE_BOUND_RESULT_PORT" in home[1]
    assert b"BLOCKED_NO_ACCEPTED_REVIEWER_TASK_STATUS_PORT" in home[1]
    assert b"UNKNOWN" in home[1] and b'data-key="b5b-preview"' in home[1]
    sid = c.cookies["b5a_session"]
    package = runtime.handoff.prepare(sid)
    before = runtime.data()
    code, body, _ = c.request("GET", path(case))
    assert code == 200 and package.candidate.document["content_digest"].encode() in body
    doc = c.request("GET", path(case, "private-document"))
    assert doc[0] == 200 and doc[1] == package.private_html
    assert hashlib.sha256(doc[1]).hexdigest() == package.candidate.document["private_html_sha256"]
    assert runtime.data() == before
    # Preview and mutation are independent positive groups under the original
    # short-lived identity. Authenticate the mutation group freshly rather than
    # assuming that an arbitrarily long inspection extends the first token.
    assert c.login(runtime.issuer, "task-" + case)[0][0] == 303
    p, fields, _ = runtime.form(c, case)
    saved = submit(c, p, fields)
    assert saved[0] == 200 and b"NOT APPROVED" in saved[1]
    counts = runtime.data()
    assert counts["intents"] == counts["audit"] == counts["outbox"] == 1
    assert c.request("GET", p + "/receipt")[1] == saved[1]
    repeated = submit(c, p, fields)
    assert repeated[0] == 200
    assert repeated[1] == saved[1] and runtime.data() == counts


@pytest.mark.parametrize("route", ["private-preview", "private-document", "private-view", "worker-result"])
def test_unauthenticated_or_cross_assignment_has_no_private_output(runtime, route):
    c = runtime.client()
    assert c.request("GET", path(action=route))[0] == 403
    assert c.login(runtime.issuer)[0][0] == 303
    assert c.request("GET", path("200", route))[0] == 403
    assert all(v == 0 for v in runtime.data().values())


@pytest.mark.parametrize(
    "change",
    ["assignment", "tenant", "version", "anchor", "b3-epoch", "policy-expiry", "policy-role"],
)
def test_current_authority_and_policy_revocation_fail_closed(runtime, change):
    c = runtime.client()
    assert c.login(runtime.issuer)[0][0] == 303
    assert c.request("GET", path())[0] == 200
    if change == "assignment":
        with runtime.lab.connect() as a:
            a.execute(
                "UPDATE ra4a_review_test.assignments SET active=false WHERE db_role='p2b1_test_a_reviewer'"
            )
    elif change == "b3-epoch":
        with runtime.lab.connect() as a:
            a.execute("UPDATE b3_p0.authority SET epoch=epoch+1")
    elif change in ("tenant", "version"):
        binding = runtime.bindings["task-404"]
        value = {"tenant": "tenant-beta"} if change == "tenant" else {"version": 2}
        runtime.store.boundary.assignments = (
            replace(binding, location=replace(binding.location, **value)),
        )
    elif change == "anchor":
        runtime.store.rotate(
            replace(runtime.store.boundary.anchor, available=False), runtime.bindings.values()
        )
    else:
        old = runtime.handoff.policies["task-404"]
        value = (
            {"expires": int(time.time()) - 1}
            if change == "policy-expiry"
            else {"role": "p2b1_test_b_reviewer"}
        )
        runtime.handoff.policies["task-404"] = replace(old, **value)
    for action in ("private-preview", "private-document"):
        code, body, _ = c.request("GET", path(action=action))
        assert code == 403 and b"b5b-candidate-digest" not in body
    assert all(v == 0 for v in runtime.data().values())


@pytest.mark.parametrize(
    "query", ["version=2", "tenant_id=tenant-beta", "request_id=fake", "DONE=true", "report=200"]
)
def test_client_metadata_cannot_create_status_or_result_join(runtime, query):
    c = runtime.client()
    assert c.login(runtime.issuer)[0][0] == 303
    assert c.request("GET", path(action="worker-result") + "?" + query)[0] == 403
    code, body, _ = c.request("GET", path(action="worker-result"))
    assert code == 409 and b"BLOCKED_NO_ACCEPTED_LEASE_BOUND_RESULT_PORT" in body
    assert b"UNKNOWN" in body and b"b5b-candidate-digest" not in body
    assert all(v == 0 for v in runtime.data().values())


@pytest.mark.parametrize("operation", sorted(OPERATIONS))
def test_real_b6_gate_refuses_every_delivery_operation_without_business_write(runtime, operation):
    c = runtime.client()
    assert c.login(runtime.issuer)[0][0] == 303
    p = path(action="delivery")
    code, body, _ = c.request("GET", path())
    assert code == 200
    fields = Forms(body.decode()).forms[p]
    fields["operation"] = operation
    before = runtime.data()
    result = c.request(
        "POST", p, urlencode(fields).encode(), {"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert result[0] == 403 and b"B6_AUTHORITY_UNAVAILABLE" in result[1]
    assert b"sent=false" in result[1] and runtime.data() == before
    assert len(runtime.consumer.delivery.sink.records) == 1


def test_new_preview_reuses_original_unknown_commit_and_restart_receipt(runtime):
    c = runtime.client()
    assert c.login(runtime.issuer)[0][0] == 303
    p, fields, _ = runtime.form(c)
    assert c.request("GET", p + "/receipt")[0] == 409
    assert all(v == 0 for v in runtime.data().values())
    saved = submit(c, p, fields)
    assert saved[0] == 200
    expected = runtime.data()
    runtime.http.shutdown()
    runtime.http.server_close()
    runtime.thread.join(timeout=10)
    runtime.store.sessions.clear()
    runtime.launch()
    after = runtime.client()
    assert after.login(runtime.issuer)[0][0] == 303
    assert after.request("GET", p + "/receipt")[1] == saved[1]
    assert after.request("GET", path())[0] == 200 and runtime.data() == expected


def test_real_b5b_child_lost_response_restart_and_profile_rotation(runtime):
    import socket
    from .process import Child
    from integration.ra4c_b5a.support import Client

    runtime.http.shutdown()
    runtime.http.server_close()
    runtime.thread.join(timeout=10)
    child = Child(runtime)
    try:
        child.start()
        c = Client(child.origin)
        assert c.login(runtime.issuer)[0][0] == 303
        p, fields, _ = runtime.form(c)
        raw = urlencode(fields).encode()
        with socket.create_connection(("127.0.0.1", c.port), timeout=10) as sock:
            header = (
                f"POST {p} HTTP/1.0\r\nHost: 127.0.0.1:{c.port}\r\nOrigin: {child.origin}\r\n"
                f"Cookie: b5a_session={c.cookies['b5a_session']}\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: {len(raw)}\r\n\r\n"
            )
            sock.sendall(header.encode() + raw)
        deadline = time.monotonic() + 30
        while runtime.data()["intents"] != 1:
            assert time.monotonic() < deadline
            time.sleep(0.05)
        child.stop()
        child.start()
        fresh = Client(child.origin)
        fresh.cookies = dict(c.cookies)
        assert fresh.request("GET", p + "/receipt")[0] == 403
        assert fresh.login(runtime.issuer)[0][0] == 303
        receipt = fresh.request("GET", p + "/receipt")
        assert receipt[0] == 200 and b"NOT APPROVED" in receipt[1]
        assert fresh.request("GET", path())[0] == 200
        assert runtime.data()["intents"] == runtime.data()["audit"] == runtime.data()["outbox"] == 1
        cfg = child.policies.read_bytes()
        child.policies.write_bytes(cfg + b" ")
        denied = fresh.request("GET", path())
        assert denied[0] == 403 and b"b5b-candidate-digest" not in denied[1]
    finally:
        child.stop()

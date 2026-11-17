"""Runtime plumbing with real C1/C2 output; DETACHED M1 boundary, not Worker E2E."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import re
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

from apps.operator_console.b5a_http import FORM
from apps.operator_console.b5b_m2_tasks import TaskWorkflow
from integration.l2.support import Issuer, login, pins
from integration.l2_ops import native_report as assembly, native_tasks, native_runtime, readiness
from integration.l2_ops.checks.test_native_report import mounted_application, reviewed  # noqa: F401
from integration.l2_ops.source_profiles import selected
from vrae.l2.report import L2Denied
from vrae.l2_ops.ledger import BriefLedger
from vrae.l2_ops.tasks import L2Tasks, RegisteredSource
from vrae.l2_ops.sources import OperationsDenied


@pytest.fixture
def runtime(native_result, native_source, reviewed, tmp_path, monkeypatch):  # noqa: F811 -- imported pytest fixture
    app, generated = mounted_application(reviewed, tmp_path)
    ref, bundle, native = selected("industrial-p40-v3")
    from vrae.application.ra4b_p2.m1.consumer import AppEndpoint, TaskClient
    client = TaskClient(AppEndpoint("x"*40, bundle.tenant_id, frozenset({"accepted-404", "accepted-200", ref})))
    port = L2Tasks(client, [RegisteredSource(ref, native)])
    generated.workflow = TaskWorkflow(client, tmp_path/"tasks.sqlite", sources={"p40": {"source_ref": ref, "label": "P40", "depth": "L2"}})
    task = native_result.evidence.task
    assignment = SimpleNamespace(issuer="https://detached-m1.invalid", subject="detached-operator", tenant=task.tenant_id)
    monkeypatch.setattr(generated.sessions, "require", lambda sid: SimpleNamespace(assignment=assignment, expires=datetime.now(UTC).timestamp()+90))
    monkeypatch.setattr(generated.workflow, "task", lambda ticket, session: task)
    deadline = datetime.now(UTC)+timedelta(seconds=90)
    state = {"held": False, "production_calls": 0}

    @contextmanager
    def current(*a, **k):
        state["held"] = True
        try:
            yield native_result.evidence, deadline
        finally:
            state["held"] = False

    monkeypatch.setattr(native_tasks, "current_worker", current)
    monkeypatch.setattr(assembly, "current_worker", current)
    monkeypatch.setattr(assembly, "production_stamp", lambda *a: native_source[0].held.created_at)

    def produce(*a, **k):
        # Port spy only; the returned Source was really C1/C2 replayed by fixture.
        with current():
            state["production_calls"] += 1
            return native_source[0], native_result.activities

    monkeypatch.setattr(assembly, "produce_current", produce)
    issuer = Issuer()
    cfg = {"issuer": issuer.issuer, "audience": issuer.audience, "jwks": issuer.jwks,
        "expires": issuer.clock()+1700, "task_issuer": assignment.issuer, "task_subject": assignment.subject,
        "actor_id": "runtime-reviewer", "subject": "runtime-reviewer", "name": "受控合成审阅员", "tenant_id": bundle.tenant_id}

    def no_pg():
        raise AssertionError("this detached controller test does not claim PG Brief COMMIT")

    manager = native_tasks.NativeTasks(app, port, bundle, BriefLedger(no_pg), policy_expires_at=deadline.isoformat(),
        identity=cfg, private_root=tmp_path/"native", enabled=True)
    app.native_tasks = generated.native_tasks = manager
    app.origin = "http://127.0.0.1:41902"
    headers = {"Host": "127.0.0.1:41902", "Origin": app.origin, "Sec-Fetch-Site": "same-origin",
        "Cookie": "b5a_m2_session="+"a"*43}
    path = "/b5a/m2/task/"+"b"*43+"/native"
    return app, manager, task, issuer, headers, path, state


def produce_from_form(runtime):
    app, manager, task, issuer, headers, path, state = runtime
    reply = app.handle("GET", path, headers)
    assert reply.response.status == 200 and state["production_calls"] == 0
    nonce = re.search('name="_csrf" value="([^"]+)"', reply.response.body.decode()).group(1)
    posted = {**headers, "Content-Type": FORM}
    body = urlencode({"_csrf": nonce}).encode()
    response = app.handle("POST", path, posted, body)
    assert response.response.status == 303 and ("Location", "/b5a/l2/") in response.headers
    return response, posted, body


def test_runtime_task_form_mounts_actual_native_source_and_current_reader(runtime, native_source):
    app, manager, task, issuer, headers, path, state = runtime
    _, posted, body = produce_from_form(runtime)
    assert state["production_calls"] == 1 and not state["held"]
    rid = manager.active["report_id"]
    assert app.deep.ledgers[rid].source is native_source[0]
    assert app.handle("POST", path, posted, body).response.status == 403
    sid = login(issuer, manager.directory, "runtime-reviewer")
    c2 = {**headers, "Cookie": "b5a_l2_session="+sid}
    page = app.handle("GET", "/b5a/l2/r/"+rid, c2)
    assert page.response.status == 200 and "P40" in page.response.body.decode() and "MP25" not in page.response.body.decode()
    ledger = app.deep.ledgers[rid]
    view = ledger.read(sid, rid)
    receipt = ledger.review(sid, rid, **pins(view), action="APPROVE", reason="原生组件受控演练，非真实Worker或正式人审。",
        items={row["id"]: "ACK" for row in view.document["findings"]+view.document["blueprint"]}, attest=True)
    reader = app.native_business.bindings[rid].factory(sid)
    with reader.current() as current:
        assert state["held"] and current.pins["job_id"] == task.job_id
        assert current.review["receipt_ref"] == receipt["decision"]["decision_id"]
    assert not state["held"]


def test_same_task_reauthentication_preserves_report_receipt_and_expiry(runtime):
    app, manager, task, issuer, headers, path, _ = runtime
    produce_from_form(runtime)
    rid = manager.active["report_id"]
    sid = login(issuer, manager.directory, "runtime-reviewer")
    original = app.deep.ledgers[rid].read(sid, rid)
    expiry = manager.directory.require(sid).expires
    manager.activate(task, "new-detached-m1-session")
    assert manager.active["report_id"] == rid and manager.active["sid"] == "new-detached-m1-session"
    assert app.deep.ledgers[rid].read(sid, rid).payload == original.payload
    assert manager.directory.require(sid).expires == expiry
    manager.directory.revoked_keys.add(issuer.kid)
    manager.activate(task, "another-detached-m1-session")
    with pytest.raises(L2Denied):
        manager.directory.require(sid)


@pytest.mark.parametrize("case", ["blocked", "wrong_actor", "csrf", "extra_fields", "wrong_task_output"])
def test_runtime_controller_refuses_unsafe_or_unaccepted_requests(runtime, monkeypatch, case):
    app, manager, task, issuer, headers, path, state = runtime
    if case == "blocked":
        manager.enabled = False
    elif case == "wrong_actor":
        manager.identity["task_subject"] = "another-person"
    if case in ("blocked", "wrong_actor"):
        assert app.handle("GET", path, headers).response.status == 403
        assert state["production_calls"] == 0 and app.deep is None
        return
    nonce = manager.sessions.action("a"*43, path)
    fields = {"_csrf": nonce}
    if case == "csrf":
        fields["_csrf"] = "invalid"
    elif case == "extra_fields":
        fields["tenant_id"] = "tenant-beta"
    else:
        monkeypatch.setattr(manager, "task", lambda *_: replace(task, job_id="another-job"))
    reply = app.handle("POST", path, {**headers, "Content-Type": FORM}, urlencode(fields).encode())
    assert reply.response.status == 403 and app.deep is None


def test_private_runtime_gate_cannot_enable_unaccepted_performance_main(monkeypatch):
    monkeypatch.setattr(readiness, "ACCEPTED_PERFORMANCE_MAIN", None)
    assert readiness.ACCEPTED_PERFORMANCE_MAIN is None and not readiness.enabled()
    cfg = {"version": "C3_NATIVE_RUNTIME_1", "enabled": True, "accepted_performance_main": None,
        "source_profile": "industrial-p40-v3", "policy_expires_at": "2026-11-16T12:00:00+00:00",
        "identity": {}, "brief_password": "x"*32}
    with pytest.raises(OperationsDenied, match="TRUSTED_RUNTIME_CONFIG"):
        native_runtime.provision(None, cfg)


def test_task_scope_switch_never_resurrects_old_c2_session_or_nonce(runtime):
    app, manager, task, issuer, headers, path, state = runtime
    produce_from_form(runtime)
    rid = manager.active["report_id"]
    sid = login(issuer, manager.directory, "runtime-reviewer")
    seen = dict(manager.directory.seen)
    nonce, csrf = manager.directory.challenge()
    expiry = manager.directory.expires
    manager._select_report("l2-native-"+"0"*32)
    manager._select_report(rid)
    assert manager.directory.seen == seen and manager.directory.expires == expiry
    with pytest.raises(L2Denied):
        manager.directory.require(sid)
    with pytest.raises(L2Denied):
        manager.directory.login(issuer.token("runtime-reviewer", nonce), nonce, csrf)

"""Detached route contract; real Worker/PG/browser evidence is a separate stage."""
from contextlib import contextmanager
import json

import pytest

from integration.l2.support import login
from integration.l2_ops.checks.test_native_tasks import runtime, produce_from_form  # noqa: F401
from integration.l2_ops.checks.test_native_report import reviewed  # noqa: F401
from integration.s2_buyer_workbench.workbench import install
from vrae.l2_ops.sources import OperationsDenied


def ready(scenario):
    app, manager, task, issuer, headers, _, state = scenario
    produce_from_form(scenario)
    rid = manager.active["report_id"]
    sid = login(issuer, manager.directory, "runtime-reviewer")
    return app, manager, task, {**headers, "Cookie": "b5a_l2_session="+sid}, rid, state


def test_additive_source_view_preserves_original_ports_report_and_review(runtime):  # noqa: F811
    app, manager, task, headers, rid, state = ready(runtime)
    business, directory, ledger = app.native_business, manager.directory, app.deep.ledgers[rid]
    assert business.source_views[rid].binding.pack.ref == manager.active["source"].held.native_pack_ref
    assert business.source_views[rid].binding.scope["run_id"] == task.run_id
    sid = app.deep.sid(headers)
    before = ledger.read(sid, rid)
    response = app.handle("GET", "/b5a/l2/r/"+rid+"/source-tasks", headers)
    assert response.response.status == 200 and b"s2-source-workbench" in response.response.body
    assert response.response.body.count(b'data-key="buyer-task-card"') == 2
    assert app.native_tasks is manager and app.native_business is business and manager.directory is directory
    assert ledger.read(sid, rid).version == before.version
    assert ledger.read(sid, rid).display_hash == before.display_hash
    assert not state["held"]
    with pytest.raises(ValueError):
        install(app, business.source_views[rid].binding)
    proof = json.loads((manager.root/"active-proof.json").read_bytes())
    assert proof["s2_source"]["pack_ref"] == proof["pack_ref"]
    assert proof["s2_source"]["authority"] == "READ_ONLY_CANDIDATE_NOT_RX_OR_GUARD"


def test_source_route_rechecks_original_task_authority(runtime, monkeypatch):  # noqa: F811
    app, manager, _, headers, rid, _ = ready(runtime)

    @contextmanager
    def revoked():
        raise OperationsDenied("DETACHED_ORIGINAL_TASK_REVOKED")
        yield

    monkeypatch.setattr(manager, "access", revoked)
    response = app.handle("GET", "/b5a/l2/r/"+rid+"/source-tasks", headers)
    assert response.response.status == 403 and b"s2-source-workbench" not in response.response.body


@pytest.mark.parametrize("kind", ["unsigned", "c2_revoked", "post", "tampered_projection", "tampered_buyer"])
def test_source_route_does_not_gain_identity_or_projection_authority(runtime, kind):  # noqa: F811
    app, manager, _, headers, rid, _ = ready(runtime)
    if kind == "unsigned":
        headers = {k:v for k,v in headers.items() if k != "Cookie"}
    elif kind == "c2_revoked":
        manager.directory.people["runtime-reviewer"] = __import__("dataclasses").replace(
            manager.directory.people["runtime-reviewer"], active=False)
    elif kind == "tampered_projection":
        component = app.native_business.source_views[rid]
        value = json.loads(component.binding.payload)
        value["industrial_projection"]["rows"][0]["observation"]["result"] = "PASS"
        value["scope"]["run_id"] = "foreign-run"
        component.binding.payload = json.dumps(value).encode()
    elif kind == "tampered_buyer":
        component = app.native_business.source_views[rid]
        value = json.loads(component.binding.buyer_payload)
        value["cards"][0]["result"] = "PASS"
        value["subject_model"] = "V25"
        component.binding.buyer_payload = json.dumps(value).encode()
    response = app.handle("POST" if kind == "post" else "GET",
                          "/b5a/l2/r/"+rid+"/source-tasks", headers)
    assert response.response.status == 403 and b"s2-source-workbench" not in response.response.body


@pytest.mark.parametrize("placement", ["private", "launch"])
def test_first_failure_receipt_retains_locations_and_hashes_without_log_text(tmp_path, monkeypatch, placement):
    import hashlib
    from integration.l2_ops import s2_acceptance_runtime as controller
    launch = tmp_path/"launch"
    launch.mkdir()
    monkeypatch.setattr(controller.local_app, "launch_for", lambda label: launch)
    raw = (b'Traceback (most recent call last):\n'
           b'  File "/source/integration/beta_review/codex3/runner.py", line 156, in start_native\n'
           b'    command = "postgresql://user:DO_NOT_PUBLISH@private.invalid/db"\n'
           b'subprocess.CalledProcessError: https://private.invalid/SECRET_TOKEN <html>PRIVATE_HTML</html>\n')
    raw += (b'Traceback (most recent call last):\n'
            b'  File "/source/integration/l2_ops/workbench.py", line 99, in cleanup\n'
            b'RuntimeError: SECONDARY_CLEANUP_MESSAGE\n')
    (launch/"local-supervisor.private.log").write_bytes(raw)
    root = tmp_path if placement == "private" else launch
    (root/"s2-original-red.private.log").write_text("PRIVATE_CONTROLLER_BODY", encoding="utf-8")
    receipt = controller.failure_receipt(tmp_path, "bounded-test", "original_local_app.status_until_ready",
                                      AssertionError("DO_NOT_PUBLISH"))
    assert receipt["phase"] == "original_local_app.status_until_ready"
    assert receipt["exception_type"] == "AssertionError"
    assert receipt["original_exception_type"] == "CalledProcessError"
    assert receipt["original_method_locations"] == [
        {"module": "integration/beta_review/codex3/runner.py", "line": 156, "method": "start_native"}]
    assert receipt["private_logs"][1]["sha256"] == hashlib.sha256(raw).hexdigest()
    exported = json.dumps(receipt)
    for forbidden in ("postgresql", "DO_NOT_PUBLISH", "SECRET_TOKEN", "PRIVATE_HTML",
                      "https:", "private.invalid", "PRIVATE_CONTROLLER_BODY", "/source/"):
        assert forbidden not in exported


def test_first_failure_receipt_missing_logs_does_not_invent_root_cause(tmp_path, monkeypatch):
    from integration.l2_ops import s2_acceptance_runtime as controller
    monkeypatch.setattr(controller.local_app, "launch_for", lambda label: tmp_path/"absent")
    receipt = controller.failure_receipt(tmp_path, "bounded-test", "original_local_app.start",
                                      RuntimeError("a missing log is not evidence"))
    assert receipt["private_logs"] == receipt["original_method_locations"] == []
    assert receipt["original_exception_type"] is None
    assert receipt["root_cause"] == "UNKNOWN_REQUIRES_PRIVATE_LOG_CORRELATION"


def test_metadata_receipt_does_not_replay_or_grant_current_source_read(runtime, monkeypatch):  # noqa: F811
    from integration.l2_ops.s2_acceptance_sources import proof
    app, manager, _, headers, rid, _ = ready(runtime)
    binding = app.native_business.source_views[rid].binding
    expected = proof(app.native_business, rid)
    calls = []

    def denied(projection):
        calls.append("actual_current_candidate_verification")
        raise ValueError("current read must still verify")

    monkeypatch.setattr(binding, "read_buyer", denied)
    detached = proof(app.native_business, rid)
    assert detached == expected and calls == []
    detached["buyer"]["cards"][0]["result"] = "untrusted mutation"
    assert proof(app.native_business, rid) == expected
    reply = app.handle("GET", "/b5a/l2/r/"+rid+"/source-tasks", headers)
    assert reply.response.status == 403
    assert calls == ["actual_current_candidate_verification"]


@pytest.mark.parametrize("kind,expected", [("Empty", "Empty"), ("https://SECRET.invalid", "OTHER"),
                                          ({"token": "SECRET"}, "OTHER")])
def test_transport_receipt_exports_only_allowlisted_exception_class(tmp_path, monkeypatch, kind, expected):
    from integration.l2_ops import s2_acceptance_runtime as controller
    monkeypatch.setattr(controller.local_app, "launch_for", lambda label: tmp_path/"absent")
    (tmp_path/"transport-failure.private.json").write_text(json.dumps({"kind":kind}), encoding="utf-8")
    receipt = controller.failure_receipt(tmp_path, "bounded-test", "original_browser.same_task",
                                         AssertionError("SECRET"))
    assert receipt["observed_transport_exception_type"] == expected
    assert receipt["private_logs"][0]["role"] == "original_http_transport"
    assert "SECRET" not in json.dumps(receipt)

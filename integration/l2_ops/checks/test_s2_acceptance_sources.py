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


@pytest.mark.parametrize("kind", ["unsigned", "c2_revoked", "post", "tampered_projection"])
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
    response = app.handle("POST" if kind == "post" else "GET",
                          "/b5a/l2/r/"+rid+"/source-tasks", headers)
    assert response.response.status == 403 and b"s2-source-workbench" not in response.response.body

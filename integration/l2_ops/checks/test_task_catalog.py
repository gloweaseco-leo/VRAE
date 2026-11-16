"""Original SSR TaskWorkflow catalog compatibility, no APP/DB authority claim."""
from contextlib import contextmanager
from types import SimpleNamespace
import threading

import pytest

from apps.operator_console.b5b_m2_tasks import TaskWorkflow
from vrae.application.ra4b_p2.m1.consumer import AppEndpoint, TaskClient
from vrae.identity.boundary import IdentityDenied


def client():
    return TaskClient(AppEndpoint("x" * 40, "tenant-test", frozenset({"accepted-404", "accepted-200", "l2-industrial-p40-v3"})))


def spec(**kwargs):
    return {"p40": {"source_ref": "l2-industrial-p40-v3", "label": "P40/V25 L2", "depth": "L2", **kwargs}}


def test_default_original_404_200_catalog_and_task_schema_stay_identical(tmp_path):
    workflow = TaskWorkflow(client(), tmp_path / "tasks.sqlite")
    assert workflow.source_refs == {"404": "accepted-404", "200": "accepted-200"}
    assert workflow.source_enabled == {"404": True, "200": True}
    with workflow.connect() as c:
        assert [r[1] for r in c.execute("PRAGMA table_info(tasks)")] == ["ticket", "owner", "source_case", "idem", "handle"]


@pytest.mark.parametrize("bad", ["unprovisioned", "legacy_alias", "depth", "enabled", "duplicate", "field"])
def test_source_catalog_cannot_supply_new_permissions_or_relabel_old_sources(tmp_path, bad):
    rows = spec()
    if bad == "unprovisioned":
        rows["p40"]["source_ref"] = "not-configured"
    elif bad == "legacy_alias":
        rows = {"404": rows["p40"]}
    elif bad == "depth":
        rows["p40"]["depth"] = "APPROVED"
    elif bad == "enabled":
        rows["p40"]["enabled"] = "true"
    elif bad == "duplicate":
        rows["other"] = dict(rows["p40"])
    else:
        rows["p40"]["tenant_id"] = "tenant-beta"
    with pytest.raises(ValueError, match="SOURCE_CATALOG"):
        TaskWorkflow(client(), tmp_path / "tasks.sqlite", sources=rows)


def test_disabled_readiness_case_does_not_admit_another_known_failed_job(tmp_path, monkeypatch):
    port = client()
    calls = []
    monkeypatch.setattr(port, "create", lambda *a, **kw: calls.append((a, kw)))
    workflow = TaskWorkflow(port, tmp_path / "tasks.sqlite", sources=spec(enabled=False))
    assignment = SimpleNamespace(tenant="tenant-test")

    @contextmanager
    def current(_sid):
        yield None

    sessions = SimpleNamespace(lock=threading.RLock(), require=lambda _sid: SimpleNamespace(assignment=assignment), request=current)
    with pytest.raises(IdentityDenied):
        workflow.create(sessions, "unit-contract-only", "p40")
    assert not calls
    with workflow.connect() as c:
        assert c.execute("SELECT count(*) FROM tasks").fetchone() == (0,)

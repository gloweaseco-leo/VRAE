"""Detached integration contracts; actual PG/Worker/Chrome is a separate receipt."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import re
import time
import threading
from urllib.parse import urlencode

import pytest
from apps.operator_console.b5a_http import FORM
from integration.l2.support import login
from integration.l2_ops import native_tasks
from integration.l2_ops.checks.test_native_tasks import runtime, produce_from_form  # noqa: F401
from integration.l2_ops.checks.test_native_report import reviewed  # noqa: F401
from integration.l2_ops.conftest import native_result, native_source  # noqa: F401
from integration.s5_ops import adapter
from integration.s5_ops.trusted import write, read


@pytest.fixture
def ports(runtime, monkeypatch):  # noqa: F811
    app, manager, task, issuer, headers, _, state = runtime
    produce_from_form(runtime)
    rid = manager.active["report_id"]
    sid = login(issuer, manager.directory, "runtime-reviewer")
    headers = {**headers, "Cookie": headers["Cookie"] + "; b5a_l2_session=" + sid}
    # Only the M1 boundary is detached, as in accepted native_tasks tests.
    monkeypatch.setattr(adapter, "current_worker", native_tasks.current_worker)
    port = adapter.S5Ports(manager)
    manager.s5 = port
    port.bind(app.native_business, rid)
    with manager.access() as (evidence, _):
        # Explicit detached boundary values, never actual PG/Worker evidence.
        monkeypatch.setitem(
            evidence.signed_locator, "finish_event", "00000000-0000-4000-8000-000000000099"
        )
        monkeypatch.setitem(evidence.signed_locator, "report_sha256", "f" * 64)
        now = datetime.now(UTC)
        marker = {
            "version": "S5_SERVER_POST_COMMIT_1",
            "task": {
                k: getattr(task, k)
                for k in ("tenant_id", "request_id", "run_id", "job_id", "source_ref")
            },
            "lease_started_at": (now - timedelta(seconds=31)).isoformat(),
            "lease_expires_at": (now - timedelta(seconds=1)).isoformat(),
            "worker_completed_at": (now - timedelta(seconds=2)).isoformat(),
            "finish_event": evidence.signed_locator["finish_event"],
            "signed_result_sha256": evidence.signed_locator["report_sha256"],
            "completion_clock_basis": "VISIBLE_ROW_CREATED_AT_WITH_ORIGINAL_DEFERRED_LEASE_GUARD",
            "observed_committed_at": now.isoformat(),
        }
    path = manager.root / "s5-postcommit" / (task.job_id + ".json")
    write(path, marker)
    return app, manager, port, headers, rid, path


def submit(s, mode, extra=None):
    app, manager, port, headers, rid, _ = s
    path = "/b5a/l2/r/" + rid + "/s3"
    result = app.handle("GET", path, headers)
    assert result.response.status == 200
    match = re.search('name="_csrf" value="([^"]+)"', result.response.body.decode())
    assert match is not None
    nonce = match[1]
    raw = urlencode({"_csrf": nonce, "mode": mode, **(extra or {})}).encode()
    return app.handle("POST", path, {**headers, "Content-Type": FORM}, raw)


@pytest.mark.parametrize(
    "mode,status", [("NO_MODEL", "NOT_RUN"), ("FIXTURE", "CANDIDATES_FOR_HUMAN_REVIEW")]
)
def test_original_s3_is_called_with_current_native_task_and_unchanged_report(ports, mode, status):
    app, manager, port, headers, rid, _ = ports
    before = manager.active["source"].read()
    assert submit(ports, mode).response.status == 200
    job = list(port.jobs.values())[-1]
    deadline = time.monotonic() + 65
    while job.state not in (status, "REFUSED_OR_INTERRUPTED", "REFUSED"):
        assert time.monotonic() < deadline
        time.sleep(0.05)
    assert job.state == status
    assert job.result["mode"] == mode and job.result["real_model_calls"] == 0
    assert job.result["usage"]["amount"] is None and job.result["usage"]["cost_status"] == "UNKNOWN"
    assert job.result["deterministic_report_hash"] == before.version["content_hash"]
    assert job.session.context.completion.task == manager.active["source"].held
    assert manager.active["source"].read().display_hash == before.display_hash
    assert job.session.context.pack.ref == manager.active["source"].held.native_pack_ref
    assert submit(ports, mode).response.status == 200 and len(port.jobs) == 1
    result = app.handle("GET", "/b5a/l2/r/" + rid + "/s3", headers)
    assert result.response.status == 200 and b"s5-result" in result.response.body
    # A restarted controller retains history and cannot silently redispatch a fixture.
    restarted = adapter.S5Ports(manager)
    restarted.bind(app.native_business, rid)
    assert (
        restarted.jobs == {}
        and restarted.history(job.held)[0]["receipt_ref"] == job.result["receipt_ref"]
    )
    assert submit(ports, mode).response.status == 403
    assert manager.active["source"].read().display_hash == before.display_hash


@pytest.mark.parametrize(
    "extra",
    [
        {"tenant_id": "tenant-other"},
        {"report_hash": "0" * 64},
        {"provider": "NETWORK"},
        {"task": "browser-owned"},
    ],
)
def test_browser_cannot_supply_scope_report_or_provider_pins(ports, extra):
    assert submit(ports, "FIXTURE", extra).response.status == 403
    assert not ports[2].jobs


@pytest.mark.parametrize("kind", ["foreign_commit", "wrong_result_hash", "wrong_lease"])
def test_untrusted_completion_never_starts_original_session(ports, kind):
    path = ports[-1]
    value = read(path)
    if kind == "foreign_commit":
        value["task"]["run_id"] = "foreign-run"
    elif kind == "wrong_result_hash":
        value["signed_result_sha256"] = "0" * 64
    else:
        value["lease_started_at"] = value["lease_expires_at"]
    write(path, value)
    assert submit(ports, "FIXTURE").response.status == 403
    assert not ports[2].jobs


def test_current_c2_revocation_and_unsigned_access_are_not_receipt_authority(ports):
    app, manager, port, headers, rid, _ = ports
    path = "/b5a/l2/r/" + rid + "/s3"
    assert app.handle("GET", path, {}).response.status == 403
    person = manager.directory.people["runtime-reviewer"]
    manager.directory.people["runtime-reviewer"] = replace(person, active=False)
    assert app.handle("GET", path, headers).response.status == 403
    assert not port.jobs


def test_modes_keep_one_original_ledger_and_refuse_parallel_dispatch(ports, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    original = adapter.prepare_context

    def held_preparation(*args, **kwargs):
        entered.set()
        assert release.wait(15)
        return original(*args, **kwargs)

    monkeypatch.setattr(adapter, "prepare_context", held_preparation)
    assert submit(ports, "NO_MODEL").response.status == 200
    port = ports[2]
    first = list(port.jobs.values())[-1]
    assert entered.wait(10)
    try:
        assert submit(ports, "FIXTURE").response.status == 403
    finally:
        release.set()
    deadline = time.monotonic() + 65
    while first.result is None and first.state != "REFUSED_OR_INTERRUPTED":
        assert time.monotonic() < deadline
        time.sleep(0.05)
    assert first.result["status"] == "NOT_RUN"
    book = port.books[port.key(first.held)]
    assert submit(ports, "FIXTURE").response.status == 200
    second = list(port.jobs.values())[-1]
    while second.result is None and second.state != "REFUSED_OR_INTERRUPTED":
        assert time.monotonic() < deadline
        time.sleep(0.05)
    assert second.result["status"] == "CANDIDATES_FOR_HUMAN_REVIEW"
    assert port.books[port.key(first.held)] is book
    assert first.session.ledger is second.session.ledger is book.ledger

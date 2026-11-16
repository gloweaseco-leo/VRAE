"""Real C1/C2/controlled signatures; detached task context is NOT Worker E2E."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import sqlite3

import pytest

from integration.l2.support import Issuer, login, pins
from integration.l2_ops import native_report as assembly
from integration.l2_ops.source_profiles import selected
from vrae.l2.identity import Directory, Person
from vrae.l2.ledger import Ledger
from vrae.l2.report import L2Denied
from vrae.l2_ops.briefs import BriefService
from vrae.l2_ops.sources import OperationsDenied


@pytest.fixture(scope="module")
def native_source(native_result):
    _, bundle, _ = selected("industrial-p40-v3")
    source = assembly.produce(native_result, bundle, created_at="2026-11-16T12:00:00+00:00")
    return source, bundle


@pytest.fixture
def reviewed(native_source, tmp_path):
    source, bundle = native_source
    issuer = Issuer()
    rid = source.read().version["report_id"]
    person = Person("c3-controlled-reviewer", "c3-controlled-reviewer", "合成内部审阅员", bundle.tenant_id, "REVIEWER", (rid,))
    directory = Directory(issuer=issuer.issuer, audience=issuer.audience, jwks=issuer.jwks,
        people=[person], expires=issuer.clock()+3600)
    ledger = Ledger(tmp_path/"native-review.sqlite", source, directory)
    sid = login(issuer, directory, person.subject)
    view = ledger.read(sid, rid)
    ledger.review(sid, rid, **pins(view), action="APPROVE", reason="合成组件受控逐项复核，不是正式人审或实际Worker整链。",
        items={r["id"]: "ACK" for r in view.document["findings"]+view.document["blueprint"]}, attest=True)
    return ledger, sid, rid


def detached_reader(monkeypatch, native_result, native_source, reviewed, *, seconds=60):
    ledger, sid, _ = reviewed
    state = {"task_locked": False, "released": False}
    deadline = datetime.now(UTC)+timedelta(seconds=seconds)

    @contextmanager
    def worker(*args, **kwargs):
        state["task_locked"] = True
        try:
            yield native_result.evidence, deadline
        finally:
            state["task_locked"] = False
            state["released"] = True

    # Explicit detached test boundary; production uses original GeneratedSessions.
    monkeypatch.setattr(assembly, "current_worker", worker)
    reader = assembly.NativeCurrentReader(None, native_result.evidence.task, None, "detached-only",
        policy_expires_at=deadline, ledger=ledger, review_sid=sid, bundle=native_source[1])
    return reader, state, deadline


def test_report_uses_same_detached_task_native_pins_and_not_mp25(native_result, native_source):
    source, bundle = native_source
    assembly.bind_worker(native_result.evidence, source, bundle)
    view = source.read()
    assert view.document["native_context"]["job_id"] == native_result.evidence.task.job_id
    assert view.document["native_context"]["native_pack_ref"] == native_result.evidence.pack.ref
    assert len(view.document["blueprint"]) == 7 and "MP25" not in view.payload.decode()
    assert not view.document["formal_human_review"] and not view.document["external_delivery_allowed"]
    assert source.held.created_at == "2026-11-16T12:00:00+00:00"


@pytest.mark.parametrize("field", ["tenant_id", "request_id", "run_id", "job_id", "event_id", "source_ref", "source_bundle_sha256"])
def test_current_report_cannot_splice_another_task(native_result, native_source, field):
    source, bundle = native_source
    evidence = native_result.evidence
    if field == "source_bundle_sha256":
        evidence = replace(evidence, source_bundle_sha256="0"*64)
    else:
        evidence = replace(evidence, task=replace(evidence.task, **{field: "another-task"}))
    with pytest.raises(OperationsDenied, match="REPORT_TASK_MISMATCH"):
        assembly.bind_worker(evidence, source, bundle)


def test_brief_save_keeps_both_contexts_and_minimum_deadline(monkeypatch, native_result, native_source, reviewed):
    reader, state, deadline = detached_reader(monkeypatch, native_result, native_source, reviewed)
    ledger, _, _ = reviewed
    service = BriefService(reader)
    doc = service.prepare(native_source[1], brief_ref="detached-native-brief", activities=native_result.activities)
    assert doc["cost_total"]["cost_status"] == "UNKNOWN" and not doc["activities"][0]["human_labor_claim"]

    class CommitObserver:
        def put(self, value, *, authority_expires_at):
            assert state["task_locked"]
            assert authority_expires_at == deadline
            with sqlite3.connect(ledger.path, timeout=0) as competing:
                with pytest.raises(sqlite3.OperationalError, match="locked"):
                    competing.execute("BEGIN IMMEDIATE")
            return value["content_sha256"]

    assert service.save_current(CommitObserver(), doc) == doc["content_sha256"]
    assert state == {"task_locked": False, "released": True}


def test_c2_deadline_is_used_when_earlier(monkeypatch, native_result, native_source, reviewed):
    reader, _, deadline = detached_reader(monkeypatch, native_result, native_source, reviewed, seconds=3600)
    ledger, sid, _ = reviewed
    expected = datetime.fromtimestamp(ledger.directory.require(sid).expires, UTC)
    with reader.current() as current:
        assert current.authority_expires_at == expected < deadline


def test_expired_task_denies_even_with_valid_c2_review(monkeypatch, native_result, native_source, reviewed):
    reader, state, _ = detached_reader(monkeypatch, native_result, native_source, reviewed, seconds=-1)
    with pytest.raises(OperationsDenied, match="AUTHORITY_EXPIRED"):
        with reader.current():
            pytest.fail("expired original task must never yield")
    assert not state["task_locked"]


def test_c2_revocation_denies_even_with_task_context(monkeypatch, native_result, native_source, reviewed):
    reader, state, _ = detached_reader(monkeypatch, native_result, native_source, reviewed)
    ledger, _, _ = reviewed
    ledger.directory.revoked_keys.add(next(iter(ledger.directory.jwks["keys"]))["kid"])
    with pytest.raises(L2Denied):
        with reader.current():
            pytest.fail("revoked C2 identity must never yield")
    assert not state["task_locked"]


def test_revision_invalidates_prior_brief_until_new_review(monkeypatch, native_result, native_source, reviewed):
    reader, _, _ = detached_reader(monkeypatch, native_result, native_source, reviewed)
    service = BriefService(reader)
    doc = service.prepare(native_source[1], brief_ref="revision-native-brief")
    ledger, sid, rid = reviewed
    view = ledger.read(sid, rid)
    ledger.revise(sid, rid, **pins(view), changes={view.document["blueprint"][0]["id"]: "企业核实资料版本后实施，不改变原生事实。"})
    with pytest.raises(L2Denied):
        service.read_current(doc)


def test_creation_stamp_survives_restart_without_new_time_or_scope(tmp_path, native_result, native_source):
    task, bundle = native_result.evidence.task, native_source[1]
    first = assembly.production_stamp(tmp_path/"custody", task, bundle)
    assert assembly.production_stamp(tmp_path/"custody", task, bundle) == first
    path = next((tmp_path/"custody").iterdir())
    from vrae.reviewing.canonical import canonical, parse
    record = parse(path.read_bytes())
    record["task"]["job_id"] = "another-job"
    path.write_bytes(canonical(record))
    with pytest.raises(OperationsDenied, match="CREATION_RECORD_DENIED"):
        assembly.production_stamp(tmp_path/"custody", task, bundle)


def test_mount_reuses_original_application_and_controlled_ledger(native_source, reviewed, tmp_path):
    import json
    import secrets
    from apps.operator_console.b5a_http import Application as Base
    from apps.operator_console.b5a_sessions import SessionStore
    from apps.operator_console.b5p0_http import RehearsalApplication
    from apps.operator_console.b5p0_journal import Journal
    from apps.operator_console.b5b_http import Application
    from apps.operator_console.b5b_m2_http import GeneratedConsole
    from apps.operator_console.b5b_m2_sessions import GeneratedSessions
    from vrae.b6_p0.reader import PrivateHandoffReader
    from vrae.identity.boundary import TrustAnchor
    from vrae.application.ra4b_p2.m1.reader import SignedGeneratedReader

    ledger, sid, rid = reviewed
    d = ledger.directory
    anchor = TrustAnchor(d.issuer, d.audience, json.dumps(d.jwks).encode(), d.expires)
    legacy = SessionStore(anchor=anchor, bindings={}, readers={})
    rehearsal = RehearsalApplication(Base(legacy, {}), {}, Journal(tmp_path/"legacy.sqlite"), key_secret=secrets.token_bytes(32))

    def deny_connection(_role):
        raise AssertionError("mount-only component test must not claim a PG task read")

    generated = GeneratedConsole(GeneratedSessions(SignedGeneratedReader(anchor=anchor, assignments=(), connect=deny_connection)), {})
    app = Application(rehearsal, PrivateHandoffReader(legacy, {}), generated=generated)
    refreshes = []
    installed = assembly.mount(app, native_source[0], d, ledger.path, refresh=lambda: refreshes.append(True))
    assert app.generated is generated and app.deep.directory is d and app.deep.l1_enabled
    assert set(app.deep.ledgers) == {rid} and installed.source is native_source[0]
    response = app.deep.handle("GET", "/b5a/l2/r/"+rid, {"Cookie": "b5a_l2_session="+sid}, b"")
    assert response.response.status == 200 and refreshes
    assert "P40" in response.response.body.decode() and "MP25" not in response.response.body.decode()
    with pytest.raises(OperationsDenied, match="REPLACEMENT_DENIED"):
        assembly.mount(app, native_source[0], d, tmp_path/"different.sqlite", refresh=lambda: None)

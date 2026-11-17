"""Real PG16 sidecar tests; synthetic upstream DTOs are explicitly not L2 E2E."""
import os
import secrets
from datetime import UTC
from pathlib import Path

import pytest

from vrae.l2_ops.briefs import BriefService
from vrae.l2_ops.ledger import BriefLedger, install
from vrae.l2_ops.sources import OperationsDenied
from vrae.reviewing.canonical import canonical, sha


@pytest.fixture(scope="module")
def database():
    dsn = os.environ.get("L2OPS_TEST_DSN")
    assert dsn, "Explicit isolated PG16 DSN is required for this integration suite"
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    password = secrets.token_urlsafe(32)
    runtime = make_conninfo(dsn, user="l2_ops_runtime", password=password)
    output = os.environ.get("L2OPS_RUNTIME_OUTPUT")
    if output:
        # Archive disposable credentials privately before any failing SQL could
        # include a Literal/connection repr in pytest's exception diagnostics.
        Path(output).write_text(runtime, encoding="utf-8")
    with psycopg.connect(dsn) as c:
        assert 160000 <= c.info.server_version < 170000
        c.execute(sql.SQL("CREATE ROLE l2_ops_runtime LOGIN PASSWORD {}").format(sql.Literal(password)))
        install(c, "l2_ops_runtime")
    return lambda: psycopg.connect(runtime)


def test_pg_append_only_replay_conflict_and_current_lock(database, bundle, reader):
    service = BriefService(reader)
    ledger = BriefLedger(database)
    document = service.prepare(bundle, brief_ref="pg-brief")
    assert service.save_current(ledger, document) == document["content_sha256"]
    assert service.save_current(ledger, document) == document["content_sha256"]
    assert service.load_current(ledger, "pg-brief") == document
    altered = {**document, "consultation": {**document["consultation"], "reference": "another", "state": "UNVERIFIED_REFERENCE"}}
    altered["content_sha256"] = sha(canonical({k: v for k, v in altered.items() if k != "content_sha256"}, limit=2_000_000))
    with pytest.raises(OperationsDenied, match="IMMUTABLE_BRIEF_CONFLICT"):
        service.save_current(ledger, altered)
    assert ledger.get(bundle.tenant_id, "pg-brief") == document
    with pytest.raises(OperationsDenied, match="NOT_FOUND"):
        ledger.get("another-tenant", "pg-brief")

    class LockObservingLedger:
        def put(self, value, *, authority_expires_at):
            assert reader.locked
            return ledger.put(value, authority_expires_at=authority_expires_at)

    service.save_current(LockObservingLedger(), document)
    reader.allowed = False
    with pytest.raises(OperationsDenied, match="REVOKED"):
        service.load_current(ledger, "pg-brief")


def test_pg_runtime_cannot_update_delete_or_bootstrap(database):
    import psycopg
    for query in ("UPDATE l2_ops_v1.briefs SET brief_ref='changed'",
                  "DELETE FROM l2_ops_v1.briefs", "DROP TABLE l2_ops_v1.briefs",
                  "CREATE TABLE l2_ops_v1.unauthorized(x int)"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), database() as c:
            c.execute(query)


def test_pg_restart_marker(database, bundle, reader):
    service = BriefService(reader)
    ledger = BriefLedger(database)
    original = service.prepare(bundle, brief_ref="restart-readback")
    service.save_current(ledger, original)
    assert service.load_current(ledger, "restart-readback") == original


def test_pg_real_deferred_commit_failure_returns_no_receipt(database, bundle, reader):
    import psycopg
    with psycopg.connect(os.environ["L2OPS_TEST_DSN"]) as c:
        c.execute("""CREATE FUNCTION l2_ops_v1.test_commit_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.brief_ref = 'commit-must-fail' THEN RAISE EXCEPTION 'test deferred failure' USING ERRCODE='23514'; END IF;
            RETURN NEW; END $$""")
        c.execute("""CREATE CONSTRAINT TRIGGER test_commit_failure AFTER INSERT ON l2_ops_v1.briefs
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION l2_ops_v1.test_commit_failure()""")
    service = BriefService(reader)
    ledger = BriefLedger(database)
    document = service.prepare(bundle, brief_ref="commit-must-fail")
    with pytest.raises(psycopg.errors.CheckViolation, match="test deferred failure"):
        service.save_current(ledger, document)
    with pytest.raises(OperationsDenied, match="NOT_FOUND"):
        ledger.get(bundle.tenant_id, "commit-must-fail")


def test_pg_real_commit_after_source_deadline_rolls_back(database, bundle, reader):
    from contextlib import contextmanager
    from dataclasses import replace
    from datetime import datetime, timedelta

    import psycopg

    # Source session deadline is not extended; this deliberately short test
    # expires while the actual DB transaction remains open before COMMIT.
    reader.value = replace(reader.value,
                           authority_expires_at=datetime.now(UTC) + timedelta(seconds=3))
    document = BriefService(reader).prepare(bundle, brief_ref="auth-expired-at-commit")

    @contextmanager
    def delayed_commit():
        with database() as c:
            yield c
            c.execute("SELECT pg_sleep(3.2)")

    with pytest.raises(psycopg.errors.CheckViolation, match="L2_AUTHORIZATION_EXPIRED"):
        BriefService(reader).save_current(BriefLedger(delayed_commit), document)
    with pytest.raises(OperationsDenied, match="NOT_FOUND"):
        BriefLedger(database).get(bundle.tenant_id, "auth-expired-at-commit")


def test_pg_native_c2_bridge_holds_review_and_task_context_through_real_commit(
        database, native_result, native_source, reviewed, monkeypatch):
    # Actual C1/C2 + controlled signed review + actual PG COMMIT. The original
    # task context alone is DETACHED/observed, explicitly NOT an APP/Worker E2E.
    import sqlite3
    from integration.l2_ops.checks.test_native_report import detached_reader
    from vrae.l2.ledger import Ledger
    from vrae.l2.report import L2Denied
    reader, state, deadline = detached_reader(monkeypatch, native_result, native_source, reviewed)
    review_ledger, sid, rid = reviewed
    document = BriefService(reader).prepare(native_source[1], brief_ref="native-c2-bridge-component",
        activities=native_result.activities)

    class ObservedCommit(BriefLedger):
        def put(self, value, *, authority_expires_at):
            assert state["task_locked"] and authority_expires_at == deadline
            with sqlite3.connect(review_ledger.path, timeout=0) as other:
                with pytest.raises(sqlite3.OperationalError, match="locked"):
                    other.execute("BEGIN IMMEDIATE")
            return super().put(value, authority_expires_at=authority_expires_at)

    ledger = ObservedCommit(database)
    service = BriefService(reader)
    assert service.save_current(ledger, document) == document["content_sha256"]
    assert not state["task_locked"]
    # Reopen original durable C2 and C3 ledgers; no recreated receipt or hashes.
    reopened = Ledger(review_ledger.path, review_ledger.source, review_ledger.directory)
    assert reopened.read(sid, rid).display_hash == document["pins"]["report_sha256"]
    reader.ledger = reopened
    assert service.load_current(BriefLedger(database), document["brief_ref"]) == document
    reopened.directory.revoked_keys.add(next(iter(reopened.directory.jwks["keys"]))["kid"])
    with pytest.raises(L2Denied):
        service.load_current(BriefLedger(database), document["brief_ref"])
    assert not state["task_locked"]


def native_business_app(database, native_result, native_source, reviewed, monkeypatch, tmp_path):
    from integration.l2_ops import native_report as assembly
    from integration.l2_ops.checks.test_native_report import detached_reader, mounted_application
    reader, state, _ = detached_reader(monkeypatch, native_result, native_source, reviewed)
    app, _ = mounted_application(reviewed, tmp_path)
    original, sid, rid = reviewed
    current = assembly.mount(app, native_source[0], original.directory, original.path, refresh=lambda: None)
    reader.ledger = current
    pg = BriefLedger(database)
    subject = current.directory.require(sid, rid).person.subject
    path = assembly.attach_business(app, pg, report_id=rid, bundle=native_source[1],
        activities=native_result.activities, subject=subject, factory=lambda _: reader)
    app.origin = "http://127.0.0.1:41901"
    headers = {"Host": "127.0.0.1:41901", "Origin": app.origin,
        "Sec-Fetch-Site": "same-origin", "Cookie": "b5a_l2_session="+sid}
    return app, path, headers, reader, state, pg


def test_pg_native_business_ui_preview_save_readback_and_nonce_replay(
        database, native_result, native_source, reviewed, monkeypatch, tmp_path):
    # Original B5B Application.handle + real Controlled signature/C2 ledger +
    # actual PG. M1 task context is detached/observed, NOT a browser/Worker E2E.
    import re
    from urllib.parse import urlencode
    from apps.operator_console.b5a_http import FORM
    app, path, headers, reader, state, pg = native_business_app(
        database, native_result, native_source, reviewed, monkeypatch, tmp_path)
    with reader.current() as current:
        brief_ref = "rb-" + current.review["receipt_ref"]
    response = app.handle("GET", path, headers)
    assert response.response.status == 200
    html = response.response.body.decode()
    assert "预览尚未持久保存" in html and "费用未知" in html and "尚未关联真实咨询" in html
    for item in native_source[0].read().document["blueprint"]:
        assert item["title"] in html
        assert item["owner_role"] in html
        assert all(text in html for text in item["customer_inputs"]+item["acceptance"])
    assert html.index("实际改法") < html.index("<pre>")
    with pytest.raises(OperationsDenied, match="NOT_FOUND"):
        pg.get(native_source[1].tenant_id, brief_ref)
    nonce = re.search('name="_csrf" value="([^"]+)"', html).group(1)
    posted = {**headers, "Content-Type": FORM}
    body = urlencode({"_csrf": nonce}).encode()
    saved = app.handle("POST", path, posted, body)
    assert saved.response.status == 200 and "PostgreSQL 回读" in saved.response.body.decode()
    original = pg.get(native_source[1].tenant_id, brief_ref)
    assert original["pins"]["job_id"] == native_result.evidence.task.job_id
    assert original["blueprint"]["items"] == native_source[0].read().document["blueprint"]
    assert original["external_delivery_allowed"] is False and original["consultation"]["state"] == "UNLINKED"
    assert app.handle("POST", path, posted, body).response.status == 403
    assert pg.get(native_source[1].tenant_id, brief_ref) == original
    assert app.handle("GET", path, headers).response.status == 200
    assert not state["task_locked"]
    rid = reviewed[2]
    report = app.handle("GET", "/b5a/l2/r/"+rid, headers)
    assert report.response.status == 200 and 'data-key="l2-business-brief"' in report.response.body.decode()


@pytest.mark.parametrize("negative", ["csrf", "wrong_actor", "revoked_c2", "task_expired", "stale_version"])
def test_pg_native_business_ui_denies_without_current_dual_authority(
        database, native_result, native_source, reviewed, monkeypatch, tmp_path, negative):
    from contextlib import contextmanager
    from datetime import datetime, timedelta
    from integration.l2_ops import native_report as assembly
    from integration.l2.support import pins
    from apps.operator_console.b5a_http import FORM
    app, path, headers, reader, state, pg = native_business_app(
        database, native_result, native_source, reviewed, monkeypatch, tmp_path)
    ledger, sid, rid = reviewed
    method, raw = "GET", b""
    if negative == "csrf":
        method, raw = "POST", b"_csrf=not-a-real-nonce"
        headers["Content-Type"] = FORM
    elif negative == "wrong_actor":
        app.native_business.bind(rid, bundle=native_source[1], activities=(), subject="not-the-held-operator", factory=lambda _: reader)
    elif negative == "revoked_c2":
        ledger.directory.revoked_keys.add(next(iter(ledger.directory.jwks["keys"]))["kid"])
    elif negative == "stale_version":
        view = ledger.read(sid, rid)
        ledger.revise(sid, rid, **pins(view), changes={view.document["blueprint"][0]["id"]: "企业确认资料后修订；原事实保持。"})
    else:
        @contextmanager
        def expired(*args, **kwargs):
            yield native_result.evidence, datetime.now(UTC)-timedelta(seconds=1)
        monkeypatch.setattr(assembly, "current_worker", expired)
    response = app.handle(method, path, headers, raw)
    assert response.response.status == 403 and b"L2_NATIVE_BUSINESS_DENIED" in response.response.body
    assert not state["task_locked"]


def test_cross_store_source_exit_failure_leaves_only_pending_brief(database, bundle, reader):
    from contextlib import contextmanager
    service = BriefService(reader)
    document = service.prepare(bundle, brief_ref="pending-source-context-exit")
    original = reader.current

    @contextmanager
    def broken():
        with original() as current:
            yield current
            raise OperationsDenied("SOURCE_CONTEXT_COMMIT_LOST")

    reader.current = broken
    ledger = BriefLedger(database)
    with pytest.raises(OperationsDenied, match="SOURCE_CONTEXT_COMMIT_LOST"):
        service.save_current(ledger, document)
    # Own PG row really committed, but is not usable after a failed source exit.
    with database() as c:
        assert c.execute("SELECT count(*) FROM l2_ops_v1.briefs WHERE brief_ref=%s", (document["brief_ref"],)).fetchone() == (1,)
    with pytest.raises(OperationsDenied, match="PENDING_REVALIDATION"):
        ledger.get(bundle.tenant_id, document["brief_ref"])
    reader.current = original
    assert service.save_current(ledger, document) == document["content_sha256"]
    assert service.load_current(ledger, document["brief_ref"]) == document


def test_cross_store_post_commit_version_change_cannot_be_confirmed(database, bundle, reader):
    from contextlib import contextmanager
    from dataclasses import replace
    service = BriefService(reader)
    document = service.prepare(bundle, brief_ref="pending-version-fence")
    original = reader.current

    @contextmanager
    def changing():
        with original() as current:
            yield current
        reader.value = replace(reader.value, review={**reader.value.review, "receipt_ref": "new-decision"})

    reader.current = changing
    ledger = BriefLedger(database)
    with pytest.raises(OperationsDenied, match="STALE_OR_CROSS_TASK"):
        service.save_current(ledger, document)
    with pytest.raises(OperationsDenied, match="PENDING_REVALIDATION"):
        ledger.get(bundle.tenant_id, document["brief_ref"])

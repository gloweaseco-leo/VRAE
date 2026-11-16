"""TEST_ONLY private-file fault probes against the live ORIGINAL dual reader.

No listener, signer, grant, SQL migration or detached result. The local operator
queues one closed probe in the owned SSR volume; an already authenticated POST
with its original one-use CSRF consumes it. Each fault preserves an explicit
result and uses a separate immutable audit Brief, never the business Brief.
"""
from contextlib import contextmanager
from dataclasses import replace
import copy
import json
import threading
import time

from vrae.l2_ops.briefs import BriefService
from vrae.l2_ops.ledger import BriefLedger
from vrae.l2_ops.sources import OperationsDenied
from vrae.l2.report import L2Denied
from vrae.identity.boundary import IdentityDenied
from vrae.reviewing.canonical import sha
import psycopg

CASES = frozenset({"idempotent", "wrong-task", "pg-interruption", "task-connection-loss",
                   "sqlite-unavailable", "post-exit-review-change", "concurrent-review", "c2-revocation"})


def denied(fn):
    try:
        fn()
    except (OperationsDenied, L2Denied, IdentityDenied, OSError) as e:
        return type(e).__name__ + ":" + str(e)
    except psycopg.Error as e:
        return type(e).__name__ + ":" + str(e.sqlstate)
    raise AssertionError("S0_EXPECTED_LIVE_AUTHORITY_DENIAL")


def consume(manager, reader, ledger, bundle, activities):
    request = manager.root / "s0-audit-request.json"
    if not request.exists():
        return None
    if request.is_symlink():
        raise OperationsDenied("S0_PRIVATE_AUDIT_FILE_DENIED")
    command = json.loads(request.read_bytes())
    if (set(command) != {"case", "job_id"} or command["case"] not in CASES
            or command["job_id"] != reader.task.job_id):
        raise OperationsDenied("S0_PRIVATE_AUDIT_SCOPE_DENIED")
    case = command["case"]
    output = manager.root / ("s0-audit-" + case + ".json")
    running = manager.root / ("s0-audit-" + case + ".running.json")
    if output.exists() or running.exists():
        raise OperationsDenied("S0_PRIVATE_AUDIT_ALREADY_EXECUTED")
    request.rename(running)
    result = {"case": case, "scope": "LIVE_ORIGINAL_M1_C2_REAL_PG_TEST_ONLY_FAULT_INJECTION",
              "task": manager.active["capture"]["signed_reader"]["task"], "pass": False,
              "detached_authority": False, "original_permissions_changed": False}
    start = time.monotonic_ns()
    try:
        service = BriefService(reader)
        document = service.prepare(bundle, brief_ref="s0-audit-" + case + "-" + reader.task.job_id,
                                   activities=activities)
        result.update(pins=document["pins"], review=document["review"], brief_ref=document["brief_ref"])
        with reader.current() as current:
            task_session = reader.sessions.require(reader.sid)
            c2_session = reader.ledger.directory.require(reader.review_sid, reader.report_id)
            from datetime import UTC, datetime
            expected = min(reader.policy_expires_at, datetime.fromtimestamp(min(
                task_session.expires, task_session.assignment.expires, reader.sessions.reader.anchor.expires,
                c2_session.expires, reader.ledger.directory.expires), UTC))
            assert current.authority_expires_at == expected
            result["minimum_original_deadline"] = expected.isoformat()
        if case == "idempotent":
            a = service.save_current(ledger, document)
            b = service.save_current(ledger, document)
            assert a == b == document["content_sha256"]
            assert service.load_current(ledger, document["brief_ref"]) == document
            with ledger.connect() as c:
                assert c.execute("SELECT count(*) FROM l2_ops_v1.briefs WHERE tenant_id=%s AND brief_ref=%s",
                                 (bundle.tenant_id, document["brief_ref"])).fetchone() == (1,)
            result["same_bytes_same_row"] = True
        elif case == "wrong-task":
            failures = {}
            for field, value in (("tenant_id", "tenant-other"), ("run_id", "00000000-0000-0000-0000-000000000000"),
                                 ("job_id", "00000000-0000-0000-0000-000000000000")):
                wrong = copy.copy(reader)
                wrong.task = replace(reader.task, **{field: value})
                failures[field] = denied(lambda: BriefService(wrong).save_current(ledger, document))
            result["refused"] = failures
        elif case == "pg-interruption":
            @contextmanager
            def interrupted():
                with ledger.connect() as c:
                    yield c
                    # The low role can terminate only its own actual PG backend.
                    c.execute("SELECT pg_terminate_backend(pg_backend_pid())")
            try:
                service.save_current(BriefLedger(interrupted), document)
            except psycopg.OperationalError as e:
                result["actual_pg_error"] = type(e).__name__
            else:
                raise AssertionError("S0_PG_INTERRUPTION_MUST_NOT_COMMIT")
            result["readback_denial"] = denied(lambda: ledger.get(bundle.tenant_id, document["brief_ref"]))
            assert "NOT_FOUND" in result["readback_denial"]
        elif case == "task-connection-loss":
            original = reader.sessions.reader.connect
            held = []
            def tracking(role):
                c = original(role)
                held.append(c)
                return c
            class Interrupted(BriefLedger):
                def put(self, value, *, authority_expires_at):
                    assert held and not held[-1].closed
                    held[-1].close()  # real original signed-reader PG transaction lost
                    return super().put(value, authority_expires_at=authority_expires_at)
            reader.sessions.reader.connect = tracking
            try:
                result["source_failure"] = denied(lambda: service.save_current(Interrupted(ledger.connect), document))
            finally:
                reader.sessions.reader.connect = original
            result["readback_denial"] = denied(lambda: ledger.get(bundle.tenant_id, document["brief_ref"]))
            assert "PENDING_REVALIDATION" in result["readback_denial"]
            # Same bytes, real fresh original contexts; no new task/Worker run.
            service.save_current(ledger, document)
            assert service.load_current(ledger, document["brief_ref"]) == document
            result["reauthorized_same_bytes_compensation"] = True
        elif case == "sqlite-unavailable":
            path = reader.ledger.path
            unavailable = path.with_name(path.name + ".s0-unavailable")
            assert not unavailable.exists()
            digest = sha(path.read_bytes())
            class Missing(BriefLedger):
                def put(self, value, *, authority_expires_at):
                    path.rename(unavailable)
                    return super().put(value, authority_expires_at=authority_expires_at)
            try:
                result["source_failure"] = denied(lambda: service.save_current(Missing(ledger.connect), document))
            finally:
                if unavailable.exists():
                    unavailable.rename(path)
            assert sha(path.read_bytes()) == digest
            result["readback_denial"] = denied(lambda: ledger.get(bundle.tenant_id, document["brief_ref"]))
            assert "PENDING_REVALIDATION" in result["readback_denial"]
            service.save_current(ledger, document)
            assert service.load_current(ledger, document["brief_ref"]) == document
            result["original_sqlite_bytes_retained"] = True
        elif case in {"post-exit-review-change", "concurrent-review"}:
            def reject():
                target = reader.ledger
                view = target.read(reader.review_sid, reader.report_id)
                target.review(reader.review_sid, reader.report_id, version=view.version["version"],
                    content_hash=view.version["content_hash"], display_hash=view.display_hash,
                    action="REJECT", reason="S0 live concurrency probe; synthetic controlled decision only.",
                    items={r["id"]: "REJECT" for r in view.document["findings"] + view.document["blueprint"]}, attest=True)
            if case == "post-exit-review-change":
                class Between:
                    calls = 0
                    @contextmanager
                    def current(self):
                        self.calls += 1
                        with reader.current() as current:
                            yield current
                        if self.calls == 1:
                            reject()
                result["post_commit_cas_denial"] = denied(lambda: BriefService(Between()).save_current(ledger, document))
                result["readback_denial"] = denied(lambda: ledger.get(bundle.tenant_id, document["brief_ref"]))
                assert "PENDING_REVALIDATION" in result["readback_denial"]
            else:
                started, finished = threading.Event(), threading.Event()
                errors = []
                def competing():
                    started.set()
                    try:
                        reject()
                    except BaseException as e:
                        errors.append(type(e).__name__)
                    finally:
                        finished.set()
                thread = threading.Thread(target=competing)
                class Concurrent(BriefLedger):
                    def put(self, value, *, authority_expires_at):
                        thread.start()
                        assert started.wait(1)
                        assert not finished.wait(0.15), "C2_UPDATE_ESCAPED_HELD_AUTHORITY_LOCK"
                        return super().put(value, authority_expires_at=authority_expires_at)
                try:
                    try:
                        service.save_current(Concurrent(ledger.connect), document)
                        result["linearization"] = "BRIEF_COMPLETED_BEFORE_COMPETING_REVIEW"
                    except (OperationsDenied, L2Denied):
                        result["linearization"] = "POST_COMMIT_CAS_REFUSED_COMPETING_REVIEW"
                finally:
                    thread.join(5)
                assert finished.is_set() and not errors
                result["stale_read_denied"] = denied(lambda: service.load_current(ledger, document["brief_ref"]))
                result["competing_current_review_committed"] = True
        else:
            directory = reader.ledger.directory
            kid = directory.require(reader.review_sid, reader.report_id).key_id
            @contextmanager
            def revoked():
                with ledger.connect() as c:
                    yield c
                    # Real original key revocation at the commit boundary. It is
                    # permanent for this SSR boot; no clearing/reviving old SID.
                    with directory.lock:
                        directory.revoked_keys.add(kid)
            result["revoked_denial"] = denied(lambda: service.save_current(BriefLedger(revoked), document))
            result["readback_denial"] = denied(lambda: ledger.get(bundle.tenant_id, document["brief_ref"]))
            assert "PENDING_REVALIDATION" in result["readback_denial"]
            result["old_review_session_denied"] = denied(lambda: directory.require(reader.review_sid, reader.report_id))
            result["revocation_not_cleared"] = kid in directory.revoked_keys
        result["pass"] = True
        return result
    except BaseException as e:
        result["failure_type"] = type(e).__name__
        import traceback
        result["failure_frames"] = [{"file": f.filename.rsplit("/", 1)[-1], "line": f.lineno, "function": f.name}
                                    for f in traceback.extract_tb(e.__traceback__)]
        if isinstance(e, (AssertionError, OperationsDenied, L2Denied, IdentityDenied)):
            result["failure_code"] = str(e)
        # No credentials, connection repr or request headers in public evidence.
        raise
    finally:
        result["wall_ns"] = time.monotonic_ns() - start
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

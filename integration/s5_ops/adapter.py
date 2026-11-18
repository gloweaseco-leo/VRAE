"""S3 composition only: original signed readers, original Session/Gateway/Guard."""

import asyncio
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
import re
import threading
import traceback
from types import SimpleNamespace

from apps.operator_console.views import link
from vrae.intelligence import FixtureProvider
from vrae.intelligence.s3 import Session, prepare_context
from vrae.l2_ops.sources import OperationsDenied
from integration.l2_ops.current_worker import current_worker
from integration.l2_ops.native_report import bind_worker
from .trusted import Book, completion, read, write
from .views import render


@dataclass(frozen=True)
class Held:
    task: object
    source: object
    m1_sid: str
    review_sid: str
    report_id: str
    version: int
    content_hash: str
    display_hash: str
    deadline: datetime


class Job:
    def __init__(self, held, mode, intent):
        self.held, self.mode, self.intent = held, mode, intent
        self.state, self.session, self.result = "PENDING", None, None
        self.book = None
        self.cancel = threading.Event()
        self.loop = self.task = None


class S5Ports:
    """One service-local S3 adjunct; no replacement identity/report/Worker."""

    def __init__(self, manager):
        self.manager = manager
        self.root = manager.root / "s5"
        self.jobs = {}
        self.books = {}
        self.lock = threading.RLock()

    def route(self, path):
        match = re.fullmatch(r"/b5a/l2/r/([A-Za-z0-9_.-]{3,128})/s3", path)
        return match[1] if match else None

    def bind(self, business, rid):
        business.extensions["s5-offline"] = self

    def decorate(self, path, reply):
        active = self.manager.active
        if active is None or path != "/b5a/l2/r/" + active["report_id"]:
            return reply
        from apps.operator_console.b5a_http import Reply
        from apps.operator_console.interface import Response

        marker = '<main id="main" tabindex="-1">'
        text = reply.response.body.decode()
        if reply.response.status == 200 and text.count(marker) == 1:
            text = text.replace(
                marker,
                marker + link(path + "/s3", "离线采购解释 · NO_MODEL / Fixture", key="s5-open"),
                1,
            )
            return Reply(Response(200, text.encode(), reply.response.content_type), reply.headers)
        return reply

    @contextmanager
    def authorized(self, headers=None, held=None):
        manager, app = self.manager, self.manager.app
        active = manager.active
        if active is None or (
            held is not None
            and (active["task"] != held.task or active["source"].expected != held.source.expected)
        ):
            raise OperationsDenied("S5_CURRENT_TASK_REQUIRED")
        source, task = active["source"], active["task"]
        m1_sid = held.m1_sid if held else active["sid"]
        # The accepted session lock serializes original PG reads. No lease is held.
        with current_worker(
            manager.port, task, manager.sessions, m1_sid, policy_expires_at=manager.deadline
        ) as (evidence, deadline):
            bind_worker(evidence, source, manager.bundle)
            deep = app.deep
            with deep.directory.lock:
                deep.refresh()
                sid = held.review_sid if held else deep.sid(headers)
                session, report = deep.current(sid, active["report_id"])
                if (
                    session.person.role not in ("OWNER", "REVIEWER")
                    or session.person.subject != manager.identity["subject"]
                    or session.person.tenant_id != source.held.tenant_id
                ):
                    raise OperationsDenied("S5_REVIEWER_REQUIRED")
                expiry = min(
                    deadline,
                    datetime.fromtimestamp(session.expires, UTC),
                    datetime.fromtimestamp(deep.directory.expires, UTC),
                )
                snapshot = Held(
                    task,
                    source,
                    m1_sid,
                    sid,
                    active["report_id"],
                    report.version["version"],
                    report.version["content_hash"],
                    report.display_hash,
                    expiry,
                )
                if held and (
                    snapshot.report_id,
                    snapshot.version,
                    snapshot.content_hash,
                    snapshot.display_hash,
                ) != (held.report_id, held.version, held.content_hash, held.display_hash):
                    raise OperationsDenied("S5_REPORT_VERSION_CHANGED")
                yield snapshot, evidence
                deep.directory.require(sid, active["report_id"])
                if datetime.now(UTC) >= expiry:
                    raise OperationsDenied("S5_AUTHORITY_EXPIRED")

    def key(self, held):
        return hashlib.sha256(
            json.dumps(
                {
                    "task": asdict(held.task),
                    "source": held.source.expected,
                    "version": held.version,
                    "content_hash": held.content_hash,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()

    def history(self, held):
        root = self.root / self.key(held)
        return [read(p, 8192) for p in root.glob("*-intent.json")]

    def start(self, held, evidence, mode):
        key = (self.key(held), mode)
        with self.lock:
            if key in self.jobs:
                return self.jobs[key]
            if any(
                self.key(j.held) == key[0]
                and j.state
                in (
                    "PENDING",
                    "WAIT_ORIGINAL_LEASE_END",
                    "PREPARING_ORIGINAL_S3_CONTEXT",
                    "RUNNING_ORIGINAL_S3_SESSION",
                )
                for j in self.jobs.values()
            ):
                raise OperationsDenied("S5_OPERATION_IN_FLIGHT")
            intent = self.root / key[0] / (mode.lower() + "-intent.json")
            if intent.exists():
                # A restart does not reset the accepted ledger or retry an unknown dispatch.
                raise OperationsDenied("S5_PRIOR_OPERATION_HISTORY_ONLY")
            pins = completion(
                self.manager.root / "s5-postcommit", held.source, evidence, held.deadline
            )
            write(
                intent,
                {
                    "mode": mode,
                    "state": "IN_FLIGHT",
                    "task": asdict(held.task),
                    "report_hash": held.content_hash,
                },
            )
            job = Job(held, mode, intent)
            self.jobs[key] = job
            threading.Thread(
                target=self.worker, args=(job, pins), daemon=True, name="s5-original-s3-sidecar"
            ).start()
            return job

    def worker(self, job, pins):
        async def run():
            job.loop = asyncio.get_running_loop()
            job.state = "WAIT_ORIGINAL_LEASE_END"
            while datetime.now(UTC) < pins.lease_expires_at:
                if job.cancel.is_set() or datetime.now(UTC) >= job.held.deadline:
                    raise OperationsDenied("S5_CANCELLED_OR_EXPIRED")
                await asyncio.sleep(0.1)
            if job.cancel.is_set():
                raise OperationsDenied("S5_CANCELLED_BEFORE_CONTEXT")
            # The snapshot is consistency input, not authority while replaying.
            with self.authorized(held=job.held):
                pass
            component = self.manager.app.native_business.source_views[job.held.report_id]
            binding = component.binding
            projection = json.loads(binding.payload)
            job.state = "PREPARING_ORIGINAL_S3_CONTEXT"
            context = prepare_context(
                binding.pack,
                job.held.source,
                projection,
                buyer_pins=binding.buyer_pins,
                completion=pins,
                now=datetime.now(UTC),
            )
            with self.lock:
                key = self.key(job.held)
                if key not in self.books:
                    self.books[key] = Book(job.intent.parent, context)
                book = self.books[key]
                if book.scope != context.gateway_pins.scope:
                    raise OperationsDenied("S5_BOOK_SCOPE_CHANGED")
            job.book = book
            session = Session(context, ledger=book.ledger)
            provider = None
            if job.mode == "FIXTURE":
                claims = [
                    {
                        "kind": "MISSING_INFORMATION",
                        "task": card["buyer_task"],
                        "refs": [card["observation_id"]],
                        "counter_refs": [],
                        "template": "KEEP_UNKNOWN",
                    }
                    for card in context.candidate["cards"]
                ]
                first = context.candidate["cards"][0]
                claims.append(
                    {
                        "kind": "IMPROVEMENT_OPPORTUNITY",
                        "task": first["buyer_task"],
                        "refs": [first["observation_id"]],
                        "counter_refs": [],
                        "template": "REQUEST_REVISION",
                    }
                )
                provider = FixtureProvider(
                    json.dumps(
                        {
                            "version": "s3-offline-1.0.0",
                            "context_ref": context.context_ref,
                            "claims": claims,
                        },
                        ensure_ascii=False,
                    )
                )
            with self.authorized(held=job.held):
                pass
            job.state = "RUNNING_ORIGINAL_S3_SESSION"
            job.task = asyncio.create_task(
                session.run(
                    "s5-" + job.held.task.job_id + "-" + job.mode.lower(),
                    mode=job.mode,
                    provider=provider,
                    cancel_before_dispatch=job.cancel.is_set(),
                )
            )
            result = await job.task
            # Publication and every later read require both ORIGINAL current authorities.
            with self.authorized(held=job.held):
                checked = session.read(result["operation_id"])
                if checked["deterministic_report_hash"] != job.held.content_hash:
                    raise OperationsDenied("S5_REPORT_HASH_CHANGED")
                book.finish(job.intent, checked)
                job.session, job.result, job.state = session, checked, checked["status"]

        try:
            asyncio.run(run())
        except BaseException as exc:
            # Only class/stage/hash leave private storage, never reflective messages.
            raw = traceback.format_exc().encode()
            log = job.intent.parent / (job.mode.lower() + ".failure.private.log")
            log.write_bytes(raw)
            log.chmod(0o600)
            write(
                job.intent.parent / (job.mode.lower() + "-failure.json"),
                {
                    "phase": job.state,
                    "exception_type": type(exc).__name__,
                    "private_log_sha256": hashlib.sha256(raw).hexdigest(),
                    "private_log_bytes": len(raw),
                    "private_text_published": False,
                },
            )
            if job.book is not None:
                job.book.save()
            job.state = "REFUSED_OR_INTERRUPTED"
            previous = read(job.intent, 8192)
            write(job.intent, {**previous, "state": "INTERRUPTED_UNKNOWN", "retry_allowed": False})
        finally:
            job.loop = job.task = None

    def readable(self, held):
        jobs = [j for (key, _), j in self.jobs.items() if key == self.key(held)]
        if not jobs:
            return None
        job = jobs[-1]
        data = None
        state = job.state
        if job.session is not None:
            try:
                data = job.session.read(job.result["operation_id"])
            except Exception:
                state = "EXPIRED_SESSION_HISTORY_ONLY"
        return SimpleNamespace(state=state, result=data)

    def read_only_s4_port(self, headers):
        """Narrow trusted port for Owner-merged summary/ACK integration, never an HTTP DTO."""
        with self.authorized(headers) as (held, _):
            return {
                "version": "S5_READ_ONLY_HANDOFF_1",
                "tenant_id": held.source.held.tenant_id,
                "task": asdict(held.task),
                "pack_ref": held.source.held.native_pack_ref,
                "report_id": held.report_id,
                "report_version": held.version,
                "content_hash": held.content_hash,
                "display_hash": held.display_hash,
                "s3_history": self.history(held),
                "customer_approval": False,
                "external_delivery_allowed": False,
                "s4": "AWAITING_ACCEPTED_MAIN",
            }

    def handle(self, method, path, headers, raw):
        deep = self.manager.app.deep
        try:
            if method not in ("GET", "HEAD", "POST") or headers.get("Authorization") is not None:
                raise OperationsDenied("S5_REQUEST_DENIED")
            with self.authorized(headers) as (held, evidence):
                if self.route(path) != held.report_id:
                    raise OperationsDenied("S5_CURRENT_REPORT_REQUIRED")
                if method == "POST":
                    fields = deep.fields(headers, raw, held.review_sid, path, {"mode"})
                    mode = fields["mode"]
                    if mode not in ("NO_MODEL", "FIXTURE", "CANCEL"):
                        raise OperationsDenied("S5_OFFLINE_ONLY")
                    if mode == "CANCEL":
                        for job in self.jobs.values():
                            if self.key(job.held) == self.key(held):
                                job.cancel.set()
                                if job.loop and job.task:
                                    job.loop.call_soon_threadsafe(job.task.cancel)
                    else:
                        self.start(held, evidence, mode)
                nonce = deep.directory.action(held.review_sid, path)
                root = "/b5a/l2/r/" + held.report_id
                body = render(
                    root, nonce, self.readable(held), held.content_hash, self.history(held)
                )
                body += '<form method="post" action="' + path + '">'
                from apps.operator_console.proposal_views import hidden

                body += hidden("_csrf", deep.directory.action(held.review_sid, path)) + hidden(
                    "mode", "CANCEL"
                )
                body += '<button data-key="s5-cancel">请求取消（原检查边界生效）</button></form>'
                return deep.reply("离线采购解释候选", body)
        except Exception:
            return deep.reply(
                "未提供解释",
                '<p data-code="S5_ACCESS_DENIED">请核对本任务签名、当前审核权限、原COMMIT及离线会话期限。原报告仍可用。</p>',
                403,
            )

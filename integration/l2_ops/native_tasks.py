"""Single-current-task assembly on the original signed B5B SSR.

Production stays disabled until Owner supplies an accepted performance main.
No task/pack/report/role is accepted from HTTP. Only original ticket + CSRF
route the original signed task; Worker DONE alone never creates an L2 report.
"""
from contextlib import contextmanager
from datetime import datetime
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any
import re
import hashlib
import json

from apps.operator_console.b5a_http import FORM, Reply, form
from apps.operator_console.b5b_m2_http import cookies, page
from apps.operator_console.interface import Response
from apps.operator_console.proposal_views import hidden
from apps.operator_console.views import e, link
from vrae.l2.identity import Directory, Person
from vrae.l2.native import NativeSource
from vrae.l2_ops.sources import OperationsDenied
from . import native_report as assembly
from .current_worker import current_worker


class NativeTasks:
    def __init__(self, app, port, bundle, brief_ledger, *, policy_expires_at,
                 identity, private_root, enabled=False):
        self.app, self.port, self.bundle, self.brief_ledger = app, port, bundle, brief_ledger
        self.sessions, self.workflow = app.generated.sessions, app.generated.workflow
        keys = {"issuer", "audience", "jwks", "expires", "task_issuer", "task_subject",
                "actor_id", "subject", "name", "tenant_id"}
        if (type(identity) is not dict or set(identity) != keys or self.workflow is None
                or identity["tenant_id"] != bundle.tenant_id or type(enabled) is not bool):
            raise OperationsDenied("L2_NATIVE_OPERATOR_CONFIG_REQUIRED")
        jwks = identity["jwks"]
        if (type(jwks) is not dict or set(jwks) != {"keys"} or type(jwks["keys"]) is not list
                or not 1 <= len(jwks["keys"]) <= 4 or any(type(k) is not dict
                    or set(k) != {"kty", "crv", "alg", "use", "kid", "x"} for k in jwks["keys"])):
            raise OperationsDenied("L2_NATIVE_PUBLIC_KEYS_ONLY")
        self.identity = dict(identity)
        self.deadline = datetime.fromisoformat(policy_expires_at)
        if self.deadline.tzinfo is None:
            raise OperationsDenied("L2_NATIVE_POLICY_DEADLINE_REQUIRED")
        self.root, self.enabled = Path(private_root), enabled
        self.active, self.directory = None, None
        self.s5: Any = None

    def route(self, path):
        found = re.fullmatch(r"/b5a/m2/task/([A-Za-z0-9_-]{43})/native", path)
        return found[1] if found else None

    def task(self, ticket, sid):
        session = self.sessions.require(sid)
        a, c = session.assignment, self.identity
        if (a.issuer, a.subject, a.tenant) != (c["task_issuer"], c["task_subject"], c["tenant_id"]):
            raise OperationsDenied("L2_NATIVE_OPERATOR_MAPPING_DENIED")
        task = self.workflow.task(ticket, session)
        if task is None or task.source_ref not in self.port.sources:
            raise OperationsDenied("L2_NATIVE_TASK_REQUIRED")
        self.port._source(task)
        return task

    def task_fragment(self, task, ticket):
        if task.source_ref not in self.port.sources:
            return ""
        if not self.enabled:
            return '<p data-code="L2_NATIVE_RUNTIME_BLOCKED">原生接线已就绪；实际P40任务等待已验收性能增量。</p>'
        target = "/b5a/m2/task/"+ticket+"/native"
        return link(target, "签名核对本任务并生成／恢复深度报告", key="l2-native-task")

    def activate(self, task, sid):
        if not self.enabled:
            raise OperationsDenied("L2_NATIVE_RUNTIME_BLOCKED")
        if self.s5 is not None:
            self.s5.phase("activate_enter")
        stamp = assembly.production_stamp(self.root, task, self.bundle)
        captured = {}

        def capture(evidence, diagnosis):
            captured.update(signed_reader=evidence.metadata(), c1=diagnosis.metadata())

        source, activities = assembly.produce_current(self.port, task, self.sessions, sid,
            policy_expires_at=self.deadline, bundle=self.bundle, created_at=stamp, audit=capture)
        if self.s5 is not None:
            self.s5.phase("produce_current_complete")
        if (type(source) is not NativeSource or any(getattr(source.held, k) != value for k, value in asdict(task).items())
                or source.held.created_at != stamp
                or source.held.source_bundle_sha256 != self.bundle.document()["content_sha256"]):
            raise OperationsDenied("L2_NATIVE_PRODUCED_TASK_MISMATCH")
        rid = source.read().version["report_id"]
        c = self.identity
        self._select_report(rid)
        if self.active is None or self.active["report_id"] != rid:
            # Same application/listener. A different task requires C2 reauth;
            # prior source/versions/receipts remain in the original SQLite file.
            self.app.deep = None
            self.app.native_business = None
        ledger = assembly.mount(self.app, source, self.directory, self.root/"reviews.sqlite", refresh=lambda: None)
        self.active = {"task": task, "sid": sid, "report_id": rid, "source": source, "activities": activities, "capture": captured}

        def current(review_sid):
            active = self.active
            return assembly.NativeCurrentReader(self.port, active["task"], self.sessions, active["sid"],
                policy_expires_at=self.deadline, ledger=self.app.deep.ledgers[active["report_id"]],
                review_sid=review_sid, bundle=self.bundle)

        assembly.attach_business(self.app, self.brief_ledger, report_id=rid, bundle=self.bundle,
            activities=activities, subject=c["subject"], factory=current)
        if self.s5 is not None:
            self.s5.phase("native_mount_complete")
        from .s2_acceptance_sources import bind
        bind(self.app.native_business, rid)
        if self.s5 is not None:
            self.s5.bind(self.app.native_business, rid)
            self.s5.phase("s2_binding_complete")
        self.audit()
        if self.s5 is not None:
            self.s5.phase("activate_complete")
        return ledger

    def audit(self, document=None, stored=False):
        active = self.active
        source = active["source"]
        capture = source._pack.document["sources"][0]["document"]
        proof = {"task": asdict(active["task"]), "pack_ref": source.held.native_pack_ref,
            "diagnosis_ref": source.held.diagnosis_ref, "diagnosis_sha256": hashlib.sha256(source._diagnosis).hexdigest(),
            "source_bundle_sha256": source.held.source_bundle_sha256, "industry_ref": source.held.industry_ref,
            "source_expected": source.expected, "report_id": active["report_id"],
            "created_at": source.held.created_at, "pages": [{"url": p["snapshot"]["url"], "status": p["http_status"],
                "body_sha256": p["snapshot"]["sha256"]} for p in capture["pages"]],
            "production": active["capture"], "brief_stored": stored,
            "counts": {"assessments": len(source.read().document["findings"]), "blueprint": len(source.read().document["blueprint"])},
            "formal_human_review": False, "external_delivery": False}
        from .s2_acceptance_sources import proof as source_proof
        proof["s2_source"] = source_proof(self.app.native_business, active["report_id"])
        if document is not None:
            proof.update(brief=document)
        (self.root/"active-proof.json").write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding="utf-8")

    def _select_report(self, rid):
        c = self.identity
        if self.directory is None:
            self.directory = Directory(issuer=c["issuer"], audience=c["audience"], jwks=c["jwks"], expires=c["expires"],
                people=[Person(c["actor_id"], c["subject"], c["name"], c["tenant_id"], "REVIEWER", (rid,))], mode="CONTROLLED")
        else:
            # Preserve revocations, replay protection, fixed expiry and identity.
            # Only this actual task creator's CURRENT report scope is assigned.
            with self.directory.lock:
                self.directory.now()
                person = self.directory.people[c["subject"]]
                if not person.active or person.role != "REVIEWER" or person.actor_id != c["actor_id"] or person.tenant_id != c["tenant_id"]:
                    raise OperationsDenied("L2_NATIVE_OPERATOR_REVOKED")
                if person.report_ids != (rid,):
                    self.directory.people[c["subject"]] = replace(person, report_ids=(rid,))
                    self.directory.sessions.clear()
                    self.directory.actions.clear()
                    self.directory.challenges.clear()

    @contextmanager
    def access(self):
        """Hold original M1 current authority around the existing C2 handler."""
        if self.active is None:
            raise OperationsDenied("L2_NATIVE_ACTIVE_TASK_REQUIRED")
        active = self.active
        with current_worker(self.port, active["task"], self.sessions, active["sid"],
                            policy_expires_at=self.deadline) as (evidence, deadline):
            assembly.bind_worker(evidence, active["source"], self.bundle)
            yield evidence, deadline

    def handle(self, method, path, headers, raw):
        try:
            if not self.enabled:
                raise OperationsDenied("L2_NATIVE_RUNTIME_BLOCKED")
            if method not in ("GET", "HEAD", "POST") or headers.get("Authorization") is not None:
                raise OperationsDenied("L2_NATIVE_REQUEST_DENIED")
            sid = cookies(headers).get("b5a_m2_session", "")
            ticket = self.route(path)
            if ticket is None:
                raise OperationsDenied("L2_NATIVE_REQUEST_DENIED")
            task = self.task(ticket, sid)
            if method == "POST":
                if headers.get("Content-Type") != FORM or set(fields := form(raw)) != {"_csrf"}:
                    raise OperationsDenied("L2_NATIVE_REQUEST_DENIED")
                self.sessions.consume(sid, path, fields["_csrf"])
                self.activate(task, sid)
                return Reply(Response(303, b""), (("Location", "/b5a/l2/"),))
            with current_worker(self.port, task, self.sessions, sid, policy_expires_at=self.deadline):
                nonce = self.sessions.action(sid, path)
            html = ('<section class="card"><h1>本次工业采购深度诊断</h1>'
                '<p>先核对本任务的真实Worker证据，再完整重放工业诊断并生成七包改造蓝图。已有版本与决定保留；本操作不批准或外发。</p>'
                '<form method="post" action="'+e(path)+'">'+hidden('_csrf', nonce)
                +'<button data-key="l2-produce-native">生成／恢复本任务深度报告</button></form></section>')
            return Reply(Response(200, page("本任务原生深度诊断", html).encode()))
        except Exception:
            return Reply(Response(403, page("请求未提供深度报告", '<p data-code="L2_NATIVE_TASK_DENIED">L2_NATIVE_TASK_DENIED</p>'
                '<p>请先重新签名登录本任务，核对任务已提交真实证据。运行时未获准时不会执行P40试验。</p>').encode()))

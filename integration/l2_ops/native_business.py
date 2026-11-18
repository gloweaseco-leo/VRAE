"""Internal Brief routes on the original B5B SSR; no server or auth issuer."""
from dataclasses import dataclass

from apps.operator_console.b5a_http import Reply
from apps.operator_console.interface import Response
from apps.operator_console.proposal_views import hidden
from apps.operator_console.views import link
from vrae.l2.native import NativeSource
from vrae.l2_ops.briefs import BriefService
from vrae.l2_ops.ledger import BriefLedger
from vrae.l2_ops.panel import render_verified
from vrae.l2_ops.sources import OperationsDenied
from vrae.l2_ops.intake import SyntheticIntake
from vrae.l2_ops.intake_panel import render as render_intake
from .native_report import NativeCurrentReader


@dataclass(frozen=True)
class Binding:
    bundle: object
    activities: tuple
    subject: str
    factory: object


class NativeBusiness:
    """Trusted composition binds actual M1 sessions to the exact C2 review actor.

    Browser input supplies ONLY original CSRF, never a task, identity, pin,
    report, receipt, consultation claim, cost, deadline or service credential.
    The factory returns the original dual-authority reader for this request.
    """
    def __init__(self, app, ledger):
        if app.deep is None or app.generated is None or type(ledger) is not BriefLedger:
            raise OperationsDenied("L2_NATIVE_BUSINESS_PORTS_REQUIRED")
        self.app, self.ledger = app, ledger
        self.bindings = {}
        self.intake = SyntheticIntake()
        self.source_views = {}

    def bind(self, report_id, *, bundle, activities, subject, factory):
        # Configuration comes from the trusted production context, never HTTP.
        source = self.app.deep.ledgers[report_id].source
        if (type(source) is not NativeSource or source.held.tenant_id != bundle.tenant_id
                or source.held.source_bundle_sha256 != bundle.document()["content_sha256"]
                or not callable(factory) or type(subject) is not str or not subject):
            raise OperationsDenied("L2_NATIVE_BUSINESS_BINDING_DENIED")
        if report_id not in self.bindings and len(self.bindings) >= 40:
            raise OperationsDenied("L2_NATIVE_BUSINESS_BOUND")
        self.bindings[report_id] = Binding(bundle, tuple(activities), subject, factory)

    def route(self, path):
        from .s2_acceptance_sources import route
        if (rid := route(self, path)) is not None:
            return rid
        for rid in self.bindings:
            if path in {"/b5a/l2/r/" + rid + "/brief" + suffix for suffix in ('', '/submit', '/retry', '/revoke')}:
                return rid
        return None

    def decorate(self, path, reply):
        if reply.response.status != 200 or not reply.response.content_type.startswith("text/html"):
            return reply
        for rid in self.bindings:
            if path == "/b5a/l2/r/" + rid:
                html = reply.response.body.decode("utf-8")
                marker = '<main id="main" tabindex="-1">'
                if html.count(marker) == 1:
                    html = html.replace(marker, marker + (link(path+"/source-tasks", "五维来源候选复核", key="l2-source-workbench") if rid in self.source_views else "") + link(path+"/brief", "内部商务 RebuildBrief", key="l2-business-brief") + link("/b5a/m2/", "返回任务登录／恢复原任务", key="l2-task-login"), 1)
                    response = reply.response
                    return Reply(Response(response.status, html.encode("utf-8"), response.content_type), reply.headers)
        return reply

    def handle(self, method, path, headers, raw):
        from .s2_acceptance_sources import route, handle
        if route(self, path) is not None:
            return handle(self, method, path, headers, raw)
        try:
            rid = self.route(path)
            if rid is None or method not in ("GET", "HEAD", "POST") or headers.get("Authorization") is not None:
                raise OperationsDenied("L2_NATIVE_BUSINESS_DENIED")
            deep = self.app.deep
            deep.refresh()
            sid = deep.sid(headers)
            person = deep.directory.require(sid, rid).person
            binding = self.bindings[rid]
            root = "/b5a/l2/r/" + rid + "/brief"
            action = path.removeprefix(root).lstrip('/')
            if action and method != 'POST':
                raise OperationsDenied('S4_POST_REQUIRED')
            if (person.subject != binding.subject or person.tenant_id != binding.bundle.tenant_id
                    or person.role not in ("OWNER", "REVIEWER")):
                raise OperationsDenied("L2_NATIVE_BUSINESS_IDENTITY_DENIED")
            if method == "POST":
                deep.fields(headers, raw, sid, path, set())
            reader = binding.factory(sid)
            if (type(reader) is not NativeCurrentReader or reader.review_sid != sid
                    or reader.ledger is not deep.ledgers[rid] or reader.bundle != binding.bundle):
                raise OperationsDenied("L2_NATIVE_BUSINESS_CURRENT_READER_REQUIRED")
            service = BriefService(reader)
            if method == "POST" and not action and self.app.native_tasks is not None:
                from .runtime_audit import consume
                audit = consume(self.app.native_tasks, reader, self.ledger, binding.bundle, binding.activities)
                if audit is not None:
                    return deep.reply("S0 内部故障演练", '<p data-key="s0-audit-pass">TEST_ONLY ' + audit["case"] + '</p>')
            with reader.current() as current:
                # Each stored review has its own immutable internal Brief.
                brief_ref = "rb-" + current.review["receipt_ref"]
            if method == "POST" and not action:
                document = service.prepare(binding.bundle, brief_ref=brief_ref, activities=binding.activities)
                service.save_current(self.ledger, document)
            try:
                document = service.load_current(self.ledger, brief_ref)
                stored = True
            except OperationsDenied as error:
                if str(error) != "L2_BRIEF_NOT_FOUND" or method == "POST":
                    raise
                document = service.prepare(binding.bundle, brief_ref=brief_ref, activities=binding.activities)
                stored = False
            if self.app.native_tasks is not None:
                self.app.native_tasks.audit(document, stored)
            if action:
                if not stored:
                    raise OperationsDenied('S4_SAVED_BRIEF_REQUIRED')
                self.intake.transition(service, self.ledger, brief_ref, action)
            if stored and self.app.native_tasks is not None:
                from integration.l2_executive.runtime_intake import consume
                consume(self.app.native_tasks, self.intake, service, self.ledger, brief_ref)
            row = None
            if stored and document['source']['access_mode'] == 'OFFLINE_SYNTHETIC' and document['preparation_status'] == 'INTERNAL_REVIEW_RECORDED':
                row = self.intake.view_verified(document)
            nonce = deep.directory.action(sid, root)
            nonces = {a: deep.directory.action(sid, root+'/'+a) for a in ('submit', 'retry', 'revoke')}
            body = ('<p data-key="l2-brief-persistence">' + ("已从 PostgreSQL 回读持久交接。" if stored else "预览尚未持久保存；保存时将再次核验任务与本版本审核。")
                + '</p>' + render_intake(document, row, root, nonces, stored=stored and document['source']['access_mode'] == 'OFFLINE_SYNTHETIC' and document['preparation_status'] == 'INTERNAL_REVIEW_RECORDED')
                + render_verified(document) + '<form method="post" action="' + root + '">'
                + hidden('_csrf', nonce) + '<button data-key="l2-save-brief">保存内部商务 Brief</button></form>'
                + link('/b5a/l2/r/'+rid, '返回本次深度报告'))
            return deep.reply("内部商务 RebuildBrief", body)
        except Exception:
            return self.app.deep.reply("请求未提供交接数据", '<p data-code="L2_NATIVE_BUSINESS_DENIED">L2_NATIVE_BUSINESS_DENIED</p><p>请重新签名登录本任务及深度审核，并核对当前版本已保存逐项决定。</p>' + link("/b5a/m2/", "返回任务登录，恢复原任务", key="l2-task-login"), 403)

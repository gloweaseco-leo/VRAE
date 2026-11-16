"""Generated M2 routes mounted on the existing B5B signed SSR, never a server.

Task submission/status reuse the Owner-merged C1 TaskClient. Task handles route
requests; only fresh signed M1 reads and current DB assignments authorize data.
"""

from http.cookies import SimpleCookie
import json
from pathlib import Path
import re
import secrets
from uuid import UUID, uuid4
from datetime import datetime, timezone

from psycopg.types.json import Jsonb
from psycopg import OperationalError
from vrae.identity.boundary import IdentityDenied
from .b5a_http import Reply, FORM, form
from .interface import Response
from .contracts import ConsoleError
from .views import e, frame, link
from .proposal_views import hidden
from .b5b_m2_sessions import GeneratedSessions
from .b5b_m2_report import report_body, a4, receipt_body, review_label
from .b5b_m2_review import ReviewCommand
from .b5b_m2_views import generated_decision_fields
from .b5b_m2_tasks import TaskWorkflow

PREFIX = '/b5a/m2/'


def page(title, content):
    html = frame('/b5a/', title, content, '本次生成任务 · 内部审核')
    html = html.replace('</head>', '<link rel="stylesheet" href="/b5a/m2/style.css"></head>', 1)
    html = html.replace('<body>', '<body class="m2-workspace">', 1)
    start = html.index('<footer>')
    return html[:start] + ('<footer>仅保存本次实际生成版本的内部合成审核回执。'
        '不是实际人工批准，不产生 ShareGrant 或外部交付。NOT APPROVED。</footer></body></html>')


def cookies(headers):
    raw = headers.get('Cookie', '')
    keys = [p.strip().split('=', 1)[0] for p in raw.split(';')] if raw else []
    if len(raw) > 1024 or len(keys) != len(set(keys)) or set(keys) - {
        'b5a_session', 'b5a_challenge', 'b5a_m2_session', 'b5a_m2_challenge'
    }:
        raise IdentityDenied('M2_SESSION_DENIED')
    c = SimpleCookie()
    c.load(raw)
    if set(c) != set(keys) or any(not re.fullmatch('[A-Za-z0-9_-]{43}', v.value) for v in c.values()):
        raise IdentityDenied('M2_SESSION_DENIED')
    return {k: v.value for k, v in c.items()}


def cookie(name, value, age):
    return f'{name}={value}; Path={PREFIX}; Max-Age={age}; HttpOnly; SameSite=Strict'


class GeneratedConsole:
    def __init__(self, sessions, tasks, *, workflow=None):
        if type(sessions) is not GeneratedSessions:
            raise ValueError('M2_ACCEPTED_GENERATED_SESSIONS_REQUIRED')
        self.sessions = sessions
        # Launcher-provisioned aliases -> exact tenant/job; not HTTP authority.
        self.tasks = dict(tasks)
        if any(k not in ('404', '200') or set(v) != {'tenant', 'job_id'} for k, v in self.tasks.items()):
            raise ValueError('M2_SYNTHETIC_TASK_MAPPING_REQUIRED')
        self.bootstrap_csrf = secrets.token_urlsafe(32)
        if workflow is not None and type(workflow) is not TaskWorkflow:
            raise ValueError('M2_ACCEPTED_TASK_WORKFLOW_REQUIRED')
        self.workflow = workflow

    def task_routes(self, method, route, path, headers, raw, sid):
        workflow = self.workflow
        if workflow is None:
            raise ValueError('M2_TASK_WORKFLOW_UNAVAILABLE')
        session = self.sessions.require(sid)
        if route == 'tasks' and method in ('GET', 'HEAD'):
            with self.sessions.request(sid):
                rows = workflow.list(session)
            csrf = self.sessions.action(sid, PREFIX + 'create')
            html = ('<section class="card"><h1>提交新的合成制造业诊断</h1>'
                '<p>仅固定授权的合成来源；任务完成后须重新签名打开该任务报告。</p>'
                '<form method="post" action="/b5a/m2/create">' + hidden('_csrf', csrf)
                + '<label>合成来源<select name="case"><option value="404">制造业 · 联系路径404</option>'
                '<option value="200">制造业 · 静态路径200／证据不足</option></select></label>'
                '<button type="submit" data-key="m2-create">提交新诊断任务</button></form></section>'
                '<section class="card"><h2>当前 Reviewer 的已提交任务</h2>')
            for ticket, case, known in rows:
                html += link(PREFIX + 'task/' + ticket, '合成来源 ' + case + (' · 查询状态' if known else ' · 提交结果待核对'), key='m2-task-history')
            return Reply(Response(200, page('合成任务提交与状态', html + '</section>').encode()))
        if route == 'create' and method == 'POST':
            if headers.get('Content-Type') != FORM:
                raise ValueError('M2_INVALID_REQUEST')
            f = form(raw)
            if set(f) != {'_csrf', 'case'}:
                raise ValueError('M2_INVALID_REQUEST')
            self.sessions.consume(sid, path, f['_csrf'])
            ticket = workflow.create(self.sessions, sid, f['case'])
            return Reply(Response(303, b''), (('Location', PREFIX + 'task/' + ticket),))
        match = re.fullmatch(r'task/([A-Za-z0-9_-]{43})(?:/(retry|challenge))?', route)
        if match is None:
            raise ValueError('M2_INVALID_REQUEST')
        ticket, action = match.groups()
        if action is not None and method == 'POST':
            if headers.get('Content-Type') != FORM:
                raise ValueError('M2_INVALID_REQUEST')
            f = form(raw)
            if set(f) != {'_csrf'}:
                raise ValueError('M2_INVALID_REQUEST')
            self.sessions.consume(sid, path, f['_csrf'])
            if action == 'retry':
                row = workflow.row(ticket, session)
                workflow.create(self.sessions, sid, row[1], ticket=ticket)
                return Reply(Response(303, b''), (('Location', PREFIX + 'task/' + ticket),))
            challenge, nonce, csrf = workflow.challenge(ticket, self.sessions, sid)
            return Reply(Response(200, json.dumps({'nonce': nonce, 'csrf': csrf}).encode(), 'application/json'),
                         (('Set-Cookie', cookie('b5a_m2_challenge', challenge, 30)),))
        if action is not None or method not in ('GET', 'HEAD'):
            raise ValueError('M2_INVALID_REQUEST')
        task, state = workflow.status(ticket, self.sessions, sid)
        html = '<section class="card"><h1>本次新提交任务</h1>'
        if task is None:
            html += '<p data-code="M2_SUBMISSION_UNKNOWN">提交结果待核对；用原幂等键恢复，不另建任务。</p>'
            action = 'retry'
            label = '核对原提交结果'
        else:
            state_label = {'PENDING': '任务已提交，正在等待生成诊断报告',
                           'TEST_ONLY_DONE': '诊断报告已生成，请打开查看'}.get(
                               state['job_state'], '任务尚未完成，请刷新状态核对')
            html += '<p class="m2-outcome">' + e(state_label) + '</p>'
            html += '<details class="m2-technical"><summary>技术详情：提交响应与任务标识</summary>'
            html += '<p data-app-status="202">原 APP 202 已提交</p><dl>'
            for key in ('request_id', 'run_id', 'job_id', 'source_ref'):
                html += '<dt>' + e(key) + '</dt><dd data-key="m2-' + e(key) + '">' + e(getattr(task, key)) + '</dd>'
            html += '</dl><p data-key="m2-job-state">' + e(state['job_state']) + '</p>'
            html += '<p>状态与 request/run/job/来源已核对；状态字段不是报告版本或读取授权。</p></details>'
            action = 'challenge' if state['job_state'] == 'TEST_ONLY_DONE' else None
            label = '签名打开本次新生成报告'
        if action:
            target = PREFIX + 'task/' + ticket + '/' + action
            csrf = self.sessions.action(sid, target)
            html += '<form method="post" action="' + e(target) + '">' + hidden('_csrf', csrf)
            html += '<button type="submit" data-key="m2-new-report">' + label + '</button></form>'
        html += link(PREFIX + 'task/' + ticket, '刷新任务状态', key='m2-status-refresh')
        html += link(PREFIX + 'tasks', '返回我的合成任务') + '</section>'
        return Reply(Response(200, page('新任务处理状态', html).encode()))

    def handle(self, method, path, headers, raw):
        try:
            if hasattr(headers, 'get_all') and any(len(headers.get_all(k, [])) > 1 for k in ('X-M2-CSRF',)):
                raise IdentityDenied('M2_SESSION_DENIED')
            if method not in ('GET', 'HEAD', 'POST'):
                raise ValueError('M2_INVALID_REQUEST')
            route = path.removeprefix(PREFIX)
            auth = headers.get('Authorization')
            if auth is not None and (route != 'session' or method != 'POST'):
                raise IdentityDenied('M2_SESSION_DENIED')
            if route == 'style.css' and method in ('GET', 'HEAD'):
                return Reply(Response(200, Path(__file__).with_name('b5b_m2.css').read_bytes(), 'text/css; charset=utf-8'))
            jar = cookies(headers)
            if route == '' and method in ('GET', 'HEAD'):
                options = ''.join('<option value="' + e(k) + '">合成制造业 · ' + e(k) + ' 路径</option>' for k in self.tasks)
                html = ('<section class="card"><h1>合成诊断与内部审核</h1>'
                    '<p>仅合成制造业网站。新报告需要新的签名挑战；旧封存报告不作为本次结果。</p>'
                    '<form action="/b5a/m2/challenge" method="post">' + hidden('_csrf', self.bootstrap_csrf)
                    + '<label>当前已分配任务<select name="case">' + options + '</select></label>'
                    '<button type="submit">打开签名挑战</button></form>'
                    '<p>先通过当前已分配任务验证 Reviewer 身份；'
                    + ('登录后可提交新合成来源。' if self.workflow is not None else '当前仅开放已分配报告。')
                    + '不使用封存结果替代新任务。</p></section>')
                return Reply(Response(200, page('新生成任务', html).encode()))
            if route == 'challenge' and method == 'POST':
                if headers.get('Content-Type') != FORM:
                    raise ValueError('M2_INVALID_REQUEST')
                f = form(raw)
                if set(f) != {'_csrf', 'case'} or f['_csrf'] != self.bootstrap_csrf or f['case'] not in self.tasks:
                    raise IdentityDenied('M2_SESSION_DENIED')
                task = self.tasks[f['case']]
                challenge, nonce, csrf = self.sessions.challenge(task['tenant'], task['job_id'])
                return Reply(Response(200, json.dumps({'nonce': nonce, 'csrf': csrf}).encode(), 'application/json'),
                             (('Set-Cookie', cookie('b5a_m2_challenge', challenge, 30)),))
            if route == 'session' and method == 'POST':
                if headers.get('Content-Type') != 'application/json' or raw != b'{}':
                    raise ValueError('M2_INVALID_REQUEST')
                sid = self.sessions.login(jar.get('b5a_m2_challenge', ''), auth or '', headers.get('X-M2-CSRF', ''))
                return Reply(Response(303, b''), (('Location', PREFIX + 'report'),
                    ('Set-Cookie', cookie('b5a_m2_challenge', '', 0)),
                    ('Set-Cookie', cookie('b5a_m2_session', sid, 120))))
            sid = jar.get('b5a_m2_session', '')
            if route in ('tasks', 'create') or route.startswith('task/'):
                return self.task_routes(method, route, path, headers, raw, sid)
            with self.sessions.request(sid) as (c, view):
                session = self.sessions.require(sid)
                a = session.assignment
                if route == 'report' and method in ('GET', 'HEAD'):
                    csrf = self.sessions.action(sid, PREFIX + 'review')
                    html = report_body(view) + generated_decision_fields(view, csrf)
                    receipts = c.execute('SELECT b5b_m2.list_receipts(%s,%s)', (a.tenant, a.job_id)).fetchone()[0]
                    html += '<section class="card"><h2>本版本的内部审核记录</h2><p>以下是操作记录；诊断内容请以上方报告为准。最近 20 条，重新登录仍可回读。</p>'
                    for item in receipts:
                        html += link(PREFIX + 'receipt/' + item['command_id'],
                            review_label(item['decision']) + ' · ' + item['recorded_at'], key='m2-saved-receipt')
                    html += '</section>'
                    if self.workflow is not None:
                        html += link(PREFIX + 'tasks', '提交／查询新的合成任务', key='m2-tasks')
                    html += link(PREFIX + 'export', '查看中文 A4 单页诊断成果', key='m2-a4')
                    response = Reply(Response(200, page('实际生成报告', html).encode()))
                elif route == 'review' and method == 'POST':
                    if headers.get('Content-Type') != FORM:
                        raise ValueError('M2_INVALID_REQUEST')
                    f = form(raw)
                    self.sessions.consume(sid, path, f.pop('_csrf', ''))
                    cmd = ReviewCommand.parse(f, view)
                    command_id = str(uuid4())
                    receipt = c.execute('SELECT b5b_m2.submit(%s,%s,%s,%s,%s)',
                        (a.tenant, a.job_id, command_id, Jsonb(cmd.document()),
                         datetime.fromtimestamp(session.expires, timezone.utc))).fetchone()[0]
                    if receipt['report'] != view.payload.locator:
                        raise ValueError('M2_RECEIPT_REPORT_MISMATCH')
                    response = Reply(Response(303, b''), (('Location', PREFIX + 'receipt/' + command_id),))
                elif method in ('GET', 'HEAD') and (route == 'export' or route.startswith(('receipt/', 'export/'))):
                    receipt = None
                    if '/' in route:
                        kind, command_id = route.split('/', 1)
                        if str(UUID(command_id)) != command_id:
                            raise ValueError('M2_INVALID_REQUEST')
                        receipt = c.execute('SELECT b5b_m2.read_receipt(%s,%s,%s)',
                                            (a.tenant, a.job_id, command_id)).fetchone()[0]
                    if route.startswith('receipt/'):
                        html = receipt_body(view, receipt, command_id)
                        response = Reply(Response(200, page('持久审核回执', html).encode()))
                    else:
                        response = Reply(Response(200, a4(view, receipt=receipt).encode()),
                            (('Content-Disposition', 'inline; filename="synthetic-l1-a4.html"'),))
                else:
                    raise ValueError('M2_INVALID_REQUEST')
            # Commit has really completed before success/redirect can escape.
            return response
        except Exception as exc:
            code = 'M2_STALE_REPORT' if isinstance(exc, ValueError) and str(exc) == 'M2_STALE_REPORT' else 'M2_REQUEST_DENIED'
            status = 409 if code == 'M2_STALE_REPORT' else 403
            if isinstance(exc, OperationalError):
                status, code = 503, 'M2_DB_UNAVAILABLE'
            if isinstance(exc, ConsoleError):
                code = 'M2_REQUEST_DENIED'
            html = '<h1>请求未提供数据</h1><p data-code="' + code + '">' + code + '</p>'
            if self.workflow is not None:
                html += link(PREFIX + 'tasks', '返回我的任务／核对原提交结果', key='m2-recover-task')
            return Reply(Response(status, page('请求未提供数据', html).encode()))

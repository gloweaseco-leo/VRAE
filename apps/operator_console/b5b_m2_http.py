"""Generated M2 routes mounted on the existing B5B signed SSR, never a server.

Task submission/status remain an explicit dependency on the Owner-merged C1
consumer port. This component serves already provisioned REAL generated jobs.
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
from .views import e, frame, dump, link
from .proposal_views import hidden
from .b5b_m2_sessions import GeneratedSessions
from .b5b_m2_report import report_body, a4
from .b5b_m2_review import ReviewCommand
from .b5b_m2_views import generated_decision_fields

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
    def __init__(self, sessions, tasks):
        if type(sessions) is not GeneratedSessions:
            raise ValueError('M2_ACCEPTED_GENERATED_SESSIONS_REQUIRED')
        self.sessions = sessions
        # Launcher-provisioned aliases -> exact tenant/job; not HTTP authority.
        self.tasks = dict(tasks)
        if any(k not in ('404', '200') or set(v) != {'tenant', 'job_id'} for k, v in self.tasks.items()):
            raise ValueError('M2_SYNTHETIC_TASK_MAPPING_REQUIRED')
        self.bootstrap_csrf = secrets.token_urlsafe(32)

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
                html = ('<section class="card"><h1>本次 Worker 生成任务</h1>'
                    '<p>仅合成制造业网站。新报告需要新的签名挑战；旧封存报告不作为本次结果。</p>'
                    '<form action="/b5a/m2/challenge" method="post">' + hidden('_csrf', self.bootstrap_csrf)
                    + '<label>已分配的新任务<select name="case">' + options + '</select></label>'
                    '<button type="submit">打开签名挑战</button></form>'
                    '<p data-code="M2_TASK_SUBMISSION_DEPENDS_ON_ACCEPTED_C1_CONSUMER">'
                    '新任务提交／状态入口等待已验收的 C1 消费端口接入；下方不使用封存结果代替。</p></section>')
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
            with self.sessions.request(sid) as (c, view):
                session = self.sessions.require(sid)
                a = session.assignment
                if route == 'report' and method in ('GET', 'HEAD'):
                    csrf = self.sessions.action(sid, PREFIX + 'review')
                    html = report_body(view) + generated_decision_fields(view, csrf)
                    receipts = c.execute('SELECT b5b_m2.list_receipts(%s,%s)', (a.tenant, a.job_id)).fetchone()[0]
                    html += '<section class="card"><h2>本版本已持久化的内部回执</h2><p>最近 20 条；重启后重新签名登录仍可回读。</p>'
                    for item in receipts:
                        html += link(PREFIX + 'receipt/' + item['command_id'],
                            item['recorded_at'] + ' · ' + item['decision'], key='m2-saved-receipt')
                    html += '</section>'
                    html += link(PREFIX + 'export', '查看中文 A4 合成样本', key='m2-a4')
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
                        html = '<section class="card"><h1>已持久化的内部合成审核回执</h1>' + dump(receipt)
                        html += link(PREFIX + 'export/' + command_id, '查看／导出本版本 A4', key='m2-a4')
                        html += link(PREFIX + 'report', '返回实际生成报告') + '</section>'
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
            return Reply(Response(status, page('请求未提供数据', '<h1>请求未提供数据</h1><p data-code="' + code + '">' + code + '</p>').encode()))

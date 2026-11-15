"""Real M1 Worker -> public signed read -> M2 projection/PG ledger.

The receipt SQL is tested with a real low role. This is NOT evidence of the
pending signed task/session HTTP port or a browser approval flow.
"""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from contextlib import closing
import http.client
import threading
import time
from urllib.parse import urlencode

import psycopg
from psycopg.types.json import Jsonb
import pytest

from integration.ra4a import support
from integration.ra4b_p2.audit_cases import runtime as runtime
from integration.ra4b_p2.m1.native_cases import m1 as m1, reader
from integration.ra4b_p2.interface_cases import admit
from apps.operator_console.b5b_m2_report import ReportView, report_body, a4
from apps.operator_console.b5b_m2_review import ReviewCommand
from apps.operator_console.b5b_m2_sessions import GeneratedSessions
from apps.operator_console.b5b_m2_http import GeneratedConsole
from apps.operator_console.b5a_sessions import SessionStore
from apps.operator_console.b5a_http import Application as Base, server
from apps.operator_console.b5p0_http import RehearsalApplication
from apps.operator_console.b5p0_journal import Journal
from apps.operator_console.b5b_http import Application
from vrae.b6_p0.reader import PrivateHandoffReader
from vrae.identity.boundary import TrustAnchor, IdentityDenied
from vrae.application.ra4b_p2.m1.reader import SignedGeneratedReader, JobAssignment
from tests.identity.issuer import Issuer, ISSUER, AUDIENCE

OUT = Path('/evidence')


@pytest.fixture(scope='module')
def ledger(m1):
    with support.connect() as c:
        c.execute(Path('/work/db/b5b_m2/001_internal_review.sql').read_text())
    m1['receipts'] = {}
    yield m1
    (OUT / 'm2-restart-proof.json').write_text(json.dumps(m1['receipts']))


def fields(view, decision='APPROVE_INTERNAL', revision=''):
    f = dict(report_version=str(view.pins['report_version']),
             report_sha256=view.pins['report_sha256'], decision=decision, revision=revision)
    for i in view.issue_ids:
        f['decision.' + i] = decision
        f['revision.' + i] = revision
    return f


@pytest.mark.parametrize('case', ['404', '200'])
def test_fresh_worker_signed_result_and_internal_ledger(ledger, case):
    request = admit(ledger['runtime'], 'm2-fresh-' + case, 'accepted-' + case)
    finished = ledger['spawn']()
    assert all(finished[k] == request[k] for k in ('request_id', 'run_id', 'job_id'))
    port, bearer, nonce = reader(ledger, request)
    generated = port.read(bearer, 'tenant-test', request['job_id'], nonce=nonce)
    view = ReportView(generated)
    assert len(view.issue_ids) == (1 if case == '404' else 0)
    body = report_body(view)
    assert view.pins['report_sha256'] in body
    assert 'NOT APPROVED' in body and 'Guard' in body and 'Evidence' in body
    assert ('证据不足' in body) == (case == '200')
    if case == '404':
        assert view.pins['native_content_hash'] != view.pins['report_sha256']
    else:
        assert view.pins['native_content_hash'] is None
    with pytest.raises(ValueError, match='HASH_MISMATCH'):
        ReportView(replace(generated, html=generated.html + b'forged'))
    records = []
    for action, revision in [('APPROVE_INTERNAL', ''), ('REJECT_INTERNAL', '内部拒绝'),
                             ('REVISE_INTERNAL', '请核对来源，不修改源事实。')]:
        cmd = ReviewCommand.parse(fields(view, action, revision), view)
        command_id = str(uuid4())
        with support.connect('p2b1_test_a_reviewer') as c:
            with c.transaction():
                receipt = c.execute('SELECT b5b_m2.submit(%s,%s,%s,%s)',
                    ('tenant-test', request['job_id'], command_id, Jsonb(cmd.document()))).fetchone()[0]
            # New real transaction; committed receipt must be readable.
            restored = c.execute('SELECT b5b_m2.read_receipt(%s,%s,%s)',
                ('tenant-test', request['job_id'], command_id)).fetchone()[0]
            assert restored == receipt
            assert c.execute('SELECT b5b_m2.submit(%s,%s,%s,%s)',
                ('tenant-test', request['job_id'], command_id, Jsonb(cmd.document()))).fetchone()[0] == receipt
            bad = dict(cmd.document(), decision='REJECT_INTERNAL' if action != 'REJECT_INTERNAL' else 'APPROVE_INTERNAL')
            with pytest.raises(psycopg.Error, match='M2_IDEMPOTENCY_CONFLICT'):
                c.execute('SELECT b5b_m2.submit(%s,%s,%s,%s)',
                    ('tenant-test', request['job_id'], command_id, Jsonb(bad)))
        assert receipt['human_approval'] is False and receipt['external_delivery'] is False
        assert receipt['report_approval_status'] == 'NOT_APPROVED'
        exported = a4(view, receipt=receipt)
        assert '合成样本' in exported and request['job_id'] in exported
        assert '不是实际人工批准' in exported
        records.append(dict(command_id=command_id, receipt=receipt))
    (OUT / ('m2-' + case + '.html')).write_text(a4(view, receipt=receipt))
    (OUT / ('m2-' + case + '-view.html')).write_text(report_body(view))
    (OUT / 'm2-style.css').write_bytes(Path('/work/apps/operator_console/b5b_m2.css').read_bytes())
    ledger['results'][case] = finished
    ledger['receipts'][case] = dict(result=finished, records=records,
        report_sha256=hashlib.sha256(generated.report).hexdigest())


@pytest.mark.parametrize('role,tenant', [
    ('p2b1_test_a_peer', 'tenant-test'), ('p2b1_test_b_reviewer', 'tenant-beta'),
    ('ra4b_test_a_worker', 'tenant-test')])
def test_receipt_peer_cross_tenant_and_worker_denied(ledger, role, tenant):
    item = ledger['receipts']['404']
    with support.connect(role) as c:
        with pytest.raises(psycopg.Error) as error:
            c.execute('SELECT b5b_m2.read_receipt(%s,%s,%s)',
                (tenant, item['result']['job_id'], item['records'][0]['command_id']))
        assert error.value.sqlstate == '42501'


@pytest.mark.parametrize('key,value', [
    ('report_version', 2), ('report_sha256', '0'*64), ('scope', 'HUMAN_APPROVED'),
    ('decision', 'APPROVED'), ('issues', []), ('revision', None)])
def test_wrong_version_hash_scope_decision_issues_fail_without_receipt(ledger, key, value):
    item = ledger['receipts']['404']
    request = item['result']
    port, bearer, nonce = reader(ledger, request)
    view = ReportView(port.read(bearer, 'tenant-test', request['job_id'], nonce=nonce))
    cmd = ReviewCommand.parse(fields(view), view).document()
    cmd[key] = value
    command_id = str(uuid4())
    with support.connect('p2b1_test_a_reviewer') as c:
        with pytest.raises(psycopg.Error) as error:
            c.execute('SELECT b5b_m2.submit(%s,%s,%s,%s)',
                ('tenant-test', request['job_id'], command_id, Jsonb(cmd)))
        assert error.value.sqlstate == '42501'
        with pytest.raises(psycopg.Error, match='M2_RECEIPT_DENIED'):
            c.execute('SELECT b5b_m2.read_receipt(%s,%s,%s)',
                ('tenant-test', request['job_id'], command_id))


def test_no_runtime_table_privileges_or_report_mutation(ledger):
    with support.connect('p2b1_test_a_reviewer') as c:
        for sql in ['SELECT * FROM b5b_m2.receipts',
                    'DELETE FROM b5b_m2.receipts',
                    "UPDATE ra4b_p2.m1_results SET report_version=2"]:
            with pytest.raises(psycopg.Error) as error:
                c.execute(sql)
            assert error.value.sqlstate == '42501'
    with support.connect() as c:
        assert c.execute('SELECT count(*) FROM b5b_m2.receipts').fetchone()[0] == 6


def test_review_command_rejects_stale_and_foreign_issue_intent(ledger):
    request = ledger['results']['404']
    port, bearer, nonce = reader(ledger, request)
    view = ReportView(port.read(bearer, 'tenant-test', request['job_id'], nonce=nonce))
    for f in [dict(fields(view), report_version='2'),
              dict(fields(view), report_sha256='0'*64),
              dict(fields(view), **{'decision.foreign': 'APPROVE_INTERNAL'}),
              fields(view, 'REVISE_INTERNAL', '  ')]:
        with pytest.raises(ValueError):
            ReviewCommand.parse(f, view)


def launch(ledger, *, clock=time.time):
    issuer = Issuer()
    now = int(clock())
    anchor = TrustAnchor(ISSUER, AUDIENCE, issuer.jwks(), now + 180)
    assignments = [JobAssignment(ISSUER, 'synthetic-reviewer-1', 'p2b1_test_a_reviewer',
        'tenant-test', ledger['results'][case]['job_id'], now + 180) for case in ('404', '200')]
    reader = SignedGeneratedReader(anchor=anchor, assignments=assignments, connect=support.connect, clock=clock)
    sessions = GeneratedSessions(reader)
    generated = GeneratedConsole(sessions, {case: {'tenant': 'tenant-test', 'job_id': ledger['results'][case]['job_id']} for case in ('404', '200')})
    # SAME original SSR composition; the legacy lane has no fixture reports or
    # assignments at all. Nothing sealed can become a new Worker result.
    legacy = SessionStore(anchor=anchor, bindings={}, readers={})
    base = Base(legacy, {})
    rehearsal = RehearsalApplication(base, {}, Journal('/tmp/m2-journal-' + uuid4().hex), key_secret=b'x'*32)
    app = Application(rehearsal, PrivateHandoffReader(legacy, {}), generated=generated)
    http = server(app)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    return app, http, thread, issuer, generated


def http_call(app, method, path, body=b'', *, cookie='', auth=None, csrf=None, content_type=None):
    headers = {'Host': app.origin.removeprefix('http://'), 'Origin': app.origin}
    if cookie:
        headers['Cookie'] = cookie
    if auth:
        headers['Authorization'] = auth
    if csrf:
        headers['X-M2-CSRF'] = csrf
    if content_type:
        headers['Content-Type'] = content_type
    with closing(http.client.HTTPConnection('127.0.0.1', int(app.origin.rsplit(':', 1)[1]), timeout=30)) as c:
        c.request(method, path, body, headers)
        response = c.getresponse()
        return response.status, response.read(), response.getheaders()


def signin(app, generated, issuer, case):
    f = urlencode({'_csrf': generated.bootstrap_csrf, 'case': case}).encode()
    status, raw, headers = http_call(app, 'POST', '/b5a/m2/challenge', f,
                                  content_type='application/x-www-form-urlencoded')
    assert status == 200
    challenge = json.loads(raw)
    cookie = next(v.split(';')[0] for k, v in headers if k.lower() == 'set-cookie')
    now = int(time.time())
    token = issuer.token({'iat': now, 'nbf': now, 'exp': now + 90, 'nonce': challenge['nonce']})
    status, raw, headers = http_call(app, 'POST', '/b5a/m2/session', b'{}',
        cookie=cookie, auth=token, csrf=challenge['csrf'], content_type='application/json')
    assert status == 303
    session_cookie = next(v for k, v in headers if k.lower() == 'set-cookie' and v.startswith('b5a_m2_session='))
    assert 'HttpOnly' in session_cookie and 'SameSite=Strict' in session_cookie and 'Path=/b5a/m2/' in session_cookie
    return session_cookie.split(';')[0]


@pytest.mark.parametrize('case', ['404', '200'])
def test_same_ssr_real_signed_http_review_and_a4(ledger, case):
    import re
    from html import unescape
    app, http, thread, issuer, generated = launch(ledger)
    try:
        assert http_call(app, 'GET', '/b5a/m2/report')[0] == 403
        cookie = signin(app, generated, issuer, case)
        status, raw, headers = http_call(app, 'GET', '/b5a/m2/report', cookie=cookie)
        assert status == 200
        html = raw.decode()
        assert ledger['results'][case]['job_id'] in html
        assert '保存本版本内部回执' in html
        assert any(k.lower() == 'content-security-policy' and "style-src 'self'" in v for k, v in headers)
        assert '<script' not in html and '<style' not in html
        values = {unescape(k): unescape(v) for k, v in re.findall(r'name="([^"]+)" value="([^"]*)"', html)}
        values.update(decision='REVISE_INTERNAL', revision='内部修订；请复核当前版本。')
        for key in re.findall(r'<select name="([^"]+)"', html):
            values[unescape(key)] = 'REVISE_INTERNAL'
            if key.startswith('decision.'):
                values['revision.' + key.removeprefix('decision.')] = '保留源事实，仅请求复核。'
        status, _, headers = http_call(app, 'POST', '/b5a/m2/review', urlencode(values).encode(),
            cookie=cookie, content_type='application/x-www-form-urlencoded')
        assert status == 303
        url = next(v for k, v in headers if k.lower() == 'location')
        status, raw, _ = http_call(app, 'GET', url, cookie=cookie)
        assert status == 200 and '已持久化' in raw.decode()
        status, raw, _ = http_call(app, 'GET', url.replace('/receipt/', '/export/'), cookie=cookie)
        assert status == 200 and '合成样本' in raw.decode() and ledger['results'][case]['report_sha256'] in raw.decode()
        generated.sessions.reader.anchor = replace(generated.sessions.reader.anchor, revoked=frozenset({'old'}))
        assert http_call(app, 'GET', url, cookie=cookie)[0] == 403
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def test_generated_session_expiry_and_restart_do_not_reuse_old_login(ledger):
    now = [time.time()]
    app, http, thread, issuer, generated = launch(ledger, clock=lambda: now[0])
    try:
        cookie = signin(app, generated, issuer, '404')
        sid = cookie.split('=', 1)[1]
        with generated.sessions.request(sid):
            now[0] += 121
            # End-of-request recheck must roll back, not return a stale success.
            with pytest.raises(IdentityDenied):
                generated.sessions.require(sid)
    except IdentityDenied:
        pass
    else:
        raise AssertionError('M2_EXPIRED_TRANSACTION_NOT_DENIED')
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=5)
    fresh = GeneratedSessions(generated.sessions.reader)
    with pytest.raises(IdentityDenied):
        fresh.require(sid)


def test_real_commit_after_signed_deadline_rolls_back_receipt(ledger):
    request = ledger['results']['404']
    port, bearer, nonce = reader(ledger, request)
    view = ReportView(port.read(bearer, 'tenant-test', request['job_id'], nonce=nonce))
    cmd = ReviewCommand.parse(fields(view), view).document()
    command_id = str(uuid4())
    with support.connect('p2b1_test_a_reviewer') as c:
        with pytest.raises(psycopg.Error, match='M2_SESSION_EXPIRED_AT_COMMIT') as error:
            with c.transaction():
                deadline = c.execute("SELECT clock_timestamp()+interval '500 milliseconds'").fetchone()[0]
                c.execute('SELECT b5b_m2.submit(%s,%s,%s,%s,%s)',
                    ('tenant-test', request['job_id'], command_id, Jsonb(cmd), deadline))
                c.execute('SELECT pg_sleep(0.6)')
        assert error.value.sqlstate == '42501'
        with pytest.raises(psycopg.Error, match='M2_RECEIPT_DENIED'):
            c.execute('SELECT b5b_m2.read_receipt(%s,%s,%s)',
                ('tenant-test', request['job_id'], command_id))

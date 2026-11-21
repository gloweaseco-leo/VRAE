"""Disposable actual PG vertical. No external website/provider or retained ledger.

Run only in a fresh network-none PG namespace with VRAE_AUTOMATIC_PG_TEST=1.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, UTC, timedelta
import os
import json
from pathlib import Path
import secrets
import time

import psycopg
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import pytest

from contracts.l2_launch.contract import canonical, Refused
from infra.windows_service import intake
from integration.authorized_targets import store, worker, source_authority
from integration.authorized_targets.authority import token_hash, check_submission
from integration.authorized_targets.automatic_result import current, project
from integration.authorized_targets.provision import install, grant_automatic_sessions
from infra.linux_service.ai_loop import adapter
from integration.qwen_provider.committed import execute
from vrae.intelligence.qwen import Config, Permission, Price, QwenProvider, Quota
from vrae.intelligence.qwen.provider import MODEL_SOURCE, CONTEXT_PROMPT
from vrae.intelligence.qwen.testing import FakeTransport
from vrae.intelligence.qwen.session import RULE_TASK
from integration.authorized_targets.automatic_result import TASKS
from integration.authorized_targets.api_contract import openapi
from jsonschema import Draft202012Validator
from tests.collection.test_pipeline import FixedDNS, SyntheticTransport
from vrae.collection.collector import Collector
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Limits
from vrae.collection.policy import SourceAccess
from integration.authorized_targets.egress import CurrentAccess
from integration.l2_launch.security.adapter import TaskPins, OfflinePermit, fingerprint

pytestmark = pytest.mark.skipif(os.environ.get('VRAE_AUTOMATIC_PG_TEST') != '1',
    reason='requires a NEW disposable PG namespace, never a running service')


def test_actual_pg_automatic_submission_worker_qwen_and_same_subject_result(tmp_path, monkeypatch):
    def admin():
        return psycopg.connect(host='127.0.0.1', dbname='vrae_ra4a_p1', user='postgres',
            password='synthetic-automatic-pg-only', autocommit=True)
    with admin() as c:
        for path in ('db/migrations/0001_ra4a_test_only.sql',
            'infra/authorized_targets/001_authority.sql', 'infra/authorized_targets/002_delivery.sql',
            'infra/authorized_targets/003_api.sql', 'infra/linux_service/004_ai_pending.sql',
            'infra/authorized_targets/006_automatic_diagnosis.sql',
            'infra/authorized_targets/007_automatic_sessions.sql',
            'infra/authorized_targets/008_committed_language.sql',
            'infra/authorized_targets/009_committed_scoped_language.sql',
            'infra/authorized_targets/010_committed_context_language.sql',
            'infra/authorized_targets/011_committed_procurement_language.sql'):
            c.execute(Path(path).read_text())
        assert c.execute('SELECT current_user').fetchone()[0] == 'postgres'
    now = datetime.now(UTC)
    end = (now + timedelta(minutes=15)).isoformat()
    tenant = 'tenant-automatic-test'
    keys = {name: Ed25519PrivateKey.generate() for name in ('source', 'permission')}
    registry = {'keys': {'source': {'role': 'SOURCE_ADMIN', 'source_class': 'CONTROLLED_NON_CUSTOMER',
        'revoked': False, 'public': keys['source'].public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()}}}
    # A test registry, not a deployment identity or permission issuer.
    monkeypatch.setattr(source_authority, 'root_document', lambda _: registry)
    monkeypatch.setattr(intake, 'key', lambda name: keys[name])
    monkeypatch.setattr(intake, 'admin', admin)
    monkeypatch.setattr(intake, 'private', lambda _: b'synthetic-hmac-only')
    monkeypatch.setattr(intake, 'delegation', lambda: {'proof': intake.AUTO_PROOF,
        'source_class': 'CONTROLLED_NON_CUSTOMER', 'expires_at': end, 'max_pages': 6})
    monkeypatch.setattr(intake, 'resolve_public', lambda host: ['93.184.216.20'])
    monkeypatch.setattr(intake, 'apply_policy', lambda *a: None)
    bindings = {kind: {'role': 'automatic_test_' + kind, 'password': secrets.token_hex(16),
        'tenant_id': tenant, 'kind': 'WORKER' if kind == 'worker' else 'APP',
        **({'port': 'AI'} if kind == 'ai' else {})} for kind in ('app', 'worker', 'ai')}
    invitations = [{'token': 'synthetic-invitation-' + n, 'document': {
        'tenant_id': tenant, 'reference': 'invitation-' + n, 'subject_ref': 'subject-' + n,
        'target_ids': [], 'expires_at': end, 'revoked': False}} for n in ('one', 'two')]
    with admin() as c, c.transaction():
        install(c, [{'tenant_id': tenant, 'expires_at': end, 'max_pending': 3,
            'actors': list(bindings.values()), 'plans': [], 'invitations': invitations}])
    app = bindings['app']
    sessions = []
    for inv in invitations:
        cookie, csrf = token_hash(inv['token'] + '-cookie'), token_hash(inv['token'] + '-csrf')
        store.invoke(app, 'exchange', tenant, token_hash(inv['token']), cookie, csrf)
        sessions.append((cookie, csrf))
    # Legacy invitation remains one-use; it is no longer a new-diagnosis gate.
    with pytest.raises(psycopg.Error):
        store.invoke(app, 'exchange', tenant, token_hash(invitations[0]['token']),
                     token_hash('duplicate-cookie'), token_hash('duplicate-csrf'))
    with pytest.raises(psycopg.Error):
        store.invoke(app, 'automatic_session', tenant, token_hash('no-grant-cookie'), token_hash('no-grant-csrf'))
    with admin() as c, c.transaction():
        grant_automatic_sessions(c, app)
        for restricted in (bindings['worker'], bindings['ai'], {**app, 'port': 'REVIEW'},
                           {**app, 'health_probe': {'expires_at': end}}):
            with pytest.raises(ValueError):
                grant_automatic_sessions(c, restricted)
        # Preserve the expired session instead of reviving it.
        c.execute('UPDATE target_v1.sessions SET expires_at=clock_timestamp()-interval \'1 second\' WHERE cookie_sha256=%s',
                  (sessions[0][0],))
    with pytest.raises(psycopg.Error):
        store.invoke(app, 'session', tenant, *sessions[0])
    def create_session(n):
        cookie, csrf = token_hash('automatic-cookie-' + str(n)), token_hash('automatic-csrf-' + str(n))
        created = store.invoke(app, 'automatic_session', tenant, cookie, csrf)
        assert datetime.fromisoformat(created['expires_at']) <= datetime.fromisoformat(end)
        return (cookie, csrf), store.invoke(app, 'session', tenant, cookie, csrf)
    with ThreadPoolExecutor(max_workers=2) as pool:
        established = list(pool.map(create_session, range(2)))
    sessions = [s[0] for s in established]
    principals = [s[1] for s in established]
    assert principals[0]['subject_ref'] != principals[1]['subject_ref']
    assert principals[0]['invitation_ref'] != principals[1]['invitation_ref']
    assert all(p['invitation']['target_ids'] == [] for p in principals)
    with pytest.raises(psycopg.Error):
        store.invoke(app, 'automatic_session', 'other-tenant', token_hash('foreign-cookie'), token_hash('foreign-csrf'))
    with pytest.raises(psycopg.Error):
        store.invoke(bindings['ai'], 'automatic_session', tenant, token_hash('ai-cookie'), token_hash('ai-csrf'))
    for invalid_cookie, invalid_csrf in (('invalid', token_hash('valid')), (None, token_hash('valid')),
                                       (token_hash('same'), token_hash('same'))):
        with pytest.raises(psycopg.Error):
            store.invoke(app, 'automatic_session', tenant, invalid_cookie, invalid_csrf)
    cookie, csrf = sessions[0]
    actor = store.invoke(app, 'session', tenant, cookie, csrf)
    body = {'url': 'https://supplier.example.com/', 'authorized': True,
        'consent_version': intake.AUTO_CONSENT, 'idempotency_key': 'actual-pg-test-0001',
        'accepted_at': now.isoformat(), 'language': 'zh'}
    submitted = intake.automatic_submission(app, actor, body, cookie, csrf)
    resolved = store.invoke(app, 'plan', tenant, cookie, csrf, body['url'])
    assert resolved['plan']['limits']['max_pages'] == 6
    verification = {'permission': {'public': keys['permission'].public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw).hex(), 'tenant': tenant, 'role': 'PERMISSION_AUTHORITY',
        'subject': 'vrae-operator-permission', 'revoked': False}}
    intent = check_submission(submitted, resolved['plan'], resolved['actor']['invitation'],
        resolved['actor'], verification)
    accepted = store.invoke(app, 'admit', tenant, cookie, csrf, intent, canonical(submitted).decode())
    ref, job = accepted['audit_ref'], accepted['job_id']
    with current(app, cookie, csrf, ref) as (code, result):
        assert code == 202 and result['state'] == 'CAPTURE_PENDING'
    with pytest.raises(psycopg.Error):
        with current(app, *sessions[1], ref):
            pytest.fail('CROSS_SUBJECT_READ')

    dense_links = b''.join(f'<a href="/products/item-{i:03d}">Item</a>'.encode() for i in range(154))
    routes = {'https://supplier.example.com/robots.txt': (200, {'content-type': 'text/plain'},
        b'User-agent: *\nDisallow: /forbidden\n'),
        body['url']: (200, {'content-type': 'text/html'},
        b'<html><head><title>Industrial supplier</title><link rel="canonical" href="https://supplier.example.com/"/><meta name="description" content="Export equipment"/></head><body><h1>Export equipment</h1>'
        b'<a href="/products">Products</a><a href="/contact">Contact</a><a href="/about.html">About</a><a href="/applications">Applications</a>'
        b'<a href="/login">Login</a><a href="/forbidden">Forbidden</a>' + dense_links + b'</body></html>'),
        'https://supplier.example.com/products': (200, {'content-type': 'text/html'},
        b'<html><head><title>Product information</title></head><body><h1>Equipment catalog</h1>' + dense_links + b'</body></html>'),
        'https://supplier.example.com/products/item-000': (200, {'content-type': 'text/html'},
        b'<html><head><script>window.fixture=true;</script></head><body><main>'
        b'<h1><span>Grinding wheel W100</span></h1><p>A bounded source description for industrial abrasive buyer review.</p>'
        b'<a href="/contact">Request information</a></main></body></html>'),
        'https://supplier.example.com/contact': (200, {'content-type': 'text/html'},
        b'<html><head><title>Contact supplier</title></head><body><h1>Contact</h1></body></html>'),
        'https://supplier.example.com/about.html': (200, {'content-type': 'text/html'},
        b'<html><body><h1>About this synthetic supplier</h1></body></html>'),
        'https://supplier.example.com/applications': (200, {'content-type': 'text/html'},
        b'<html><body><h1>Source applications</h1></body></html>')}
    delay = float(os.environ.get('VRAE_AUTOMATIC_CAPTURE_DELAY', '0'))
    assert delay in (0, 2), 'SYNTHETIC_DELAY_ONLY'

    class SlowTransport(SyntheticTransport):
        async def exchange(self, url, method, ip, budget, max_bytes):
            if delay and not url.endswith('/robots.txt'):
                await asyncio.sleep(delay)
            return await super().exchange(url, method, ip, budget, max_bytes)

    transport = SlowTransport(routes)
    def capture(audit, policy_provider, plan, run_id, workload, current):
        access = CurrentAccess(SourceAccess(audit, policy_provider, terms_reference=plan['terms_reference']),
            TaskPins(tenant, audit['request_id'], run_id, plan['policy']['policy_id'], 1,
                fingerprint(plan['policy'])), OfflinePermit(plan['origin'], tuple(plan['exact_paths']),
                datetime.fromisoformat(plan['policy']['created_at']), min(
                    datetime.fromisoformat(plan['expires_at']), datetime.fromisoformat(workload['deadline'])), True),
            current, plan)
        for forbidden in ('https://other.example.com/', plan['origin'] + '/login',
                          plan['origin'] + '/api/delete', plan['origin'] + '/?token=private'):
            with pytest.raises(Exception):
                access.check(forbidden)
        limits = {**plan['limits'], 'task_seconds': min(plan['limits']['task_seconds'], workload['task_seconds'])}
        return asyncio.run(Collector(SafeFetcher(FixedDNS(), transport)).capture(run_id,
            access, limits=Limits(**limits), retain_raw_html=True, representative_pages=True))
    monkeypatch.setattr(worker, 'capture', capture)
    port = store.WorkerPort(bindings['worker'])
    try:
        outcome = worker.run(bindings['worker'], {'kind': 'AUTHORIZED_EGRESS_V2'}, port)
        assert outcome.get('artifact_sha256'), outcome
        # A retry while the original lease is still alive returns the same body.
        assert intake.automatic_submission(app, actor, body, cookie, csrf) == submitted
        assert store.invoke(app, 'admit', tenant, cookie, csrf, intent, canonical(submitted).decode()) == accepted
    finally:
        port.close()
    assert all('/login' not in url and '/forbidden' not in url for url, _, _ in transport.calls)
    with current(app, cookie, csrf, ref) as (code, result):
        assert code == 202 and result['state'] == 'AI_PENDING' and result['evidence']
        assert result['customer_presentation']['rules_available']
        assert len(result['customer_presentation']['tasks']) == 5
        assert result['customer_presentation']['artifact_sha256'] == result['artifact_sha256']
        assert result['deterministic_diagnosis']['diagnostic_version'] == 'l2-industrial-1.0.6'
        assert result['customer_presentation']['procurement_review']['products']
        assert result['buyer_review']['state'] == 'AVAILABLE'
        assert result['customer_presentation']['buyer_review'] == result['buyer_review']
        assert len(result['buyer_review']['tasks']) == 5
        if delay:
            assert 3 <= result['capture_summary']['fetched_pages'] <= 6
            assert all(row['reason'] == 'TIMEOUT' for row in result['page_scope']['failed_attempt_records'])
        else:
            assert result['capture_summary']['fetched_pages'] == 6
            assert result['capture_summary']['http_requests_including_robots'] == 7
        assert result['capture_summary']['unvisited_candidates'] > 150
        assert len(result['page_scope']['visited_pages']) == result['capture_summary']['fetched_pages']
        if not delay:
            assert not result['page_scope']['failed_attempt_records']
        assert len(result['page_scope']['unvisited_candidates']) > 150
        assert all(not row['is_defect'] for row in result['page_scope']['unvisited_candidates'])
        pending_facts = deepcopy(result['deterministic_diagnosis'])
        assert [t['task'] for t in pending_facts['buyer_tasks']] == list(TASKS)
        rows = [o for t in pending_facts['buyer_tasks'] for r in t['rules'] for o in r['observations']]
        assert any(o['observation']['result'] == 'PASS' and o.get('citations') for o in rows)
        assert any(o['observation']['result'] == 'UNKNOWN' and o['reason'] for o in rows)
    # Wait for the original 30s lease to end; never rewrite completion timestamps.
    time.sleep(31)
    selected = adapter(bindings['ai'], job, {})
    request_result = execute(bindings['ai'], job, selected, operation_id='preflight-' + job)
    assert request_result['reason'] == 'PROVIDER_GO_NOT_GRANTED', request_result
    assert request_result['provider_attempts'] == request_result['real_model_calls'] == 0
    with current(app, cookie, csrf, ref) as (code, dto):
        # The existing read port selects the canonical service-ai operation;
        # this separate preflight does not replace that immutable receipt.
        assert dto['analysis_outcome'] == 'PENDING'
    c = selected._session.context
    assert c.completion.response_language == 'zh'
    assert any(e['fact']['rule_id'] == 'INFO-01' for e in c.catalog['entries'].values())
    assert any(e['fact']['observation_result'] == 'UNKNOWN' for e in c.catalog['entries'].values())
    anchor, entry = next((ref, entry) for ref, entry in c.catalog['entries'].items()
                         if entry['type'] == 'GUARD_LITERAL')
    content = {'prompt_version': CONTEXT_PROMPT, 'context_ref': c.context_ref, 'claims': [{
        'task': RULE_TASK[entry['fact']['rule_id']], 'refs': [anchor], 'counter_refs': [],
        'explanation': 'A buyer may need clearer navigation based on the saved page.',
        'uncertainties': ['Only bounded static pages were checked.'],
        'questions': ['Which page should a buyer read first?'],
        'rebuild': ['Group the saved page information by buyer task.']}]}
    content['claims'][0]['verification'] = 'Check the revised page organization against the same cited source.'
    fake = FakeTransport({'id': 'synthetic-only', 'object': 'chat.completion', 'model': 'qwen4-max', 'choices': [{
        'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': canonical(content).decode()}}],
        'usage': {'prompt_tokens': 137, 'completion_tokens': 83, 'total_tokens': 220}})
    expiry = datetime.now(UTC) + timedelta(minutes=5)
    selected._provider = QwenProvider(Config('synthetic-workspace'),
        Quota(tmp_path / 'FAKE-shared-quota.sqlite', create=True),
        permission=Permission('SYNTHETIC_PG_ONLY', expiry, 3, 1000000),
        price=Price('SYNTHETIC_PRICE_ONLY', MODEL_SOURCE, 1000000, 2000000, expiry),
        key='synthetic-key-no-real-secret', _transport=fake)
    # No native model I/O is possible in this network-none namespace.
    result = execute(bindings['ai'], job, selected, operation_id='service-ai-' + job)
    assert result['state'] == 'AI_CANDIDATES_FOR_HUMAN_REVIEW', result
    assert result['pg_receipt_status'] == 'RECORDED' and result['real_model_calls'] == 0
    assert result['usage']['prompt_version'] == CONTEXT_PROMPT
    assert result['claims'][0]['verification_status'] == 'PROPOSED_NOT_EXECUTED'
    sent = fake.bodies[0]
    assert 'Use concise Simplified Chinese:' in sent['messages'][0]['content']
    assert json.loads(sent['messages'][1]['content'])['response_language'] == 'zh'
    with current(app, cookie, csrf, ref) as (code, dto):
        assert code == 200 and not dto['claims']
        assert dto['state'] == 'AI_UNAVAILABLE' and not dto['diagnosis_complete']
        assert dto['buyer_tasks'] == list(TASKS)
        assert dto['deterministic_diagnosis'] and dto['evidence']
        assert dto['deterministic_diagnosis'] == pending_facts
        assert 'objects_base64' not in dto and not dto['formal_human_review']
    # Unit-check the supplier-success DTO shape using explicitly synthetic
    # receipt metadata. This is not evidence of a real supplier call.
    with store.connect(app) as connection:
        value = connection.execute('SELECT target_v1.automatic_diagnosis(%s,%s,%s,%s)',
            (tenant, cookie, csrf, ref)).fetchone()[0]
    synthetic = deepcopy(value)
    schema = openapi()['components']['schemas']['AutomaticDiagnosis']
    Draft202012Validator.check_schema(schema)
    for reason, stage, attempts, expected in (
            ('INSUFFICIENT_GUARDED_EVIDENCE', 'CONTEXT', 0, 'INSUFFICIENT_EVIDENCE'),
            ('PROVIDER_GO_NOT_GRANTED', 'PREFLIGHT', 0, 'NOT_DISPATCHED'),
            ('SYNTHETIC_PROVIDER_FAILURE', 'PROVIDER', 1, 'PROVIDER_FAILED'),
            ('SYNTHETIC_VALIDATION_REJECTION', 'VALIDATION', 1, 'VALIDATION_REJECTED')):
        failed = deepcopy(value)
        failed['receipt'].update(state='AI_UNAVAILABLE', reason=reason, failure_stage=stage,
                                 provider_attempts=attempts, claims=[])
        code, report = project(failed, ref)
        assert code == 200 and report['analysis_outcome'] == expected
        assert report['deterministic_diagnosis'] == pending_facts
        assert report['capture_summary']['fetched_pages'] == len(report['page_scope']['visited_pages'])
        assert report['model']['failure_stage'] == stage
        assert not report['diagnosis_complete'] and not report['claims']
        Draft202012Validator(schema).validate(report)
    synthetic['receipt'].update(verification_realm='REAL_PROVIDER', real_model_calls=1)
    synthetic['receipt']['usage']['usage_origin'] = 'PROVIDER_REPORTED'
    code, dto = project(synthetic, ref)
    assert code == 200 and dto['diagnosis_complete'] and dto['state'] == 'DIAGNOSED'
    assert dto['analysis_outcome'] == 'COMPLETED'
    assert dto['deterministic_diagnosis'] == pending_facts
    assert dto['claims'][0]['source_bindings'] and dto['claims'][0]['rebuild']
    synthetic['receipt']['artifact_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='SAME_COMMITTED_AI_BINDING_REQUIRED'):
        project(synthetic, ref)
    with admin() as c:
        c.execute('UPDATE target_v1.authorizations SET revoked=true WHERE tenant_id=%s', (tenant,))
    with pytest.raises(psycopg.Error):
        with current(app, cookie, csrf, ref):
            pytest.fail('WITHDRAWN_SOURCE_READ')
    # Fresh sessions can be created after an old one expires, but never reopen
    # another session's existing task or bypass actor revocation.
    with admin() as c:
        c.execute('UPDATE target_v1.sessions SET expires_at=clock_timestamp()-interval \'1 second\' WHERE cookie_sha256=%s', (cookie,))
    fresh_cookie, fresh_csrf = token_hash('later-cookie'), token_hash('later-csrf')
    store.invoke(app, 'automatic_session', tenant, fresh_cookie, fresh_csrf)
    with pytest.raises(psycopg.Error):
        with current(app, fresh_cookie, fresh_csrf, ref):
            pytest.fail('NEW_SESSION_CANNOT_REOPEN_OLD_TASK')
    fresh = store.invoke(app, 'session', tenant, fresh_cookie, fresh_csrf)
    with admin() as c:
        c.execute("""INSERT INTO target_v1.sessions
          SELECT %s,encode(sha256(('capacity-cookie-'||n::text)::bytea),'hex'),
           encode(sha256(('capacity-csrf-'||n::text)::bytea),'hex'),%s,%s,
           clock_timestamp()+interval '5 minutes',false FROM generate_series(1,1000) n""",
          (tenant, fresh['subject_ref'], fresh['invitation_ref']))
    with pytest.raises(psycopg.Error) as limited:
        store.invoke(app, 'automatic_session', tenant, token_hash('limited-cookie'), token_hash('limited-csrf'))
    assert limited.value.sqlstate == '53000'
    with admin() as c:
        c.execute('UPDATE target_v1.actors SET active=false WHERE db_role=%s', (app['role'],))
    with pytest.raises((psycopg.Error, Refused)):
        store.invoke(app, 'automatic_session', tenant, token_hash('revoked-cookie'), token_hash('revoked-csrf'))

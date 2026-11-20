"""Disposable actual PG vertical. No external website/provider or retained ledger.

Run only in a fresh network-none PG namespace with VRAE_AUTOMATIC_PG_TEST=1.
"""
import asyncio
from copy import deepcopy
from datetime import datetime, UTC, timedelta
import os
from pathlib import Path
import secrets
import time

import psycopg
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import pytest

from contracts.l2_launch.contract import canonical
from infra.windows_service import intake
from integration.authorized_targets import store, worker, source_authority
from integration.authorized_targets.authority import token_hash, check_submission
from integration.authorized_targets.automatic_result import current, project
from integration.authorized_targets.provision import install
from infra.linux_service.ai_loop import adapter
from integration.qwen_provider.committed import execute
from vrae.intelligence.qwen import Config, Permission, Price, QwenProvider, Quota
from vrae.intelligence.qwen.provider import MODEL_SOURCE, PROMPT
from vrae.intelligence.qwen.testing import FakeTransport
from vrae.intelligence.qwen.session import RULE_TASK
from integration.authorized_targets.automatic_result import TASKS
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
            'infra/authorized_targets/006_automatic_diagnosis.sql'):
            c.execute(Path(path).read_text())
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
        'source_class': 'CONTROLLED_NON_CUSTOMER', 'expires_at': end})
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
    cookie, csrf = sessions[0]
    actor = store.invoke(app, 'session', tenant, cookie, csrf)
    body = {'url': 'https://supplier.example.com/', 'authorized': True,
        'consent_version': intake.AUTO_CONSENT, 'idempotency_key': 'actual-pg-test-0001',
        'accepted_at': now.isoformat(), 'language': 'zh'}
    submitted = intake.automatic_submission(app, actor, body, cookie, csrf)
    resolved = store.invoke(app, 'plan', tenant, cookie, csrf, body['url'])
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

    routes = {'https://supplier.example.com/robots.txt': (200, {'content-type': 'text/plain'},
        b'User-agent: *\nDisallow: /forbidden\n'),
        body['url']: (200, {'content-type': 'text/html'},
        b'<html><head><title>Industrial supplier</title><link rel="canonical" href="https://supplier.example.com/"></head><body><h1>Export equipment</h1>'
        b'<a href="/products">Products</a><a href="/contact">Contact</a>'
        b'<a href="/login">Login</a><a href="/forbidden">Forbidden</a></body></html>'),
        'https://supplier.example.com/products': (200, {'content-type': 'text/html'},
        b'<html><head><title>Product information</title></head><body><h1>Equipment catalog</h1></body></html>'),
        'https://supplier.example.com/contact': (200, {'content-type': 'text/html'},
        b'<html><head><title>Contact supplier</title></head><body><h1>Contact</h1></body></html>')}
    transport = SyntheticTransport(routes)
    def capture(audit, policy_provider, plan, run_id, workload, current):
        access = CurrentAccess(SourceAccess(audit, policy_provider, terms_reference=plan['terms_reference']),
            TaskPins(tenant, audit['request_id'], run_id, plan['policy']['policy_id'], 1,
                fingerprint(plan['policy'])), OfflinePermit(plan['origin'], tuple(plan['exact_paths']),
                datetime.fromisoformat(plan['policy']['created_at']), datetime.fromisoformat(plan['expires_at']), True),
            current, plan)
        for forbidden in ('https://other.example.com/', plan['origin'] + '/login',
                          plan['origin'] + '/api/delete', plan['origin'] + '/?token=private'):
            with pytest.raises(Exception):
                access.check(forbidden)
        return asyncio.run(Collector(SafeFetcher(FixedDNS(), transport)).capture(run_id,
            access, limits=Limits(max_pages=4, interval_seconds=0.01), retain_raw_html=True))
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
    # Wait for the original 30s lease to end; never rewrite completion timestamps.
    time.sleep(31)
    selected = adapter(bindings['ai'], job, {})
    request_result = execute(bindings['ai'], job, selected, operation_id='preflight-' + job)
    assert request_result['reason'] == 'PROVIDER_GO_NOT_GRANTED', request_result
    c = selected._session.context
    anchor, entry = next((ref, entry) for ref, entry in c.catalog['entries'].items()
                         if entry['type'] == 'GUARD_LITERAL')
    content = {'prompt_version': PROMPT, 'context_ref': c.context_ref, 'claims': [{
        'task': RULE_TASK[entry['fact']['rule_id']], 'refs': [anchor], 'counter_refs': [],
        'explanation': 'A buyer may need clearer navigation based on the saved page.',
        'uncertainties': ['Only bounded static pages were checked.'],
        'questions': ['Which page should a buyer read first?'],
        'rebuild': ['Group the saved page information by buyer task.']}]}
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
    with current(app, cookie, csrf, ref) as (code, dto):
        assert code == 200 and not dto['claims']
        assert dto['state'] == 'AI_UNAVAILABLE' and not dto['diagnosis_complete']
        assert dto['buyer_tasks'] == list(TASKS)
        assert dto['deterministic_diagnosis'] and dto['evidence']
        assert 'objects_base64' not in dto and not dto['formal_human_review']
    # Unit-check the supplier-success DTO shape using explicitly synthetic
    # receipt metadata. This is not evidence of a real supplier call.
    with store.connect(app) as connection:
        value = connection.execute('SELECT target_v1.automatic_diagnosis(%s,%s,%s,%s)',
            (tenant, cookie, csrf, ref)).fetchone()[0]
    synthetic = deepcopy(value)
    synthetic['receipt'].update(verification_realm='REAL_PROVIDER', real_model_calls=1)
    synthetic['receipt']['usage']['usage_origin'] = 'PROVIDER_REPORTED'
    code, dto = project(synthetic, ref)
    assert code == 200 and dto['diagnosis_complete'] and dto['state'] == 'DIAGNOSED'
    assert dto['claims'][0]['source_bindings'] and dto['claims'][0]['rebuild']
    synthetic['receipt']['artifact_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='SAME_COMMITTED_AI_BINDING_REQUIRED'):
        project(synthetic, ref)
    with admin() as c:
        c.execute('UPDATE target_v1.authorizations SET revoked=true WHERE tenant_id=%s', (tenant,))
    with pytest.raises(psycopg.Error):
        with current(app, cookie, csrf, ref):
            pytest.fail('WITHDRAWN_SOURCE_READ')

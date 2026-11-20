"""Automatic intake/result boundaries; synthetic sources and fake provider only."""
import asyncio
from datetime import datetime, UTC
import json
import socket

import pytest

from infra.windows_service import intake
from integration.authorized_targets import automatic_result
from integration.s3_offline.fixture import context, NOW
from integration.qwen_provider.fixture import provider
from vrae.intelligence.s3 import prepare_context, Session
from vrae.intelligence.qwen.session import compact_input
from vrae.intelligence import ModelGateway


def body():
    return {'url': 'https://supplier.example.com/', 'authorized': True,
        'consent_version': intake.AUTO_CONSENT, 'idempotency_key': 'diagnosis-0001',
        'accepted_at': datetime.now(UTC).isoformat(), 'language': 'zh'}


@pytest.mark.parametrize('change', [{'authorized': False}, {'authorized': 1},
    {'consent_version': intake.CONSENT}, {'url': 'http://supplier.example.com/'},
    {'url': 'https://127.0.0.1/'}, {'url': 'https://supplier.example.com/?token=secret'},
    {'url': 'https://supplier.example.com/admin/../'}, {'idempotency_key': 'short'}])
def test_invalid_automatic_input_never_issues_or_calls_network(monkeypatch, change):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a: pytest.fail('DNS'))
    monkeypatch.setattr(intake, 'authorize', lambda *a: pytest.fail('ISSUED'))
    with pytest.raises(Exception):
        intake.automatic_submission({}, {}, {**body(), **change}, 'cookie', 'csrf')


def test_one_checkbox_creates_signed_source_then_original_submission(monkeypatch):
    calls = []
    b, actor = {'tenant_id': 'tenant-test'}, {'subject_ref': 'subject-one', 'invitation_ref': 'invite-one'}
    monkeypatch.setattr(intake, 'delegation', lambda: {'proof': intake.AUTO_PROOF})
    monkeypatch.setattr(intake, 'private', lambda _: b'test-only-hmac-material')
    monkeypatch.setattr(intake, 'authorize', lambda *a: calls.append('source'))
    monkeypatch.setattr(intake.store, 'invoke', lambda *a: None if a[1] == 'automatic_retry' else actor)
    def submit(binding, current, request, cookie, csrf):
        calls.append('submission')
        assert request['consent_version'] == intake.AUTO_CONSENT
        assert 'authorized' not in request and current == actor
        return {'original_signed_submission': True}
    monkeypatch.setattr(intake, 'signed_submission', submit)
    assert intake.automatic_submission(b, actor, body(), 'cookie', 'csrf')['original_signed_submission']
    assert calls == ['source', 'submission']


def test_old_dns_only_delegation_cannot_silently_enable_attestation(monkeypatch):
    monkeypatch.setattr(intake, 'delegation', lambda: {'proof': 'DNS_ONLY'})
    monkeypatch.setattr(intake.store, 'invoke', lambda *a: None)
    with pytest.raises(intake.Denied, match='AUTOMATIC_DIAGNOSIS_DELEGATION_REQUIRED'):
        intake.automatic_submission({'tenant_id': 'tenant-test'}, {}, body(), 'cookie', 'csrf')


def test_website_context_uses_original_guard_without_product_selection(tmp_path, monkeypatch):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a: pytest.fail('NETWORK'))
    original = context()
    c = prepare_context(original.pack, original.source, {}, buyer_pins=None,
        completion=original.completion, now=NOW)
    assert c.candidate['cards'] == []
    assert all(e['type'] == 'GUARD_LITERAL' for e in c.catalog['entries'].values())
    p = provider(tmp_path / 'FAKE-quota.sqlite', c)
    result = asyncio.run(Session(c, clock=lambda: NOW).run('automatic-test-only', mode='REAL_QWEN', provider=p))
    assert result['status'] == 'AI_CANDIDATES_FOR_HUMAN_REVIEW', result
    assert result['real_model_calls'] == 0
    assert result['verification_realm'] == 'PROTOCOL_FAKE_NOT_REAL_API'
    assert result['claims'][0]['source_bindings']
    preflight = asyncio.run(ModelGateway().run(c.pack, json.loads(c.execution_bytes),
        c.package, pins=c.gateway_pins, operation_id='automatic-preflight', recorded_at=NOW.isoformat()))
    data = compact_input(c, preflight['request']['provider_request'])
    assert data['selectable_tasks'] == sorted(data['required_anchor_by_task'])
    assert all(ref in c.catalog['entries'] for ref in data['required_anchor_by_task'].values())


def test_pending_failure_and_fake_cannot_be_real_diagnosis():
    value = {'status': {'run_id': 'run-test', 'state': 'PENDING'}, 'artifact': None, 'receipt': None}
    code, result = automatic_result.project(value, 'audit-test')
    assert code == 202 and not result['diagnosis_complete']
    value['status']['state'] = 'DEAD_LETTER'
    code, result = automatic_result.project(value, 'audit-test')
    assert code == 200 and result['state'] == 'CAPTURE_FAILED'
    assert not result['formal_human_review']

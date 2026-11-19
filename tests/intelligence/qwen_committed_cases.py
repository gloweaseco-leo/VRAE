"""Current-authority stub tests; actual PG proof lives in the controlled drill."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import hashlib
import socket

import pytest

from tests.intelligence.qwen_postcommit_cases import sample as sample
from integration.qwen_provider import committed
from integration.qwen_provider.fixture import provider, response
from integration.s3_offline.fixture import NOW
from tests.s2_contract.p1_industrial_cases import evaluate, pins, scope
from vrae.intelligence.common import encode
from vrae.intelligence.qwen.testing import FakeTransport
from vrae.intelligence.s3 import S3Error
from vrae.reporting.s2_candidate import BuyerCandidatePins, ObservationPin


@pytest.fixture(scope='module')
def selected(sample):
    c = sample[0]
    projection = evaluate(c.pack)
    rows = [next(r for r in projection['industrial_projection']['rows']
                 if r['model'] == 'P40' and r['observation']['rule_id'] == rule)
            for rule in ('INFO-02', 'TRUST-02')]
    buyer = BuyerCandidatePins(**scope(c.pack), pack_ref=c.pack.ref,
        projection_ref=projection['projection_ref'], projection_version='s2-projection-1.2.0',
        industry_pins=pins(c.pack), subject_model='P40',
        subject_snapshot_ref=next(s['snapshot_ref'] for s in c.pack.document['snapshots']
                                  if s['url'].endswith('/p40')),
        observations=tuple(ObservationPin(r['observation']['observation_id'],
            r['observation']['rule_id'], r['observation']['rule_version'], r['source_version'],
            tuple(sorted(p['snapshot_ref'] for p in r['source_pages']))) for r in rows))
    return projection, buyer


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail('Unexpected network access')
    monkeypatch.setattr(socket, 'getaddrinfo', denied)
    monkeypatch.setattr(socket, 'create_connection', denied)


@pytest.fixture
def bridge(sample, selected, monkeypatch):
    c, d, _, held = sample
    current = {'contract': 'vrae.committed-target-input.v1', 'purpose': 'POST_COMMIT_AI_INPUT',
        'task': deepcopy(d['task']), 'artifact': deepcopy(d), 'publication': 'UNPUBLISHED', 'grants_report_access': False,
        'commit': {'transaction_id': 42, 'artifact_sha256': held.artifact_sha256,
            'lease_started_at': c.completion.lease_started_at.isoformat(),
            'lease_expires_at': c.completion.lease_expires_at.isoformat(),
            'committed_at': c.completion.worker_completed_at.isoformat()},
        'source_plan': {'expires_at': (NOW + timedelta(minutes=5)).isoformat(),
                        'policy': {'expires_at': (NOW + timedelta(minutes=4)).isoformat()}}}
    state = {'revoked': False, 'reads': 0}

    def read(binding, job):
        state['reads'] += 1
        if state['revoked']:
            raise ValueError('private source authority withdrawn')
        return deepcopy(current)

    monkeypatch.setattr(committed, 'current_input', read)
    request = {**deepcopy(current), 'ai_operation_id': 'committed-unit-operation'}
    adapter = committed.Adapter({'tenant_id': d['task']['tenant_id']}, d['task']['job_id'],
        projection=selected[0], buyer_pins=selected[1], clock=lambda: NOW)
    return adapter, request, state, current


def test_default_go_missing_prepares_original_public_source_without_dispatch(bridge):
    adapter, request, state, _ = bridge
    out = adapter(request)
    assert out['reason'] == 'PROVIDER_GO_NOT_GRANTED' and out['real_model_calls'] == 0
    assert adapter._session.context.source.held.source_access_mode == 'PUBLIC_READONLY_CAPTURE'
    assert state['reads'] >= 2


def enable(adapter, request, tmp_path, fake=None):
    assert adapter(request)['reason'] == 'PROVIDER_GO_NOT_GRANTED'
    c = adapter._session.context
    adapter._provider = provider(tmp_path / 'fake.sqlite', c, fake=fake)
    return c


def test_original_session_candidate_usage_idempotency_and_hashes(bridge, tmp_path):
    adapter, request, _, current = bridge
    c = enable(adapter, request, tmp_path)
    before = c.source.read().document
    out = adapter(request)
    assert out['state'] == 'AI_CANDIDATES_FOR_HUMAN_REVIEW'
    assert out['usage']['usage_origin'] == 'PROTOCOL_FAKE_NOT_REAL_API'
    assert out['usage']['real_model_calls'] == 0
    assert out['operation_id'] == request['ai_operation_id']
    assert out['deterministic_report_hash'] == current['artifact']['version']['content_hash']
    assert adapter(request) == out and adapter._provider._transport.calls == 1
    assert c.source.read().document == before and not out['shareable']


@pytest.mark.parametrize('kind', ['schema', 'guard', 'usage', 'timeout'])
def test_usage_and_guard_failure_keep_deterministic_report(bridge, tmp_path, kind):
    adapter, request, _, current = bridge
    c = enable(adapter, request, tmp_path)
    reply = response(c)
    if kind == 'schema':
        reply['choices'][0]['message']['content'] = '{}'
    elif kind == 'guard':
        import json
        claims = json.loads(reply['choices'][0]['message']['content'])
        claims['claims'][0]['explanation'] = 'Certificate is authentic.'
        reply['choices'][0]['message']['content'] = json.dumps(claims)
    elif kind == 'usage':
        reply.pop('usage')
    adapter._provider._transport.response = reply
    if kind == 'timeout':
        adapter._provider._transport.timeout = True
        adapter._timeout = 5
    out = adapter(request)
    assert out['state'] == 'AI_UNAVAILABLE' and out['claims'] == []
    assert out['deterministic_report_hash'] == current['artifact']['version']['content_hash']
    assert (out['usage'] is not None) == (kind in ('schema', 'guard'))
    if kind in ('usage', 'timeout'):
        assert out['cost_status'] == 'UNKNOWN'


def test_revocation_after_dispatch_preserves_usage_and_refuses_cached_read(bridge, tmp_path, monkeypatch):
    adapter, request, state, _ = bridge
    enable(adapter, request, tmp_path)
    original = FakeTransport.post

    async def revoke(self, *args):
        result = await original(self, *args)
        state['revoked'] = True
        return result

    monkeypatch.setattr(FakeTransport, 'post', revoke)
    out = adapter(request)
    assert out['state'] == 'AI_UNAVAILABLE' and out['claims'] == []
    assert out['usage'] is not None and out['cost_status'] == 'ESTIMATED'
    with pytest.raises(S3Error, match='CURRENT_COMMITTED_AUTHORITY_DENIED'):
        adapter._session.context.completion.check(adapter._session.context.source, NOW)
    assert adapter._provider._transport.calls == 1


@pytest.mark.parametrize('change', ['purpose', 'job', 'tenant', 'hash', 'transaction_bool',
    'transaction_zero', 'active_lease', 'bad_completion', 'expiry', 'report', 'operation', 'source_mode'])
def test_current_input_and_timing_forgeries_do_not_create_context(bridge, change):
    adapter, request, _, current = bridge
    if change == 'purpose':
        current['purpose'] = 'HUMAN_REVIEW_INPUT'
    elif change in ('job', 'tenant'):
        current['task'][change + '_id'] = 'private-foreign'
    elif change == 'hash':
        current['commit']['artifact_sha256'] = '0' * 64
    elif change.startswith('transaction'):
        current['commit']['transaction_id'] = True if change.endswith('bool') else 0
    elif change == 'active_lease':
        current['commit']['lease_expires_at'] = (NOW + timedelta(seconds=1)).isoformat()
        current['commit']['lease_started_at'] = (NOW - timedelta(seconds=29)).isoformat()
    elif change == 'bad_completion':
        current['commit']['committed_at'] = (NOW + timedelta(seconds=2)).isoformat()
    elif change == 'expiry':
        current['source_plan']['expires_at'] = NOW.isoformat()
    elif change == 'report':
        current['artifact']['native_document']['semantic_approval'] = 0
        current['commit']['artifact_sha256'] = hashlib.sha256(encode(current['artifact'])).hexdigest()
    elif change == 'source_mode':
        current['artifact']['native_document']['native_context']['source_access_mode'] = 'OFFLINE_SYNTHETIC'
        current['commit']['artifact_sha256'] = hashlib.sha256(encode(current['artifact'])).hexdigest()
    request = {**deepcopy(current), 'ai_operation_id': '' if change == 'operation' else request['ai_operation_id']}
    out = adapter(request)
    assert out['state'] == 'AI_UNAVAILABLE' and out['claims'] == []
    assert adapter._session is None


def test_original_offline_completion_gate_remains_strict(sample):
    c = sample[0]
    with pytest.raises(S3Error, match='POST_COMMIT_BINDING_INVALID'):
        replace(c.completion, task=sample[3].task).check(c.source, NOW)


def test_concurrent_invocation_cannot_share_session_between_event_loops(bridge):
    adapter, request, _, _ = bridge
    adapter._lock.acquire()
    try:
        out = adapter(request)
        assert out['reason'] == 'OPERATION_IN_FLIGHT' and out['usage'] is None
        assert out['cost_status'] == 'UNKNOWN' and adapter._session is None
    finally:
        adapter._lock.release()


@pytest.mark.parametrize('stage', ['before_adapter', 'after_adapter', 'receipt_write'])
def test_original_pg_port_failure_never_returns_candidates_or_refunds_usage(bridge, tmp_path, monkeypatch, stage):
    from integration.authorized_targets import postcommit
    adapter, request, _, _ = bridge
    enable(adapter, request, tmp_path)
    def fail(binding, job, invoke, *, operation_id):
        if stage != 'before_adapter':
            assert invoke(request)['state'] == 'AI_CANDIDATES_FOR_HUMAN_REVIEW'
        raise TimeoutError('private DB detail must never escape')
    monkeypatch.setattr(postcommit, 'run', fail)
    out = committed.execute({}, 'unused', adapter, operation_id=request['ai_operation_id'])
    assert out['state'] == 'AI_UNAVAILABLE' and out['claims'] == []
    assert out['pg_receipt_status'] == 'UNKNOWN' and not out['grants_report_access']
    assert (out['usage'] is not None) == (stage != 'before_adapter')
    assert adapter._provider._transport.calls == (0 if stage == 'before_adapter' else 1)
    assert 'private DB' not in str(out)

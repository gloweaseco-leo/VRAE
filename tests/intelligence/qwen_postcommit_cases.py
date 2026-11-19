"""Offline PR162 input interoperability; synthetic bytes, no PG/current-authority claim."""
import base64
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import socket

import pytest

from integration.qwen_provider.postcommit import InputPins, replay_input, MAX_ARTIFACT, TASK_FIELDS
from integration.s3_offline.fixture import NOW, context
from vrae.industry.l2_v1 import diagnose
from vrae.intelligence.common import encode
from vrae.intelligence.qwen import QwenError
from vrae.intelligence.s3 import S3Error
from vrae.l2.native import NativeSource


@pytest.fixture(autouse=True)
def no_sockets(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail('Offline adapter attempted network access')
    monkeypatch.setattr(socket, 'socket', denied)
    monkeypatch.setattr(socket, 'getaddrinfo', denied)


@pytest.fixture(scope='module')
def sample():
    c = context()
    task = replace(c.completion.task, source_access_mode='PUBLIC_READONLY_CAPTURE')
    diagnosis = diagnose(c.pack, expected_pack_ref=task.native_pack_ref,
                         expected_industry_ref=task.industry_ref)
    source = NativeSource(c.pack, diagnosis, held=task)
    view = source.read()
    # Shape pinned to PR162 producer.py at 994c037; all data here is synthetic.
    d = {'task': {k: asdict(task)[k] for k in TASK_FIELDS}, 'pack': c.pack.document,
         'objects_base64': {k: base64.b64encode(v).decode() for k, v in c.pack.objects.items()},
         'diagnosis': diagnosis, 'native_document': view.document, 'version': view.version,
         'display_hash': view.display_hash, 'pack_ref': c.pack.ref,
         'diagnosis_ref': task.diagnosis_ref, 'source_bundle_sha256': task.source_bundle_sha256,
         'source_access_mode': 'L1', 'diagnostic_depth': 'L2', 'ai_state': 'NO_MODEL',
         'publication': 'UNPUBLISHED', 'authority': 'GENERATED_DRAFT_NOT_HUMAN_APPROVED',
         'external_release': False}
    raw = encode(d)
    pins = InputPins(task, hashlib.sha256(raw).hexdigest(), view.version['content_hash'], view.display_hash)
    return c, d, raw, pins


def test_original_replay_keeps_task_mode_report_and_objects(sample):
    _, d, raw, pins = sample
    pack, source = replay_input(raw, pins=pins)
    assert pack.ref == pins.task.native_pack_ref
    assert source.held == pins.task
    assert source.read().document == d['native_document']
    assert source.held.source_access_mode == 'PUBLIC_READONLY_CAPTURE'
    assert set(pack.objects) == set(d['objects_base64'])


def test_replay_is_not_s3_authorization_even_with_synthetic_completion_times(sample):
    c, _, raw, pins = sample
    _, source = replay_input(raw, pins=pins)
    completion = replace(c.completion, task=pins.task, report_content_hash=pins.report_content_hash)
    with pytest.raises(S3Error, match='^POST_COMMIT_BINDING_INVALID$'):
        completion.check(source, NOW)
    # Relabeling just the pins as synthetic cannot match the original held task.
    forged = replace(completion, task=replace(pins.task, source_access_mode='OFFLINE_SYNTHETIC'))
    with pytest.raises(S3Error, match='^POST_COMMIT_BINDING_INVALID$'):
        forged.check(source, NOW)


@pytest.mark.parametrize('field', list(TASK_FIELDS) + ['native_pack_ref', 'industry_ref',
    'diagnosis_ref', 'source_bundle_sha256', 'source_access_mode', 'created_at'])
def test_independent_task_pins_cannot_be_replaced_by_artifact(sample, field):
    _, _, raw, pins = sample
    bad = replace(pins, task=replace(pins.task, **{field: 'private-foreign-value'}))
    with pytest.raises(QwenError, match='^POST_COMMIT_INPUT_REPLAY_DENIED$'):
        replay_input(raw, pins=bad)


@pytest.mark.parametrize('field', ['artifact_sha256', 'report_content_hash', 'display_hash'])
def test_hash_pins_are_independent(sample, field):
    _, _, raw, pins = sample
    with pytest.raises(QwenError, match='^POST_COMMIT_INPUT_REPLAY_DENIED$'):
        replay_input(raw, pins=replace(pins, **{field: '0' * 64}))


@pytest.mark.parametrize('change', ['task', 'mode', 'depth', 'ai', 'release', 'authority',
    'pack', 'diagnosis', 'report', 'version', 'objects', 'base64', 'pack_ref',
    'diagnosis_ref', 'bundle', 'display', 'publication', 'extra'])
def test_even_matching_artifact_hash_does_not_bypass_original_replay(sample, change):
    _, original, _, pins = sample
    d = deepcopy(original)
    if change == 'task':
        d['task']['job_id'] = 'private-foreign-value'
    elif change == 'pack':
        d['pack']['run_id'] = 'private-foreign-value'
    elif change == 'diagnosis':
        d['diagnosis']['source_facts'] = []
    elif change == 'report':
        d['native_document']['semantic_approval'] = True
    elif change == 'version':
        d['version']['content_hash'] = '0' * 64
    elif change == 'extra':
        d['current_authority_verified'] = True
    elif change in ('objects', 'base64'):
        key = next(iter(d['objects_base64']))
        d['objects_base64'][key] = 'eA==' if change == 'objects' else '***invalid***'
    else:
        key, value = {'mode': ('source_access_mode', 'OFFLINE_SYNTHETIC'),
            'depth': ('diagnostic_depth', 'L1'), 'ai': ('ai_state', 'APPROVED'),
            'release': ('external_release', True), 'authority': ('authority', 'APPROVED'),
            'publication': ('publication', 'PUBLISHED'), 'pack_ref': ('pack_ref', 'ep-' + '0' * 64),
            'diagnosis_ref': ('diagnosis_ref', 'l2-' + '0' * 64),
            'bundle': ('source_bundle_sha256', '0' * 64), 'display': ('display_hash', '0' * 64)}[change]
        d[key] = value
    raw = encode(d)
    bad = replace(pins, artifact_sha256=hashlib.sha256(raw).hexdigest())
    with pytest.raises(QwenError, match='^POST_COMMIT_INPUT_REPLAY_DENIED$'):
        replay_input(raw, pins=bad)


@pytest.mark.parametrize('raw', [b'', b'{', b'[]', b'{"task":null,"task":null}',
                                 b'{"task":NaN}', b'x' * (MAX_ARTIFACT + 1)])
def test_malformed_oversized_duplicate_and_nonfinite_input(sample, raw):
    pins = replace(sample[3], artifact_sha256=hashlib.sha256(raw).hexdigest())
    with pytest.raises(QwenError, match='^POST_COMMIT_INPUT_REPLAY_DENIED$'):
        replay_input(raw, pins=pins)

"""Real Ed25519 fee/source policy checks; no key, model dispatch or network."""
from copy import deepcopy
from datetime import timedelta
import socket

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from contracts.l2_launch.contract import canonical
from integration.authorized_targets import source_authority
from integration.s3_offline.fixture import NOW
from infra.linux_service import qwen_runtime as runtime
from vrae.intelligence.qwen import Permission, QwenError
from vrae.intelligence.qwen.provider import MODEL_SOURCE

SHA = '1' * 40


@pytest.fixture
def signed(monkeypatch):
    key = Ed25519PrivateKey.generate()
    registry = {'keys': {'operator': {'public': key.public_key().public_bytes(Encoding.Raw,
        PublicFormat.Raw).hex(), 'role': 'DEPLOYMENT_OWNER',
        'source_class': 'CONTROLLED_NON_CUSTOMER', 'revoked': False}}}
    monkeypatch.setattr(source_authority, 'root_document', lambda _: registry)
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: pytest.fail('UNEXPECTED_DNS'))
    document = {'contract': 'vrae.qwen-runtime-allowance.v1', 'source_sha': SHA,
        'source_class': 'CONTROLLED_NON_CUSTOMER', 'model_fee_go': 'GRANTED',
        'region': 'cn-beijing', 'model': 'qwen4-max', 'workspace_id': 'synthetic-workspace',
        'data_scope': runtime.DATA_SCOPE, 'max_output_tokens': 2048,
        'max_dispatches_per_task': 1, 'automatic_retry': False, 'daily_cap_micros': 5_000_000,
        'approval_ref': 'TEST_ONLY_NOT_LIVE_GO', 'authorization_hashes': ['a' * 64],
        'not_before': (NOW - timedelta(minutes=1)).isoformat(),
        'expires_at': (NOW + timedelta(hours=1)).isoformat(), 'price_source': MODEL_SOURCE,
        'input_micros_per_million': 10_000_000, 'output_micros_per_million': 30_000_000}
    def sign(doc):
        return {'key_id': 'operator', 'document': doc, 'signature': key.sign(canonical(doc)).hex()}
    return document, sign, registry


def test_valid_operator_allowance_is_exact_model_bounded_and_minimized(signed):
    d, sign, _ = signed
    assert runtime.validate(sign(d), source_sha=SHA, source_class=d['source_class'], now=NOW) == d


@pytest.mark.parametrize('field,value', [
    ('model_fee_go', 'NOT_GRANTED'), ('model', 'qwen3.7-plus'), ('region', 'other'),
    ('source_sha', '2' * 40), ('data_scope', 'RAW_HTML'), ('max_output_tokens', 2049),
    ('max_dispatches_per_task', 2), ('max_dispatches_per_task', True), ('automatic_retry', True),
    ('daily_cap_micros', True), ('daily_cap_micros', 0), ('authorization_hashes', []),
    ('authorization_hashes', ['z' * 64]), ('input_micros_per_million', 1),
    ('output_micros_per_million', 1), ('price_source', 'unverified'),
    ('expires_at', NOW.isoformat())])
def test_even_a_signed_invalid_allowance_never_grants_model_access(signed, field, value):
    original, sign, _ = signed
    d = {**deepcopy(original), field: value}
    with pytest.raises((ValueError, PermissionError)):
        runtime.validate(sign(d), source_sha=SHA, source_class=original['source_class'], now=NOW)


def test_tampered_or_revoked_operator_signature_is_not_permission(signed):
    d, sign, registry = signed
    envelope = sign(d)
    envelope['document'] = {**d, 'daily_cap_micros': 99_000_000}
    with pytest.raises(PermissionError):
        runtime.validate(envelope, source_sha=SHA, source_class=d['source_class'], now=NOW)
    registry['keys']['operator']['revoked'] = True
    with pytest.raises(PermissionError):
        runtime.validate(sign(d), source_sha=SHA, source_class=d['source_class'], now=NOW)


def test_legacy_permission_cannot_claim_customer_data_without_root_runtime_allowance():
    p = Permission('TEST_ONLY', NOW + timedelta(hours=1), 1, 1_000_000, synthetic_only=False)
    with pytest.raises(QwenError, match='OWNER_PERMISSION_REQUIRED'):
        p.check(NOW)

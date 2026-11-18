"""Synthetic independent receiver protocol over the existing Brief service."""
from dataclasses import replace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from vrae.l2_ops.briefs import BriefService
from vrae.l2_ops.intake import SyntheticIntake, SyntheticReceiver
from vrae.l2_ops.sources import OperationsDenied
from vrae.reviewing.canonical import canonical


class MemoryTestLedger:
    def put(self, doc, **kwargs):
        self.doc = doc

    def get(self, tenant, ref):
        assert self.doc['pins']['tenant_id'] == tenant and self.doc['brief_ref'] == ref
        return self.doc


def setup(reader, bundle, ledger=None):
    service = BriefService(reader)
    ledger = ledger or MemoryTestLedger()
    doc = service.prepare(bundle, brief_ref='synthetic-s4')
    service.save_current(ledger, doc)
    key = Ed25519PrivateKey.generate()
    adapter = SyntheticIntake(SyntheticReceiver(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)))
    return service, ledger, doc, key, adapter


def receipt(row, state):
    return {**{k: row[k] for k in ('scope_sha256', 'brief_sha256', 'attempt', 'nonce')}, 'state': state}


def test_independent_ack_idempotency_and_no_commercial_upgrade(reader, bundle):
    service, ledger, doc, key, adapter = setup(reader, bundle)
    row = adapter.transition(service, ledger, doc['brief_ref'], 'submit')
    assert row['state'] == 'WAITING_ACK'
    assert adapter.transition(service, ledger, doc['brief_ref'], 'submit') == row
    response = receipt(row, 'ACKNOWLEDGED')
    ack = adapter.receive(service, ledger, doc['brief_ref'], response, key.sign(canonical(response)))
    assert ack['state'] == 'ACKNOWLEDGED'
    assert adapter.receive(service, ledger, doc['brief_ref'], response, key.sign(canonical(response))) == ack
    assert not any(ack[k] for k in ('customer_approval', 'counts_as_e2', 'counts_as_e3', 'quote_allowed', 'external_delivery_allowed', 'material_authorization'))
    adapter.transition(service, ledger, doc['brief_ref'], 'revoke')
    with pytest.raises(OperationsDenied, match='REVOKED'):
        adapter.receive(service, ledger, doc['brief_ref'], response, key.sign(canonical(response)))


@pytest.mark.parametrize('state', ['REJECTED', 'RETRYABLE_FAILED'])
def test_return_retry_rejects_old_attempt_and_forged_ack(reader, bundle, state):
    service, ledger, doc, key, adapter = setup(reader, bundle)
    row = adapter.transition(service, ledger, doc['brief_ref'], 'submit')
    old = receipt(row, state)
    with pytest.raises(OperationsDenied, match='SIGNATURE'):
        adapter.receive(service, ledger, doc['brief_ref'], old, b'x'*64)
    adapter.receive(service, ledger, doc['brief_ref'], old, key.sign(canonical(old)))
    new = adapter.transition(service, ledger, doc['brief_ref'], 'retry')
    assert new['attempt'] == 2 and new['nonce'] != row['nonce']
    with pytest.raises(OperationsDenied, match='STALE_OR_CROSS_TASK'):
        adapter.receive(service, ledger, doc['brief_ref'], old, key.sign(canonical(old)))


@pytest.mark.parametrize('negative', ['revoked', 'version', 'cross_task'])
def test_current_brief_authority_is_required_on_every_read_and_ack(reader, bundle, negative):
    service, ledger, doc, key, adapter = setup(reader, bundle)
    row = adapter.transition(service, ledger, doc['brief_ref'], 'submit')
    if negative == 'revoked':
        reader.allowed = False
    elif negative == 'version':
        reader.value = replace(reader.value, review={**reader.value.review, 'receipt_ref': 'new-review'})
    else:
        reader.value = replace(reader.value, pins={**reader.value.pins, 'request_id': 'another-request'})
    response = receipt(row, 'ACKNOWLEDGED')
    with pytest.raises(OperationsDenied):
        adapter.current(service, ledger, doc['brief_ref'])
    with pytest.raises(OperationsDenied):
        adapter.receive(service, ledger, doc['brief_ref'], response, key.sign(canonical(response)))

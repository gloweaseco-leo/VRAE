"""Joint routing and private-control contracts, not the real Worker proof."""
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from integration.l2_executive.runtime_intake import consume
from integration.l2_ops.checks.test_intake import setup
from integration.l2_ops.checks.test_s2_acceptance_sources import ready
from integration.l2_ops.checks.test_native_tasks import runtime  # noqa: F401
from integration.l2_ops.checks.test_native_report import reviewed  # noqa: F401
from vrae.l2_ops.sources import OperationsDenied
from vrae.reviewing.canonical import canonical


def test_shared_business_routes_keep_S2_and_S4_without_replacement(runtime):  # noqa: F811
    app, manager, task, headers, rid, _ = ready(runtime)
    business = app.native_business
    assert rid in business.source_views and business.intake.receiver is None
    root = '/b5a/l2/r/'+rid
    for suffix in ('/source-tasks', '/source-tasks/buyer-cite/0', '/brief', '/brief/submit', '/brief/retry', '/brief/revoke'):
        assert business.route(root+suffix) == rid
    source = app.handle('GET', root+'/source-tasks', headers)
    assert source.response.status == 200 and source.response.body.count(b'data-key="buyer-task-card"') == 2
    assert app.native_tasks is manager and business.source_views[rid].binding.scope['run_id'] == task.run_id
    assert app.handle('GET', root+'/brief/submit', headers).response.status == 403


def private_command(tmp_path, doc, operation, **extra):
    body = {'request_id': 'a'*32, 'operation': operation, 'job_id': doc['pins']['job_id'],
            'report_id': doc['pins']['report_ref'], **extra}
    (tmp_path/'s4-intake-request.json').write_text(json.dumps(body), encoding='utf-8')


def manager(tmp_path, doc):
    return SimpleNamespace(root=tmp_path, active={'task': SimpleNamespace(job_id=doc['pins']['job_id']),
                                                'report_id': doc['pins']['report_ref']})


def test_private_current_receiver_does_not_need_browser_ACK_or_write_PG(reader, bundle, tmp_path):
    service, ledger, doc, key, adapter = setup(reader, bundle)
    adapter.receiver = None
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    m = manager(tmp_path, doc)
    private_command(tmp_path, doc, 'configure', public_key=public)
    consume(m, adapter, service, ledger, doc['brief_ref'])
    row = adapter.transition(service, ledger, doc['brief_ref'], 'submit')
    receipt = {**{k: row[k] for k in ('scope_sha256', 'brief_sha256', 'attempt', 'nonce')}, 'state': 'ACKNOWLEDGED'}
    private_command(tmp_path, doc, 'receive', receipt=receipt, signature=key.sign(canonical(receipt)).hex())
    consume(m, adapter, service, ledger, doc['brief_ref'])
    result = json.loads((tmp_path/'s4-intake-response.json').read_bytes())
    assert result['ok'] and result['row']['state'] == 'ACKNOWLEDGED'
    assert not result['row']['external_delivery_allowed'] and service.load_current(ledger, doc['brief_ref']) == doc
    assert not (tmp_path/'s4-intake-request.json').exists()
    assert not (tmp_path/'s4-intake-running.json').exists()


@pytest.mark.parametrize('negative', ['revoked', 'version', 'task', 'receiver_replacement'])
def test_private_control_does_not_replace_original_current_authority(reader, bundle, tmp_path, negative):
    service, ledger, doc, _, adapter = setup(reader, bundle)
    m = manager(tmp_path, doc)
    other = Ed25519PrivateKey.generate().public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    private_command(tmp_path, doc, 'configure', public_key=other)
    if negative == 'revoked':
        reader.allowed = False
    elif negative == 'version':
        reader.value = replace(reader.value, review={**reader.value.review, 'receipt_ref': 'changed-version-review'})
    elif negative == 'task':
        m.active['task'].job_id = 'another-current-task'
    with pytest.raises(OperationsDenied):
        consume(m, adapter, service, ledger, doc['brief_ref'])
    assert json.loads((tmp_path/'s4-intake-response.json').read_bytes())['ok'] is False

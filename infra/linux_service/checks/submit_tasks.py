"""Explicit controlled mTLS requests for AI-runtime acceptance, not a public client."""
import argparse
from copy import deepcopy
from datetime import datetime, UTC
import json
from pathlib import Path
import time
import uuid

from contracts.l2_launch.contract import canonical, permission_document
from contracts.l2_launch.vf_b import submission_document
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from integration.authorized_targets.checks import external_client as client
from integration.authorized_targets.checks.issuer import Issuer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--count', type=int, default=1)
    count = parser.parse_args().count
    assert 1 <= count <= 6
    state = json.loads(client.STATE.read_bytes())
    signer = Issuer('tenant-beta')
    signer.key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(client.CFG['permission_key']))
    requests = []
    for index in range(count):
        i = index % len(client.CFG['requests'])
        request, subject = client.CFG['requests'][i], state['subjects'][i]
        session = subject['session']
        code, frame, _ = client.call('GET', '/v1/source-plans/' + request['target_id'], session=session)
        assert code == 200, 'CURRENT_SIGNED_SOURCE_CONTEXT_REQUIRED'
        value = deepcopy(subject['submit'])
        value['subject_ref'] = frame['subject_ref']
        value['invitation_ref'] = frame['invitation_ref']
        uid = uuid.uuid4().hex
        value['command']['request'].update(request_id='model-request-' + uid,
            audit_id='model-audit-' + uid, idempotency_key='model-idem-' + uid,
            requested_at=datetime.now(UTC).isoformat())
        value['command']['permission_reference']['proof'] = signer.sign('permission', 'permission',
            permission_document(value['command'], frame['source_policy']))
        value['submission_proof'] = signer.sign('permission', 'permission', submission_document(value))
        code, accepted, _ = client.call('POST', '/v1/audit-requests', value, session)
        assert code == 202
        assert client.call('POST', '/v1/audit-requests', value, session)[1] == accepted
        end = time.monotonic() + 90
        while time.monotonic() < end:
            code, status, _ = client.call('GET', '/v1/audits/' + accepted['audit_ref'], session=session)
            assert code == 200
            if status['task']['status'] == 'DRAFT_READY':
                break
            time.sleep(.5)
        else:
            raise AssertionError('ORIGINAL_WORKER_COMMIT_NOT_OBSERVED')
        assert status['task']['run_id'] == accepted['run_id']
        requests.append({'accepted': accepted, 'deterministic_task_status': status['task']['status']})
    Path('/state/model-requests.json').write_bytes(canonical(requests))
    print(canonical({'phase': 'MODEL_RUNTIME_SIGNED_HTTPS_REQUESTS', 'requests': requests,
                     'http': client.events, 'customer_sources': 0}).decode())


if __name__ == '__main__':
    main()

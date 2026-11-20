"""Current same-subject automated analysis DTO over original committed artifacts."""
from contextlib import contextmanager
from copy import deepcopy

from contracts.l2_launch.contract import canonical
from integration.authorized_targets.store import connect
from integration.authorized_targets.source_authority import authorization
from integration.qwen_provider.postcommit import InputPins, replay_input
from vrae.l2.native import NativeTask

TASKS = ('DISCOVER', 'UNDERSTAND', 'TRUST', 'INQUIRE', 'SEARCH_TECHNICAL')


def project(value, audit_ref):
    status, artifact, receipt = value['status'], value['artifact'], value['receipt']
    result = {'contract': 'vrae.automatic-diagnosis.v1', 'audit_ref': audit_ref,
        'run_id': status['run_id'], 'task_state': status['state'],
        'state': 'CAPTURE_PENDING', 'diagnosis_complete': False,
        'formal_human_review': False, 'publication': 'UNPUBLISHED',
        'buyer_tasks': list(TASKS), 'deterministic_diagnosis': None,
        'claims': [], 'model': None, 'evidence': [], 'coverage': []}
    if status['state'] == 'DEAD_LETTER':
        result['state'] = 'CAPTURE_FAILED'
        return 200, result
    if status['state'] != 'DRAFT_READY':
        return 202, result
    if artifact is None:
        raise ValueError('COMMITTED_ARTIFACT_REQUIRED')
    auth = artifact['source_authority']
    authorization(auth['authorization'], value['plan'], plan_sha256=auth['plan_sha256'])
    pack, _ = replay_input(canonical(artifact), pins=InputPins(
        NativeTask(**artifact['native_document']['native_context']), value['artifact_sha256'],
        artifact['version']['content_hash'], artifact['display_hash']))
    result.update(state='AI_PENDING', pack_ref=pack.ref,
        artifact_sha256=value['artifact_sha256'],
        report_content_hash=artifact['version']['content_hash'],
        deterministic_diagnosis=deepcopy(artifact['diagnosis']),
        evidence=[{k: s[k] for k in ('snapshot_ref', 'url', 'status', 'observed_at')}
                  for s in pack.document['snapshots']],
        coverage=deepcopy(pack.document['coverage']))
    if receipt is None:
        return 202, result
    if (receipt['task'] != artifact['task']
            or receipt['artifact_sha256'] != value['artifact_sha256']
            or receipt['report_content_hash'] != artifact['version']['content_hash']
            or receipt['display_hash'] != artifact['display_hash']):
        raise ValueError('SAME_COMMITTED_AI_BINDING_REQUIRED')
    # Retain original Guard statuses; automatic delivery is not human approval.
    result['claims'] = deepcopy(receipt.get('claims', []))
    result['model'] = {k: deepcopy(receipt.get(k)) for k in (
        'model_constraint', 'state', 'reason', 'usage', 'real_model_calls', 'verification_realm')}
    genuine = (receipt['state'] == 'AI_CANDIDATES_FOR_HUMAN_REVIEW'
        and receipt.get('verification_realm') == 'REAL_PROVIDER'
        and receipt.get('real_model_calls') == 1 and bool(result['claims'])
        and (receipt.get('usage') or {}).get('usage_origin') == 'PROVIDER_REPORTED')
    result['state'] = 'DIAGNOSED' if genuine else 'AI_UNAVAILABLE'
    result['diagnosis_complete'] = genuine
    if not genuine:
        result['claims'] = []
    return 200, result


@contextmanager
def current(binding, cookie, csrf, audit_ref):
    with connect(binding) as c, c.transaction():
        def read():
            return c.execute('SELECT target_v1.automatic_diagnosis(%s,%s,%s,%s)',
                (binding['tenant_id'], cookie, csrf, audit_ref)).fetchone()[0]
        value = read()
        response = project(value, audit_ref)
        # Recheck current authorization after potentially expensive replay and
        # hold PG source/session/subject locks through actual response writing.
        if canonical(read()) != canonical(value):
            raise PermissionError('CURRENT_DIAGNOSIS_CHANGED')
        yield response

"""Current same-subject automated analysis DTO over original committed artifacts."""
from contextlib import contextmanager
from copy import deepcopy

from contracts.l2_launch.contract import canonical
from integration.authorized_targets.store import connect
from integration.authorized_targets.source_authority import authorization
from integration.qwen_provider.postcommit import InputPins, replay_input
from vrae.l2.native import NativeTask

TASKS = ('DISCOVER', 'UNDERSTAND', 'TRUST', 'INQUIRE', 'SEARCH_TECHNICAL')


def capture_summary(pack):
    manifests = [s['document'] for s in pack.document['sources'] if s['kind'] == 'CaptureManifest']
    pages = [p for m in manifests for p in m['pages']]
    candidates = {i['url'] for m in manifests for i in m['inventory']}
    recorded = {p['snapshot']['url'] for p in pages}
    return {'candidate_urls': len(candidates), 'page_records': len(pages),
        'fetched_pages': sum(p['snapshot']['status'] == 'FETCHED' for p in pages),
        'unvisited_candidates': len(candidates - recorded),
        'http_requests_including_robots': sum(m['requests'] for m in manifests),
        'timeout_page_records': sum((p['error'] or {}).get('code') == 'TIMEOUT' for p in pages),
        'inventory_truncated': any(m['coverage']['inventory_truncated'] for m in manifests),
        'unvisited_is_defect': False}


def analysis_outcome(receipt, genuine):
    if genuine:
        return 'COMPLETED'
    if receipt.get('reason') == 'INSUFFICIENT_GUARDED_EVIDENCE':
        return 'INSUFFICIENT_EVIDENCE'
    if receipt.get('provider_attempts') == 0:
        return 'NOT_DISPATCHED'
    if receipt.get('failure_stage') == 'VALIDATION':
        return 'VALIDATION_REJECTED'
    if receipt.get('failure_stage') == 'PROVIDER':
        return 'PROVIDER_FAILED'
    # Legacy null counts, quota errors and protocol fakes stay uncertain.
    return 'UNAVAILABLE'


def project(value, audit_ref):
    status, artifact, receipt = value['status'], value['artifact'], value['receipt']
    result = {'contract': 'vrae.automatic-diagnosis.v1', 'audit_ref': audit_ref,
        'run_id': status['run_id'], 'task_state': status['state'],
        'state': 'CAPTURE_PENDING', 'diagnosis_complete': False,
        'formal_human_review': False, 'publication': 'UNPUBLISHED',
        'buyer_tasks': list(TASKS), 'deterministic_diagnosis': None,
        'claims': [], 'model': None, 'evidence': [], 'coverage': [],
        'capture_summary': None, 'analysis_outcome': 'PENDING'}
    if status['state'] == 'DEAD_LETTER':
        result['state'] = 'CAPTURE_FAILED'
        result['analysis_outcome'] = 'NOT_RUN'
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
        capture_summary=capture_summary(pack),
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
        'model_constraint', 'state', 'reason', 'usage', 'real_model_calls', 'verification_realm',
        'provider_attempts', 'cost_status', 'failure_stage')}
    genuine = (receipt['state'] == 'AI_CANDIDATES_FOR_HUMAN_REVIEW'
        and receipt.get('verification_realm') == 'REAL_PROVIDER'
        and receipt.get('real_model_calls') == 1 and bool(result['claims'])
        and (receipt.get('usage') or {}).get('usage_origin') == 'PROVIDER_REPORTED')
    result['state'] = 'DIAGNOSED' if genuine else 'AI_UNAVAILABLE'
    result['diagnosis_complete'] = genuine
    result['analysis_outcome'] = analysis_outcome(receipt, genuine)
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

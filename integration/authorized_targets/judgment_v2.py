"""vrae.diagnosis-judgment.v2. L-B failures stay pending review. L-C obstacles stay empty."""
from integration.authorized_targets.presentation import (
    FORBIDDEN_JUDGMENT_COPY, bilingual, observation_copy)

CONTRACT = 'vrae.diagnosis-judgment.v2'
STAGES = (
    ('SCREENING', 'DISCOVER'),
    ('COMPARISON', 'UNDERSTAND'),
    ('TECH_CONFIRMATION', 'TRUST'),
    ('INQUIRY', 'INQUIRE'),
    ('TECHNICAL_ACCESS', 'SEARCH_TECHNICAL'),
)
NOTE = '单次测量，含调度开销，不含 DNS。不是用户体验，也不是评分。渲染性能与移动端本次未测。'


def _guard(text):
    if any(phrase in text for phrase in FORBIDDEN_JUDGMENT_COPY):
        raise ValueError('JUDGMENT_COPY_FORBIDDEN')
    return text


def build(result):
    diagnosis = result.get('deterministic_diagnosis') or {}
    enabled = []
    pending = []
    seen = {}
    for task in diagnosis.get('buyer_tasks') or []:
        for rule in task.get('rules') or []:
            if rule.get('enabled') is False:
                continue
            enabled.append(rule.get('rule_id'))
            codes = set()
            for row in rule.get('observations') or []:
                observation = row.get('observation') or {}
                code = observation.get('result')
                codes.add(code)
                if code != 'FAIL_WITH_EVIDENCE':
                    continue
                pending.append({
                    'rule_id': rule.get('rule_id'), 'task': task.get('task'),
                    'result': 'FAIL_WITH_EVIDENCE', 'evidence_level': rule.get('evidence_level') or 'L-B',
                    'is_confirmed_defect': False, 'counts_as_score': False,
                    'text': bilingual(observation_copy(rule.get('rule_id'), row, buyer=True))})
            seen[rule.get('rule_id')] = codes
    unjudged = [{
        'rule_id': rule_id, 'is_defect': False,
        'text': _guard('这项启用规则这次没有通过或有证据的异常，不能当成缺陷。'),
    } for rule_id in enabled if not ({'PASS', 'FAIL_WITH_EVIDENCE'} & (seen.get(rule_id) or set()))]
    stages = []
    by_task = {task.get('task'): task for task in diagnosis.get('buyer_tasks') or []}
    for stage, task_name in STAGES:
        task = by_task.get(task_name) or {}
        counts = {}
        for rule in task.get('rules') or []:
            for row in rule.get('observations') or []:
                code = (row.get('observation') or {}).get('result')
                if code:
                    counts[code] = counts.get(code, 0) + 1
        stages.append({'stage': stage, 'task': task_name, 'counts': counts,
                       'unknown_is_defect': False, 'unvisited_is_defect': False})
    lead = _guard('这次预诊断不是正式报告，也没有经过人工审核。有证据的异常进入待审，不记为已确认障碍，也不是评分。')
    return {
        'contract': CONTRACT, 'is_report': False, 'formal_human_review': False,
        'lead': bilingual((lead, 'This pre-diagnosis is not a formal report and has no human review. Evidenced issues stay pending review and are not confirmed obstacles or a score.')),
        'confirmed_obstacles': {'items': [], 'count': 0, 'accepts': 'L-C',
                                'is_defect_score': False, 'confirmed_obstacle_count_is_score': False},
        'evidenced_pending_review': {'items': pending, 'count': len(pending), 'accepts': 'L-B',
                                     'is_confirmed_defect': False, 'is_defect_score': False},
        'unjudged': {'items': unjudged, 'is_defect': False, 'basis': 'ENABLED_RULES'},
        'stages': stages,
        'supplier_questions': {'items': [], 'presented_as_priority_fix': False, 'is_confirmed_defect': False},
        'sample_boundary': {'unvisited_is_defect': False},
    }


def technical_access(result):
    scope = result.get('page_scope') if isinstance(result.get('page_scope'), dict) else {}
    rows = []
    for page in (scope.get('visited_pages') or []) + (scope.get('failed_attempt_records') or []):
        if not isinstance(page, dict):
            continue
        rows.append({'http_status': page.get('http_status'), 'redirects_recorded': bool(page.get('redirects')),
                     'bytes': page.get('bytes'), 'first_byte_ms': page.get('first_byte_ms'),
                     'exchange_ms': page.get('exchange_ms')})
    return {'contract': 'vrae.technical-access-facts.v1', 'rows': rows, 'is_score': False,
            'includes_dns': False, 'is_user_experience': False, 'rendering_measured': False,
            'mobile_measured': False, 'note': NOTE}

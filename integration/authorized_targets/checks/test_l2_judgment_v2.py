"""Judgment v2 stays off the 1.0.7 customer presentation."""
import json

from integration.authorized_targets.judgment_v2 import build as judgment_v2
from integration.authorized_targets.presentation import build as present


def test_judgment_v2_keeps_confirmed_obstacles_empty_and_v1_copy():
    pending = {'rule_id': 'TECH-01', 'buyer_task': 'SEARCH_TECHNICAL', 'enabled': True, 'evidence_level': 'L-B',
               'observations': [{'observation': {'result': 'FAIL_WITH_EVIDENCE', 'observation_id': 'obs-tech'},
                                 'reason': 'CAPTURED_INTERNAL_LINK_404_OR_410'}]}
    unknown = {'rule_id': 'INFO-02', 'buyer_task': 'UNDERSTAND', 'enabled': True,
               'observations': [{'observation': {'result': 'UNKNOWN', 'observation_id': 'obs-info'},
                                 'reason': 'CHECKLIST_UNSIGNED_REVIEW_REQUIRED'}]}
    tasks = [{'task': name, 'rules': []} for name in
             ('DISCOVER', 'UNDERSTAND', 'TRUST', 'INQUIRE', 'SEARCH_TECHNICAL')]
    tasks[1]['rules'].append(unknown)
    tasks[4]['rules'].append(pending)
    review = {'contract': 'vrae.l2-procurement-review.v1'}
    result = {'deterministic_diagnosis': {'diagnostic_version': 'l2-industrial-1.0.8', 'buyer_tasks': tasks,
              'procurement_review': review},
              'claims': [], 'analysis_outcome': 'INSUFFICIENT_EVIDENCE', 'state': 'AI_UNAVAILABLE',
              'page_scope': {'visited_pages': [{'request_role': 'HOME', 'http_status': 200}],
                             'failed_attempt_records': [], 'unvisited_candidates': []}}
    view = present(result)
    judgment = view['judgment']
    assert judgment['contract'] == 'vrae.diagnosis-judgment.v2'
    assert judgment['confirmed_obstacles']['items'] == [] and judgment['confirmed_obstacles']['count'] == 0
    assert judgment['evidenced_pending_review']['items'][0]['result'] == 'FAIL_WITH_EVIDENCE'
    assert judgment['formal_human_review'] is False
    assert view['technical_access']['is_score'] is False and view['technical_access']['mobile_measured'] is False
    assert len(judgment['stages']) == 5
    previous = present({'deterministic_diagnosis': {'diagnostic_version': 'l2-industrial-1.0.7',
                       'buyer_tasks': tasks, 'procurement_review': review},
                       'claims': [], 'analysis_outcome': 'INSUFFICIENT_EVIDENCE', 'state': 'AI_UNAVAILABLE'})
    assert previous['judgment']['contract'] == 'vrae.diagnosis-judgment.v1'
    text = json.dumps(judgment_v2(result), ensure_ascii=False)
    assert '建议优先关注' not in text and '可以先这样改' not in text

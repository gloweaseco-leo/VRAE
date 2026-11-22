"""Read-only decision projection of the accepted report; no diagnostic authority.

Coverage counts retained assessments, not the unknown whole-site denominator.
Only retained HTTP 404/410 observations qualify for the narrow D1 presentation.
Native industrial comparison FAILs never qualify as website failures here.
"""
from .report import TASKS, encoded, sha

VERSION = 'l2-executive-1'
GROUPS = {'D1': '已证路径阻碍', 'D2': '资料组织改善', 'D3': '工程与资质待核',
          'D4': '买方待补输入', 'D5': '未观察与访问受限', 'D6': '商业影响假设'}


def project(view):
    d = view.document
    snapshots = {s['id']: s for s in d['snapshots']}
    evidence = {e['id']: e for e in d['evidence']}
    groups: dict[str, list[dict]] = {key: [] for key in GROUPS}
    known_normal = []
    for f in d['findings']:
        refs = f.get('evidence_ids', []) + f.get('context_evidence_ids', [])
        locations = [{'evidence_ref': ref, 'url': evidence[ref].get('url') or
                      snapshots[evidence[ref]['snapshot_id']]['url']} for ref in refs if ref in evidence]
        rule = f.get('native_rule_id')
        if rule in ('IND-DUTY', 'IND-FIT', 'IND-PROOF'):
            group = 'D3'
        elif rule == 'IND-RFQ' and f.get('native_details', {}).get('missing_buyer_inputs'):
            group = 'D4'
        elif f['kind'] == 'UNKNOWN' or f.get('native_result') == 'NOT_APPLICABLE':
            group = 'D5'
        elif not rule and f['kind'] == 'OBSERVATION' and any(
                snapshots[evidence[ref]['snapshot_id']].get('http_status') in (404, 410)
                for ref in refs if ref in evidence):
            group = 'D1'
        else:
            group = 'D2'
        item = {'id': f['id'], 'title': f['title'], 'task': f['task'], 'statement': f['statement'],
                'locations': locations, 'limited_source': f['scope'], 'uncertainty': f['uncertainty'],
                'counter_evidence': '未取得独立反证；不表示反证不存在。',
                'impact_status': 'HYPOTHESIS', 'impact': f['buyer_impact'],
                'recheck': f['recheck'], 'recommendation': f['recommendation']}
        groups[group].append(item)
        if f.get('native_result') == 'PASS':
            known_normal.append(f['id'])
        if f['buyer_impact']:
            groups['D6'].append(item)
    coverage = []
    tasks = [j['task'] for j in d['journey']] or list(TASKS)
    for task in tasks:
        rows = [f for f in d['findings'] if f['task'] == task]
        coverage.append({'task': task, 'label': next((j.get('label') or j['goal'] for j in d['journey'] if j['task'] == task), task), 'retained': len(rows),
                         'unknown': sum(f['kind'] == 'UNKNOWN' for f in rows),
                         'not_applicable': sum(f.get('native_result') == 'NOT_APPLICABLE' for f in rows),
                         'whole_site_denominator': None})
    core = {'version': VERSION, 'report_ref': d['meta']['report_id'],
            'report_version': view.version['report_version_id'], 'content_hash': view.version['content_hash'],
            'display_hash': view.display_hash, 'source_digest': view.source_digest,
            'source_mode': d['meta']['source_mode'], 'policy_ref': d['meta']['source_policy_ref'],
            'sources': [{'url': s['url'], 'observed_at': s['captured_at']} for s in d['snapshots']],
            'coverage': coverage, 'groups': groups, 'top_obstacles': groups['D1'][:3],
            'd1_count': len(groups['D1']), 'normal_refs': known_normal,
            'service_catalog_status': 'SERVICE_CATALOG_PENDING', 'service_catalog_version': None,
            'blueprint_count': len(d['blueprint']), 'limitations': d['limitations']}
    return {**core, 'summary_sha256': sha(encoded(core))}


VERSION_2 = 'l2-executive-2'
DEPTH = ('SCREENING', 'COMPARISON', 'TECH_CONFIRMATION', 'INQUIRY')


def _segment(stage, finding):
    statement = finding.get('statement') or '本次没有写成缺陷。'
    return {'stage': stage,
            'buyer_intent': '买家在这一阶段要核对已记录资料。',
            'seen': statement,
            'effect': '影响限于本次已访问页面，不推广到全站。',
            'suggested_change': '先核对该条已记录内容。',
            'enterprise_input': finding.get('enterprise_input') or '企业可补充对应资料；未补充不是网站缺陷。',
            'recheck': '用同一页面和同一证据重新核对。'}


def project_v2(document):
    """Depth summary for the new diagnostic path. l2-executive-1 stays unchanged."""
    findings = list(document.get('findings') or [])
    groups: dict[str, list] = {key: [] for key in GROUPS}
    for finding in findings:
        rule = finding.get('rule_id') or finding.get('native_rule_id')
        result = finding.get('result') or finding.get('native_result')
        if rule == 'TECH-01' and result == 'FAIL_WITH_EVIDENCE':
            group = 'D1'
        elif rule in ('DISC-01', 'DISC-02', 'CTA-02') and result == 'FAIL_WITH_EVIDENCE':
            group = 'D1'
        elif rule == 'INFO-02' and result == 'FAIL_WITH_EVIDENCE':
            group = 'D2'
        elif rule == 'TRUST-02' or finding.get('site_role') == 'CLARIFY_CHANNEL' or finding.get('reason') == 'CONFLICT_REVIEW_REQUIRED':
            group = 'D3'
        elif finding.get('enterprise_input'):
            group = 'D4'
        elif result in ('UNKNOWN', 'ACCESS_BLOCKED', 'NOT_APPLICABLE') or finding.get('unvisited'):
            group = 'D5'
        else:
            group = 'D6' if finding.get('commercial_hypothesis') else 'D5'
        groups[group].append({'id': finding.get('id'), 'rule_id': rule, 'result': result,
                              'is_score': False, 'quantified_loss': None})
    if not any(groups.values()):
        groups['D5'].append({'id': None, 'rule_id': None, 'result': 'UNKNOWN',
                             'is_score': False, 'note': '没有缺陷的报告仍然成立。'})
    depth = []
    for stage in DEPTH:
        rows = [finding for finding in findings if finding.get('stage') == stage] or [{'statement': '这一阶段没有已确认缺陷。'}]
        depth.append({'stage': stage, 'segments': [_segment(stage, row) for row in rows[:4]]})
    packages = []
    for item in document.get('blueprint') or []:
        packages.append({'stage': item.get('stage'), 'judgment': item.get('judgment'),
                         'evidence_ids': list(item.get('evidence_ids') or []),
                         'target_pages': list(item.get('target_pages') or []),
                         'action': item.get('action'), 'enterprise_input': item.get('enterprise_input'),
                         'owner': item.get('owner') or 'UNASSIGNED', 'depends_on': list(item.get('depends_on') or []),
                         'recheck': item.get('recheck'), 'candidate': item.get('candidate') or 'UNDECIDED',
                         'price': None, 'schedule': None})
    core = {'version': VERSION_2, 'groups': groups, 'depth': depth, 'blueprint': packages,
            'confirmed_obstacle_count': 0, 'quantified_loss': None, 'is_score': False,
            'empty_defect_report_valid': True}
    return {**core, 'summary_sha256': sha(encoded(core))}

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

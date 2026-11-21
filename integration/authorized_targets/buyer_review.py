"""Bounded read projection over a replayed artifact; no new native facts or IO."""
import logging

from vrae.collection.manifest import document_hash
from vrae.evidence import EvidenceError
from vrae.industry.l2_v1.pack import load_s2
from vrae.rules.s2 import IndustryPins, evaluate_s2

TASK_RULES = {
    'DISCOVER': ('DISC-03',), 'UNDERSTAND': ('INFO-02',),
    'TRUST': ('TRUST-02', 'TRUST-03'), 'INQUIRE': (),
    'SEARCH_TECHNICAL': ('SEO-02', 'TECH-01'),
}
CAP_PER_RULE = 16
PATH_CAP = 16
COPY = {
    'DISC-03': ('应用页到产品的静态路径', 'Static application-to-product route'),
    'INFO-02': ('技术资料的配置与来源上下文', 'Configured technical information and source context'),
    'TRUST-02': ('供方展示的证明材料上下文', 'Supplier-stated proof context'),
    'TRUST-03': ('同一声明标识下的公开信息比对', 'Public information under the same declared identifier'),
    'SEO-02': ('来源中的产品文字与静态链接', 'Product text and static links in the source'),
    'TECH-01': ('本次保存的页面响应', 'Retained page response'),
}
STATES = {
    'PASS': ('已有有限证据，仍待复核；不改变原规则结论。',
             'Bounded evidence is available for review; the native rule result is unchanged.'),
    'UNKNOWN': ('本次证据或适用关系尚未核实，不能据此判定网站缺失。',
                'Evidence or applicability remains unresolved; website absence is unproven.'),
    'ACCESS_BLOCKED': ('该来源访问受限，未据此评价网站业务质量。',
                       'Source access was blocked; no business-quality judgment follows.'),
    'NOT_APPLICABLE': ('按已固定的配置，此候选检查不适用。',
                       'This candidate check is excluded by the pinned configuration.'),
}


def bilingual(pair):
    return dict(zip(('zh', 'en'), pair))


def build(pack, diagnosis, artifact_sha256):
    """Caller retains current authority and has replayed the original artifact."""
    pack.verify(expected_ref=diagnosis['expected_pack_ref'])
    doc = pack.document
    scope = {k: doc[k] for k in ('tenant_id', 'run_id', 'policy_id', 'policy_version')}
    result = {'contract': 'vrae.buyer-review.v1', 'artifact_sha256': artifact_sha256,
        'pack_ref': pack.ref, 'native_execution_ref': diagnosis['native_execution_ref'],
        'state': 'AVAILABLE', 's2_projection_ref': None, 'industry_ref': None,
        'tasks': [], 'paths': [], 'path_coverage': {},
        'native_fact_admission': 'NONE', 'formal_human_review': False,
        'unknown_is_defect': False, 'inquiry_submitted': False,
        'product_context_transfer': 'UNKNOWN', 'technical_material_route': 'UNKNOWN',
        'proof_route': 'UNKNOWN'}
    # S2 is a separate review layer. Never substitute its baseline for the
    # original committed five-task evaluator or promote candidate PASS to it.
    try:
        config = load_s2(tenant_id=doc['tenant_id'])
        projection = evaluate_s2(pack, expected_pack_ref=pack.ref, trusted_scope=scope,
            projection_version='s2-projection-1.2.0', industry_pins=IndustryPins(
                config['industry_ref'], doc['tenant_id'], profile_id='industrial'))
        result.update(s2_projection_ref=projection['projection_ref'],
                      industry_ref=config['industry_ref'])
        rows = projection['static_projection']['rows'] + projection['industrial_projection']['rows']
    except Exception as exc:
        # Optional enrichment must not erase already replayed native facts.
        # Never log raw source text, request data or exception messages.
        logging.getLogger(__name__).warning('Buyer review candidate projection unavailable: %s',
                                            type(exc).__name__)
        rows = []
        result['state'] = 'CANDIDATES_UNAVAILABLE'
    snapshots = {s['snapshot_ref']: s for s in doc['snapshots']}
    evidence = {e['evidence_ref']: e for e in doc['evidence']}
    for task, rules in TASK_RULES.items():
        candidates, coverage = [], []
        for rule in rules:
            selected = [r for r in rows if r['observation']['rule_id'] == rule]
            coverage.append({'rule_id': rule, 'total': len(selected),
                'returned': min(len(selected), CAP_PER_RULE), 'truncated': len(selected)>CAP_PER_RULE})
            for row in selected[:CAP_PER_RULE]:
                obs = row['observation']
                refs = set()
                for page in [*row.get('source_pages', []), row.get('response'), row.get('target_response')]:
                    if page and page['snapshot_ref'] in snapshots:
                        refs.add(page['snapshot_ref'])
                bindings = []
                for citation in row['citations']:
                    ev = evidence[citation['evidence_ref']]
                    if ev['snapshot_ref'] != citation['snapshot_ref']:
                        raise EvidenceError('BUYER_REVIEW_SOURCE_BINDING')
                    refs.add(ev['snapshot_ref'])
                    # Do not export raw HTML, contact values or source quotes.
                    bindings.append({k: ev[k] for k in ('evidence_ref', 'snapshot_ref',
                        'locator', 'content_sha256')} | {
                        k: citation[k] for k in ('byte_start', 'byte_end')})
                candidates.append({'observation_id': obs['observation_id'],
                    'rule_id': rule, 'rule_version': obs['rule_version'],
                    'source_version': row['source_version'], 'candidate_result': obs['result'],
                    'reason': row['reason'], 'title': bilingual(COPY[rule]),
                    'text': bilingual(STATES[obs['result']]),
                    'source_snapshot_refs': sorted(refs), 'evidence_bindings': bindings,
                    'native_fact_admission': 'NONE', 'human_review_required': True})
        result['tasks'].append({'task': task, 'candidates': candidates, 'coverage': coverage})
    pointers = {row['observation']['observation_id']:
        f'/deterministic_diagnosis/buyer_tasks/{ti}/rules/{ri}/observations/{oi}'
        for ti, task in enumerate(diagnosis['buyer_tasks'])
        for ri, rule in enumerate(task['rules']) for oi, row in enumerate(rule['observations'])}
    paths = diagnosis['buyer_journey']
    for path in paths[:PATH_CAP]:
        steps = [{'rule_id': step['rule_id'], 'observation_id': step['observation_id'],
            'result': step['result'], 'source_pointer': pointers[step['observation_id']]}
            for step in path['steps']]
        result['paths'].append({'journey_ref': path['journey_ref'], 'steps': steps,
            'static_path_complete': path['complete'], 'terminal_result': path['terminal_result'],
            'product_context_transfer': 'UNKNOWN', 'inquiry_submitted': False})
    result['path_coverage'] = {'total': len(paths), 'returned': len(result['paths']),
        'truncated': len(paths)>PATH_CAP, 'whole_site_coverage_known': False}
    result['review_ref'] = 'brv-'+document_hash(result)
    return result

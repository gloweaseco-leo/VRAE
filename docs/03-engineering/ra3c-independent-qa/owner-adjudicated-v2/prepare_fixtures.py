"""Derive V2 guards from immutable independent captures; never imports reporting."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0,str(ROOT))
spec = importlib.util.spec_from_file_location('ra3c_v2_support_authoring',HERE/'support.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
v1 = support.v1
TEMPLATES = {
    'impact':('HYPOTHESIS','采购商从产品页继续寻找联系入口时，可能需要额外绕行。是否影响实际询盘，仍需人工核实。'),
    'action':('RECOMMENDATION','建议先确认该联系页面是否仍在使用，再修正产品页链接或恢复对应页面；实施前须人工批准。'),
    'recheck':('RECOMMENDATION','在获准环境中从同一产品页重新访问该 href，核对目标 HTTP 状态与跳转；表单送达需另行授权验证。')}


def request(scenario,*,profile=None,partial=False):
    old = v1.prepare_context(scenario)
    pins = {k:v for k,v in old['pins'].items() if k != 'expected_guard_ref'}
    known = v1.catalog(old['pack'],old['package'],**pins)
    facts = known['facts']
    if partial or profile:
        facts = ([f for f in facts if f['rule_id'] == 'CTA-02'] or facts)[:1]
    bundles = []
    for index,fact in enumerate(facts):
        ai = deepcopy(old['interpretation'])
        ai.update(interpretation_id=f'qa-ra3c-v2-{scenario}-{index}',
            observation_ids=[fact['observation_id']],evidence_ids=[fact['source']['citation']['evidence_ref']],
            hypotheses=[],recommendations=[],missing_information=[],status='VALIDATED')
        statements = [('hypotheses','OBJECTIVE_SOURCE_FACT',fact['statement'])]
        if fact['proof_kind'] == 'CAPTURED_CTA_HTTP_FAILURE':
            statements += [('hypotheses',*TEMPLATES['impact']),('recommendations',*TEMPLATES['action']),
                           ('recommendations',*TEMPLATES['recheck'])]
        if profile:
            statements += [('hypotheses','OBJECTIVE_SOURCE_FACT',t) for t in v1.INPUT['profiles'][profile]]
        bindings = []
        for field,kind,text in statements:
            pointer = f'/{field}/{len(ai[field])}'
            ai[field].append(text)
            bindings.append(v1.binding(pointer=pointer,text=text,claim_type=kind,
                fact=deepcopy(fact),context=deepcopy(known['context'])))
        guard = v1.guard_validate(ai,bindings,old['pack'],old['package'],**pins)
        bundles.append(dict(interpretation=ai,bindings=bindings,guard=guard.document,
            expected_guard_ref=guard.ref,original_fact_ref=fact['fact_ref']))
    assert len(bundles) <= 16
    return dict(scenario=scenario,source_pins=pins,bundles=bundles,
        source_fact_count=len(facts),explicit_empty_guard_request=not bundles,
        purpose='SEPARATELY_PINNED_ADMISSIBLE_REQUEST' if not profile else 'SEPARATE_UNTRUSTED_CLAIM_ATTACK')


def main():
    target = HERE/'fixtures/guard-requests.json'
    assert not target.exists(), 'Never overwrite held V2 fixtures'
    requests = {'positive/'+scenario:request(scenario) for scenario in v1.INPUT['scenarios']}
    for scenario,profile in (('broken404','credentials'),('broken404','rank_revenue'),
        ('healthy200','delivery_case'),('broken404','instructions')):
        requests['attack/'+scenario+'/'+profile] = request(scenario,profile=profile)
    requests['partial/duplicate_contact'] = request('duplicate_contact',partial=True)
    prior = json.loads((HERE.parent/'phase-b-native-v1/py313/results.json').read_text(encoding='utf-8'))
    denials = [dict(id=n['name'].split('[',1)[1].split('-',1)[0],
        expected_code='REPORT_GUARD_NOT_VALIDATED' if n['classification'].startswith('M07') else 'REPORT_UNSUPPORTED_PROSE')
        for n in prior['nodes'] if n['status'] == 'failed']
    assert len(denials) == 53 and len({n['id'] for n in denials}) == 53
    raw = dict(version=support.VERSION,authority=support.AUTHORITY,
        original_freeze='fa645b58549dfd21a6b80656d403f672b790acd8',
        original_input_git_sha256='93dee1d7045327281bf310edd412ca189257707cb36c8bd0665e7099f38e6604',
        templates=TEMPLATES,requests=requests,original_denials=denials,
        scenarios=14,primary_objectives=64,companion_denials=54,
        template_sha256=hashlib.sha256(v1.canonical(TEMPLATES)).hexdigest(),
        candidate_imported=False,real_model_calls=0)
    target.write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('V2 independently source-derived requests:',len(requests),'objectives64 + companion denials54')


if __name__ == '__main__':
    main()

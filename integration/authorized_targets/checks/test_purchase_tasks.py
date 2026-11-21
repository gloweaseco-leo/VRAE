"""Procurement decisions and narrow Qwen admission; synthetic evidence only."""
import asyncio
import json

import pytest

from integration.authorized_targets.checks.test_content_sources import prepared
from integration.authorized_targets.checks.test_procurement_review import wheel
from integration.qwen_provider.fixture import NOW, provider, response
from vrae.industry.l2_v1 import diagnose
from vrae.industry.l2_v1.purchase_tasks import ACTIONS, QUESTIONS, VERIFICATIONS
from vrae.intelligence.qwen.provider import PURCHASE_PROMPT, CONTEXT_PROMPT, QwenError
from vrae.intelligence.qwen.session import compact_input, candidate_schema, dispatch, validate_candidates


@pytest.fixture(scope='module')
def held():
    return prepared(wheel([('Size(MM)','D140*M10*T26*W12*X5'),('Abrasive','Diamond'),
        ('Grain Size','220/260 or customer request'),('Bond','Resin Metal'),
        ('Usage','For thinning a stated substrate')]), version='l2-industrial-1.0.7')


def candidate(c, task='SPECIFICATION_COMPARISON'):
    rows=compact_input(c, {'data':{'confirmed':[],'unknown_or_blocked':[]}})['references']
    selected=[r['ref'] for r in rows if r['type']=='GUARD_LITERAL' and r['rule_id']=='INFO-01']
    lang=0 if getattr(c.completion,'response_language','en')=='zh' else 1
    from vrae.industry.l2_v1.purchase_tasks import TASKS
    from vrae.industry.l2_v1.procurement import configuration, normalized
    from vrae.industry.l2_v1.pack import load
    _,aliases=configuration(load()['profile'],'1.1.0')
    fields={}
    for r in selected:
        cite=c.catalog['entries'][r]['fact']['source']['citation']
        fields.setdefault(cite.get('field_index'),{})[cite['fact_role']]=cite['text']
    source=next(p['SPEC_VALUE'] for p in fields.values() if 'SPEC_LABEL' in p and
        aliases.get(normalized(p['SPEC_LABEL'])) in TASKS[task][1])
    return {'task':'UNDERSTAND','purchase_task':task,'opportunity_kind':'CLARIFICATION',
        'refs':selected,'counter_refs':[],
        'explanation':source+' may need supplier clarification for this purchasing task.',
        'uncertainties':['Only this bounded product region was checked.'],
        'rebuild':[ACTIONS[task][lang]],'questions':[QUESTIONS[task][lang]],'verification':VERIFICATIONS[task][lang]}


def text(c, claims):
    return json.dumps({'prompt_version':PURCHASE_PROMPT,'context_ref':c.context_ref,'claims':claims})


def test_size_label_is_observed_while_compound_code_remains_unparsed_and_old_version_unchanged(held):
    c=held
    d=diagnose(c.pack, expected_pack_ref=c.pack.ref,expected_industry_ref=c.completion.task.industry_ref,
        diagnostic_version='l2-industrial-1.0.7')
    old=diagnose(c.pack, expected_pack_ref=c.pack.ref,expected_industry_ref=c.completion.task.industry_ref,
        diagnostic_version='l2-industrial-1.0.6')
    card=d['procurement_review']['products'][0]
    assert card['fields'][0]['key']=='dimensions' and card['fields'][0]['normalization'] is None
    assert next(g for g in card['groups'] if g['key']=='dimensions')['state']=='OBSERVED'
    assert old['procurement_review']['products'][0]['fields'][0]['key'] is None
    assert 'purchase_tasks' not in old['procurement_review']['products'][0]
    assert len(card['purchase_tasks'])==3
    assert all(not t['is_defect'] and not t['relationships_verified'] for t in card['purchase_tasks'])
    assert card['inquiry_preparation']['inquiry_submitted'] is False
    assert {k:v for k,v in old.items() if k not in ('procurement_review','diagnosis_ref','diagnostic_version')} == {
        k:v for k,v in d.items() if k not in ('procurement_review','diagnosis_ref','diagnostic_version')}


def test_new_prompt_allows_zero_and_requires_safe_actions_without_changing_old_prompt(held):
    assert candidate_schema(held)['properties']['prompt_version']['const']==PURCHASE_PROMPT
    assert candidate_schema(held)['properties']['claims']['minItems']==0
    assert validate_candidates(text(held, []),held,{})==[]
    assert candidate_schema(prepared(version='l2-industrial-1.0.6'))['properties']['prompt_version']['const']==CONTEXT_PROMPT


def test_valid_task_clarification_is_bound_and_ranked_without_native_fact_promotion(held):
    receipt={'input_tokens':100,'output_tokens':50}
    out=validate_candidates(text(held,[candidate(held,'OPTION_SELECTION'),candidate(held)]),held,receipt)
    assert [c['purchase_task'] for c in out]==['SPECIFICATION_COMPARISON','OPTION_SELECTION']
    assert all(c['native_fact_admission']=='NONE' and c['status']=='HUMAN_REVIEW_REQUIRED' for c in out)


@pytest.mark.parametrize('bad', ['Publish all valid combinations of independently listed options.',
    'Explain every part of the composite code as millimetres.'])
def test_unsupported_relationship_or_dimension_action_is_refused(held,bad):
    c=candidate(held)
    c['rebuild']=[bad]
    with pytest.raises(QwenError,match='CANDIDATE_SCHEMA'):
        validate_candidates(text(held,[c]),held,{})


def test_values_without_labels_cannot_support_a_purchasing_task(held):
    c=candidate(held)
    c['refs']=[r for r in c['refs'] if held.catalog['entries'][r]['fact']['source']['citation'].get('fact_role')!='SPEC_LABEL']
    with pytest.raises(QwenError,match='PURCHASE_TASK_LABEL_VALUE_REQUIRED'):
        validate_candidates(text(held,[c]),held,{})


def test_fake_dispatch_keeps_existing_call_budget_and_supports_zero_claims(held,tmp_path):
    p=provider(tmp_path/'synthetic-quota.sqlite',held)
    p._transport.response=response(held)
    # The protocol helper exposes a mutable payload; this is never a real API.
    p._transport.response['choices'][0]['message']['content']=text(held,[])
    raw,receipt=asyncio.run(dispatch(held,provider=p,operation='synthetic-purchase-zero',
        now=NOW,timeout_ms=1000,clock=lambda:NOW))
    assert receipt['real_model_calls']==0 and receipt['prompt_version']==PURCHASE_PROMPT
    assert validate_candidates(raw,held,receipt)==[]


def test_zero_recommendation_metadata_cannot_promote_failures_or_protocol_fakes():
    from integration.authorized_targets.automatic_result import completed_model_result, analysis_outcome
    # Synthetic metadata shape only; this test is not real-provider evidence.
    receipt={'state':'AI_CANDIDATES_FOR_HUMAN_REVIEW','verification_realm':'REAL_PROVIDER',
        'real_model_calls':1,'reason':'NO_SUPPORTED_OPPORTUNITIES','failure_stage':None,'claims':[],
        'usage':{'usage_origin':'PROVIDER_REPORTED','prompt_version':PURCHASE_PROMPT}}
    assert completed_model_result(receipt,'l2-industrial-1.0.7')
    assert analysis_outcome(receipt,True)=='COMPLETED_NO_RECOMMENDATIONS'
    assert not completed_model_result(receipt,'l2-industrial-1.0.6')
    for patch in [{'real_model_calls':0},{'verification_realm':'PROTOCOL_FAKE_NOT_REAL_API'},
        {'failure_stage':'VALIDATION'},{'reason':'CANDIDATES_BOUND_NOT_APPROVED'},
        {'usage':{'usage_origin':'PROVIDER_REPORTED','prompt_version':CONTEXT_PROMPT}}]:
        assert not completed_model_result({**receipt,**patch},'l2-industrial-1.0.7')


def test_placeholder_field_is_retained_but_does_not_establish_task_information():
    c=prepared(wheel([('Size(MM)','N/A')]), version='l2-industrial-1.0.7')
    d=diagnose(c.pack,expected_pack_ref=c.pack.ref,expected_industry_ref=c.completion.task.industry_ref,
        diagnostic_version='l2-industrial-1.0.7')
    card=d['procurement_review']['products'][0]
    assert card['fields'][0]['value']=='N/A'
    assert next(g for g in card['groups'] if g['key']=='dimensions')['state']=='OBSERVED'
    assert all(t['state']=='UNKNOWN' for t in card['purchase_tasks'])
    assert not card['inquiry_preparation']['available_input_field_indexes']
    with pytest.raises(QwenError,match='INSUFFICIENT_GUARDED_EVIDENCE'):
        compact_input(c,{'data':{'confirmed':[],'unknown_or_blocked':[]}})

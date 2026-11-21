"""Delivery copy, bounded paths and model quality; synthetic sources only."""
from copy import deepcopy

import pytest

from tests.s2_contract.batch2_fixtures import fixture
from integration.authorized_targets.presentation import build, observation_copy
from vrae.industry.l2_v1.diagnose import source_chain
from vrae.rules.patch_execution import execute
from vrae.intelligence.qwen.output_quality import check
from vrae.intelligence.qwen.provider import QwenError


def test_bilingual_copy_keeps_unknown_and_exact_source_pointers_without_mutation():
    def row(rule, result, reason, **extra):
        return {'observation': {'rule_id': rule, 'observation_id': 'obs-'+rule,
            'result': result, 'statement': 'Untranslated original statement'}, 'reason': reason, **extra}
    rows = [row('INFO-01', 'PASS', 'BOUNDED_STATIC_PRODUCT_TEXT_RETAINED'),
            row('INFO-02', 'UNKNOWN', 'No industry applicability mapping.'),
            row('CTA-01', 'UNKNOWN', 'STATIC_HREF_OBSERVED_VISIBILITY_UNVERIFIED')]
    original = {'state': 'AI_UNAVAILABLE', 'analysis_outcome': 'PROVIDER_FAILED', 'claims': [],
        'artifact_sha256': 'a'*64, 'deterministic_diagnosis': {'buyer_tasks': [
            {'task': 'UNDERSTAND', 'rules': [{'rule_id': 'INFO-01', 'observations': rows[:1]},
                {'rule_id': 'INFO-02', 'observations': rows[1:2]}]},
            {'task': 'INQUIRE', 'rules': [{'rule_id': 'CTA-01', 'observations': rows[2:]}]}]}}
    before = deepcopy(original)
    out = build(original)
    assert original == before and out['rules_available']
    assert not out['is_report'] and not out['formal_human_review']
    assert out['tasks'][0]['observations'][0]['result'] == 'PASS'
    assert out['tasks'][0]['observations'][1]['result'] == 'UNKNOWN'
    assert '不能判定缺少' in out['tasks'][0]['observations'][1]['text']['zh']
    assert '送达' in out['tasks'][1]['observations'][0]['text']['zh']
    assert out['tasks'][0]['observations'][1]['source_pointer'].endswith('/rules/1/observations/0')
    original.update(state='AI_PENDING', analysis_outcome='PENDING')
    assert build(original)['tasks'] == out['tasks']
    assert '保留' in out['analysis_text']['zh']


def test_current_buyer_judgment_keeps_supplier_questions_out_of_the_lead():
    home = {'url': 'https://example.org/', 'snapshot_ref': 's-home'}
    catalog = {'url': 'https://example.org/products', 'snapshot_ref': 's-cat'}
    product = {'url': 'https://example.org/Back%20Grinding%20Wheel.html', 'snapshot_ref': 's-prod'}
    contact = {'url': 'https://example.org/contacts', 'snapshot_ref': 's-con'}

    def row(rule, result, reason, **extra):
        return {'observation': {'rule_id': rule, 'observation_id': 'obs-'+rule, 'result': result},
                'reason': reason, **extra}
    tasks = [
        ('DISCOVER', [('DISC-01', 'PASS', 'CAPTURED_REACHABLE_HREF'), ('DISC-02', 'PASS', 'CAPTURED_REACHABLE_HREF')]),
        ('UNDERSTAND', [('INFO-01', 'PASS', 'BOUNDED_STATIC_PRODUCT_TEXT_RETAINED')]),
        ('TRUST', [('TRUST-01', 'UNKNOWN', 'TRUST_PREREQUISITES_OR_CAPTURE_SCOPE_UNRESOLVED')]),
        ('INQUIRE', [('CTA-02', 'PASS', 'CAPTURED_REACHABLE_HREF')]),
        ('SEARCH_TECHNICAL', [('SEO-01', 'UNKNOWN', 'PARTIAL_MISSING_AMBIGUOUS_OR_UNSUPPORTED_HEAD_SIGNALS')]),
    ]
    diagnosis = {'diagnostic_version': 'l2-industrial-1.0.7', 'buyer_tasks': [
        {'task': task, 'rules': [{'rule_id': rule, 'observations': [row(rule, result, reason)]}
            for rule, result, reason in rules]} for task, rules in tasks],
        'buyer_journey': [{'complete': True, 'steps': [
            {'rule_id': 'DISC-01', 'result': 'PASS', 'source_page': home, 'target_response': catalog},
            {'rule_id': 'DISC-02', 'result': 'PASS', 'source_page': catalog, 'target_response': product},
            {'rule_id': 'CTA-02', 'result': 'PASS', 'source_page': product, 'target_response': contact}]}]}
    diagnosis['buyer_tasks'][1]['rules'][0]['observations'][0]['citations'] = [
        {'fact_role': 'NAME', 'url': product['url'], 'text': 'Back Grinding Wheel for Thinning Sapphire'}]
    result = {'state': 'DIAGNOSED', 'analysis_outcome': 'COMPLETED', 'artifact_sha256': 'a'*64,
        'claims': [{'task': 'UNDERSTAND', 'explanation': '结合剂与粒度的对应关系需要供方说明。',
                    'questions': ['这些并列项如何对应尺寸编码？']}],
        'page_scope': {'visited_pages': [home, catalog, product, contact], 'failed_attempt_records': [],
                       'unvisited_candidates': [{}] * 71},
        'capture_summary': {'fetched_pages': 6, 'unvisited_candidates': 71, 'unvisited_is_defect': False},
        'deterministic_diagnosis': diagnosis}
    out = build(result)
    judgment = out['judgment']
    rendered = str(out)
    assert '建议优先关注' not in rendered and '可以先这样改' not in rendered
    assert judgment['confirmed_obstacles'] == []
    assert judgment['confirmed_obstacle_count_is_score'] is False
    assert judgment['supplier_questions'][0]['presented_as_priority_fix'] is False
    assert judgment['supplier_questions'][0]['is_confirmed_defect'] is False
    assert '没有已证实的网站缺陷' in judgment['lead']['zh']
    labels = [step['label']['zh'] for step in judgment['walked_path']['steps']]
    assert labels == ['网站首页', '产品分类', 'Back Grinding Wheel for Thinning Sapphire', '联系页面']
    assert 'Wheel.html' not in judgment['walked_path']['summary']['zh']
    assert judgment['scope_hypothesis']['kind'] == 'CHECK_RECORDED_PRODUCT_PAGE'
    assert judgment['scope_hypothesis']['whole_site_rebuild'] is False
    assert {item['task'] for item in judgment['unjudged']} == {'TRUST', 'SEARCH_TECHNICAL'}
    assert judgment['sample_boundary']['unvisited_is_defect'] is False
    assert judgment['sample_boundary']['unvisited_candidates'] == 71
    assert '采购商可以从首页进入' in out['tasks'][0]['observations'][0]['text']['zh']
    assert out['is_report'] is False and judgment['formal_human_review'] is False
    diagnosis.pop('diagnostic_version')
    legacy = build(result)
    assert 'judgment' not in legacy
    assert legacy['tasks'][0]['observations'][0]['text']['zh'].startswith('已记录首页导航')


def test_other_rule_failures_do_not_invent_http_status_or_new_facts():
    assert '404' not in observation_copy('INFO-01', {'observation': {'result': 'FAIL_WITH_EVIDENCE'}})[0]
    for reason in ('STATIC_PRODUCT_NAME_AMBIGUOUS', 'HTML_UNSUPPORTED_OR_AMBIGUOUS'):
        text = observation_copy('INFO-01', {'observation': {'result': 'UNKNOWN'}, 'reason': reason})
        assert text[0] and text[1]


def test_new_static_path_parser_replays_only_captured_category_product_contact_edges():
    pack = fixture(overrides={
        '/products': b'<html><head><script>var fixture=true;</script></head><body>'
            b'<a href="/unsupported-a" href="/unsupported-b">Ambiguous decoy</a>'
            b'<a href="/products/p40"><span>Wheel</span></a>'
            b'<a href="../products/not-captured">Other</a></body></html>',
        '/products/p40': b'<html><head><script>var fixture=true;</script></head>'
            b'<body><main><h1>Wheel</h1><a href="../contact"><span>Contacts</span></a></main></body></html>'})
    old = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b6-1.0.2')
    new, _, _, _ = source_chain(pack, pack.ref, diagnostic_version='l2-industrial-1.0.3')
    def rows(output, rule):
        return next(r for r in output['executions'] if r['rule_id'] == rule)['observations']
    assert not any(o['observation']['result'] == 'PASS' for o in rows(old, 'DISC-02'))
    assert any(o['observation']['result'] == 'PASS' for o in rows(new, 'DISC-02'))
    assert any(o['observation']['result'] == 'PASS' for o in rows(new, 'CTA-02'))
    assert any(o['reason'] == 'TARGETS_OUTSIDE_CAPTURE_SCOPE' for o in rows(new, 'DISC-02'))
    assert any(j['complete'] for j in new['journeys'])
    for rule in ('DISC-02', 'CTA-02'):
        for o in rows(new, rule):
            if o['observation']['result'] == 'PASS':
                assert o['target_response']['http_status'] == 200
                assert o['citations'][0]['target_evidence_ref']
                assert 'delivery' in o['observation']['coverage_note']


def test_unvisited_or_hidden_contact_links_are_not_complete_paths():
    pack = fixture(overrides={'/products/p40': b'<html><body><main><h1>Wheel</h1>'
        b'<a hidden href="/contact">Contacts</a><a href="../not-captured">Contact us</a></main></body></html>'})
    result = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b6-1.0.3')
    rows = next(r for r in result['executions'] if r['rule_id'] == 'CTA-02')['observations']
    assert not any(o['observation']['result'] == 'PASS' for o in rows
                   if o.get('source_page', {}).get('url', '').endswith('/p40'))


def test_html_base_does_not_create_a_false_same_origin_inquiry_path():
    from vrae.collection.discovery import labelled_contact_targets
    html = b'<html><head><base href="https://other.example.org/" /></head><body>' \
        b'<main><h1>Wheel</h1><a href="/contact">Contacts</a></main></body></html>'
    assert not labelled_contact_targets(html, 'https://example.org/products/p40')
    pack = fixture(overrides={'/products/p40': html})
    result = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b6-1.0.3')
    rows = next(r for r in result['executions'] if r['rule_id'] == 'CTA-02')['observations']
    assert not any(o['observation']['result'] == 'PASS' for o in rows
                   if o.get('source_page', {}).get('url', '').endswith('/p40'))


@pytest.mark.parametrize('text,code', [
    ('A buyer cannot confirm this because its source text is withheld.', 'MODEL_INTERNAL_LIMIT_NOT_BUYER_FINDING'),
    ('The pinned description anchor carries rule_result UNKNOWN.', 'MODEL_INTERNAL_LIMIT_NOT_BUYER_FINDING'),
    ('This product has no specifications.', 'UNSUPPORTED_SPECIFICATION_ABSENCE'),
    ('产品页面缺少关键规格。', 'UNSUPPORTED_SPECIFICATION_ABSENCE'),
])
def test_internal_model_limits_and_unsupported_absence_are_not_buyer_findings(text, code):
    claim = {'task': 'UNDERSTAND', 'explanation': text, 'rebuild': ['Organize the observed values.'],
             'verification': 'Compare the revised section with the cited source.'}
    with pytest.raises(QwenError, match=code):
        check(claim)


def test_verification_is_distinct_from_the_rebuild_action():
    claim = {'task': 'UNDERSTAND', 'explanation': 'A buyer may need the applicable conditions alongside the recorded diameter.',
        'rebuild': ['Group the recorded diameter with seller-confirmed conditions.'],
        'verification': 'After the change, compare the diameter and conditions with the same cited source.'}
    check(claim)
    claim['verification'] = claim['rebuild'][0]
    with pytest.raises(QwenError, match='DISTINCT_VERIFICATION_REQUIRED'):
        check(claim)

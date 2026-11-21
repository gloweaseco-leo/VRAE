"""Delivery copy, bounded paths and model quality; synthetic sources only."""
import json
from copy import deepcopy

import pytest

from integration.authorized_targets.presentation import build, observation_copy
from tests.s2_contract.batch2_fixtures import fixture
from vrae.industry.l2_v1.diagnose import source_chain
from vrae.intelligence.qwen.output_quality import check
from vrae.intelligence.qwen.provider import QwenError
from vrae.rules.patch_execution import execute


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


def test_customer_judgment_uses_the_product_name_and_does_not_promote_questions():
    product = 'Outdoor Wall Panel'
    product_url = 'https://example.org/products/outdoor-wall.html'
    home = {'snapshot_ref': 'snap-home', 'url': 'https://example.org/'}
    category = {'snapshot_ref': 'snap-cat', 'url': 'https://example.org/products/'}
    product_page = {'snapshot_ref': 'snap-product', 'url': product_url}
    contact = {'snapshot_ref': 'snap-contact', 'url': 'https://example.org/contact'}

    def row(rule, result, reason, **extra):
        return {'observation': {'rule_id': rule, 'observation_id': 'obs-' + rule,
            'result': result, 'statement': 'Synthetic source statement'}, 'reason': reason, **extra}

    tasks = [
        {'task': 'DISCOVER', 'rules': [
            {'rule_id': 'DISC-01', 'observations': [row(
                'DISC-01', 'PASS', 'CAPTURED_REACHABLE_HREF', homepage=home, target_response=category)]},
            {'rule_id': 'DISC-02', 'observations': [row(
                'DISC-02', 'PASS', 'CAPTURED_REACHABLE_HREF', source_page=category,
                target_response=product_page)]}]},
        {'task': 'UNDERSTAND', 'rules': [{'rule_id': 'INFO-01', 'observations': [row(
            'INFO-01', 'PASS', 'BOUNDED_STATIC_PRODUCT_TEXT_RETAINED', source_page=product_page,
            source_text_presence='OBSERVED', citations=[{
                'fact_role': 'NAME', 'text': product, 'url': product_url,
                'snapshot_ref': product_page['snapshot_ref']}])]}]},
        {'task': 'TRUST', 'rules': [{'rule_id': 'TRUST-01', 'observations': [row(
            'TRUST-01', 'UNKNOWN', 'TRUST_PREREQUISITES_OR_CAPTURE_SCOPE_UNRESOLVED')]}]},
        {'task': 'INQUIRE', 'rules': [{'rule_id': 'CTA-02', 'observations': [row(
            'CTA-02', 'PASS', 'CAPTURED_REACHABLE_HREF', source_page=product_page,
            target_response=contact)]}]},
        {'task': 'SEARCH_TECHNICAL', 'rules': [{'rule_id': 'SEO-01', 'observations': [row(
            'SEO-01', 'UNKNOWN', 'PARTIAL_MISSING_AMBIGUOUS_OR_UNSUPPORTED_HEAD_SIGNALS')]}]},
    ]
    journey = {'journey_ref': 'journey-synthetic', 'complete': True, 'terminal_result': 'PASS', 'steps': [
        {'rule_id': 'DISC-01', 'observation_id': 'obs-DISC-01', 'result': 'PASS',
         'source_page': home, 'target_response': category},
        {'rule_id': 'DISC-02', 'observation_id': 'obs-DISC-02', 'result': 'PASS',
         'source_page': category, 'target_response': product_page},
        {'rule_id': 'CTA-02', 'observation_id': 'obs-CTA-02', 'result': 'PASS',
         'source_page': product_page, 'target_response': contact},
    ]}
    payload = {
        'state': 'DIAGNOSED', 'analysis_outcome': 'COMPLETED', 'artifact_sha256': 'a' * 64,
        'claims': [{'task': 'UNDERSTAND', 'questions': ['这组尺寸对应哪一份图纸？'],
                    'explanation': '需要供方核对。', 'rebuild': ['把尺寸和图纸放在一起。']}],
        'capture_summary': {'fetched_pages': 6, 'unvisited_candidates': 71, 'unvisited_is_defect': False},
        'page_scope': {
            'visited_pages': [
                {**home, 'request_role': 'HOME'}, {**category, 'request_role': 'CATALOG'},
                {**product_page, 'request_role': 'PRODUCT'}, {**contact, 'request_role': 'CONTACT'}],
            'failed_attempt_records': [],
            'unvisited_candidates': [
                {'url': f'https://example.org/candidate/{i}.html', 'is_defect': False} for i in range(71)]},
        'deterministic_diagnosis': {
            'diagnostic_version': 'l2-industrial-1.0.7', 'buyer_tasks': tasks, 'buyer_journey': [journey],
            'procurement_review': {'contract': 'vrae.l2-procurement-review.v1', 'products': []}}}
    out = build(payload)
    found = out['judgment']
    assert found['contract'] == 'vrae.diagnosis-judgment.v1'
    assert found['is_report'] is False and found['formal_human_review'] is False
    product_step = next(step for step in found['walked_path']['steps'] if step['rule_id'] == 'DISC-02')
    assert product_step['label'] == {'zh': product, 'en': product}
    assert product_step['url'].endswith('/outdoor-wall.html')
    assert all('.html' not in step['label']['zh'] and '.html' not in step['label']['en']
               for step in found['walked_path']['steps'])
    assert found['confirmed_obstacles']['items'] == []
    assert found['confirmed_obstacles']['is_defect_score'] is False
    assert found['confirmed_obstacles']['confirmed_obstacle_count_is_score'] is False
    questions = found['supplier_questions']
    assert questions['presented_as_priority_fix'] is False and questions['is_confirmed_defect'] is False
    assert questions['items'][0]['question'] == '这组尺寸对应哪一份图纸？'
    assert questions['items'][0]['presented_as_priority_fix'] is False
    assert questions['items'][0]['is_confirmed_defect'] is False
    unjudged = {item['task'] for item in found['unjudged']['items']}
    assert {'TRUST', 'SEARCH_TECHNICAL'} <= unjudged
    assert 'DISCOVER' not in unjudged and 'UNDERSTAND' not in unjudged and 'INQUIRE' not in unjudged
    assert found['unjudged']['is_defect'] is False
    assert all(item['is_defect'] is False for item in found['unjudged']['items'])
    assert found['sample_boundary']['fetched_pages'] == 6
    assert found['sample_boundary']['unvisited_candidates'] == 71
    assert found['sample_boundary']['unvisited_is_defect'] is False
    assert found['scope_hypothesis']['kind'] == 'CHECK_RECORDED_PRODUCT_PAGE'
    assert found['scope_hypothesis']['whole_site_rebuild'] is False
    rendered = json.dumps(found, ensure_ascii=False)
    assert '建议优先关注' not in rendered and '可以先这样改' not in rendered
    assert '把尺寸和图纸放在一起' not in rendered
    assert out['tasks'][1]['observations'][0]['text']['zh'].startswith('已看到供方写的名称或描述')
    assert '已记录首页导航' not in out['tasks'][0]['observations'][0]['text']['zh']
    for version in (None, 'l2-industrial-1.0.6'):
        legacy = deepcopy(payload)
        if version is None:
            del legacy['deterministic_diagnosis']['diagnostic_version']
        else:
            legacy['deterministic_diagnosis']['diagnostic_version'] = version
        old = build(legacy)
        assert 'judgment' not in old
        assert '已记录首页导航' in old['tasks'][0]['observations'][0]['text']['zh']


def test_verification_is_distinct_from_the_rebuild_action():
    claim = {'task': 'UNDERSTAND', 'explanation': 'A buyer may need the applicable conditions alongside the recorded diameter.',
        'rebuild': ['Group the recorded diameter with seller-confirmed conditions.'],
        'verification': 'After the change, compare the diameter and conditions with the same cited source.'}
    check(claim)
    claim['verification'] = claim['rebuild'][0]
    with pytest.raises(QwenError, match='DISTINCT_VERIFICATION_REQUIRED'):
        check(claim)

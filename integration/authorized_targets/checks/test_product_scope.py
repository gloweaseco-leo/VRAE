"""Attribution regressions; HTML and model outputs are synthetic."""
import asyncio
import json

import pytest

from integration.authorized_targets.checks.test_content_sources import prepared
from integration.qwen_provider.fixture import provider, response
from integration.s3_offline.fixture import NOW
from vrae.intelligence.qwen.output_quality import check_product_scopes
from vrae.intelligence.qwen.provider import QwenError
from vrae.intelligence.qwen.session import compact_input, dispatch, validate_candidates
from vrae.intelligence.qwen.testing import FakeTransport
from vrae.rules.product_scope import extract
from vrae.rules.universal_static import product

BODY = b'''<html><body><div id="main">
<div id="sidebar_left"><div class="product_menu">
<p><a href="/products/other">Other abrasive wheel category</a></p>
<p><a href="/products/board">Paper cutting wheel category</a></p></div></div>
<div id="sidebar_right"><h1>Precision thinning wheel W100</h1>
<p>Diamond wheel for the separately stated crystal thinning application.</p>
<table><tr><th>Item</th><th>Abrasive</th><th>Diameter</th></tr>
<tr><td>Precision thinning wheel W100</td><td>Diamond</td><td>100 mm</td></tr></table>
<section><h2>Other wheel</h2><p>PCBN wheel for another application and product.</p>
<table><tr><th>Abrasive</th><td>CBN</td></tr></table></section>
</div></div></body></html>'''


def test_sidebar_and_other_product_blocks_do_not_become_current_product_text():
    _, _, old_fields, old_descriptions = product(BODY, multi_column=True)
    assert [p['text'] for p in old_descriptions] == ['Other abrasive wheel category', 'Paper cutting wheel category']
    _, name, fields, descriptions, _ = extract(BODY)
    assert name['text'] == 'Precision thinning wheel W100'
    assert [p['text'] for p in descriptions] == [
        'Diamond wheel for the separately stated crystal thinning application.']
    assert [v['text'] for _, v in fields] == [
        'Precision thinning wheel W100', 'Diamond', '100 mm']
    assert len(old_fields) > len(fields)


@pytest.mark.parametrize('tag', ['nav', 'aside', 'header', 'footer'])
def test_navigation_cannot_supply_product_name(tag):
    with pytest.raises(ValueError, match='STATIC_PRODUCT_(SCOPE|NAME)_AMBIGUOUS'):
        extract(f'<{tag}><h1>Wheel</h1><table><tr><th>Size</th><td>100</td></tr></table></{tag}>'.encode())


def test_link_paragraphs_and_base_rewrites_are_not_model_descriptions():
    simple = b'<main><h1>Wheel</h1><p><a href="/other">Another product description</a></p></main>'
    assert extract(simple)[3] == []
    with pytest.raises(ValueError, match='STATIC_(PRODUCT_SCOPE|HTML)_AMBIGUOUS'):
        extract(simple.replace(b'<main>', b'<main><base href="https://example.org/">'))


def test_explicit_item_cell_anchors_specs_when_headings_are_only_navigation():
    body = BODY.replace(b'<h1>Precision thinning wheel W100</h1>', b'')
    body = body.replace(b'<div class="product_menu">', b'<div class="product_menu"><h1>PRODUCTS</h1>')
    _, name, fields, descriptions, region = extract(body)
    assert name['text'] == 'Precision thinning wheel W100'
    assert region['tag'] == 'table'
    assert [v['text'] for _, v in fields] == [name['text'], 'Diamond', '100 mm']
    assert descriptions == []
    ambiguous = body.replace(b'</section>', b'<table><tr><th>Item</th><td>Other wheel</td></tr></table></section>')
    with pytest.raises(ValueError, match='STATIC_PRODUCT_SCOPE_AMBIGUOUS'):
        extract(ambiguous)


def test_model_input_has_current_product_values_without_menu_or_related_text():
    context = prepared(BODY, version='l2-industrial-1.0.4')
    data = compact_input(context, {'data': {'confirmed': [], 'unknown_or_blocked': []}})
    values = [r for r in data['references'] if 'source_value' in r]
    assert data['prompt_version'] == 'qwen-evidence-buyer-1.3.0'
    assert {r['source_value'] for r in values} >= {'Diamond', '100 mm'}
    assert not {'Other abrasive wheel category', 'Paper cutting wheel category', 'CBN'} & {r['source_value'] for r in values}
    assert len({r['source_group'] for r in values}) == 1
    assert all(r['source_group'].startswith('ps-') for r in values)
    for row in values:
        c = context.catalog['entries'][row['ref']]['fact']['source']['citation']
        assert c['text'] == row['source_value']
        assert c['product_identity_verified'] is False


def test_cross_product_references_on_same_page_are_rejected():
    def entry(scope):
        return {'type': 'GUARD_LITERAL', 'fact': {'rule_id': 'INFO-01',
            'source': {'citation': {'snapshot_ref': 'same-page', 'product_scope_ref': scope}}}}
    entries = {'a': entry('ps-' + 'a'*64), 'b': entry('ps-' + 'b'*64)}
    with pytest.raises(QwenError, match='PRODUCT_SCOPE_MISMATCH'):
        check_product_scopes({'refs': ['a', 'b'], 'counter_refs': []}, entries)
    check_product_scopes({'refs': ['a'], 'counter_refs': []}, entries)
    entries['a']['fact']['source']['citation'].pop('product_scope_ref')
    with pytest.raises(QwenError, match='UNSCOPED_PRODUCT_REFERENCE'):
        check_product_scopes({'refs': ['a'], 'counter_refs': []}, entries)


def test_same_product_candidate_keeps_guard_and_proposed_verification(tmp_path):
    context = prepared(BODY, version='l2-industrial-1.0.4')
    data = compact_input(context, {'data': {'confirmed': [], 'unknown_or_blocked': []}})
    ref = next(r['ref'] for r in data['references'] if r.get('source_value') == '100 mm')
    raw = {'context_ref': context.context_ref, 'prompt_version': data['prompt_version'], 'claims': [{
        'task': 'UNDERSTAND', 'refs': [ref], 'counter_refs': [],
        'explanation': 'The recorded diameter may help a buyer prepare a specification question.',
        'rebuild': ['Keep the recorded diameter and applicable model together.'],
        'uncertainties': ['The supplier-stated specification is not independently verified.'],
        'questions': ['Which model does this recorded diameter apply to?'],
        'verification': 'Compare the revised model entry with the same retained diameter source.'}]}
    fake_response = response(context)
    fake_response['choices'][0]['message']['content'] = json.dumps(raw)
    transport = FakeTransport(fake_response)
    p = provider(tmp_path/'scoped.sqlite', context, fake=transport)
    text, receipt = asyncio.run(dispatch(context, provider=p, operation='scoped-fixture',
        now=NOW, timeout_ms=1000, clock=lambda: NOW))
    assert receipt['prompt_version'] == 'qwen-evidence-buyer-1.3.0'
    assert receipt['real_model_calls'] == 0
    claims = validate_candidates(text, context, receipt)
    assert len(claims) == 1 and claims[0]['guard_semantic_approval'] is False
    assert claims[0]['verification_status'] == 'PROPOSED_NOT_EXECUTED'

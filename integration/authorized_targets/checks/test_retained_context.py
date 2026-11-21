"""Synthetic captured sources only; no external sites or provider calls."""
import pytest

from integration.authorized_targets.checks.test_content_sources import prepared
from tests.s2_contract.batch2_fixtures import fixture
from vrae.collection.discovery import labelled_contact_targets, page_role
from vrae.industry.l2_v1.diagnose import source_chain
from vrae.intelligence.qwen.output_quality import check_commercial
from vrae.intelligence.qwen.provider import QwenError
from vrae.intelligence.qwen.session import compact_input
from vrae.rules.retained_context import contact_targets, role

HTML = b'''<html><body><main><h1>Wheel W100</h1>
<a href="/bad"><a href="/other">Bad nesting</a></a>
<a href="/contacts/">Contacts</a>
<table><tr><th>Item</th><th>Size</th><th>Abrasive</th><th>Grain Size</th><th>Bond</th><th>Usage</th></tr>
<tr><td>Wheel W100</td><td>100 mm</td><td>Diamond</td><td>240/280 or customer request</td><td>Resin</td><td>For thinning a stated substrate</td></tr></table>
</main></body></html>'''


def test_nested_anchor_does_not_erase_unrelated_closed_contact_link():
    assert labelled_contact_targets(HTML, 'https://example.org/products/wheel') == set()
    assert contact_targets(HTML, 'https://example.org/products/wheel') == {'https://example.org/contacts/'}
    assert page_role('https://example.org/contacts/') == 'OTHER'
    assert role('https://example.org/contacts/') == 'CONTACT'
    assert role('https://example.org/aboutus/') == 'ABOUT'


@pytest.mark.parametrize('http_status, expected', [(200, 'PASS'), (404, 'FAIL_WITH_EVIDENCE')])
def test_same_pack_contact_response_determines_path_result(http_status, expected):
    home = b'<html><body><nav><a href="/products">Products</a><a href="/contacts/">Contacts</a></nav></body></html>'
    pack = fixture(overrides={'/':home, '/products/p40':HTML,
        '/contacts/':b'<html><body><h1>Contacts</h1></body></html>'},
        statuses={'/contacts/':http_status})
    execution, _, _, _ = source_chain(pack, pack.ref, diagnostic_version='l2-industrial-1.0.5')
    rows = next(r for r in execution['executions'] if r['rule_id']=='CTA-02')['observations']
    assert any(r['observation']['result']==expected for r in rows)
    if http_status == 200:
        hit = next(r for r in rows if r['observation']['result']=='PASS')
        assert hit['citations'][0]['target_evidence_ref']


@pytest.mark.parametrize('link', [b'<a hidden href="/contacts/">Contacts</a>',
    b'<a href="https://other.example.org/contacts/">Contacts</a>',
    b'<a href="/contacts/?send=1">Contacts</a>', b'<a href="/contacts/">Contacts',
    b'<form><a href="/contacts/">Contacts</a></form>'])
def test_untrusted_or_unclosed_contact_regions_are_not_hints(link):
    assert not contact_targets(b'<main>'+link+b'</main>', 'https://example.org/products/wheel')


def test_new_model_projection_deduplicates_item_and_includes_bond_and_usage():
    c = prepared(HTML, version='l2-industrial-1.0.5')
    data = compact_input(c, {'data': {'confirmed': [], 'unknown_or_blocked': []}})
    rows = [r for r in data['references'] if 'source_value' in r]
    assert len(rows) == 11
    assert {'Resin', 'For thinning a stated substrate'} <= {r['source_value'] for r in rows}
    assert 'Item' not in {r['source_value'] for r in rows}
    assert data['prompt_version'] == 'qwen-evidence-buyer-1.4.0'


def test_about_and_contact_pages_contribute_partial_context_without_identity_certification():
    about = b'''<html><body><main><h1>About us</h1><script>ignored()</script>
    <p>A retained supplier introduction paragraph with a bounded public source.</p>
    <a href="/contacts/">Contacts</a></main></body></html>'''
    pack = fixture(overrides={'/about': about,
        '/contact': b'<main><h1>Contact</h1><a href="/contact">Contact us</a></main>'})
    execution, _, _, _ = source_chain(pack, pack.ref, diagnostic_version='l2-industrial-1.0.5')
    row = next(r for r in execution['executions'] if r['rule_id']=='TRUST-01')['observations'][0]
    assert any(c['kind']=='ABOUT_TEXT' for c in row['context_facts'])
    assert row['observation']['result'] == 'UNKNOWN'
    assert 'UNAMBIGUOUS_DECLARED_ORGANIZATION_NAME' in row['missing_prerequisites']


@pytest.mark.parametrize('bom', [b'', b'\xef\xbb\xbf'])
def test_explicit_self_declarations_can_pass_bounded_presence_with_original_guard(bom):
    about = bom+b'''<html><body><section itemscope itemtype="https://schema.org/Organization">
    <h1>About us</h1><span itemprop="name">Demo Fixture Company</span>
    <p>A bounded supplier-stated introduction for this synthetic company fixture.</p>
    <a href="/contact">Contact us</a></section></body></html>'''
    pack = fixture(overrides={'/about':about, '/contact':b'<main><h1>Contact</h1></main>'})
    execution, _, _, _ = source_chain(pack,pack.ref,diagnostic_version='l2-industrial-1.0.5')
    row=next(r for r in execution['executions'] if r['rule_id']=='TRUST-01')['observations'][0]
    assert row['observation']['result']=='PASS'
    assert not row['missing_prerequisites']
    assert 'authenticity' in row['observation']['statement']


def test_stock_inferences_are_rejected_but_neutral_questions_are_allowed():
    entry = {'type': 'GUARD_LITERAL', 'fact': {'rule_id': 'INFO-01', 'source': {
        'citation': {'fact_role': 'SPEC_VALUE', 'text': '240/280 or customer request'}}}}
    claim = {'refs':['a'],'counter_refs':[], 'explanation':'Listed grit choices may need clarification.',
        'rebuild':['Separate listed choices from customization.'], 'uncertainties':['Supply conditions are unverified.'],
        'verification':'Compare the revised wording to the same source.',
        'questions':['Are these options in stock and what is the MOQ?']}
    check_commercial(claim, {'a':entry})
    for bad in ['明确区分库存品与定制品。', 'Standard specifications are in stock.', '无法判断是营销话术还是实际产能承诺。']:
        with pytest.raises(QwenError, match='UNSUPPORTED_COMMERCIAL_INFERENCE'):
            check_commercial({**claim, 'rebuild':[bad]}, {'a':entry})

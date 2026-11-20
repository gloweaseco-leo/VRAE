"""Synthetic static sources; no real websites, providers or approval authority."""
import asyncio
from types import SimpleNamespace

import pytest

from tests.s2_contract.batch2_fixtures import fixture
from tests.collection.test_pipeline import FixedDNS, SyntheticTransport
from tests.collection.test_security import access
from vrae.collection.collector import Collector
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Limits
from vrae.collection.discovery import representative_role
from vrae.industry.l2_v1.diagnose import source_chain
from vrae.rules.patch_execution import execute
from vrae.rules.universal_static import product
from vrae.rules.product_facts import extract, verify_facts
from vrae.intelligence.qwen.session import catalog as qwen_catalog

WHEEL = b'''<html><head><script>window.untrusted = true;</script></head>
<body><main><h1><span>Grinding wheel W100</span></h1>
<p>Source description of an industrial abrasive wheel for buyer review.</p>
<table><tr><td>Diameter</td><td><strong>100 mm</strong></td></tr>
<tr><td>Abrasive</td><td>Aluminium oxide</td></tr></table>
<a href="/contact.html">Request information</a></main></body></html>'''


def test_guarded_broken_discovery_links_are_valid_qwen_discover_anchors():
    pack = fixture(statuses={'/products': 404})
    _, _, facts, _ = source_chain(pack, pack.ref, diagnostic_version='l2-industrial-1.0.2')
    broken = [f for f in facts if f['rule_id'] == 'DISC-01']
    assert broken and all(f['source']['target_response']['http_status'] == 404 for f in broken)
    context = SimpleNamespace(catalog={'entries': {f['fact_ref']: {'type': 'GUARD_LITERAL', 'fact': f}
                              for f in broken}},
                              gateway_pins=SimpleNamespace(expected_evaluator_version='ra2b6-1.0.2'))
    assert all(row['task'] == 'DISCOVER' for row in qwen_catalog(context))


def test_generic_wheel_sources_become_exact_guard_anchors_without_pump_fields():
    pack = fixture(overrides={'/products/p40': WHEEL})
    extracted = extract(pack, expected_pack_ref=pack.ref, generic=True)
    assert extracted['extractor_version'] == 'ra2b2-product-facts-1.0.1'
    verify_facts(extracted, pack, expected_pack_ref=pack.ref)
    old = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b6-1.0.1')
    execution, _, facts, _ = source_chain(pack, pack.ref, diagnostic_version='l2-industrial-1.0.2')
    def product_row(value):
        return next(o for r in value['executions'] if r['rule_id'] == 'INFO-01'
                    for o in r['observations'] if o.get('source_page', {}).get('url', '').endswith('/p40'))
    assert product_row(old)['observation']['result'] == 'UNKNOWN'
    row = product_row(execution)
    assert row['observation']['result'] == 'PASS'
    assert any(c['text'] == '100 mm' for c in row['citations'])
    anchors = [f for f in facts if f['rule_id'] == 'INFO-01' and f['source']['citation']['url'].endswith('/p40')]
    assert anchors
    for fact in anchors:
        s = fact['source']
        body = pack.resolve(s['citation']['evidence_ref'], expected_pack_ref=pack.ref)['content']
        assert body[s['byte_start']:s['byte_end']] == s['quote'].encode()
    contact = next(r for r in execution['executions'] if r['rule_id'] == 'CTA-01')
    observed = [o for o in contact['observations'] if o.get('static_href_presence') == 'OBSERVED']
    assert observed and all(o['observation']['result'] == 'UNKNOWN' for o in observed)
    assert all(o['rendered_visibility'] == 'UNKNOWN' and o['citations'] for o in observed)


@pytest.mark.parametrize('body', [
    b'<main><h1 hidden>Hidden wheel</h1><table><tr><td>Diameter</td><td>100 mm</td></tr></table></main>',
    b'<main><h1>A</h1><h1>B</h1></main>',
    b'<main><h1 aria-hidden="true">Hidden</h1></main>',
])
def test_ambiguous_or_hidden_product_names_are_not_positive(body):
    with pytest.raises(ValueError):
        product(body)


def test_definition_lists_and_description_only_have_distinct_evidence():
    _, _, fields, descriptions = product(b'<main><h1>Wheel</h1><dl><dt>Grit</dt><dd><b>60</b></dd></dl><p>A source description long enough to retain as context.</p></main>')
    assert fields[0][1]['text'] == '60' and descriptions
    _, _, fields, descriptions = product(b'<main><h1>Wheel</h1><p>A source description without any verified specifications.</p></main>')
    assert not fields and descriptions
    # A unique display heading remains evidence even if the layout repeats it
    # elsewhere; boilerplate exclusion only resolves multiple-heading ambiguity.
    _, name, _, _ = product(b'<main><h1>Shared heading</h1><dl><dt>Grit</dt><dd>60</dd></dl></main>',
                            excluded_names={'Shared heading'})
    assert name['text'] == 'Shared heading'


def test_repeated_side_headings_are_excluded_only_by_same_pack_source_context():
    repeated = b'<h1>Shared navigation heading</h1>'
    body = b'<html><body><div id="main">'+repeated+WHEEL.split(b'<main>')[1].split(b'</main>')[0]+b'</div></body></html>'
    pack = fixture(overrides={'/products/p40': body, '/about': b'<html><body>'+repeated+b'</body></html>'})
    execution, _, _, _ = source_chain(pack, pack.ref, diagnostic_version='l2-industrial-1.0.2')
    row = next(o for r in execution['executions'] if r['rule_id'] == 'INFO-01' for o in r['observations']
               if o.get('source_page', {}).get('url', '').endswith('/p40'))
    assert row['observation']['result'] == 'PASS'
    assert next(c['text'] for c in row['citations'] if c['fact_role'] == 'NAME') == 'Grinding wheel W100'


def test_six_representative_pages_prioritize_contact_without_exceeding_limits():
    paths = ['/', '/products', '/products/wheel', '/contact.html', '/about.html', '/applications']
    html = b'<html><body><nav>' + b''.join(('<a href="'+p+'">Page</a>').encode() for p in paths[1:]) + b'</nav></body></html>'
    routes = {'https://example.org'+p: (200, {'content-type':'text/html'}, html) for p in paths}
    routes['https://example.org/robots.txt'] = (200, {'content-type':'text/plain'}, b'User-agent: *\nDisallow:\n')
    transport = SyntheticTransport(routes)
    result = asyncio.run(Collector(SafeFetcher(FixedDNS(), transport)).capture('representative-six', access(),
        limits=Limits(max_pages=6, interval_seconds=0.01), retain_raw_html=True, representative_pages=True))
    pages = result.manifest['pages']
    assert [p['snapshot']['url'] for p in pages] == ['https://example.org'+p for p in paths]
    result.verify()  # Original manifest role/hash contract stays unchanged.
    assert len(transport.calls) == 7
    assert representative_role('https://example.org/en/contact_us.html') == 'CONTACT'

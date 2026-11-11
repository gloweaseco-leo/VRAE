"""Source-text declarations only, not legal identity or a TRUST-01 judgment."""
from pathlib import Path
import asyncio
from copy import deepcopy
from html import unescape
import json

import pytest

from tests.collection.test_pipeline import FixedDNS, SyntheticTransport
from tests.collection.test_security import access
from vrae.collection.collector import Collector
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Limits
from vrae.collection.manifest import document_hash
from vrae.evidence import build_pack, EvidenceError, EvidencePack
from vrae.rules.trust_facts import extract, verify_facts, VERSION

FIXTURES = Path(__file__).parents[1] / 'fixtures/sites'


def trust_pack(name='about', *, retained=True, about=None, contact=None, status=200,
               home=None, home_status=200, contact_status=200, max_pages=5, blocked=None,
               redirect=None):
    # Fixed synthetic transport inputs use UTF-8/LF across Git checkout platforms.
    html = (FIXTURES / f'trust-{name}.html').read_text(encoding='utf-8').encode('utf-8') if about is None else about
    routes = {
        'https://example.org/': (home_status, {'content-type': 'text/html'}, home if home is not None else
            b'<html><nav><a href="/about">About</a><a href="/contact">Contact</a></nav></html>'),
        'https://example.org/about': (status, {'content-type': 'text/html'}, html),
        'https://example.org/contact': (contact_status, {'content-type': 'text/html'},
            (FIXTURES / 'trust-contact.html').read_text(encoding='utf-8').encode('utf-8') if contact is None else contact),
    }
    routes['https://example.org/robots.txt'] = (200, {'content-type': 'text/plain'},
        b'User-agent: *\nDisallow: /about\n' if blocked == 'robots' else b'User-agent: *\nDisallow:\n')
    if blocked == 'waf':
        routes['https://example.org/about'] = (200, {'content-type': 'text/html'}, b'<html>Verify you are human</html>')
    if redirect:
        routes['https://example.org/contact'] = (302, {'location': redirect}, b'')
        routes['https://example.org' + redirect] = (200, {'content-type': 'text/html'},
            (FIXTURES / 'trust-contact.html').read_text(encoding='utf-8').encode('utf-8'))
    transport = SyntheticTransport(routes)
    bundle = asyncio.run(Collector(SafeFetcher(FixedDNS(), transport)).capture(
        'run-trust-facts', access(), limits=Limits(max_pages=max_pages, interval_seconds=0.01),
        retain_raw_html=retained))
    assert all(call[1] == 'GET' for call in transport.calls)
    return build_pack([bundle])


def run(pack):
    return extract(pack, expected_pack_ref=pack.ref)


def page(output, path='/about'):
    return next(p for p in output['pages'] if p['source_page']['url'] == 'https://example.org' + path)


def reseal(output):
    output['facts_ref'] = 'tf-' + document_hash({k: v for k, v in output.items() if k != 'facts_ref'})
    return output


@pytest.fixture(scope='module')
def positive():
    pack = trust_pack()
    return pack, run(pack)


def test_positive_original_self_description_and_static_contact_link():
    pack = trust_pack()
    result = extract(pack, expected_pack_ref=pack.ref)
    assert result['status'] == 'EXTRACTED'
    assert result['trust01_enabled'] is False
    about = next(p for p in result['pages'] if p['source_page']['url'].endswith('/about'))
    name = next(f for f in about['facts'] if f['kind'] == 'DECLARED_NAME')
    assert name['citation']['text'] == 'Heshan Meridian Valve Works'
    assert name['citation']['element']['line'] == 3
    verify_facts(result, pack, expected_pack_ref=pack.ref)


def test_complete_raw_citations_and_independent_response_edges(positive):
    pack, result = positive
    assert result == run(pack) and result['extractor_version'] == VERSION
    assert result['trust01_result'] == 'UNKNOWN'
    about = page(result)
    assert {f['kind'] for f in about['facts']} == {'DECLARED_NAME', 'SELF_DESCRIPTION', 'STATIC_CONTACT_LINK'}
    for row in result['pages']:
        assert row['status'] == 'EXTRACTED' and row['evidence_ids']
        for fact in row['facts']:
            for citation in (fact['citation'], fact.get('label_citation')):
                if citation is None:
                    continue
                resolved = pack.resolve(citation['evidence_ref'], expected_pack_ref=pack.ref)
                assert citation['content_sha256'] == resolved['evidence']['content_sha256']
                assert citation['source_ref'] == resolved['evidence']['source_ref']
                assert citation['snapshot_ref'] == resolved['evidence']['snapshot_ref']
                assert citation['locator'] == resolved['evidence']['locator']
                assert citation['observed_at'] == resolved['snapshot']['observed_at']
                assert citation['url'] == row['source_page']['url']
                raw = resolved['content'].decode('utf-8')
                pos = citation['element']
                offset = sum(len(s) + 1 for s in raw.split('\n')[:pos['line'] - 1]) + pos['column']
                assert raw[offset:].startswith(citation['raw_element'])
                assert citation['raw_element'].startswith(pos['start_tag'])
                inner = citation['raw_element'].split('>', 1)[1].rsplit('</', 1)[0]
                assert unescape(inner) == citation['text']
    link = next(f for f in about['facts'] if f['kind'] == 'STATIC_CONTACT_LINK')
    assert link['raw_href'] == '/contact'
    assert link['citation']['element'] == {
        'line': 8, 'column': 0, 'path': '/html[1]/main[1]/a[3]',
        'start_tag': '<a href="/contact">'}
    assert link['target_scope'] == 'CAPTURED_RESPONSE_METADATA_ONLY'
    target = link['target_responses'][0]
    assert target == page(result, '/contact')['source_page']
    assert target['http_status'] == 200 and target['redirect_trace'] and target['error'] is None
    contact = page(result, '/contact')
    assert {f['kind'] for f in contact['facts']} == {'DECLARED_NAME', 'ADDRESS_TEXT', 'STATIC_CONTACT_LINK'}
    endpoints = [f for f in contact['facts'] if f['kind'] == 'STATIC_CONTACT_LINK']
    assert {f['endpoint_kind'] for f in endpoints} == {'MAILTO_LITERAL', 'TEL_LITERAL'}
    assert all(f['target_responses'] == [] for f in endpoints)


def test_different_industrial_entities_remain_unresolved():
    output = run(trust_pack('mixed', contact=b'<html></html>'))
    assert output['status'] == 'UNKNOWN'
    row = page(output)
    assert row['status'] == 'UNKNOWN' and row['evidence_ids'] == []
    assert row['reason'] == 'MULTIPLE_DECLARED_NAMES_UNRESOLVED'
    assert [f['citation']['text'] for f in row['facts'] if f['kind'] == 'DECLARED_NAME'] == [
        'Qinglan Precision Drives Ltd', 'Harbor Motion Export Group']
    assert all(p['status'] != 'EXTRACTED' for p in output['pages'])


def test_conflicting_names_across_pages_are_not_resolved_to_one_company():
    contact = (FIXTURES / 'trust-contact.html').read_bytes().replace(
        b'Heshan Meridian Valve Works', b'Other Pump Systems')
    output = run(trust_pack(contact=contact))
    assert output['status'] == 'UNKNOWN'
    assert all(p['status'] != 'EXTRACTED' and p['evidence_ids'] == [] for p in output['pages'])


@pytest.mark.parametrize('about', [
    b'<html><main></main></html>', b'<html><h1>Gearbox Supplier</h1><p>Welcome</p></html>',
    b'<html><main id="company"></main><script>render()</script></html>',
    b'<html><div itemprop="name">Unscoped name</div></html>',
    b'<html><main itemscope itemtype="https://schema.org/Organization"><h1 itemprop="name">A</h1></main>'
    b'<main itemscope itemtype="https://schema.org/Organization"><h1 itemprop="name">B</h1></main></html>',
    b'<html><table><tr><th>Company name</th><td></td></tr></table></html>',
    b'<html><table><tr><th>Company name</th><td><b>A</b></td></tr></table></html>',
    b'<html><address><span>Nested contact</span></address></html>',
    b'<html><section><h2>About us</h2><p><b>Nested prose</b></p></section></html>',
    b'<html><tr><th>Company name</th><td>A</td></tr></html>',
    b'<html><table><tr><th>Company name</th><td>A</td></tr>',
    b'<html><div hidden><address>A</address></div></html>',
    b'<html><div aria-hidden="true"><address>A</address></div></html>',
    b'<html><div style="display:none"><address>A</address></div></html>',
    b'<html><template><address>A</address></template></html>',
    b'<html><base href="https://other.example/"><address>A</address></html>',
    b'<html><a href="/contact" href="/rfq">Contact</a></html>',
    b'<html><a href="javascript:send()">Contact</a></html>',
    b'<html><a href="https://other.example/contact">Contact</a></html>',
    b'<html><a href="mailto:sales@example.org?subject=RFQ">Contact</a></html>',
    b'<html><a href="tel:invalid">Contact</a></html>',
    b'<html><a href="/contact"><span>Contact</span></a></html>',
    b'<html>' + b'<div>' * 34 + b'</div>' * 34 + b'</html>',
    b'<html>' + b'<br>' * 2050 + b'</html>', b'<html>' + b'x' * 131073 + b'</html>',
])
def test_unsupported_or_ambiguous_static_scope_is_unknown(about):
    output = run(trust_pack(about=about, contact=b'<html></html>'))
    assert output['status'] == 'UNKNOWN'
    row = page(output)
    assert row['status'] == 'UNKNOWN' and row['evidence_ids'] == []
    assert row['facts'] == []
    assert output['trust01_result'] == 'UNKNOWN'


def test_js_fixture_and_missing_raw_are_unknown():
    js = run(trust_pack('js', contact=b'<html></html>'))
    assert js['status'] == 'UNKNOWN' and page(js)['facts'] == []
    missing = run(trust_pack(retained=False))
    assert missing['status'] == 'UNKNOWN'
    assert all(p['status'] == 'UNKNOWN' and p['facts'] == [] and p['evidence_ids'] == [] for p in missing['pages'])


@pytest.mark.parametrize('kwargs,aggregate', [({'status': 403}, 'UNKNOWN'),
    ({'blocked': 'waf'}, 'UNKNOWN'), ({'blocked': 'robots'}, 'EXTRACTED')])
def test_access_denial_is_preserved_not_a_company_defect(kwargs, aggregate):
    output = run(trust_pack(**kwargs))
    row = page(output)
    assert row['status'] == 'ACCESS_BLOCKED' and row['evidence_ids'] == [] and row['facts'] == []
    assert row['source_page']['error']['code'] in {'ACCESS_BLOCKED', 'ROBOTS_DISALLOWED'}
    assert output['status'] == aggregate
    if aggregate == 'EXTRACTED':
        # Robots denied ABOUT; independently captured CONTACT still declares a name.
        assert page(output, '/contact')['status'] == 'EXTRACTED'


def test_entire_capture_blocked_and_browser_only_input():
    from tests.evidence.synthetic import browser
    blocked = run(trust_pack(home_status=403))
    assert blocked['status'] == 'ACCESS_BLOCKED'
    assert all(p['facts'] == [] and p['evidence_ids'] == [] for p in blocked['pages'])
    output = run(build_pack([browser(True)]))
    assert output['pages'] == [] and output['status'] == 'UNKNOWN'


@pytest.mark.parametrize('status', [404, 410, 500])
def test_incomplete_or_error_page_has_no_source_text_facts(status):
    output = run(trust_pack(status=status))
    row = page(output)
    assert row['status'] == 'UNKNOWN' and row['facts'] == [] and row['evidence_ids'] == []
    assert row['source_page']['http_status'] == status


def test_unvisited_contact_is_only_a_static_link_not_reachability():
    output = run(trust_pack(max_pages=1))
    assert output['status'] == 'UNKNOWN'
    assert {c['url'] for c in output['unvisited_candidates']} == {
        'https://example.org/about', 'https://example.org/contact'}
    links = [f for f in output['pages'][0]['facts'] if f['kind'] == 'STATIC_CONTACT_LINK']
    assert len(links) == 1 and links[0]['target_responses'] == []
    assert links[0]['target_scope'] == 'TARGET_NOT_CAPTURED'


@pytest.mark.parametrize('status', [403, 404, 410, 500])
def test_bad_target_status_does_not_invent_company_or_link_judgments(status):
    output = run(trust_pack(contact_status=status))
    assert output['status'] == 'EXTRACTED'  # Name + observed href only, even when target fails.
    link = next(f for f in page(output)['facts'] if f['kind'] == 'STATIC_CONTACT_LINK')
    target = link['target_responses'][0]
    assert target['http_status'] == status and target['error'] and target['redirect_trace']
    assert target['snapshot']['snapshot_ref'] == target['snapshot_ref']
    assert output['trust01_enabled'] is False and output['trust01_result'] == 'UNKNOWN'


def test_entities_unicode_and_whitespace_are_original_source_text():
    html = ('<html><table><tr><th>Company name</th><td> 岚山 &amp; Pumps </td></tr></table>'
            '<a href="/contact"> 联系我们 </a></html>').encode('utf-8')
    output = run(trust_pack(about=html, contact=b'<html></html>'))
    name = page(output)['facts'][0]['citation']
    assert output['status'] == 'EXTRACTED'
    assert name['text'] == ' 岚山 & Pumps ' and '&amp;' in name['raw_element']


@pytest.mark.parametrize('mutation', [
    'name', 'intro', 'address', 'href', 'endpoint', 'element_line', 'element_column', 'element_path',
    'start_tag', 'raw_element', 'hash', 'evidence_ref', 'source_ref', 'snapshot_ref', 'locator',
    'url', 'time', 'target_status', 'target_trace', 'target_source', 'target_snapshot', 'target_error',
    'missing_target', 'invented_target', 'scope', 'coverage', 'enabled', 'status', 'version', 'unvisited',
])
def test_rehashed_outer_result_cannot_forge_source_or_response_metadata(positive, mutation):
    pack, original = positive
    output = deepcopy(original)
    about = page(output)
    citation = next(f['citation'] for f in about['facts'] if f['kind'] == 'DECLARED_NAME')
    link = next(f for f in about['facts'] if f['kind'] == 'STATIC_CONTACT_LINK')
    if mutation in {'name', 'intro', 'address'}:
        kind = {'name': 'DECLARED_NAME', 'intro': 'SELF_DESCRIPTION', 'address': 'ADDRESS_TEXT'}[mutation]
        next(f for p in output['pages'] for f in p['facts'] if f['kind'] == kind)['citation']['text'] = 'Fabricated'
    elif mutation in {'href', 'endpoint'}:
        link['raw_href' if mutation == 'href' else 'endpoint'] = '/invented'
    elif mutation.startswith('element_'):
        key = mutation.removeprefix('element_')
        citation['element'][key] = '/invented' if key == 'path' else 999
    elif mutation in {'start_tag', 'raw_element', 'hash', 'evidence_ref', 'source_ref', 'snapshot_ref', 'locator', 'url', 'time'}:
        if mutation == 'start_tag':
            citation['element']['start_tag'] = '<fake>'
        else:
            citation[{'hash': 'content_sha256', 'time': 'observed_at'}.get(mutation, mutation)] = 'fake'
    elif mutation.startswith('target_'):
        key, value = {'target_status': ('http_status', 404), 'target_trace': ('redirect_trace', []),
            'target_source': ('source_ref', 'fake'), 'target_snapshot': ('snapshot_ref', 'fake'),
            'target_error': ('error', {'code': 'HTTP_ERROR'})}[mutation]
        link['target_responses'][0][key] = value
    elif mutation == 'missing_target':
        del link['target_responses']
    elif mutation == 'invented_target':
        link['target_responses'].append(deepcopy(link['target_responses'][0]))
    else:
        key, value = {'scope': ('run_id', 'other'), 'coverage': ('coverage', []),
            'enabled': ('trust01_enabled', True), 'status': ('status', 'TRUSTWORTHY'),
            'version': ('extractor_version', 'future'), 'unvisited': ('unvisited_candidates', [])}[mutation]
        # Positive fixture has no unvisited pages; invent one instead of a no-op mutation.
        output[key] = [{'url': 'https://example.org/fake'}] if mutation == 'unvisited' else value
    with pytest.raises(EvidenceError, match='TRUST_FACTS_INTEGRITY'):
        verify_facts(reseal(output), pack, expected_pack_ref=pack.ref)


@pytest.mark.parametrize('field', ['tenant_id', 'run_id', 'policy_id', 'policy_version'])
def test_scope_drift_with_recomputed_pack_hash_is_rejected(positive, field):
    pack, _ = positive
    doc = pack.document
    doc[field] = 2 if field == 'policy_version' else 'other'
    doc['pack_ref'] = 'ep-' + document_hash({k: v for k, v in doc.items() if k != 'pack_ref'})
    forged = EvidencePack(json.dumps(doc).encode(), tuple(sorted(pack.objects.items())))
    with pytest.raises(EvidenceError):
        extract(forged, expected_pack_ref=pack.ref)


def test_changed_original_bytes_and_other_valid_packs_fail_the_trusted_pin(positive):
    pack, output = positive
    blobs = dict(pack.objects)
    key = next(k for k, v in blobs.items() if b'Heshan Meridian' in v)
    blobs[key] = blobs[key].replace(b'Heshan Meridian', b'Invented Company')
    forged = EvidencePack(pack._payload, tuple(sorted(blobs.items())))
    with pytest.raises(EvidenceError):
        verify_facts(output, forged, expected_pack_ref=pack.ref)
    other = trust_pack('mixed')
    with pytest.raises(EvidenceError):
        extract(other, expected_pack_ref=pack.ref)


@pytest.mark.parametrize('pin', [None, '', 'ep-' + '0' * 64])
def test_separately_trusted_pin_is_required(positive, pin):
    pack, output = positive
    with pytest.raises(EvidenceError):
        extract(pack, expected_pack_ref=pin)
    with pytest.raises(EvidenceError):
        verify_facts(output, pack, expected_pack_ref=pin)


def test_cross_site_pack_is_rejected_by_existing_unmodified_guard():
    from tests.evidence.synthetic import http
    from tests.evidence.test_site_coherence import relocate_browser
    with pytest.raises(EvidenceError):
        build_pack([http(), relocate_browser(True)])


def test_output_is_detached_and_oversize_replay_is_refused(positive):
    pack, output = positive
    detached = run(pack)
    detached['pages'][0]['facts'].clear()
    assert run(pack) == output
    oversized = deepcopy(output)
    oversized['padding'] = 'x' * 8_000_001
    with pytest.raises(EvidenceError):
        verify_facts(reseal(oversized), pack, expected_pack_ref=pack.ref)


def test_no_execution_or_finding_integration_and_legacy_outputs_unchanged(positive):
    from vrae.rules import execute
    pack, _ = positive
    for version in ('ra2b0-1.0.0', 'ra2b1-1.0.0', 'ra2b3-1.0.0'):
        before = execute(pack, expected_pack_ref=pack.ref, evaluator_version=version)
        result = run(pack)
        assert execute(pack, expected_pack_ref=pack.ref, evaluator_version=version) == before
        trust = next(e for e in before['executions'] if e['rule_id'] == 'TRUST-01')
        assert trust['enabled'] is False
        assert all(r['observation']['result'] == 'UNKNOWN' for r in trust['observations'])
        assert 'executions' not in result and 'observations' not in result and 'items' not in result


def test_unresolved_microdata_scope_is_not_rescued_by_another_page_name():
    output = run(trust_pack(about=b'<html><div itemprop="name">Unscoped brand</div></html>'))
    assert output['status'] == 'UNKNOWN' and page(output)['entity_scope_ambiguous'] is True
    assert all(p['status'] != 'EXTRACTED' and not p['evidence_ids'] for p in output['pages'])


def test_chinese_exact_structural_labels_not_fuzzy_identity_inference():
    raw = ('<html><table><tr><th>公司名称</th><td> 岚山泵业（虚构） </td></tr></table>'
           '<section><h2>公司简介</h2><p>我们自称提供工业泵零部件。</p></section>'
           '<a href="/contact">联系我们</a></html>').encode('utf-8')
    output = run(trust_pack(about=raw, contact=b'<html></html>'))
    assert output['status'] == 'EXTRACTED'
    facts = page(output)['facts']
    assert facts[0]['label_citation']['text'] == '公司名称'
    assert facts[0]['citation']['text'] == ' 岚山泵业（虚构） '
    assert facts[1]['citation']['text'] == '我们自称提供工业泵零部件。'


def test_contact_redirect_metadata_is_complete_but_not_reachability_judgment():
    output = run(trust_pack(redirect='/contact-us'))
    link = next(f for f in page(output)['facts'] if f['kind'] == 'STATIC_CONTACT_LINK')
    target = link['target_responses'][0]
    assert target['url'] == 'https://example.org/contact'
    assert target['final_url'] == 'https://example.org/contact-us'
    assert [hop['status'] for hop in target['redirect_trace']] == [302, 200]
    assert target['error'] is None
    assert link['target_scope'] == 'CAPTURED_RESPONSE_METADATA_ONLY'


def test_fact_count_bound_and_output_byte_bound(positive, monkeypatch):
    from vrae.rules import trust_facts
    output = run(trust_pack(about=b'<html>' + b'<a href="/contact">C</a>' * 129 + b'</html>',
                            contact=b'<html></html>'))
    assert page(output)['status'] == 'UNKNOWN' and page(output)['facts'] == []
    pack, original = positive
    monkeypatch.setattr(trust_facts, 'MAX_BYTES', len(trust_facts._encode(original)) - 1)
    with pytest.raises(EvidenceError):
        extract(pack, expected_pack_ref=pack.ref)


def test_invalid_utf8_is_unknown_without_retained_fact_ids():
    output = run(trust_pack(about=b'<html>\xff</html>', contact=b'<html></html>'))
    assert page(output)['status'] == 'UNKNOWN' and page(output)['evidence_ids'] == []


def test_new_sealed_fixture_replays_all_three_industrial_sites():
    import base64
    data = json.loads((Path(__file__).parent / 'fixtures/trust-source-facts.json').read_text(encoding='utf-8'))
    assert data['synthetic_only'] is True and data['expected_extractor_version'] == VERSION
    assert len(data['cases']) == 3
    assert [c['facts']['status'] for c in data['cases']] == ['EXTRACTED', 'UNKNOWN', 'UNKNOWN']
    for case in data['cases']:
        pack = EvidencePack.load(case['document'], {
            k: base64.b64decode(v, validate=True) for k, v in case['objects_base64'].items()
        }, expected_ref=case['expected_pack_ref'])
        verify_facts(case['facts'], pack, expected_pack_ref=case['expected_pack_ref'])
        assert case['facts']['facts_ref'] == case['expected_facts_ref']


@pytest.mark.parametrize('prefix', ['<html>\r<main>\n', '<html>\r\n<main>\r\n',
                                   '<html>\u2028<main>\n', '<html>\u0085<main>\n'])
def test_exact_slices_with_cr_lf_and_unicode_separator_characters(prefix):
    raw = prefix + '<address>Office &amp; sales</address></main></html>'
    output = run(trust_pack(about=raw.encode('utf-8'), contact=b'<html></html>'))
    citation = next(f['citation'] for f in page(output)['facts'] if f['kind'] == 'ADDRESS_TEXT')
    assert citation['raw_element'] == '<address>Office &amp; sales</address>'
    offset = raw.index('<address>')
    assert citation['element']['line'] == raw[:offset].count('\n') + 1
    assert citation['element']['column'] == len(raw[:offset].rsplit('\n', 1)[-1])

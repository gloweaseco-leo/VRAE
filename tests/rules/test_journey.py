"""Offline category/product/contact journeys; captured links, never form actions."""
import asyncio
import base64
from copy import deepcopy
import json
from pathlib import Path
import re

import pytest

from tests.collection.test_pipeline import FixedDNS, SyntheticTransport
from tests.collection.test_security import access
from vrae.collection.collector import Collector
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Limits
from vrae.collection.manifest import CaptureBundle, document_hash
from vrae.domain.contracts import validate_contract
from vrae.evidence import EvidenceError, EvidencePack, build_pack
from vrae.rules import execute, verify_execution

URLS = ['https://example.org/', 'https://example.org/category/valves',
        'https://example.org/products/valve-v1', 'https://example.org/contact']


def journey_pack(stage=3, status=200, *, retained=True, max_pages=5, markup=None,
                 blocked=None, repeats=1, extra_broken=False, redirect=None):
    bodies = [b'<html><nav><a href="/category/valves">Valves</a></nav></html>',
        b'<html><main><a href="/products/valve-v1">Valve V1</a></main></html>',
        b'<html><h1>Valve V1</h1><a href="/contact">Contact about this product</a></html>',
        b'<html><h1>Contact</h1><form method="post" action="/send"><input name="message"></form></html>']
    if markup is not None:
        bodies[stage - 1] = markup
    if repeats > 1:
        bodies = [re.sub(b'(<a .*?</a>)', lambda match: match[0] * repeats, body) for body in bodies]
    extra = '/products/broken' if stage == 2 else '/rfq'
    if extra_broken:
        bodies[stage - 1] = bodies[stage - 1].replace(b'</html>',
            b'<a href="' + extra.encode() + b'">Other path</a></html>')
    routes = {url: (status if index == stage else 200,
                   {'content-type': 'text/html'}, bodies[index]) for index, url in enumerate(URLS)}
    routes['https://example.org/robots.txt'] = (
        200, {'content-type': 'text/plain'}, b'User-agent: *\nDisallow:\n')
    if extra_broken:
        routes['https://example.org' + extra] = (404, {'content-type': 'text/html'}, b'<html>404</html>')
    if redirect:
        routes[URLS[stage]] = (302, {'location': redirect}, b'')
        routes['https://example.org' + redirect] = (200, {'content-type': 'text/html'}, bodies[stage])
    if blocked == 'robots':
        routes['https://example.org/robots.txt'] = (200, {'content-type': 'text/plain'},
            b'User-agent: *\nDisallow: ' + URLS[stage].split('example.org')[1].encode() + b'\n')
    elif blocked == 'waf':
        routes[URLS[stage]] = (200, {'content-type': 'text/html'}, b'<html>Verify you are human</html>')
    transport = SyntheticTransport(routes)
    collector = Collector(SafeFetcher(FixedDNS(), transport))
    source = asyncio.run(collector.capture('run-synthetic', access(),
        limits=Limits(max_pages=max_pages, interval_seconds=0.01), retain_raw_html=retained))
    assert all(method[0] != 'https://example.org/send' for method in transport.calls)
    assert all(call[1] == 'GET' for call in transport.calls)
    return build_pack([source])


def rows(output, rule):
    return next(e for e in output['executions'] if e['rule_id'] == rule)['observations']


def run(pack):
    return execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b1-1.0.0')


@pytest.mark.parametrize('rule,stage', [('DISC-02', 2), ('CTA-02', 3)])
@pytest.mark.parametrize('status,expected', [(200, 'PASS'), (404, 'FAIL_WITH_EVIDENCE'),
    (410, 'FAIL_WITH_EVIDENCE'), (403, 'ACCESS_BLOCKED'), (500, 'UNKNOWN')])
def test_captured_journey_edge(rule, stage, status, expected):
    pack = journey_pack(stage, status)
    output = run(pack)
    row = rows(output, rule)[0]
    assert row['observation']['result'] == expected
    validate_contract('Observation', row['observation'])
    if expected in ('PASS', 'FAIL_WITH_EVIDENCE'):
        assert row['target_response']['http_status'] == status
        assert row['target_response']['redirect_trace'][-1]['status'] == status
        assert row['citations'][0]['raw_href'] == URLS[stage].split('example.org')[1]
        for ref in row['observation']['evidence_ids']:
            assert pack.resolve(ref, expected_pack_ref=pack.ref)['content'] is not None
    else:
        assert row['observation']['evidence_ids'] == []
    verify_execution(output, pack, expected_pack_ref=pack.ref,
                     expected_evaluator_version='ra2b1-1.0.0')


def test_complete_home_category_product_contact_path_and_old_results():
    pack = journey_pack()
    output = run(pack)
    assert output == run(pack)
    assert len(output['journeys']) == 1
    path = output['journeys'][0]
    assert path['complete']
    assert [step['rule_id'] for step in path['steps']] == ['DISC-01', 'DISC-02', 'CTA-02']
    assert [step['source_page']['url'] for step in path['steps']] == URLS[:-1]
    assert [step['target_response']['url'] for step in path['steps']] == URLS[1:]
    assert all(step['result'] == 'PASS' for step in path['steps'])
    assert output['recorded_capture_scope'][0]['policy_version'] == pack.document['policy_version']
    old = execute(pack, expected_pack_ref=pack.ref)
    assert old['evaluator_version'] == 'ra2b0-1.0.0'
    assert not next(e for e in old['executions'] if e['rule_id'] == 'CTA-02')['enabled']
    verify_execution(old, pack, expected_pack_ref=pack.ref)
    assert rows(old, 'DISC-01') == rows(output, 'DISC-01')
    with pytest.raises(EvidenceError):
        verify_execution(old, pack, expected_pack_ref=pack.ref,
                         expected_evaluator_version='ra2b1-1.0.0')
    for execution in output['executions']:
        if execution['rule_id'] not in ('DISC-01', 'DISC-02', 'CTA-02'):
            assert all(row['observation']['result'] == 'UNKNOWN' for row in execution['observations'])


@pytest.mark.parametrize('rule,stage', [('DISC-02', 2), ('CTA-02', 3)])
@pytest.mark.parametrize('blocked', ['robots', 'waf'])
def test_target_robots_and_waf_are_not_defects(rule, stage, blocked):
    pack = journey_pack(stage, blocked=blocked)
    assert rows(run(pack), rule)[0]['observation']['result'] == 'ACCESS_BLOCKED'


@pytest.mark.parametrize('rule,stage', [('DISC-02', 2), ('CTA-02', 3)])
@pytest.mark.parametrize('missing', ['source_raw', 'target_raw', 'unvisited', 'source_role'])
def test_evidence_gaps_stay_unknown(rule, stage, missing):
    pack = journey_pack(max_pages=stage if missing == 'unvisited' else
                        1 if missing == 'source_role' else 5)
    if missing in ('source_raw', 'target_raw'):
        source = pack.document['sources'][0]
        manifest = source['document']
        objects = {key: pack.objects[value] for key, value in source['object_refs'].items()}
        page = next(p for p in manifest['pages']
                    if p['snapshot']['url'] == URLS[stage - 1 if missing == 'source_raw' else stage])
        objects.pop(page['snapshot']['private_object_ref'])
        page['snapshot']['private_object_ref'] = None
        page['raw_retained'] = False
        manifest['manifest_sha256'] = document_hash({k: v for k, v in manifest.items()
                                                   if k != 'manifest_sha256'})
        source_bundle = CaptureBundle(manifest, objects)
        source_bundle.verify()
        pack = build_pack([source_bundle])
    output = run(pack)
    assert rows(output, rule)[0]['observation']['result'] == 'UNKNOWN'
    assert not output['journeys'][0]['complete']


@pytest.mark.parametrize('rule,stage', [('DISC-02', 2), ('CTA-02', 3)])
@pytest.mark.parametrize('mutation', ['status', 'trace', 'source', 'snapshot', 'raw_href',
    'evidence_ref', 'scope', 'statement', 'path', 'version', 'missing_response'])
def test_resealed_execution_cannot_forge_response_or_path(rule, stage, mutation):
    pack = journey_pack(stage, 404)
    output = deepcopy(run(pack))
    row = rows(output, rule)[0]
    if mutation == 'status':
        row['target_response']['http_status'] = 200
    elif mutation == 'trace':
        row['target_response']['redirect_trace'] = []
    elif mutation == 'source':
        row['target_response']['source_ref'] = row['source_page']['source_ref'] + 'fake'
    elif mutation == 'snapshot':
        row['target_response']['snapshot_ref'] = row['source_page']['snapshot_ref']
    elif mutation in ('raw_href', 'evidence_ref'):
        row['citations'][0][mutation] = 'fabricated'
    elif mutation == 'scope':
        row['observation']['tenant_id'] = 'other-tenant'
    elif mutation == 'statement':
        row['observation']['statement'] = 'Inquiry delivered with SKU context'
    elif mutation == 'path':
        output['journeys'][0]['complete'] = True
    elif mutation == 'missing_response':
        del row['target_response']
    else:
        output['evaluator_version'] = 'ra2b2-1.0.0'
    output['execution_ref'] = 'rx-' + document_hash({
        k: v for k, v in output.items() if k != 'execution_ref'})
    with pytest.raises(EvidenceError):
        verify_execution(output, pack, expected_pack_ref=pack.ref)


@pytest.mark.parametrize('rule,stage', [('DISC-02', 2), ('CTA-02', 3)])
@pytest.mark.parametrize('markup', [b'<html><form action="/contact"></form></html>',
    b'<html><a href="https://unrelated.example/products/valve-v1">Other</a></html>',
    b'<html><a href="#">Dynamic</a><script>/* fetch products */</script></html>',
    b'<html><base href="https://unrelated.example/"><a href="/contact">Contact</a></html>'])
def test_unsupported_paths_never_become_claims(rule, stage, markup):
    pack = journey_pack(stage, markup=markup)
    assert rows(run(pack), rule)[0]['observation']['result'] == 'UNKNOWN'


@pytest.mark.parametrize('mutation', ['blob', 'run', 'cross-site'])
def test_untrusted_source_rejected_before_journey(mutation):
    pack = journey_pack()
    doc, objects = pack.document, dict(pack.objects)
    if mutation == 'blob':
        objects[next(iter(objects))] = b'fake href'
    elif mutation == 'run':
        doc['run_id'] = 'other-run'
    else:
        from tests.evidence.test_site_coherence import relocate_browser
        from tests.evidence.synthetic import http
        with pytest.raises(EvidenceError):
            build_pack([http(), relocate_browser(True)])
        return
    doc['pack_ref'] = 'ep-' + document_hash({k: v for k, v in doc.items() if k != 'pack_ref'})
    tampered = EvidencePack(json.dumps(doc).encode(), tuple(sorted(objects.items())))
    with pytest.raises(EvidenceError):
        run(tampered)


def test_wrong_or_missing_pin_and_unsupported_version_rejected():
    pack = journey_pack()
    for ref in (None, '', 'ep-' + '0' * 64):
        with pytest.raises(EvidenceError):
            execute(pack, expected_pack_ref=ref, evaluator_version='ra2b1-1.0.0')
    with pytest.raises(EvidenceError):
        execute(pack, expected_pack_ref=pack.ref, evaluator_version='future-2.0.0')


@pytest.mark.parametrize('rule,stage', [('DISC-02', 2), ('CTA-02', 3)])
def test_one_broken_link_does_not_fail_other_paths(rule, stage):
    pack = journey_pack(stage, extra_broken=True)
    output = run(pack)
    assert {row['observation']['result'] for row in rows(output, rule)} == {'PASS', 'FAIL_WITH_EVIDENCE'}
    assert any(path['complete'] for path in output['journeys'])
    assert any(path['terminal_result'] == 'FAIL_WITH_EVIDENCE' for path in output['journeys'])


@pytest.mark.parametrize('rule,stage,redirect', [('DISC-02', 2, '/products/valve-final'),
    ('CTA-02', 3, '/contact-us'), ('DISC-02', 2, '/landing'), ('CTA-02', 3, '/landing')])
def test_redirect_final_role_and_exact_trace(rule, stage, redirect):
    pack = journey_pack(stage, redirect=redirect)
    row = rows(run(pack), rule)[0]
    assert row['observation']['result'] == ('UNKNOWN' if redirect == '/landing' else 'PASS')
    assert row['target_response']['final_url'] == 'https://example.org' + redirect
    assert len(row['target_response']['redirect_trace']) == 2


def test_composed_path_count_is_bounded_and_truncation_is_explicit():
    pack = journey_pack(repeats=9)
    output = run(pack)
    assert len(output['journeys']) == 256
    assert output['journey_composition']['truncated'] is True
    assert all(path['complete'] for path in output['journeys'])


def test_sealed_industrial_journey_and_legacy_refs_replay():
    data = json.loads((Path(__file__).parents[1] /
        'fixtures/rules/industrial-journey.json').read_text(encoding='utf-8'))
    pack = EvidencePack.load(data['document'], {
        k: base64.b64decode(v, validate=True) for k, v in data['objects_base64'].items()
    }, expected_ref=data['expected_pack_ref'])
    verify_execution(data['expected_execution'], pack, expected_pack_ref=data['expected_pack_ref'],
                     expected_evaluator_version='ra2b1-1.0.0')
    assert run(pack) == data['expected_execution']
    assert execute(pack, expected_pack_ref=pack.ref)['execution_ref'] == data['expected_legacy_execution_ref']

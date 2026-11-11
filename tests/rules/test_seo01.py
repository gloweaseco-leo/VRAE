"""Bounded original head metadata, not indexing, ranking or SEO-health claims."""
import asyncio
import base64
from copy import deepcopy
import json
from pathlib import Path

import pytest

from tests.collection.test_pipeline import FixedDNS, SyntheticTransport
from tests.collection.test_security import access
from vrae.collection.collector import Collector
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Limits
from vrae.collection.manifest import document_hash
from vrae.domain.contracts import validate_contract
from vrae.evidence import EvidenceError, EvidencePack, build_pack
from vrae.rules import execute, verify_execution

VERSION = 'ra2b4-1.0.0'
HTML = (b'<html>\n<head>\n<title>Industrial valves &amp; pump components</title>\n'
        b'<link rel="canonical" href="/">\n<meta name="description" '
        b'content="Synthetic industrial components catalog">\n</head>\n<body>Valve components</body></html>')


def seo_pack(markup=HTML, *, retained=True, status=200, blocked=None):
    routes = {'https://example.org/': (status, {'content-type': 'text/html'}, markup),
              'https://example.org/robots.txt':
                  (200, {'content-type': 'text/plain'}, b'User-agent: *\nDisallow:\n')}
    if blocked == 'waf':
        routes['https://example.org/'] = (200, {'content-type': 'text/html'}, b'<html>Verify you are human</html>')
    elif blocked == 'robots':
        routes['https://example.org/robots.txt'] = (
            200, {'content-type': 'text/plain'}, b'User-agent: *\nDisallow: /\n')
    source = asyncio.run(Collector(SafeFetcher(FixedDNS(), SyntheticTransport(routes))).capture(
        'run-seo-synthetic', access(), limits=Limits(interval_seconds=0.01), retain_raw_html=retained))
    return build_pack([source])


def seo(output):
    return next(rule for rule in output['executions'] if rule['rule_id'] == 'SEO-01')


def run(pack):
    return execute(pack, expected_pack_ref=pack.ref, evaluator_version=VERSION)


def head(inner):
    return b'<html><head>' + inner + b'</head><body>Synthetic B2B components</body></html>'


def test_homepage_original_title_canonical_becomes_bounded_search_technical_observation():
    pack = seo_pack()
    output = run(pack)
    row = seo(output)['observations'][0]
    assert row['observation']['result'] == 'PASS'
    assert seo(output)['buyer_task'] == 'SEARCH_TECHNICAL'
    assert row['observation']['rule_id'] == 'SEO-01' and row['observation']['rule_version'] == '1.0.0'
    validate_contract('Observation', row['observation'])
    signals = row['seo_signals']
    assert signals['title']['value'] == 'Industrial valves & pump components'
    assert signals['canonical']['value'] == 'https://example.org/'
    assert signals['description']['value'] == 'Synthetic industrial components catalog'
    assert signals['robots']['status'] == signals['sitemap']['status'] == 'UNKNOWN'
    assert output['private'] is True
    for citation in row['citations']:
        resolved = pack.resolve(citation['evidence_ref'], expected_pack_ref=pack.ref)
        raw = resolved['content'].decode('utf-8-sig')
        pos = citation['element']
        assert raw[pos['character_start']:pos['character_end']] == pos['raw_element']
        assert raw.splitlines()[pos['line'] - 1][pos['column']:].startswith('<')
        assert citation['content_sha256'] == resolved['evidence']['content_sha256']
        assert citation['snapshot_ref'] == resolved['snapshot']['snapshot_ref']
    assert row['observation']['evidence_ids'] == sorted({c['evidence_ref'] for c in row['citations']})
    assert output == run(pack)
    verify_execution(output, pack, expected_pack_ref=pack.ref, expected_evaluator_version=VERSION)


@pytest.mark.parametrize('markup', [
    head(b'<title>Valves</title>'), head(b'<link rel="canonical" href="/">'),
    head(b'<title> </title><link rel="canonical" href="/">'),
    head(b'<title>A</title><title>B</title><link rel="canonical" href="/">'),
    head(b'<title>A</title><link rel="canonical" href="/"><link rel="canonical" href="/other">'),
    head(b'<title>A</title><link rel="canonical" href="/"><link rel="canonical" href="/">'),
    head(b'<title>A</title><link rel="canonical" href="https://unrelated.example/">'),
    head(b'<title>A</title><link rel="canonical" href="http://example.org/">'),
    head(b'<title>A</title><link rel="canonical" href="/" href="/other">'),
    head(b'<title>A</title><link rel="canonical" rel="alternate" href="/">'),
    head(b'<title>A</title><link rel="canonical" href="">'),
    head(b'<title>A</title><link rel="canonical" href="/?secret=query">'),
    head(b'<title>A</title><link rel="canonical" href="/#section">'),
    head(b'<base href="https://unrelated.example/"><title>A</title><link rel="canonical" href="/">'),
    head(b'<script>document.title="A"; const canonical="/";</script>'),
    head(b'<template><title>A</title><link rel="canonical" href="/"></template>'),
    b'<html><body><title>A</title><link rel="canonical" href="/"></body></html>',
    b'<html><template><head><title>A</title><link rel="canonical" href="/"></head></template></html>',
    b'<html><div><head><title>A</title><link rel="canonical" href="/"></head></div></html>',
    b'<html><head><title>A</title><link rel="canonical" href="/">',
    head(b'<title>A<b>B</b></title><link rel="canonical" href="/">'),
    head(b'<div><title>A</title><link rel="canonical" href="/"></div>'),
    head(b'</body><title>A</title><link rel="canonical" href="/">'),
    head(b'<title>A</title><link rel="canonical" href="https://example.org:8443/">'),
    head(b'<title>A</title><link rel="canonical" href="/%2e%2e/">'),
    head(b'<![unsupported]><title>A</title><link rel="canonical" href="/">'),
    head(b'<title>A</title><link rel="canonical" href="/\\outside.example/">'),
])
def test_missing_conflicting_external_or_dynamic_signals_never_become_seo_failure(markup):
    pack = seo_pack(markup)
    row = seo(run(pack))['observations'][0]
    assert row['observation']['result'] == 'UNKNOWN'
    assert row['observation']['kind'] == 'UNKNOWN' and row['observation']['evidence_ids'] == []
    verify_execution(run(pack), pack, expected_pack_ref=pack.ref)


def test_partial_source_values_remain_inspectable_without_completing_seo_rule():
    pack = seo_pack(head(b'<title>Industrial components</title>'))
    row = seo(run(pack))['observations'][0]
    assert row['observation']['result'] == 'UNKNOWN'
    assert row['seo_signals']['title']['value'] == 'Industrial components'
    assert row['seo_signals']['canonical']['status'] == 'UNKNOWN'
    assert row['seo_signals']['title']['candidates'][0]['element']['raw_element'] == '<title>Industrial components</title>'


@pytest.mark.parametrize('kwargs,expected', [({'retained': False}, 'UNKNOWN'),
    ({'status': 403}, 'ACCESS_BLOCKED'), ({'blocked': 'robots'}, 'ACCESS_BLOCKED'),
    ({'blocked': 'waf'}, 'ACCESS_BLOCKED'), ({'status': 404}, 'UNKNOWN'), ({'status': 500}, 'UNKNOWN')])
def test_no_original_or_blocked_source_never_produces_false_fact(kwargs, expected):
    pack = seo_pack(**kwargs)
    row = seo(run(pack))['observations'][0]
    assert row['observation']['result'] == expected and row['observation']['evidence_ids'] == []
    assert all(row['seo_signals'][key]['status'] == 'UNKNOWN' for key in ('title', 'canonical', 'robots', 'sitemap'))


def test_uncaptured_http_home_and_body_text_browser_samples_are_unknown():
    from tests.evidence.synthetic import browser
    pack = build_pack([browser(True)])
    row = seo(run(pack))['observations'][0]
    assert row['observation']['result'] == 'UNKNOWN' and row['reason'] == 'HTTP_HOME_SOURCE_NOT_CAPTURED'


@pytest.mark.parametrize('mutation', ['title', 'canonical', 'source_url', 'target', 'hash', 'locator',
    'tenant', 'run', 'policy', 'version', 'statement', 'coverage', 'robots', 'result'])
def test_recomputed_outer_hash_cannot_forge_seo_source_facts(mutation):
    pack = seo_pack()
    output = deepcopy(run(pack))
    row = seo(output)['observations'][0]
    if mutation == 'title':
        row['seo_signals']['title']['value'] = 'Invented brand'
    elif mutation == 'canonical':
        row['seo_signals']['canonical']['value'] = 'https://example.org/unobserved'
    elif mutation == 'source_url':
        row['source_page']['url'] = 'https://unrelated.example/'
    elif mutation == 'target':
        next(c for c in row['citations'] if c['fact_role'] == 'CANONICAL')['href'] = '/fabricated'
    elif mutation == 'hash':
        row['citations'][0]['content_sha256'] = '0' * 64
    elif mutation == 'locator':
        row['citations'][0]['element']['column'] += 1
    elif mutation in ('tenant', 'run'):
        output[mutation + '_id'] = 'other-value'
    elif mutation == 'policy':
        output['recorded_capture_scope'][0]['policy_version'] = 999
    elif mutation == 'version':
        output['evaluator_version'] = 'ra2b3-1.0.0'
    elif mutation == 'statement':
        row['observation']['statement'] = 'Google indexed this page and ranking will improve'
    elif mutation == 'coverage':
        output['coverage'] = []
    elif mutation == 'robots':
        row['seo_signals']['robots']['status'] = 'OBSERVED'
    else:
        row['observation']['result'] = 'FAIL_WITH_EVIDENCE'
    output['execution_ref'] = 'rx-' + document_hash({k: v for k, v in output.items() if k != 'execution_ref'})
    with pytest.raises(EvidenceError):
        verify_execution(output, pack, expected_pack_ref=pack.ref, expected_evaluator_version=VERSION)


@pytest.mark.parametrize('field', ['tenant_id', 'run_id', 'policy_id', 'policy_version'])
def test_pack_scope_drift_rejected_before_new_rule(field):
    pack = seo_pack()
    doc = pack.document
    doc[field] = 2 if field == 'policy_version' else 'other-scope'
    doc['pack_ref'] = 'ep-' + document_hash({k: v for k, v in doc.items() if k != 'pack_ref'})
    bad = EvidencePack(json.dumps(doc).encode(), tuple(sorted(pack.objects.items())))
    with pytest.raises(EvidenceError):
        run(bad)


def test_old_evaluators_unchanged_and_new_version_not_accepted_by_findings():
    from vrae.findings import build_findings, FindingError
    pack = seo_pack()
    for version in ('ra2b0-1.0.0', 'ra2b1-1.0.0', 'ra2b3-1.0.0'):
        output = execute(pack, expected_pack_ref=pack.ref, evaluator_version=version)
        assert seo(output)['enabled'] is False
        assert seo(output)['observations'][0]['observation']['result'] == 'UNKNOWN'
        verify_execution(output, pack, expected_pack_ref=pack.ref, expected_evaluator_version=version)
    assert execute(pack, expected_pack_ref=pack.ref)['evaluator_version'] == 'ra2b0-1.0.0'
    output = run(pack)
    for builder in ('ra2c0-1.0.0', 'ra2c1-1.0.0'):
        with pytest.raises(FindingError):
            build_findings(pack, output, expected_pack_ref=pack.ref,
                expected_execution_ref=output['execution_ref'], expected_evaluator_version=VERSION,
                expected_builder_version=builder)


def test_wrong_pin_is_rejected_before_metadata_is_read():
    pack = seo_pack()
    for pin in (None, '', 'ep-' + '0' * 64):
        with pytest.raises(EvidenceError):
            execute(pack, expected_pack_ref=pin, evaluator_version=VERSION)


def test_original_body_tamper_is_rejected_with_the_trusted_pack_pin():
    pack = seo_pack()
    objects = dict(pack.objects)
    key = next(key for key, body in objects.items() if b'<title>' in body)
    objects[key] = objects[key].replace(b'Industrial valves', b'Fabricated valves')
    with pytest.raises(EvidenceError):
        tampered = EvidencePack.load(pack.document, objects, expected_ref=pack.ref)
        run(tampered)


@pytest.mark.parametrize('metadata', [b'', b'<meta name="description" content="">',
    b'<meta name="description" content="A"><meta name="description" content="B">'])
def test_optional_description_never_gates_the_bounded_title_canonical_check(metadata):
    pack = seo_pack(head(b'<TITLE>Valves &amp; pumps</TITLE><LINK REL="CANONICAL" HREF="/">' + metadata))
    row = seo(run(pack))['observations'][0]
    assert row['observation']['result'] == 'PASS'
    assert row['seo_signals']['title']['value'] == 'Valves & pumps'
    assert row['seo_signals']['description']['status'] == 'UNKNOWN'


@pytest.mark.parametrize('markup', [b'\xef\xbb\xbf' + HTML,
    head(b'<title>\xe9\x98\x80\xe9\x97\xa8 &#38; components</title><link rel="canonical" href="/catalog">')])
def test_utf8_bom_entities_and_same_site_path_preserve_exact_source_offsets(markup):
    pack = seo_pack(markup)
    row = seo(run(pack))['observations'][0]
    assert row['observation']['result'] == 'PASS'
    for citation in row['citations']:
        pos = citation['element']
        assert markup.decode('utf-8-sig')[pos['character_start']:pos['character_end']] == pos['raw_element']


@pytest.mark.parametrize('markup', [head(b'<title>A</title>' + b'<meta name="x">' * 129 +
    b'<link rel="canonical" href="/">'), HTML + b' ' * 131073])
def test_bounded_parser_refuses_oversize_or_excessive_source(markup):
    pack = seo_pack(markup)
    assert seo(run(pack))['observations'][0]['observation']['result'] == 'UNKNOWN'


def test_sealed_offline_examples_and_historical_execution_refs():
    path = Path(__file__).parent / 'fixtures/seo01-static-signals.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['synthetic_only'] is True
    assert len(data['cases']) == 9
    for case in data['cases']:
        pack = EvidencePack.load(case['document'], {k: base64.b64decode(v, validate=True)
            for k, v in case['objects_base64'].items()}, expected_ref=case['expected_pack_ref'])
        assert run(pack) == case['expected_execution']
        verify_execution(case['expected_execution'], pack, expected_pack_ref=case['expected_pack_ref'],
                         expected_evaluator_version=VERSION)
        row = seo(case['expected_execution'])['observations'][0]
        assert row['observation']['result'] == case['expected_result']
        for version, ref in case['historical_execution_refs'].items():
            assert execute(pack, expected_pack_ref=pack.ref, evaluator_version=version)['execution_ref'] == ref

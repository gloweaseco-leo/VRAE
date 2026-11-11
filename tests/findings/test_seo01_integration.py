"""Explicit new private builder: SEO source positives are never defects."""
import base64
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path

import pytest

from vrae.collection.manifest import document_hash
from vrae.domain.contracts import validate_contract
from vrae.domain.evidence import validate_evidence_graph
from vrae.evidence import EvidencePack
from vrae.findings import build_findings, FindingError, FindingPackage
from vrae.rules import execute
from .seo01_synthetic import BUILDER, EVALUATOR, HEAD, HOME, diagnostic_input, pins


def build(pack, execution):
    return build_findings(pack, execution, **pins(pack, execution))


def load(doc, pack, execution):
    return FindingPackage.load(doc, pack, **pins(pack, execution), expected_package_ref=doc['package_ref'])


def reseal(document, key, prefix):
    document[key] = prefix + document_hash({k: v for k, v in document.items() if k != key})
    return document


@pytest.fixture(scope='module')
def demo():
    pack, execution = diagnostic_input()
    return pack, execution, build(pack, execution)


def test_separate_seo_product_path_positives_and_one_broken_contact():
    pack, execution = diagnostic_input()
    doc = build_findings(pack, execution, **pins(pack, execution)).document
    assert len(doc['checked_seo_signals']) == 1
    assert doc['checked_seo_signals'][0]['rule_id'] == 'SEO-01'
    assert len(doc['checked_product_facts']) == 1
    assert len(doc['checked_positive_paths']) == 2
    defects = [item for item in doc['items'] if item['finding']['kind'] == 'OBSERVATION']
    assert len(defects) == 1 and defects[0]['rule_id'] == 'CTA-02'
    assert defects[0]['provenance']['target_response']['http_status'] == 404
    assert any(item['outcome'] == 'ACCESS_BLOCKED' for item in doc['items'])


def test_original_seo_source_metadata_scope_and_versions_replay_in_package(demo):
    pack, execution, package = demo
    doc = package.document
    positive = doc['checked_seo_signals'][0]
    row = positive['provenance']
    assert positive['buyer_task'] == 'SEARCH_TECHNICAL'
    assert row['observation']['result'] == 'PASS'
    assert row['observation']['rule_version'] == '1.0.0'
    validate_contract('Observation', row['observation'])
    pointer = execution
    for token in positive['execution_locator'].split('/')[1:]:
        pointer = pointer[int(token)] if isinstance(pointer, list) else pointer[token]
    assert pointer == row
    signals = row['seo_signals']
    assert signals['title']['value'] == 'SV industrial valves & components'
    assert signals['title']['candidates'][0]['raw_inner'] == 'SV industrial valves &amp; components'
    assert signals['canonical']['value'] == 'https://example.org/'
    assert signals['description']['value'] == 'Synthetic industrial valve catalog'
    assert signals['robots']['status'] == signals['sitemap']['status'] == 'UNKNOWN'
    assert [c['element']['line'] for c in row['citations']] == [3, 4, 5]
    for citation in row['citations']:
        resolved = pack.resolve(citation['evidence_ref'], expected_pack_ref=pack.ref)
        text = resolved['content'].decode('utf-8-sig')
        pos = citation['element']
        assert text[pos['character_start']:pos['character_end']] == pos['raw_element']
        assert text.splitlines()[pos['line'] - 1][pos['column']:].startswith(pos['raw_element'])
        assert citation['content_sha256'] == resolved['evidence']['content_sha256']
        assert citation['source_ref'] == resolved['evidence']['source_ref'] == row['source_page']['source_ref']
        assert citation['snapshot_ref'] == resolved['snapshot']['snapshot_ref'] == row['source_page']['snapshot_ref']
        assert citation['observed_at'] == row['source_page']['observed_at']
        assert citation['url'] == row['source_page']['url'] == 'https://example.org/'
        assert citation['final_url'] == row['source_page']['final_url']
    assert row['source_page']['http_status'] == 200 and row['source_page']['redirect_trace']
    assert doc['recorded_capture_scope'] == execution['recorded_capture_scope']
    assert doc['evaluator_version'] == EVALUATOR and doc['builder_version'] == BUILDER
    assert doc['rule_execution'] == execution
    assert doc['private'] is True and doc['approval_status'] == 'NOT_APPROVED' and doc['shareable'] is False
    assert all(i['rule_id'] != 'SEO-01' for group in ('items', 'checked_product_facts', 'checked_positive_paths')
               for i in doc[group])
    assert load(doc, pack, execution).ref == package.ref == build(pack, execution).ref


def test_missing_optional_description_preserves_bounded_title_canonical_positive():
    pack, execution = diagnostic_input(home=HOME.replace(
        b'<meta name="description" content="Synthetic industrial valve catalog">', b''))
    doc = build(pack, execution).document
    row = doc['checked_seo_signals'][0]['provenance']
    assert row['observation']['result'] == 'PASS'
    assert row['seo_signals']['description']['status'] == 'UNKNOWN'
    assert {c['fact_role'] for c in row['citations']} == {'TITLE', 'CANONICAL'}


@pytest.mark.parametrize('status', [404, 410])
def test_only_real_404_410_creates_native_finding_with_inseparable_target_proof(status):
    pack, execution = diagnostic_input(contact_status=status)
    doc = build(pack, execution).document
    defects = [i for i in doc['items'] if i['finding']['kind'] == 'OBSERVATION']
    assert len(defects) == 1
    item = defects[0]
    finding, row, bridge = item['finding'], item['provenance'], item['guard_bridge']
    assert item['rule_id'] == 'CTA-02' and finding['buyer_task'] == 'INQUIRE'
    assert finding['severity'] is None and finding['rule_version'] == '1.0.0'
    assert row['citations'][0]['raw_href'] == '/contact'
    assert row['source_page']['url'] == 'https://example.org/products/sv-40'
    target = row['target_response']
    assert target['http_status'] == status and target['error']['code'] == 'HTTP_ERROR'
    source = next(s for s in pack.document['sources'] if s['source_ref'] == target['source_ref'])
    page = source['document']['pages'][int(target['locator'].split('/')[-1])]
    assert page['http_status'] == status and page['redirect_trace'] == target['redirect_trace']
    assert page['error'] == target['error']
    snapshot = next(s for s in pack.document['snapshots'] if s['snapshot_ref'] == target['snapshot_ref'])
    assert snapshot['url'] == target['url'] == 'https://example.org/contact'
    assert snapshot['final_url'] == target['final_url'] and snapshot['observed_at'] == target['observed_at']
    validate_contract('Finding', finding)
    validate_evidence_graph(bridge['native_snapshot'], bridge['native_evidence'],
                            bridge['guard_observation'], finding)
    assert bridge['kind'] == 'EXACT_NATIVE_HTTP_ID_MAPPING'
    assert len(doc['checked_product_facts']) == len(doc['checked_seo_signals']) == 1


@pytest.mark.parametrize('status,outcome', [(200, 'PASS'), (403, 'ACCESS_BLOCKED'),
    (500, 'UNKNOWN'), (503, 'ACCESS_BLOCKED')])
def test_reachable_unknown_or_blocked_contact_is_not_a_defect(status, outcome):
    pack, execution = diagnostic_input(contact_status=status)
    doc = build(pack, execution).document
    assert not any(i['finding']['kind'] == 'OBSERVATION' for i in doc['items'])
    if outcome == 'PASS':
        assert len(doc['checked_positive_paths']) == 3
    else:
        assert any(i['rule_id'] == 'CTA-02' and i['outcome'] == outcome for i in doc['items'])
    for item in doc['items']:
        assert item['finding']['kind'] == 'UNKNOWN' and item['finding']['evidence_ids'] == []


@pytest.mark.parametrize('kwargs,outcome', [
    ({'home': HOME.replace(HEAD, b'<head><title>Valves</title></head>')}, 'UNKNOWN'),
    ({'home': HOME.replace(HEAD, b'<head><link rel="canonical" href="/"></head>')}, 'UNKNOWN'),
    ({'home': HOME.replace(HEAD, b'<head><title> </title><link rel="canonical" href="/"></head>')}, 'UNKNOWN'),
    ({'home': HOME.replace(b'href="/">', b'href="https://outside.example/">')}, 'UNKNOWN'),
    ({'home': HOME.replace(b'</head>', b'<link rel="canonical" href="/other"></head>')}, 'UNKNOWN'),
    ({'home': HOME.replace(HEAD, b'<head><script>document.title="Valves"</script></head>')}, 'UNKNOWN'),
    ({'home': HOME.replace(b'</head>', b'<div>unsupported</div></head>')}, 'UNKNOWN'),
    ({'retained': False}, 'UNKNOWN'), ({'home_status': 404}, 'UNKNOWN'),
    ({'home_status': 500}, 'UNKNOWN'), ({'home_status': 403}, 'ACCESS_BLOCKED'),
    ({'home': b'<html>Verify you are human</html>'}, 'ACCESS_BLOCKED'),
    ({'robots': b'User-agent: *\nDisallow: /\n'}, 'ACCESS_BLOCKED'),
])
def test_seo_partial_ambiguous_missing_or_blocked_remains_unknown_not_defect(kwargs, outcome):
    pack, execution = diagnostic_input(**kwargs)
    doc = build(pack, execution).document
    assert doc['checked_seo_signals'] == []
    rows = [i for i in doc['items'] if i['rule_id'] == 'SEO-01']
    assert rows and all(i['outcome'] == outcome and i['finding']['kind'] == 'UNKNOWN'
                        and i['finding']['evidence_ids'] == []
                        and i['provenance']['observation']['evidence_ids'] == [] for i in rows)
    assert all(i['guard_bridge']['kind'] == 'UNKNOWN_RUN_CONTEXT' and i['coverage_note'] for i in rows)
    assert load(doc, pack, execution).document == doc


@pytest.mark.parametrize('mutation', ['title', 'canonical', 'description', 'raw', 'line', 'column',
    'offset', 'hash', 'source_ref', 'snapshot_ref', 'evidence_ref', 'url', 'final_url', 'time',
    'locator', 'missing_source', 'missing_seo', 'duplicate_seo', 'move_seo_to_paths',
    'seo_defect', 'unknown_fact', 'missing_target', 'target_status', 'target_trace', 'target_error',
    'native_id', 'tenant', 'run', 'policy', 'coverage', 'private', 'approved', 'shareable',
    'builder', 'evaluator', 'severity', 'indexing_claim', 'robots_claim'])
def test_rehashed_package_fields_cannot_forge_facts_or_authority(demo, mutation):
    pack, execution, package = demo
    doc = package.document
    positive = doc['checked_seo_signals'][0]
    row = positive['provenance']
    citation = row['citations'][0]
    issue = next(i for i in doc['items'] if i['finding']['kind'] == 'OBSERVATION')
    if mutation in ('title', 'canonical', 'description'):
        row['seo_signals'][mutation]['value'] = 'invented'
    elif mutation in ('raw', 'line', 'column', 'offset'):
        key, value = {'raw': ('raw_element', '<title>Invented</title>'), 'line': ('line', 999),
                      'column': ('column', 999), 'offset': ('character_start', 999)}[mutation]
        citation['element'][key] = value
    elif mutation in ('hash', 'source_ref', 'snapshot_ref', 'evidence_ref', 'url', 'final_url', 'time', 'locator'):
        citation[{'hash': 'content_sha256', 'time': 'observed_at'}.get(mutation, mutation)] = 'fabricated'
    elif mutation == 'missing_source':
        del row['source_page']
    elif mutation == 'missing_seo':
        doc['checked_seo_signals'].clear()
    elif mutation == 'duplicate_seo':
        doc['checked_seo_signals'].append(deepcopy(positive))
    elif mutation == 'move_seo_to_paths':
        doc['checked_positive_paths'].append(doc['checked_seo_signals'].pop())
    elif mutation == 'seo_defect':
        doc['items'].append({'rule_id': 'SEO-01', 'finding': {'kind': 'OBSERVATION', 'statement': 'SEO failure'}})
    elif mutation == 'unknown_fact':
        next(i for i in doc['items'] if i['finding']['kind'] == 'UNKNOWN')['finding']['kind'] = 'OBSERVATION'
    elif mutation == 'missing_target':
        del issue['provenance']['target_response']
    elif mutation in ('target_status', 'target_trace', 'target_error'):
        key, value = {'target_status': ('http_status', 200), 'target_trace': ('redirect_trace', []),
                      'target_error': ('error', None)}[mutation]
        issue['provenance']['target_response'][key] = value
    elif mutation == 'native_id':
        issue['guard_bridge']['evidence_mapping'][0]['native_evidence_id'] = 'fake'
    elif mutation in ('tenant', 'run'):
        doc[mutation + '_id'] = 'other'
    elif mutation == 'policy':
        doc['recorded_capture_scope'][0]['policy_version'] += 1
    elif mutation == 'coverage':
        doc['coverage'] = []
    elif mutation in ('private', 'approved', 'shareable', 'builder', 'evaluator'):
        key, value = {'private': ('private', False), 'approved': ('approval_status', 'APPROVED'),
            'shareable': ('shareable', True), 'builder': ('builder_version', 'ra2c1-1.0.0'),
            'evaluator': ('evaluator_version', 'ra2b3-1.0.0')}[mutation]
        doc[key] = value
    elif mutation == 'severity':
        issue['finding']['severity'] = 'HIGH'
    elif mutation == 'indexing_claim':
        row['observation']['statement'] = 'Google indexed the site; SEO is healthy and ranking will rise'
    else:
        row['seo_signals']['robots']['status'] = 'OBSERVED'
    with pytest.raises(FindingError):
        load(reseal(doc, 'package_ref', 'fp-'), pack, execution)


@pytest.mark.parametrize('mutation', ['title', 'canonical', 'href', 'raw', 'source_url', 'hash',
    'scope', 'policy', 'version', 'seo_fail', 'seo_na', 'blocked_fail', 'invented404', 'target_trace'])
def test_rehashed_execution_and_package_cannot_bypass_source_replay(demo, mutation):
    pack, original, package = demo
    execution = deepcopy(original)
    row = next(r['observations'][0] for r in execution['executions'] if r['rule_id'] == 'SEO-01')
    if mutation in ('title', 'canonical'):
        row['seo_signals'][mutation]['value'] = 'fabricated'
    elif mutation == 'href':
        next(c for c in row['citations'] if c['fact_role'] == 'CANONICAL')['href'] = '/invented'
    elif mutation == 'raw':
        row['citations'][0]['element']['raw_element'] = '<title>Invented</title>'
    elif mutation == 'source_url':
        row['source_page']['url'] = 'https://outside.example/'
    elif mutation == 'hash':
        row['citations'][0]['content_sha256'] = '0' * 64
    elif mutation == 'scope':
        execution['tenant_id'] = 'other'
    elif mutation == 'policy':
        execution['recorded_capture_scope'][0]['policy_version'] += 1
    elif mutation == 'version':
        execution['evaluator_version'] = 'ra2b3-1.0.0'
    elif mutation in ('seo_fail', 'seo_na'):
        row['observation']['result'] = 'FAIL_WITH_EVIDENCE' if mutation == 'seo_fail' else 'NOT_APPLICABLE'
    elif mutation == 'blocked_fail':
        blocked = next(r for rule in execution['executions'] for r in rule['observations']
                       if r['observation']['result'] == 'ACCESS_BLOCKED')
        blocked['observation']['result'] = 'FAIL_WITH_EVIDENCE'
        blocked['target_response']['http_status'] = 404
    elif mutation == 'invented404':
        good = next(rule['observations'][0] for rule in execution['executions'] if rule['rule_id'] == 'DISC-01')
        good['observation']['result'] = 'FAIL_WITH_EVIDENCE'
        good['target_response']['http_status'] = 404
    else:
        bad = next(r for rule in execution['executions'] for r in rule['observations']
                   if r['observation']['result'] == 'FAIL_WITH_EVIDENCE')
        bad['target_response']['redirect_trace'] = []
    reseal(execution, 'execution_ref', 'rx-')
    with pytest.raises(FindingError):
        build(pack, execution)
    doc = package.document
    doc['rule_execution'], doc['execution_ref'] = execution, execution['execution_ref']
    with pytest.raises(FindingError):
        load(reseal(doc, 'package_ref', 'fp-'), pack, execution)


@pytest.mark.parametrize('key,value', [('expected_pack_ref', None), ('expected_pack_ref', 'ep-' + '0' * 64),
    ('expected_execution_ref', ''), ('expected_execution_ref', 'rx-' + '0' * 64),
    ('expected_evaluator_version', 'ra2b1-1.0.0'), ('expected_evaluator_version', 'ra2b3-1.0.0'),
    ('expected_evaluator_version', 'future'), ('expected_builder_version', None),
    ('expected_builder_version', 'ra2c0-1.0.0'), ('expected_builder_version', 'ra2c1-1.0.0'),
    ('expected_builder_version', 'future')])
def test_pin_mismatches_rejected_for_build_load_and_verify(demo, key, value):
    pack, execution, package = demo
    expected = pins(pack, execution)
    expected[key] = value
    with pytest.raises(FindingError):
        build_findings(pack, execution, **expected)
    with pytest.raises(FindingError):
        FindingPackage.load(package.document, pack, **expected, expected_package_ref=package.ref)
    with pytest.raises(FindingError):
        package.verify(pack, **expected, expected_package_ref=package.ref)


def test_explicit_optin_immutable_detached_package_and_size_guard(demo, monkeypatch):
    from vrae.findings import builder
    pack, execution, package = demo
    expected = pins(pack, execution)
    del expected['expected_builder_version']
    with pytest.raises(FindingError):
        build_findings(pack, execution, **expected)
    with pytest.raises(FindingError):
        FindingPackage.load(package.document, pack, **expected, expected_package_ref=package.ref)
    for pin in (None, '', 'fp-' + '0' * 64):
        with pytest.raises(FindingError):
            package.verify(pack, **pins(pack, execution), expected_package_ref=pin)
    detached = package.document
    detached['checked_seo_signals'].clear()
    assert package.document['checked_seo_signals']
    with pytest.raises((FrozenInstanceError, AttributeError)):
        package._payload = b'{}'
    huge = deepcopy(execution)
    huge['padding'] = 'x' * 8_000_001
    with pytest.raises(FindingError):
        build(pack, huge)
    monkeypatch.setattr(builder, 'MAX_BYTES', len(package._payload) - 1)
    with pytest.raises(FindingError):
        build(pack, execution)


@pytest.mark.parametrize('field', ['tenant_id', 'run_id', 'policy_id', 'policy_version'])
def test_rehashed_pack_scope_drift_cannot_inherit_trusted_pins(demo, field):
    pack, execution, package = demo
    doc = pack.document
    doc[field] = 2 if field == 'policy_version' else 'other'
    reseal(doc, 'pack_ref', 'ep-')
    forged = EvidencePack(json.dumps(doc).encode(), tuple(sorted(pack.objects.items())))
    with pytest.raises(FindingError):
        build_findings(forged, execution, **pins(pack, execution))
    with pytest.raises(FindingError):
        load(package.document, forged, execution)


def test_original_seo_body_cannot_be_replaced_under_trusted_pin(demo):
    pack, execution, package = demo
    objects = dict(pack.objects)
    key = next(k for k, body in objects.items() if b'<title>' in body)
    objects[key] = objects[key].replace(b'SV industrial', b'Fake supplier')
    forged = EvidencePack(pack._payload, tuple(sorted(objects.items())))
    with pytest.raises(FindingError):
        build_findings(forged, execution, **pins(pack, execution))
    with pytest.raises(FindingError):
        load(package.document, forged, execution)


@pytest.mark.parametrize('path,version', [('tests/fixtures/findings/industrial-diagnostic.json', 'ra2c0-1.0.0'),
    ('tests/findings/fixtures/info01-private-package.json', 'ra2c1-1.0.0')])
def test_historical_packages_and_default_bytes_unchanged(path, version):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    pack = EvidencePack.load(data['document'], {k: base64.b64decode(v, validate=True)
        for k, v in data['objects_base64'].items()}, expected_ref=data['expected_pack_ref'])
    execution = data['finding_package']['rule_execution']
    expected = {k: data[k] for k in ('expected_pack_ref', 'expected_execution_ref', 'expected_evaluator_version')}
    expected['expected_builder_version'] = version
    package = build_findings(pack, execution, **expected)
    encoded = json.dumps(data['finding_package'], sort_keys=True, ensure_ascii=False,
                         separators=(',', ':'), allow_nan=False).encode('utf-8')
    assert package._payload == encoded and package.ref == data['expected_package_ref']
    assert FindingPackage.load(data['finding_package'], pack, **expected,
                               expected_package_ref=data['expected_package_ref']).ref == package.ref
    assert 'checked_seo_signals' not in package.document
    if version == 'ra2c0-1.0.0':
        del expected['expected_builder_version']
        assert build_findings(pack, execution, **expected)._payload == encoded


def test_sealed_new_package_matches_fresh_source_and_does_not_accept_legacy_evaluators():
    data = json.loads((Path(__file__).parent / 'fixtures/seo01-private-package.json').read_text(encoding='utf-8'))
    pack = EvidencePack.load(data['document'], {k: base64.b64decode(v, validate=True)
        for k, v in data['objects_base64'].items()}, expected_ref=data['expected_pack_ref'])
    execution = data['finding_package']['rule_execution']
    package = load(data['finding_package'], pack, execution)
    assert package.ref == data['expected_package_ref']
    fresh_pack, fresh_execution = diagnostic_input()
    assert pack.ref == fresh_pack.ref and execution == fresh_execution
    for version in ('ra2b0-1.0.0', 'ra2b1-1.0.0', 'ra2b3-1.0.0'):
        old = execute(pack, expected_pack_ref=pack.ref, evaluator_version=version)
        with pytest.raises(FindingError):
            build(pack, old)

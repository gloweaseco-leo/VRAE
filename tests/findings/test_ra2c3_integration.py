"""Codex-1 integration tests; independent Codex-2 QA files are never imported or edited."""
import base64
from copy import deepcopy
from dataclasses import FrozenInstanceError
from html import unescape
import json
from pathlib import Path

import pytest

from vrae.collection.manifest import CaptureBundle, document_hash
from vrae.domain.contracts import validate_contract
from vrae.domain.evidence import validate_evidence_graph
from vrae.evidence import EvidencePack, EvidenceError, build_pack
from vrae.findings import build_findings, FindingError, FindingPackage
from vrae.rules import execute
from .ra2c3_synthetic import BUILDER, EVALUATOR, CONTACT, DECLARATION, HOME, diagnostic_input, pins


def build(pack, execution):
    return build_findings(pack, execution, **pins(pack, execution))


def load(doc, pack, execution):
    return FindingPackage.load(doc, pack, **pins(pack, execution), expected_package_ref=doc['package_ref'])


def reseal(doc, key, prefix):
    doc[key] = prefix + document_hash({k: v for k, v in doc.items() if k != key})
    return doc


def trust_row(execution):
    return next(r['observations'][0] for r in execution['executions'] if r['rule_id'] == 'TRUST-01')


def link_fact(row):
    return next(f for page in row['source_facts']['pages'] for f in page['facts']
                if f['kind'] == 'STATIC_CONTACT_LINK' and f['raw_href'] == '/contact')


@pytest.fixture(scope='module')
def demo():
    pack, execution = diagnostic_input()
    return pack, execution, build(pack, execution)


def test_explicit_trust_source_group_is_separate_from_seo_product_and_paths():
    pack, execution = diagnostic_input()
    doc = build_findings(pack, execution, **pins(pack, execution)).document
    assert len(doc['checked_trust_source_facts']) == 1
    assert doc['checked_trust_source_facts'][0]['rule_id'] == 'TRUST-01'
    assert len(doc['checked_seo_signals']) == len(doc['checked_product_facts']) == 1
    assert len(doc['checked_positive_paths']) == 3
    assert not any(item['finding']['kind'] == 'OBSERVATION' for item in doc['items'])


def test_original_trust_quotes_labels_positions_roles_and_scope_are_inseparable(demo):
    pack, execution, package = demo
    doc = package.document
    positive = doc['checked_trust_source_facts'][0]
    row = positive['provenance']
    assert positive['buyer_task'] == 'TRUST' and row == trust_row(execution)
    assert row['observation']['result'] == 'PASS' and row['observation']['rule_version'] == '1.0.0'
    validate_contract('Observation', row['observation'])
    pointer = execution
    for token in positive['execution_locator'].split('/')[1:]:
        pointer = pointer[int(token)] if isinstance(pointer, list) else pointer[token]
    assert pointer == row
    assert {p['source_page']['url'] for p in row['source_facts']['pages']} == {
        'https://example.org/', 'https://example.org/contact'}
    assert row['missing_prerequisites'] == row['blocked_page_indices'] == row['unknown_page_indices'] == []
    assert row['unvisited_candidates'] == []
    for citation in row['citations']:
        resolved = pack.resolve(citation['evidence_ref'], expected_pack_ref=pack.ref)
        text, pos = resolved['content'].decode('utf-8'), citation['element']
        offset = sum(len(s) + 1 for s in text.split('\n')[:pos['line'] - 1]) + pos['column']
        assert text[offset:].startswith(citation['raw_element'])
        assert citation['raw_element'].startswith(pos['start_tag'])
        assert unescape(citation['raw_element'].split('>', 1)[1].rsplit('</', 1)[0]) == citation['text']
        assert citation['content_sha256'] == resolved['evidence']['content_sha256']
        assert citation['source_ref'] == resolved['evidence']['source_ref']
        assert citation['snapshot_ref'] == resolved['snapshot']['snapshot_ref']
        assert citation['url'] == resolved['snapshot']['url']
        assert citation['final_url'] == resolved['snapshot']['final_url']
        assert citation['observed_at'] == resolved['snapshot']['observed_at']
        source_page = row['source_facts']['pages'][citation['page_index']]['source_page']
        assert source_page['source_ref'] == citation['source_ref']
    kinds = {c['fact_kind'] for c in row['citations']}
    assert kinds == {'DECLARED_NAME', 'SELF_DESCRIPTION', 'STATIC_CONTACT_LINK', 'ADDRESS_TEXT'}
    assert {c['text'] for c in row['citations'] if c['fact_kind'] == 'DECLARED_NAME'
            and c['citation_role'] == 'VALUE'} == {'SV Industrial Valve Works'}
    assert any(c['citation_role'] == 'LABEL' and c['text'] == 'Company name' for c in row['citations'])
    assert any(c['citation_role'] == 'LABEL' and c['text'] == 'Company profile' for c in row['citations'])
    link = link_fact(row)
    target = link['target_responses'][0]
    assert link['raw_href'] == '/contact' and target['http_status'] == 200
    assert target['error'] is None and target['redirect_trace']
    assert link['limit'] == 'STATIC_LINK_ONLY_NOT_REACHABILITY_DELIVERABILITY_OR_OWNERSHIP'
    for page in row['source_facts']['pages']:
        source_page = page['source_page']
        source = next(s for s in pack.document['sources'] if s['source_ref'] == source_page['source_ref'])
        native = source['document']['pages'][int(source_page['locator'].split('/')[-1])]
        assert native['role'] in ('HOME', 'CONTACT')
        assert native['http_status'] == source_page['http_status']
    assert doc['recorded_capture_scope'] == execution['recorded_capture_scope']
    for scope in row['recorded_capture_scope']:
        assert all(scope[k] == pack.document[k] for k in ('tenant_id', 'run_id', 'policy_id', 'policy_version'))
    assert doc['builder_version'] == BUILDER and doc['evaluator_version'] == EVALUATOR
    assert doc['private'] is True and doc['shareable'] is False and doc['approval_status'] == 'NOT_APPROVED'
    assert all(i['rule_id'] != 'TRUST-01' for group in ('items', 'checked_seo_signals',
               'checked_product_facts', 'checked_positive_paths') for i in doc[group])
    assert load(doc, pack, execution).ref == build(pack, execution).ref == package.ref


@pytest.mark.parametrize('status,trust,defects', [(200, 'PASS', 0), (404, 'UNKNOWN', 1),
    (410, 'UNKNOWN', 1), (403, 'ACCESS_BLOCKED', 0), (500, 'UNKNOWN', 0), (503, 'ACCESS_BLOCKED', 0)])
def test_original_trust_scope_and_actual_contact_response_are_never_conflated(status, trust, defects):
    pack, execution = diagnostic_input(contact_status=status)
    doc = build(pack, execution).document
    row = trust_row(execution)
    assert row['observation']['result'] == trust
    actual = [i for i in doc['items'] if i['finding']['kind'] == 'OBSERVATION']
    assert len(actual) == defects
    if defects:
        item = actual[0]
        assert item['rule_id'] == 'CTA-02' and item['provenance']['target_response']['http_status'] == status
        assert item['provenance']['citations'][0]['raw_href'] == '/contact'
        target = item['provenance']['target_response']
        assert target['redirect_trace'] and target['error']['code'] == 'HTTP_ERROR'
        bridge = item['guard_bridge']
        validate_evidence_graph(bridge['native_snapshot'], bridge['native_evidence'],
                                bridge['guard_observation'], item['finding'])
        assert item['finding']['severity'] is None
    if trust != 'PASS':
        assert doc['checked_trust_source_facts'] == []
        item = next(i for i in doc['items'] if i['rule_id'] == 'TRUST-01')
        assert item['finding']['kind'] == 'UNKNOWN' and item['finding']['evidence_ids'] == []
        assert item['outcome'] == trust and item['provenance'] == row
        assert item['guard_bridge']['kind'] == 'UNKNOWN_RUN_CONTEXT'
    else:
        assert len(doc['checked_trust_source_facts']) == 1


INTRO = b'<section><h2>Company profile</h2><p>We self-describe as a supplier of industrial valve components.</p></section>'
MAILTO = b'<a href="mailto:sales@valves.example">Email sales</a>'
HTTP_LINK = b'<a href="/contact">Contact page</a>'


@pytest.mark.parametrize('kwargs,outcome', [
    ({'home': HOME.replace(b'Company name', b'Brand name'),
      'contact': CONTACT.replace(b'Company name', b'Brand name')}, 'UNKNOWN'),
    ({'contact': CONTACT.replace(b'SV Industrial Valve Works', b'Other Declared Entity')}, 'UNKNOWN'),
    ({'home': HOME.replace(INTRO, b''), 'contact': CONTACT.replace(INTRO, b'')}, 'UNKNOWN'),
    ({'home': HOME.replace(MAILTO, b''), 'contact': CONTACT.replace(MAILTO, b'').replace(HTTP_LINK, b'')}, 'UNKNOWN'),
    ({'home': HOME.replace(DECLARATION, b'<script>const company="Invented";</script>')}, 'UNKNOWN'),
    ({'contact': CONTACT.replace(b'</body>', b'<table><tr><th>Legal name</th><td>Other Entity</td></tr></table></body>')}, 'UNKNOWN'),
    ({'home': HOME.replace(b'Company name', b'Unsupported name'),
      'contact': CONTACT.replace(b'Company name', b'Unsupported name')}, 'UNKNOWN'),
    ({'max_pages': 1, 'about': CONTACT}, 'UNKNOWN'), ({'retained': False}, 'UNKNOWN'),
    ({'about': b'<html><p>No supported company declaration</p></html>'}, 'UNKNOWN'),
    ({'about': CONTACT.replace(b'SV Industrial Valve Works', b'Different Legal Name')}, 'UNKNOWN'),
    ({'home_status': 403}, 'ACCESS_BLOCKED'),
    ({'home': b'<html>Verify you are human</html>'}, 'ACCESS_BLOCKED'),
    ({'robots': b'User-agent: *\nDisallow: /contact\n'}, 'ACCESS_BLOCKED'),
    ({'robots': b'User-agent: *\nDisallow: /\n'}, 'ACCESS_BLOCKED'),
])
def test_missing_ambiguous_unvisited_or_blocked_source_is_nondefect(kwargs, outcome):
    pack, execution = diagnostic_input(**kwargs)
    doc = build(pack, execution).document
    assert doc['checked_trust_source_facts'] == []
    item = next(i for i in doc['items'] if i['rule_id'] == 'TRUST-01')
    assert item['outcome'] == outcome and item['finding']['kind'] == 'UNKNOWN'
    assert item['finding']['evidence_ids'] == item['provenance']['observation']['evidence_ids'] == []
    assert item['finding']['severity'] is None and item['coverage_note']
    assert item['guard_bridge']['kind'] == 'UNKNOWN_RUN_CONTEXT'
    assert not any(i['finding']['kind'] == 'OBSERVATION' for i in doc['items'])


def test_optional_address_and_seo_description_are_not_trust_prerequisites():
    pack, execution = diagnostic_input(contact=CONTACT.replace(b'<address>100 Synthetic Way</address>', b''),
        home=HOME.replace(b'<meta name="description" content="Synthetic industrial valve catalog">', b''))
    doc = build(pack, execution).document
    assert len(doc['checked_trust_source_facts']) == len(doc['checked_seo_signals']) == 1
    assert doc['checked_seo_signals'][0]['provenance']['seo_signals']['description']['status'] == 'UNKNOWN'


@pytest.mark.parametrize('mutation', ['name', 'description', 'href', 'label', 'raw', 'line', 'column',
    'path', 'start_tag', 'hash', 'evidence', 'source', 'snapshot', 'url', 'final_url', 'time',
    'target_status', 'target_trace', 'target_error', 'target_snapshot', 'target_removed',
    'native_name', 'missing_source_pages', 'scope', 'policy', 'coverage', 'missing', 'unvisited',
    'private', 'approved', 'shareable', 'builder', 'evaluator', 'duplicate_trust', 'remove_trust',
    'trust_as_path', 'trust_as_defect', 'unknown_as_fact', 'severity', 'authenticity_claim'])
def test_rehashed_package_cannot_forge_source_edges_or_authority(demo, mutation):
    pack, execution, package = demo
    doc = package.document
    positive = doc['checked_trust_source_facts'][0]
    row = positive['provenance']
    citation = next(c for c in row['citations'] if c['fact_kind'] == 'DECLARED_NAME' and c['citation_role'] == 'VALUE')
    link = link_fact(row)
    if mutation in ('name', 'description', 'label'):
        kind, role = {'name': ('DECLARED_NAME', 'VALUE'), 'description': ('SELF_DESCRIPTION', 'VALUE'),
                      'label': ('DECLARED_NAME', 'LABEL')}[mutation]
        next(c for c in row['citations'] if c['fact_kind'] == kind and c['citation_role'] == role)['text'] = 'Fabricated'
    elif mutation == 'href':
        link['raw_href'] = '/invented-contact'
    elif mutation in ('raw', 'hash', 'evidence', 'source', 'snapshot', 'url', 'final_url', 'time'):
        key = {'raw': 'raw_element', 'hash': 'content_sha256', 'evidence': 'evidence_ref',
               'source': 'source_ref', 'snapshot': 'snapshot_ref', 'time': 'observed_at'}.get(mutation, mutation)
        citation[key] = 'fabricated'
    elif mutation in ('line', 'column', 'path', 'start_tag'):
        citation['element'][mutation] = 999 if mutation in ('line', 'column') else 'fabricated'
    elif mutation.startswith('target_'):
        if mutation == 'target_removed':
            del link['target_responses']
        else:
            key, value = {'target_status': ('http_status', 404), 'target_trace': ('redirect_trace', []),
                'target_error': ('error', {'code': 'HTTP_ERROR'}), 'target_snapshot': ('snapshot_ref', 'fabricated')}[mutation]
            link['target_responses'][0][key] = value
    elif mutation == 'native_name':
        next(f for p in row['source_facts']['pages'] for f in p['facts']
             if f['kind'] == 'DECLARED_NAME')['citation']['text'] = 'Fake entity'
    elif mutation == 'missing_source_pages':
        row['source_pages'] = []
    elif mutation in ('scope', 'policy'):
        row['recorded_capture_scope'][0]['tenant_id' if mutation == 'scope' else 'policy_id'] = 'other'
    elif mutation in ('coverage', 'missing', 'unvisited'):
        row[{'coverage': 'coverage', 'missing': 'missing_prerequisites',
             'unvisited': 'unvisited_candidates'}[mutation]] = [] if mutation == 'coverage' else ['fake']
    elif mutation in ('private', 'approved', 'shareable', 'builder', 'evaluator'):
        key, value = {'private': ('private', False), 'approved': ('approval_status', 'APPROVED'),
            'shareable': ('shareable', True), 'builder': ('builder_version', 'ra2c2-1.0.0'),
            'evaluator': ('evaluator_version', 'ra2b4-1.0.0')}[mutation]
        doc[key] = value
    elif mutation == 'duplicate_trust':
        doc['checked_trust_source_facts'].append(deepcopy(positive))
    elif mutation == 'remove_trust':
        doc['checked_trust_source_facts'].clear()
    elif mutation == 'trust_as_path':
        doc['checked_positive_paths'].append(doc['checked_trust_source_facts'].pop())
    elif mutation == 'trust_as_defect':
        doc['items'].append({'rule_id': 'TRUST-01', 'finding': {'kind': 'OBSERVATION', 'statement': 'Trust failure'}})
    elif mutation == 'unknown_as_fact':
        doc['items'][0]['finding']['kind'] = 'OBSERVATION'
    elif mutation == 'severity':
        positive['severity'] = 'HIGH'
    else:
        row['observation']['statement'] = 'Authenticated factory and legal entity; contact ownership verified'
    with pytest.raises(FindingError):
        load(reseal(doc, 'package_ref', 'fp-'), pack, execution)


@pytest.mark.parametrize('mutation', ['name', 'description', 'href', 'line', 'hash', 'source',
    'snapshot', 'time', 'target_status', 'target_trace', 'tenant', 'run', 'policy', 'version',
    'private', 'approved', 'shareable', 'fail', 'not_applicable', 'unknown_pass', 'blocked_fail'])
def test_rehashed_execution_and_package_cannot_bypass_pinned_source_replay(demo, mutation):
    pack, original, package = demo
    if mutation in ('unknown_pass', 'blocked_fail'):
        pack, original = diagnostic_input(contact_status=404 if mutation == 'unknown_pass' else 403)
        package = build(pack, original)
    execution = deepcopy(original)
    row = trust_row(execution)
    citation = next(c for c in row['citations'] if c['fact_kind'] == 'DECLARED_NAME')
    if mutation in ('name', 'description'):
        kind = 'DECLARED_NAME' if mutation == 'name' else 'SELF_DESCRIPTION'
        next(c for c in row['citations'] if c['fact_kind'] == kind)['text'] = 'Fabricated'
    elif mutation == 'href':
        link_fact(row)['endpoint'] = 'https://outside.example/contact'
    elif mutation == 'line':
        citation['element']['line'] += 1
    elif mutation in ('hash', 'source', 'snapshot', 'time'):
        citation[{'hash': 'content_sha256', 'source': 'source_ref', 'snapshot': 'snapshot_ref',
                  'time': 'observed_at'}[mutation]] = 'fake'
    elif mutation.startswith('target_'):
        link_fact(row)['target_responses'][0]['http_status' if mutation == 'target_status' else 'redirect_trace'] = (
            404 if mutation == 'target_status' else [])
    elif mutation in ('tenant', 'run'):
        execution[mutation + '_id'] = 'other'
    elif mutation == 'policy':
        execution['recorded_capture_scope'][0]['policy_version'] += 1
    elif mutation == 'version':
        execution['evaluator_version'] = 'ra2b4-1.0.0'
    elif mutation in ('private', 'approved', 'shareable'):
        execution[{'private': 'private', 'approved': 'approval_status', 'shareable': 'shareable'}[mutation]] = (
            False if mutation == 'private' else 'APPROVED' if mutation == 'approved' else True)
    else:
        row['observation']['result'] = {'fail': 'FAIL_WITH_EVIDENCE', 'not_applicable': 'NOT_APPLICABLE',
            'unknown_pass': 'PASS', 'blocked_fail': 'FAIL_WITH_EVIDENCE'}[mutation]
    reseal(execution, 'execution_ref', 'rx-')
    with pytest.raises(FindingError):
        build(pack, execution)
    doc = package.document
    doc['rule_execution'], doc['execution_ref'] = execution, execution['execution_ref']
    with pytest.raises(FindingError):
        load(reseal(doc, 'package_ref', 'fp-'), pack, execution)


@pytest.mark.parametrize('key,value', [('expected_pack_ref', None), ('expected_pack_ref', 'ep-' + '0' * 64),
    ('expected_execution_ref', ''), ('expected_execution_ref', 'rx-' + '0' * 64),
    ('expected_evaluator_version', 'ra2b4-1.0.0'), ('expected_evaluator_version', None),
    ('expected_builder_version', 'ra2c0-1.0.0'), ('expected_builder_version', 'ra2c1-1.0.0'),
    ('expected_builder_version', 'ra2c2-1.0.0'), ('expected_builder_version', 'future'),
    ('expected_builder_version', None)])
def test_all_trusted_pins_are_required_for_build_load_and_verify(demo, key, value):
    pack, execution, package = demo
    expected = pins(pack, execution)
    expected[key] = value
    with pytest.raises(FindingError):
        build_findings(pack, execution, **expected)
    with pytest.raises(FindingError):
        FindingPackage.load(package.document, pack, **expected, expected_package_ref=package.ref)
    with pytest.raises(FindingError):
        package.verify(pack, **expected, expected_package_ref=package.ref)


@pytest.mark.parametrize('field', ['tenant_id', 'run_id', 'policy_id', 'policy_version'])
def test_resealed_pack_scope_drift_rejected(demo, field):
    pack, execution, package = demo
    doc = pack.document
    doc[field] = 2 if field == 'policy_version' else 'other'
    reseal(doc, 'pack_ref', 'ep-')
    forged = EvidencePack(json.dumps(doc).encode(), tuple(sorted(pack.objects.items())))
    with pytest.raises(FindingError):
        build_findings(forged, execution, **pins(pack, execution))
    with pytest.raises(FindingError):
        load(package.document, forged, execution)


def test_original_body_corruption_cannot_be_authorized_by_unchanged_outer_pins(demo):
    pack, execution, package = demo
    objects = dict(pack.objects)
    key = next(k for k, raw in objects.items() if b'Company name' in raw)
    objects[key] = objects[key].replace(b'SV Industrial Valve Works', b'Invented Legal Owner')
    forged = EvidencePack(pack._payload, tuple(sorted(objects.items())))
    with pytest.raises(FindingError):
        build_findings(forged, execution, **pins(pack, execution))
    with pytest.raises(FindingError):
        load(package.document, forged, execution)


def test_optional_browser_source_never_becomes_http_company_proof(demo):
    from tests.evidence.synthetic import browser
    from tests.evidence.test_site_coherence import seal, relocate_browser
    pack, _, _ = demo
    source = pack.document['sources'][0]
    http = CaptureBundle(source['document'], {k: pack.objects[v] for k, v in source['object_refs'].items()})
    observed = browser(True)
    observed.manifest['run_id'] = pack.document['run_id']
    seal(observed)
    mixed = build_pack([http, observed])
    execution = execute(mixed, expected_pack_ref=mixed.ref, evaluator_version=EVALUATOR)
    doc = build(mixed, execution).document
    assert len(doc['recorded_capture_scope']) == 2
    assert doc['checked_trust_source_facts'] == []
    item = next(i for i in doc['items'] if i['rule_id'] == 'TRUST-01')
    row = item['provenance']
    assert item['outcome'] == 'UNKNOWN' and row['unvisited_candidates']
    assert item['finding']['evidence_ids'] == []
    assert all(c['source_ref'] == source['source_ref'] for c in row['citations'])
    wrong_site = relocate_browser(True)
    wrong_site.manifest['run_id'] = pack.document['run_id']
    seal(wrong_site)
    with pytest.raises(EvidenceError):
        build_pack([http, wrong_site])


def test_explicit_optin_detached_immutable_payload_and_size_guard(demo, monkeypatch):
    from vrae.findings import builder
    pack, execution, package = demo
    expected = pins(pack, execution)
    del expected['expected_builder_version']
    with pytest.raises(FindingError):
        build_findings(pack, execution, **expected)
    with pytest.raises(FindingError):
        FindingPackage.load(package.document, pack, **expected, expected_package_ref=package.ref)
    for ref in (None, '', 'fp-' + '0' * 64):
        with pytest.raises(FindingError):
            package.verify(pack, **pins(pack, execution), expected_package_ref=ref)
    detached = package.document
    detached['checked_trust_source_facts'].clear()
    assert package.document['checked_trust_source_facts']
    with pytest.raises((FrozenInstanceError, AttributeError)):
        package._payload = b'{}'
    oversized = deepcopy(execution)
    oversized['padding'] = 'x' * 8_000_001
    with pytest.raises(FindingError):
        build(pack, oversized)
    monkeypatch.setattr(builder, 'MAX_BYTES', len(package._payload) - 1)
    with pytest.raises(FindingError):
        build(pack, execution)


@pytest.mark.parametrize('path,version', [('tests/fixtures/findings/industrial-diagnostic.json', 'ra2c0-1.0.0'),
    ('tests/findings/fixtures/info01-private-package.json', 'ra2c1-1.0.0'),
    ('tests/findings/fixtures/seo01-private-package.json', 'ra2c2-1.0.0')])
def test_historical_c0_c1_c2_canonical_bytes_refs_and_default_dispatch_unchanged(path, version):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    pack = EvidencePack.load(data['document'], {k: base64.b64decode(v, validate=True)
        for k, v in data['objects_base64'].items()}, expected_ref=data['expected_pack_ref'])
    execution = data['finding_package']['rule_execution']
    expected = {k: data[k] for k in ('expected_pack_ref', 'expected_execution_ref', 'expected_evaluator_version')}
    expected['expected_builder_version'] = version
    package = build_findings(pack, execution, **expected)
    raw = json.dumps(data['finding_package'], sort_keys=True, ensure_ascii=False,
                     separators=(',', ':'), allow_nan=False).encode('utf-8')
    assert package._payload == raw and package.ref == data['expected_package_ref']
    assert 'checked_trust_source_facts' not in package.document
    assert FindingPackage.load(data['finding_package'], pack, **expected,
                               expected_package_ref=package.ref)._payload == raw
    if version == 'ra2c0-1.0.0':
        del expected['expected_builder_version']
        assert build_findings(pack, execution, **expected)._payload == raw


def test_old_evaluators_or_preparatory_wrapper_are_not_implicitly_upgraded(demo):
    from vrae.rules.trust01 import prepare
    pack, execution, _ = demo
    assert execute(pack, expected_pack_ref=pack.ref)['evaluator_version'] == 'ra2b0-1.0.0'
    for version in ('ra2b0-1.0.0', 'ra2b1-1.0.0', 'ra2b3-1.0.0', 'ra2b4-1.0.0'):
        old = execute(pack, expected_pack_ref=pack.ref, evaluator_version=version)
        with pytest.raises(FindingError):
            build(pack, old)
    prepared = prepare(pack, expected_pack_ref=pack.ref)
    with pytest.raises(FindingError):
        build_findings(pack, prepared, **pins(pack, execution))


def test_new_sealed_status_matrix_matches_original_sources_and_fresh_captures():
    data = json.loads((Path(__file__).parent / 'fixtures/ra2c3-private-packages.json').read_text(encoding='utf-8'))
    assert data['synthetic_only'] is True and len(data['cases']) == 5
    for case in data['cases']:
        pack = EvidencePack.load(case['document'], {k: base64.b64decode(v, validate=True)
            for k, v in case['objects_base64'].items()}, expected_ref=case['expected_pack_ref'])
        execution = case['finding_package']['rule_execution']
        package = load(case['finding_package'], pack, execution)
        assert package.ref == case['expected_package_ref']
        fresh_pack, fresh_execution = diagnostic_input(contact_status=case['contact_status'])
        assert fresh_pack.ref == pack.ref and fresh_execution == execution
        assert trust_row(execution)['observation']['result'] == case['expected_trust_result']

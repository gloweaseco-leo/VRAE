"""Codex-2 black-box QA: no production stub, feature skip, xfail or candidate fixtures."""
import asyncio
import base64
from copy import deepcopy
import hashlib
from html import unescape
import json
from pathlib import Path
from dataclasses import FrozenInstanceError

import pytest

from tests.collection.test_security import access
from vrae.collection.collector import Collector
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.http_transport import FetchResponse
from vrae.collection.limits import Limits
from vrae.collection.manifest import document_hash
from vrae.domain.evidence import validate_evidence_graph
from vrae.evidence import EvidencePack, build_pack
from vrae.findings import build_findings, FindingError, FindingPackage
from vrae.rules import execute, verify_execution

ROOT = Path(__file__).resolve().parents[2]
INPUT = json.loads((Path(__file__).parent / 'fixtures/ra2c3_codex2_inputs.json').read_text(encoding='utf-8'))
LEGACY = json.loads((Path(__file__).parent / 'fixtures/ra2c3_codex2_legacy_pins.json').read_text(encoding='utf-8'))
BUILDER = 'ra2c3-1.0.0'
EVALUATOR = 'ra2b6-1.0.0'
STATEMENT = ('At this capture, website source contains explicit self-declared organization text, '
             'company introduction and at least one static public contact link.')


class _DNS:
    async def resolve(self, host):
        assert host == 'example.org', 'Independent QA forbids real or third-party resolution'
        return ('93.184.216.20',)


class _Transport:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    async def exchange(self, url, method, ip, budget, max_bytes):
        assert url in self.routes and method == 'GET' and ip == '93.184.216.20'
        self.calls.append((url, method))
        status, headers, text = self.routes[url]
        body = text.encode('utf-8')
        assert len(body) <= max_bytes
        budget.consume(len(body))
        return FetchResponse(url, status, headers, body, ip)


def site(case='positive', *, run_id='run-codex2-independent'):
    routes = deepcopy(INPUT['routes'])
    about, contact = 'https://example.org/about', 'https://example.org/contact'
    retained, max_pages = case != 'raw_absent', 4 if case == 'unvisited' else 5
    if case == 'brand_only':
        routes[about][2] = ('<html><table><tr><th>Brand name</th><td>Cedar Motion &amp; Valve Works</td></tr></table>'
            '<section><h2>Company profile</h2><p>' + INPUT['introduction'] + '</p></section>'
            '<a href="/contact">Contact</a></html>')
        routes[contact][2] = routes[contact][2].replace('Company name', 'Brand name')
    elif case == 'conflicting_name':
        routes[contact][2] = routes[contact][2].replace('Cedar Motion &amp; Valve Works', 'Separate Company B')
    elif case == 'missing_introduction':
        routes[about][2] = routes[about][2].replace('<p>' + INPUT['introduction'] + '</p>', '')
    elif case == 'missing_href':
        for url in (about, contact, 'https://example.org/', 'https://example.org/products/cv-25'):
            import re
            routes[url][2] = re.sub(r'<a href="(?:/contact|mailto:[^"]+|tel:[^"]+)">[^<]*</a>', '', routes[url][2])
    elif case == 'js_only':
        routes[about][2] = '<html><main id="identity"></main><script>renderIdentity()</script></html>'
    elif case == 'about_403':
        routes[about][0] = 403
    elif case == 'waf':
        routes[about][2] = '<html>Verify you are human</html>'
    elif case == 'robots':
        routes['https://example.org/robots.txt'][2] = 'User-agent: *\nDisallow: /about\n'
    elif case.startswith('contact_'):
        routes[contact][0] = int(case.rsplit('_', 1)[1])
    elif case == 'name_omitted':
        routes[about][2] = routes[about][2].replace('itemprop="name"', 'class="heading"')
        routes[contact][2] = routes[contact][2].replace('Company name', 'Catalogue label')
    elif case == 'same_brand_different_legal_names':
        routes[about][2] = ('<html><table><tr><th>Brand name</th><td>Shared Cedar</td></tr>'
            '<tr><th>Legal name</th><td>Entity A</td></tr><tr><th>Legal name</th><td>Entity B</td></tr>'
            '</table><section><h2>About us</h2><p>' + INPUT['introduction'] + '</p></section>'
            '<a href="/contact">Contact</a></html>')
    elif case == 'qualification_claim_is_quote_only':
        routes[about][2] = routes[about][2].replace(INPUT['introduction'],
            'We claim legal registration, ISO certification and genuine factory status. This is an unverified source quotation.')
    transport = _Transport(routes)
    source = asyncio.run(Collector(SafeFetcher(_DNS(), transport)).capture(
        run_id, access(), limits=Limits(max_pages=max_pages, interval_seconds=0.01),
        retain_raw_html=retained))
    produced = build_pack([source])
    pack = EvidencePack.load(produced.document, produced.objects, expected_ref=produced.ref)
    execution = execute(pack, expected_pack_ref=pack.ref, evaluator_version=EVALUATOR)
    return pack, execution


def trust_row(execution):
    rule = next(r for r in execution['executions'] if r['rule_id'] == 'TRUST-01')
    assert rule['enabled'] and len(rule['observations']) == 1
    return rule['observations'][0]


def pins(pack, execution):
    return dict(expected_pack_ref=pack.ref, expected_execution_ref=execution['execution_ref'],
                expected_evaluator_version=EVALUATOR, expected_builder_version=BUILDER)


def build(pack, execution):
    return build_findings(pack, execution, **pins(pack, execution))


def trust_groups(doc):
    # Issue #34 explicitly allows an equivalently clear positive-group name.
    return {key: value for key, value in doc.items() if isinstance(value, list)
            and 'trust' in key.lower() and ('source' in key.lower() or 'fact' in key.lower())}


def package_load(doc, pack, execution):
    return FindingPackage.load(doc, pack, **pins(pack, execution), expected_package_ref=doc['package_ref'])


def reseal(doc, field='package_ref', prefix='fp-'):
    doc[field] = prefix + document_hash({k: v for k, v in doc.items() if k != field})
    return doc


def assert_no_inferred_claim_metadata(document):
    forbidden = {'trustscore', 'trustrating', 'creditscore', 'leadscore', 'revenueimpact',
        'legalentityverified', 'registrationverified', 'factoryverified', 'certificateverified',
        'qualificationverified', 'contactvalid', 'contactownershipverified', 'inquirysent',
        'inquirydelivered', 'commercialtrustworthiness'}
    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {'provenance', 'rule_execution'}:
                    continue  # Original quoted claims are evidence, not new authenticated metadata.
                normalized = key.lower().replace('_', '').replace('-', '')
                assert normalized not in forbidden, 'Unauthorized inferred claim field: ' + key
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(document)


@pytest.fixture(scope='module')
def positive():
    pack, execution = site()
    assert trust_row(execution)['observation']['result'] == 'PASS'
    # Successful build/load/verify is a precondition for EVERY mutation test:
    # rejecting an unsupported builder must never masquerade as an attack defense.
    package = build(pack, execution)
    assert package.document['builder_version'] == BUILDER
    assert package_load(package.document, pack, execution).ref == package.ref
    package.verify(pack, **pins(pack, execution), expected_package_ref=package.ref)
    return pack, execution, package


@pytest.mark.parametrize('case,expected', list(INPUT['trust_expected'].items()))
def test_contract_accepted_evaluator_independent_status_oracle(case, expected):
    pack, execution = site(case)
    assert trust_row(execution)['observation']['result'] == expected
    verify_execution(execution, pack, expected_pack_ref=pack.ref, expected_evaluator_version=EVALUATOR)


@pytest.mark.parametrize('status', [404, 410])
def test_contract_separate_broken_contact_pack_preserves_cross_rule_semantics(status):
    positive_pack, positive_execution = site()
    broken_pack, execution = site(f'contact_{status}')
    assert positive_pack.ref != broken_pack.ref
    assert positive_execution['execution_ref'] != execution['execution_ref']
    assert trust_row(positive_execution)['observation']['result'] == 'PASS'
    assert trust_row(execution)['observation']['result'] == 'UNKNOWN'
    defects = [row for rule in execution['executions'] for row in rule['observations']
               if row['observation']['result'] == 'FAIL_WITH_EVIDENCE']
    assert len(defects) == 1 and defects[0]['observation']['rule_id'] == 'CTA-02'
    assert defects[0]['target_response']['http_status'] == status


def test_ra2c3_supported_builder_is_required_not_skipped_or_stubbed():
    pack, execution = site()
    package = build(pack, execution)
    assert package.document['builder_version'] == BUILDER
    assert package_load(package.document, pack, execution).ref == package.ref


def test_ra2c3_positive_is_source_only_separate_and_fully_pinned(positive):
    pack, execution, package = positive
    doc = package.document
    groups = trust_groups(doc)
    assert len(groups) == 1, 'Need a distinct clearly named TRUST source-positive group'
    group = next(iter(groups.values()))
    assert len(group) == 1
    entry = group[0]
    assert entry['rule_id'] == 'TRUST-01' and entry['buyer_task'] == 'TRUST'
    assert entry['provenance'] == trust_row(execution), 'Do not detach, rewrite or omit verified source proof'
    row = entry['provenance']
    assert row['observation']['statement'] == STATEMENT
    assert row['observation']['evidence_ids']
    assert not any(i['rule_id'] == 'TRUST-01' and i['finding']['kind'] == 'OBSERVATION' for i in doc['items'])
    assert not any(i['rule_id'] == 'TRUST-01' for i in doc['checked_positive_paths'])
    assert doc['checked_seo_signals'] and doc['checked_product_facts'] and doc['checked_positive_paths']
    assert all(i['finding']['kind'] == 'UNKNOWN' for i in doc['items'])
    assert doc['private'] is True and doc['approval_status'] == 'NOT_APPROVED' and doc['shareable'] is False
    assert doc['expected_pack_ref'] == pack.ref and doc['execution_ref'] == execution['execution_ref']
    assert doc['rule_execution'] == execution
    assert doc['coverage'] == execution['coverage'] and doc['recorded_capture_scope'] == execution['recorded_capture_scope']
    assert doc.get('share_grant') is None and doc.get('public_report') is None
    assert_no_inferred_claim_metadata(doc)
    for citation in row['citations']:
        resolved = pack.resolve(citation['evidence_ref'], expected_pack_ref=pack.ref)
        raw = resolved['content']
        assert hashlib.sha256(raw).hexdigest() == citation['content_sha256']
        text, pos = raw.decode('utf-8'), citation['element']
        offset = sum(len(s) + 1 for s in text.split('\n')[:pos['line'] - 1]) + pos['column']
        assert text[offset:].startswith(citation['raw_element'])
        assert citation['raw_element'].startswith(pos['start_tag'])
        assert unescape(citation['raw_element'].split('>', 1)[1].rsplit('</', 1)[0]) == citation['text']
    name = next(c for c in row['citations'] if c['fact_kind'] == 'DECLARED_NAME' and c['citation_role'] == 'VALUE')
    assert name['text'] == INPUT['name'] and name['element']['line'] == 3 and name['element']['column'] == 0
    assert name['element']['path'] == '/html[1]/main[1]/h1[1]'


@pytest.mark.parametrize('case,expected', list(INPUT['trust_expected'].items()))
def test_ra2c3_status_scope_is_not_promoted_to_trust_or_defect(positive, case, expected):
    assert positive[2].document['builder_version'] == BUILDER
    pack, execution = site(case)
    doc = build(pack, execution).document
    assert package_load(doc, pack, execution).ref == doc['package_ref']
    row = trust_row(execution)
    assert row['observation']['result'] == expected
    assert doc['private'] is True and doc['approval_status'] == 'NOT_APPROVED' and doc['shareable'] is False
    assert_no_inferred_claim_metadata(doc)
    entries = [entry for values in trust_groups(doc).values() for entry in values]
    trust_items = [i for i in doc['items'] if i['rule_id'] == 'TRUST-01']
    if expected == 'PASS':
        assert len(entries) == 1 and entries[0]['provenance'] == row
        assert all(i['finding']['kind'] != 'OBSERVATION' for i in trust_items)
    else:
        assert entries == []
        assert trust_row(doc['rule_execution']) == row, 'The full unknown/blocked scope cannot disappear'
        for item in trust_items:
            assert item['outcome'] == expected and item['provenance'] == row
            assert item['finding']['kind'] == 'UNKNOWN' and item['finding']['evidence_ids'] == []
            assert item['finding']['severity'] is None
            assert item['coverage_note'] == row['observation']['coverage_note']
            assert item['gap_reason'] == row['reason']
    defects = [i for i in doc['items'] if i['finding']['kind'] == 'OBSERVATION']
    count = 1 if case in {'contact_404', 'contact_410'} else 0
    assert len(defects) == count, 'Only genuinely captured supported 404/410 href failure is a defect'
    for issue in defects:
        assert issue['rule_id'] == 'CTA-02' and issue['finding']['buyer_task'] == 'INQUIRE'
        assert issue['finding']['severity'] is None
        provenance = issue['provenance']
        assert provenance['source_page']['url'] == 'https://example.org/products/cv-25'
        assert provenance['citations'][0]['raw_href'] == '/contact'
        target = provenance['target_response']
        assert target['url'] == 'https://example.org/contact'
        assert target['http_status'] in {404, 410} and target['redirect_trace']
        assert target['error']['code'] == 'HTTP_ERROR'
        assert target['source_ref'] and target['snapshot_ref'] and target['observed_at']
        bridge = issue['guard_bridge']
        validate_evidence_graph(bridge['native_snapshot'], bridge['native_evidence'],
                                bridge['guard_observation'], issue['finding'])
        mapping = bridge['evidence_mapping'][0]
        resolved = pack.resolve(mapping['evidence_ref'], expected_pack_ref=pack.ref)
        assert bridge['native_evidence'] == resolved['source_record']
        assert issue['finding']['evidence_ids'] == [resolved['source_record']['evidence_id']]


PACKAGE_ATTACKS = (
    'name', 'introduction', 'href', 'label', 'raw_element', 'opening_tag', 'line', 'column', 'path',
    'url', 'final_url', 'observed_at', 'body_hash', 'source_ref', 'snapshot_ref', 'evidence_ref',
    'source_pointer', 'fact_kind', 'missing_provenance', 'source_pages', 'fact_ids',
    'target_status', 'target_trace', 'target_error', 'target_source', 'target_snapshot', 'target_missing',
    'scope_tenant', 'scope_run', 'scope_policy', 'scope_policy_version', 'scope_terms',
    'coverage', 'unvisited', 'blocked', 'statement_authentication', 'trust_defect', 'duplicate_positive',
    'private', 'approved', 'shareable', 'public_report', 'share_grant', 'builder', 'evaluator',
    'pack_ref', 'execution_ref', 'package_ref', 'unknown_fact', 'unknown_severity', 'unknown_statement',
)


def _positive_entry(doc):
    return next(entry for values in trust_groups(doc).values() for entry in values)


def _attack_package(doc, attack):
    entry = _positive_entry(doc)
    row = entry['provenance']
    citation = next(c for c in row['citations'] if c['fact_kind'] == 'DECLARED_NAME' and c['citation_role'] == 'VALUE')
    link = next(f for p in row['source_facts']['pages'] for f in p['facts']
                if f['kind'] == 'STATIC_CONTACT_LINK' and f['raw_href'] == '/contact')
    if attack in {'name', 'introduction'}:
        kind = 'DECLARED_NAME' if attack == 'name' else 'SELF_DESCRIPTION'
        next(c for c in row['citations'] if c['fact_kind'] == kind)['text'] = 'QA fabricated authenticated entity'
    elif attack == 'href':
        link['raw_href'] = '/qa-fabricated-contact'
    elif attack == 'label':
        next(c for c in row['citations'] if c['citation_role'] == 'LABEL')['text'] = 'QA fake label'
    elif attack in {'opening_tag', 'line', 'column', 'path'}:
        citation['element'][{'opening_tag': 'start_tag'}.get(attack, attack)] = (
            999 if attack in {'line', 'column'} else 'QA_FAKE_LOCATOR')
    elif attack in {'raw_element', 'url', 'final_url', 'observed_at', 'body_hash', 'source_ref',
                    'snapshot_ref', 'evidence_ref', 'source_pointer', 'fact_kind'}:
        key = {'body_hash': 'content_sha256', 'source_pointer': 'locator'}.get(attack, attack)
        citation[key] = 'QA_FABRICATED'
    elif attack == 'missing_provenance':
        del entry['provenance']
    elif attack == 'source_pages':
        row['source_pages'] = []
    elif attack == 'fact_ids':
        row['observation']['evidence_ids'] = ['ev-' + '0' * 64]
    elif attack.startswith('target_'):
        if attack == 'target_missing':
            del link['target_responses']
        else:
            key, value = {'target_status': ('http_status', 404), 'target_trace': ('redirect_trace', []),
                'target_error': ('error', {'code': 'HTTP_ERROR'}), 'target_source': ('source_ref', 'fake'),
                'target_snapshot': ('snapshot_ref', 'fake')}[attack]
            link['target_responses'][0][key] = value
    elif attack.startswith('scope_'):
        key = {'scope_tenant': 'tenant_id', 'scope_run': 'run_id', 'scope_policy': 'policy_id',
               'scope_policy_version': 'policy_version', 'scope_terms': 'terms_reference'}[attack]
        row['recorded_capture_scope'][0][key] = 2 if key == 'policy_version' else 'QA_OTHER_SCOPE'
    elif attack in {'coverage', 'unvisited', 'blocked'}:
        key = {'coverage': 'coverage', 'unvisited': 'unvisited_candidates', 'blocked': 'blocked_page_indices'}[attack]
        row[key] = [] if attack == 'coverage' else ['QA_fake']
    elif attack == 'statement_authentication':
        row['observation']['statement'] = 'Legally authenticated factory; certificates and inquiries are valid.'
    elif attack == 'trust_defect':
        row['observation']['result'] = 'FAIL_WITH_EVIDENCE'
    elif attack == 'duplicate_positive':
        next(iter(trust_groups(doc).values())).append(deepcopy(entry))
    elif attack in {'private', 'approved', 'shareable', 'public_report', 'share_grant', 'builder', 'evaluator'}:
        key, value = {'private': ('private', False), 'approved': ('approval_status', 'APPROVED'),
            'shareable': ('shareable', True), 'public_report': ('public_report', {'approved': True}),
            'share_grant': ('share_grant', {'audience': 'PUBLIC'}), 'builder': ('builder_version', 'ra2c2-1.0.0'),
            'evaluator': ('evaluator_version', 'ra2b4-1.0.0')}[attack]
        doc[key] = value
    elif attack in {'pack_ref', 'execution_ref', 'package_ref'}:
        key = {'pack_ref': 'expected_pack_ref'}.get(attack, attack)
        doc[key] = {'pack_ref': 'ep-', 'execution_ref': 'rx-', 'package_ref': 'fp-'}[attack] + '0' * 64
    else:
        item = next(i for i in doc['items'] if i['finding']['kind'] == 'UNKNOWN')
        key, value = {'unknown_fact': ('evidence_ids', ['QA_FAKE_FACT']),
            'unknown_severity': ('severity', 'HIGH'),
            'unknown_statement': ('statement', 'This company is fraudulent and loses revenue.')}[attack]
        item['finding'][key] = value


@pytest.mark.parametrize('attack', PACKAGE_ATTACKS)
def test_ra2c3_rehashed_package_attack_cannot_authorize_new_proof_or_privacy(positive, attack):
    pack, execution, package = positive
    doc = package.document
    _attack_package(doc, attack)
    # For package-ref attack preserve the wrong ref; every other attack gets a fresh self-hash.
    if attack != 'package_ref':
        reseal(doc)
    with pytest.raises(FindingError):
        package_load(doc, pack, execution)
    forged = FindingPackage(json.dumps(doc, sort_keys=True).encode('utf-8'))
    with pytest.raises(FindingError):
        forged.verify(pack, **pins(pack, execution), expected_package_ref=doc['package_ref'])


EXECUTION_ATTACKS = ('name', 'introduction', 'href', 'label', 'line', 'column', 'path', 'body_hash',
    'observed_at', 'source_ref', 'snapshot_ref', 'evidence_ref', 'target_status', 'target_missing',
    'scope_tenant', 'scope_policy', 'statement_authentication', 'trust_defect', 'unvisited')


@pytest.mark.parametrize('attack', EXECUTION_ATTACKS)
def test_ra2c3_rehashed_embedded_execution_also_replays_original_sources(positive, attack):
    pack, original, package = positive
    execution = deepcopy(original)
    wrapper = package.document
    # Mutate the actual embedded execution row, not merely the duplicated positive projection.
    _positive_entry(wrapper)['provenance'] = trust_row(execution)
    _attack_package(wrapper, attack)
    row = trust_row(execution)
    facts = row['source_facts']
    reseal(facts, 'facts_ref', 'tf-')
    row['observation'].pop('observation_id', None)
    row['observation']['observation_id'] = 'obs-' + document_hash(row)
    reseal(execution, 'execution_ref', 'rx-')
    with pytest.raises(FindingError):
        build(pack, execution)  # fresh expected execution ref cannot bless fabricated source facts
    wrapper['rule_execution'] = execution
    wrapper['execution_ref'] = execution['execution_ref']
    reseal(wrapper)
    with pytest.raises(FindingError):
        package_load(wrapper, pack, execution)


@pytest.mark.parametrize('field', ['tenant_id', 'run_id', 'policy_id', 'policy_version', 'coverage'])
def test_ra2c3_resealed_pack_scope_is_not_authority(positive, field):
    pack, execution, _ = positive
    doc = pack.document
    doc[field] = [] if field == 'coverage' else 2 if field == 'policy_version' else 'QA_other_scope'
    reseal(doc, 'pack_ref', 'ep-')
    forged = EvidencePack(json.dumps(doc).encode('utf-8'), tuple(sorted(pack.objects.items())))
    with pytest.raises(FindingError):
        build_findings(forged, execution, **pins(pack, execution))


def test_ra2c3_changed_original_bytes_and_other_valid_run_fail_trusted_pin(positive):
    pack, execution, _ = positive
    objects = dict(pack.objects)
    key = next(k for k, body in objects.items() if b'Cedar Motion' in body)
    objects[key] = objects[key].replace(b'Cedar Motion', b'FORGED REAL ENTITY')
    forged = EvidencePack(pack._payload, tuple(sorted(objects.items())))
    with pytest.raises(FindingError):
        build_findings(forged, execution, **pins(pack, execution))
    other, _ = site(run_id='run-qa-different-valid-run')
    with pytest.raises(FindingError):
        build_findings(other, execution, **pins(pack, execution))


@pytest.mark.parametrize('key,value', [
    ('expected_pack_ref', None), ('expected_pack_ref', 'ep-' + '0' * 64),
    ('expected_execution_ref', 'rx-' + '0' * 64), ('expected_evaluator_version', 'ra2b4-1.0.0'),
    ('expected_builder_version', 'ra2c2-1.0.0'), ('expected_builder_version', None),
    ('expected_builder_version', 'ra2c9-unreviewed'),
])
def test_ra2c3_build_load_verify_require_all_independently_held_pins(positive, key, value):
    pack, execution, package = positive
    expected = pins(pack, execution)
    expected[key] = value
    with pytest.raises(FindingError):
        build_findings(pack, execution, **expected)
    with pytest.raises(FindingError):
        FindingPackage.load(package.document, pack, **expected, expected_package_ref=package.ref)
    with pytest.raises(FindingError):
        package.verify(pack, **expected, expected_package_ref=package.ref)


def test_ra2c3_never_implicitly_upgrades_or_accepts_an_old_execution(positive):
    pack, execution, _ = positive
    implicit = pins(pack, execution)
    del implicit['expected_builder_version']
    with pytest.raises(FindingError):
        build_findings(pack, execution, **implicit)
    for evaluator in ('ra2b0-1.0.0', 'ra2b1-1.0.0', 'ra2b3-1.0.0', 'ra2b4-1.0.0'):
        old = execute(pack, expected_pack_ref=pack.ref, evaluator_version=evaluator)
        expected = pins(pack, old)
        expected['expected_evaluator_version'] = evaluator
        with pytest.raises(FindingError):
            build_findings(pack, old, **expected)


def test_ra2c3_detached_documents_and_naked_finding_are_not_mutable_proof(positive):
    pack, execution, package = positive
    original = package.document
    detached = package.document
    detached['private'] = False
    detached['rule_execution']['executions'].clear()
    assert package.document == original
    independent_input = deepcopy(execution)
    built = build(pack, independent_input)
    independent_input['executions'].clear()
    assert built.ref == package.ref
    with pytest.raises((FrozenInstanceError, AttributeError)):
        package._payload = b'{}'
    naked = original['items'][0]['finding']
    with pytest.raises(FindingError):
        FindingPackage.load(naked, pack, **pins(pack, execution), expected_package_ref=package.ref)
    with pytest.raises(FindingError):
        FindingPackage.load(original, pack, **pins(pack, execution), expected_package_ref='fp-' + '0' * 64)


def test_ra2c3_oversize_wrapper_and_nan_cannot_be_rehashed_into_a_valid_package(positive):
    pack, execution, package = positive
    doc = package.document
    doc['padding'] = 'x' * 8_000_001
    with pytest.raises(FindingError):
        package_load(doc, pack, execution)
    malformed = package.document
    malformed['unapproved_numeric_claim'] = float('nan')
    with pytest.raises(FindingError):
        package_load(malformed, pack, execution)


@pytest.mark.parametrize('attack', ['missing_target', 'status', 'trace', 'error', 'source', 'snapshot',
                                  'native_id', 'native_snapshot', 'raw_href'])
def test_ra2c3_true_broken_link_never_loses_its_inseparable_target_and_native_edge(positive, attack):
    assert positive[2].document['builder_version'] == BUILDER
    pack, execution = site('contact_404')
    package = build(pack, execution)
    doc = package.document
    issue = next(i for i in doc['items'] if i['finding']['kind'] == 'OBSERVATION')
    if attack == 'missing_target':
        del issue['provenance']['target_response']
    elif attack in {'status', 'trace', 'error', 'source', 'snapshot'}:
        key, value = {'status': ('http_status', 200), 'trace': ('redirect_trace', []),
            'error': ('error', None), 'source': ('source_ref', 'fake'), 'snapshot': ('snapshot_ref', 'fake')}[attack]
        issue['provenance']['target_response'][key] = value
    elif attack == 'native_id':
        issue['guard_bridge']['evidence_mapping'][0]['native_evidence_id'] = 'QA_fake_native_id'
    elif attack == 'native_snapshot':
        issue['guard_bridge']['native_snapshot']['sha256'] = '0' * 64
    else:
        issue['provenance']['citations'][0]['raw_href'] = '/fabricated'
    with pytest.raises(FindingError):
        package_load(reseal(doc), pack, execution)


def test_ra2c3_spoofed_target_404_cannot_create_a_defect_from_a_real_200(positive):
    pack, original, _ = positive
    execution = deepcopy(original)
    row = next(r for rule in execution['executions'] if rule['rule_id'] == 'CTA-02'
               for r in rule['observations'] if r['observation']['result'] == 'PASS')
    row['observation']['result'] = 'FAIL_WITH_EVIDENCE'
    target = row['target_response']
    target['http_status'] = 404
    target['redirect_trace'][-1]['status'] = 404
    target['error'] = {'schema_version': '1.0', 'code': 'HTTP_ERROR',
                       'safe_message': 'HTTP_ERROR', 'retryable': False}
    row['observation'].pop('observation_id', None)
    row['observation']['observation_id'] = 'obs-' + document_hash(row)
    reseal(execution, 'execution_ref', 'rx-')
    with pytest.raises(FindingError):
        build(pack, execution)


@pytest.mark.parametrize('path,builder,evaluator', [
    ('tests/fixtures/findings/industrial-diagnostic.json', 'ra2c0-1.0.0', 'ra2b1-1.0.0'),
    ('tests/findings/fixtures/info01-private-package.json', 'ra2c1-1.0.0', 'ra2b3-1.0.0'),
    ('tests/findings/fixtures/seo01-private-package.json', 'ra2c2-1.0.0', 'ra2b4-1.0.0'),
])
def test_contract_historical_sealed_bytes_and_refs_are_unchanged(path, builder, evaluator):
    data = json.loads((ROOT / path).read_text(encoding='utf-8'))
    frozen = LEGACY['fixtures'][path]
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    assert hashlib.sha256(canonical).hexdigest() == frozen['canonical_fixture_sha256']
    assert data['expected_pack_ref'] == frozen['pack_ref']
    assert data['expected_execution_ref'] == frozen['execution_ref']
    assert data['expected_package_ref'] == frozen['package_ref']
    pack = EvidencePack.load(data['document'], {k: base64.b64decode(v, validate=True)
        for k, v in data['objects_base64'].items()}, expected_ref=data['expected_pack_ref'])
    doc = data['finding_package']
    expected = dict(expected_pack_ref=pack.ref, expected_execution_ref=data['expected_execution_ref'],
                    expected_evaluator_version=evaluator, expected_builder_version=builder)
    package = build_findings(pack, doc['rule_execution'], **expected)
    assert package.ref == data['expected_package_ref']
    assert package._payload == json.dumps(doc, sort_keys=True, ensure_ascii=False,
                                         separators=(',', ':'), allow_nan=False).encode('utf-8')
    assert FindingPackage.load(doc, pack, **expected, expected_package_ref=package.ref).document == doc
    if builder == 'ra2c0-1.0.0':
        del expected['expected_builder_version']
        assert build_findings(pack, doc['rule_execution'], **expected)._payload == package._payload

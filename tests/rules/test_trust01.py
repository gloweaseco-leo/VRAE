"""Phase A pure adapter; shared evaluator dispatch remains untouched."""
from copy import deepcopy
from html import unescape
import json

import pytest

from tests.rules.test_trust_facts import trust_pack, FIXTURES
from vrae.collection.manifest import document_hash
from vrae.domain.contracts import validate_contract
from vrae.evidence import EvidenceError, EvidencePack, build_pack
from vrae.rules.trust_facts import extract
from vrae.rules.trust01 import prepare, verify_preparation, evaluate_trust, PASS_STATEMENT, RULE


def run(pack):
    return prepare(pack, expected_pack_ref=pack.ref)


def result(output):
    return output['rows'][0]['observation']['result']


def reseal(output):
    row = output['rows'][0]
    facts = row['source_facts']
    facts['facts_ref'] = 'tf-' + document_hash({k: v for k, v in facts.items() if k != 'facts_ref'})
    output['trust_facts_ref'] = facts['facts_ref']
    row['observation'].pop('observation_id', None)
    row['observation']['observation_id'] = 'obs-' + document_hash(row)
    output['preparation_ref'] = 'tp-' + document_hash({k: v for k, v in output.items() if k != 'preparation_ref'})
    return output


@pytest.fixture(scope='module')
def positive():
    pack = trust_pack()
    return pack, run(pack)


def test_complete_self_declaration_yields_only_a_prepared_positive():
    pack = trust_pack()
    output = prepare(pack, expected_pack_ref=pack.ref)
    assert output['phase'] == 'PREP_ONLY' and output['trust01_enabled'] is False
    row = output['rows'][0]
    assert row['observation']['result'] == 'PASS'
    assert row['observation']['rule_id'] == 'TRUST-01'
    assert row['observation']['kind'] == 'OBJECTIVE'
    verify_preparation(output, pack, expected_pack_ref=pack.ref)


def test_three_independent_prerequisites_full_citations_and_rule_metadata(positive):
    pack, output = positive
    row = output['rows'][0]
    observation = row['observation']
    assert observation['statement'] == PASS_STATEMENT
    validate_contract('Observation', observation)
    assert row['rule_metadata'] == {'rule_id': 'TRUST-01', 'rule_version': '1.0.0', 'buyer_task': 'TRUST'}
    assert row['blocked_page_indices'] == row['unknown_page_indices'] == row['missing_prerequisites'] == []
    assert row['unvisited_candidates'] == []
    assert {c['fact_kind'] for c in row['citations']} == {
        'DECLARED_NAME', 'SELF_DESCRIPTION', 'ADDRESS_TEXT', 'STATIC_CONTACT_LINK'}
    for citation in row['citations']:
        resolved = pack.resolve(citation['evidence_ref'], expected_pack_ref=pack.ref)
        assert citation['content_sha256'] == resolved['evidence']['content_sha256']
        raw = resolved['content'].decode('utf-8')
        pos = citation['element']
        offset = sum(len(s) + 1 for s in raw.split('\n')[:pos['line'] - 1]) + pos['column']
        assert raw[offset:].startswith(citation['raw_element'])
        assert citation['raw_element'].startswith(pos['start_tag'])
        assert unescape(citation['raw_element'].split('>', 1)[1].rsplit('</', 1)[0]) == citation['text']
    name = next(c for c in row['citations'] if c['fact_kind'] == 'DECLARED_NAME' and c['citation_role'] == 'VALUE')
    assert name['text'] == 'Heshan Meridian Valve Works'
    assert name['element']['line'] == 3 and name['element']['column'] == 0
    assert name['element']['path'] == '/html[1]/main[1]/h1[1]'
    assert set(observation['evidence_ids']) == {c['evidence_ref'] for c in row['citations']
                                             if c['fact_kind'] != 'ADDRESS_TEXT'}
    assert row['coverage'] == pack.document['coverage']
    scope = row['recorded_capture_scope'][0]
    assert all(scope[k] == pack.document[k] for k in ('tenant_id', 'run_id', 'policy_id', 'policy_version'))
    assert evaluate_trust(pack, expected_pack_ref=pack.ref) == output['rows']


def test_extractor_extracted_without_intro_is_not_adapter_pass():
    about = b'<html><table><tr><th>Company name</th><td>Heshan Meridian Valve Works</td></tr></table>'
    pack = trust_pack(about=about + b'<a href="/contact">Contact</a></html>')
    assert extract(pack, expected_pack_ref=pack.ref)['status'] == 'EXTRACTED'
    output = run(pack)
    assert result(output) == 'UNKNOWN'
    assert output['rows'][0]['missing_prerequisites'] == ['STRUCTURED_COMPANY_INTRODUCTION']


def test_brand_label_alone_is_not_an_organization_self_declaration():
    about = (b'<html><table><tr><th>Brand name</th><td>Harbor Motion</td></tr></table>'
             b'<section><h2>Company profile</h2><p>We describe our industrial drives.</p></section>'
             b'<a href="/contact">Contact</a></html>')
    contact = b'<html><table><tr><th>Brand name</th><td>Harbor Motion</td></tr></table></html>'
    pack = trust_pack(about=about, contact=contact)
    assert extract(pack, expected_pack_ref=pack.ref)['status'] == 'EXTRACTED'
    output = run(pack)
    assert result(output) == 'UNKNOWN'
    assert 'UNAMBIGUOUS_DECLARED_ORGANIZATION_NAME' in output['rows'][0]['missing_prerequisites']


@pytest.mark.parametrize('kwargs', [
    {'name': 'mixed'}, {'name': 'js'}, {'retained': False}, {'max_pages': 1},
    {'about': b'<html></html>'}, {'contact': b'<html></html>'}, {'status': 404}, {'status': 500},
    {'about': b'<html><div itemprop="name">Unscoped name</div></html>'},
])
def test_unknown_or_unvisited_relevant_scope_never_gets_aggregate_pass(kwargs):
    output = run(trust_pack(**kwargs))
    row = output['rows'][0]
    assert result(output) == 'UNKNOWN'
    assert row['observation']['kind'] == 'UNKNOWN' and row['observation']['evidence_ids'] == []
    assert row['missing_prerequisites'] or row['unknown_page_indices'] or row['unvisited_candidates']


@pytest.mark.parametrize('kwargs', [
    {'status': 403}, {'blocked': 'waf'}, {'blocked': 'robots'},
    {'contact_status': 403}, {'home_status': 403},
])
def test_every_captured_relevant_block_is_preserved(kwargs):
    pack = trust_pack(**kwargs)
    output = run(pack)
    row = output['rows'][0]
    assert result(output) == 'ACCESS_BLOCKED'
    assert row['observation']['kind'] == 'UNKNOWN' and row['observation']['evidence_ids'] == []
    assert row['blocked_page_indices']
    for index in row['blocked_page_indices']:
        assert row['source_facts']['pages'][index]['status'] == 'ACCESS_BLOCKED'
        assert row['source_pages'][index]['error']['code'] in {'ACCESS_BLOCKED', 'ROBOTS_DISALLOWED'}
    if kwargs == {'blocked': 'robots'}:
        assert extract(pack, expected_pack_ref=pack.ref)['status'] == 'EXTRACTED'
        assert any(p['status'] == 'EXTRACTED' for p in row['source_facts']['pages'])


@pytest.mark.parametrize('status', [404, 410, 500])
def test_contact_literal_with_failed_target_is_not_a_successful_inquiry(status):
    output = run(trust_pack(contact_status=status))
    row = output['rows'][0]
    assert result(output) == 'UNKNOWN' and row['observation']['evidence_ids'] == []
    link = next(f for p in row['source_facts']['pages'] for f in p['facts']
                if f['kind'] == 'STATIC_CONTACT_LINK' and f['raw_href'] == '/contact')
    assert link['target_responses'][0]['http_status'] == status
    assert link['target_responses'][0]['error'] and link['target_responses'][0]['redirect_trace']
    assert all(r['observation']['result'] not in {'FAIL_WITH_EVIDENCE', 'NOT_APPLICABLE'} for r in output['rows'])


def test_duplicate_same_name_and_links_keep_all_original_citations():
    raw = (FIXTURES / 'trust-about.html').read_text(encoding='utf-8')
    raw = raw.replace('<a href="/contact">Contact our sales team</a>',
        '<a href="/contact">Contact our sales team</a>\n<a href="/contact">Second contact entry</a>')
    output = run(trust_pack(about=raw.encode('utf-8')))
    assert result(output) == 'PASS'
    row = output['rows'][0]
    names = [c for c in row['citations'] if c['fact_kind'] == 'DECLARED_NAME' and c['citation_role'] == 'VALUE']
    assert len(names) == 2  # About microdata + contact table, same literal declaration.
    links = [c for c in row['citations'] if c['fact_kind'] == 'STATIC_CONTACT_LINK'
             and c['url'].endswith('/about')]
    assert len(links) == 2 and links[0]['element'] != links[1]['element']
    ids = row['observation']['evidence_ids']
    assert len(ids) == len(set(ids))


def test_same_brand_different_legal_self_names_remain_unknown():
    raw = (b'<html><table><tr><th>Brand name</th><td>Common Brand</td></tr>'
           b'<tr><th>Legal name</th><td>Entity A</td></tr>'
           b'<tr><th>Legal name</th><td>Entity B</td></tr></table>'
           b'<section><h2>About us</h2><p>Industrial equipment suppliers.</p></section>'
           b'<a href="/contact">Contact</a></html>')
    output = run(trust_pack(about=raw, contact=b'<html></html>'))
    assert result(output) == 'UNKNOWN' and output['rows'][0]['observation']['evidence_ids'] == []


def test_missing_contact_cannot_be_replaced_by_name_and_intro():
    about = (FIXTURES / 'trust-about.html').read_text(encoding='utf-8').replace(
        '<a href="/contact">Contact our sales team</a>', '')
    output = run(trust_pack(home=b'<html><a href="/about">About</a></html>', about=about.encode('utf-8')))
    assert result(output) == 'UNKNOWN'
    assert 'STATIC_PUBLIC_CONTACT_LINK' in output['rows'][0]['missing_prerequisites']


def test_single_home_page_can_support_a_narrow_mailto_presence_claim():
    home = (b'<html><table><tr><th>Company name</th><td>Fictional Pump Works</td></tr></table>'
            b'<section><h2>About us</h2><p>We self-describe as a pump parts supplier.</p></section>'
            b'<a href="mailto:sales@pumps.example">Email sales</a></html>')
    output = run(trust_pack(home=home))
    assert result(output) == 'PASS'
    row = output['rows'][0]
    assert len(row['source_pages']) == 1 and row['unvisited_candidates'] == []
    link = next(f for f in row['source_facts']['pages'][0]['facts'] if f['kind'] == 'STATIC_CONTACT_LINK')
    assert link['target_responses'] == [] and link['endpoint_kind'] == 'MAILTO_LITERAL'


def test_browser_only_is_not_original_source_proof():
    from tests.evidence.synthetic import browser
    output = run(build_pack([browser(True)]))
    assert result(output) == 'UNKNOWN' and output['rows'][0]['observation']['evidence_ids'] == []


@pytest.mark.parametrize('mutation', [
    'name', 'paragraph', 'href', 'line', 'column', 'path', 'start_tag', 'raw_element',
    'hash', 'evidence', 'source', 'snapshot', 'time', 'url', 'native_facts',
    'target_status', 'target_missing', 'target_trace', 'target_error', 'target_snapshot',
    'scope', 'policy', 'coverage', 'unvisited', 'blocked', 'missing', 'rule', 'version',
    'enabled', 'phase', 'statement', 'evidence_ids', 'fail', 'not_applicable',
])
def test_all_resealed_wrapper_and_inner_forgery_is_rejected(positive, mutation):
    pack, original = positive
    output = deepcopy(original)
    row = output['rows'][0]
    citation = next(c for c in row['citations'] if c['fact_kind'] == 'DECLARED_NAME' and c['citation_role'] == 'VALUE')
    link = next(f for p in row['source_facts']['pages'] for f in p['facts']
                if f['kind'] == 'STATIC_CONTACT_LINK' and f['raw_href'] == '/contact')
    if mutation in {'name', 'paragraph'}:
        kind = 'DECLARED_NAME' if mutation == 'name' else 'SELF_DESCRIPTION'
        next(c for c in row['citations'] if c['fact_kind'] == kind)['text'] = 'Fabricated source claim'
    elif mutation == 'href':
        link['raw_href'] = '/invented'
    elif mutation in {'line', 'column', 'path', 'start_tag'}:
        citation['element'][mutation] = 999 if mutation in {'line', 'column'} else 'fake'
    elif mutation in {'raw_element', 'hash', 'evidence', 'source', 'snapshot', 'time', 'url'}:
        key = {'hash': 'content_sha256', 'evidence': 'evidence_ref', 'source': 'source_ref',
               'snapshot': 'snapshot_ref', 'time': 'observed_at'}.get(mutation, mutation)
        citation[key] = 'fake'
    elif mutation == 'native_facts':
        next(f for p in row['source_facts']['pages'] for f in p['facts']
             if f['kind'] == 'DECLARED_NAME')['citation']['text'] = 'Forged company'
    elif mutation == 'target_missing':
        del link['target_responses']
    elif mutation.startswith('target_'):
        key, value = {'target_status': ('http_status', 404), 'target_trace': ('redirect_trace', []),
            'target_error': ('error', {'code': 'HTTP_ERROR'}), 'target_snapshot': ('snapshot_ref', 'fake')}[mutation]
        link['target_responses'][0][key] = value
    elif mutation in {'scope', 'policy'}:
        row['recorded_capture_scope'][0]['tenant_id' if mutation == 'scope' else 'policy_id'] = 'other'
    elif mutation in {'coverage', 'unvisited', 'blocked', 'missing'}:
        key = {'coverage': 'coverage', 'unvisited': 'unvisited_candidates',
               'blocked': 'blocked_page_indices', 'missing': 'missing_prerequisites'}[mutation]
        row[key] = [] if mutation == 'coverage' else ['fabricated']
    elif mutation == 'rule':
        row['rule_metadata']['rule_id'] = 'TRUST-02'
    elif mutation in {'enabled', 'phase', 'version'}:
        key, value = {'enabled': ('trust01_enabled', True), 'phase': ('phase', 'ENABLED'),
                      'version': ('adapter_version', 'future')}[mutation]
        output[key] = value
    elif mutation == 'statement':
        row['observation']['statement'] = 'This is a certified legitimate factory and contact works.'
    elif mutation == 'evidence_ids':
        row['observation']['evidence_ids'] = []
    else:
        row['observation']['result'] = 'FAIL_WITH_EVIDENCE' if mutation == 'fail' else 'NOT_APPLICABLE'
    with pytest.raises(EvidenceError, match='TRUST01_ADAPTER_INTEGRITY'):
        verify_preparation(reseal(output), pack, expected_pack_ref=pack.ref)


@pytest.mark.parametrize('field', ['tenant_id', 'run_id', 'policy_id', 'policy_version'])
def test_cross_scope_pack_and_recomputed_outer_pack_ref_rejected(positive, field):
    pack, _ = positive
    doc = pack.document
    doc[field] = 2 if field == 'policy_version' else 'other'
    doc['pack_ref'] = 'ep-' + document_hash({k: v for k, v in doc.items() if k != 'pack_ref'})
    forged = EvidencePack(json.dumps(doc).encode(), tuple(sorted(pack.objects.items())))
    with pytest.raises(EvidenceError):
        prepare(forged, expected_pack_ref=pack.ref)


@pytest.mark.parametrize('pin', [None, '', 'ep-' + '0' * 64])
def test_independent_pack_pin_is_required(positive, pin):
    pack, output = positive
    with pytest.raises(EvidenceError):
        prepare(pack, expected_pack_ref=pin)
    with pytest.raises(EvidenceError):
        verify_preparation(output, pack, expected_pack_ref=pin)


def test_other_valid_pack_and_changed_raw_bytes_do_not_replay(positive):
    pack, output = positive
    other = trust_pack('mixed')
    with pytest.raises(EvidenceError):
        prepare(other, expected_pack_ref=pack.ref)
    objects = dict(pack.objects)
    key = next(k for k, value in objects.items() if b'Heshan Meridian' in value)
    objects[key] = objects[key].replace(b'Heshan Meridian', b'Fake organization')
    forged = EvidencePack(pack._payload, tuple(sorted(objects.items())))
    with pytest.raises(EvidenceError):
        verify_preparation(output, forged, expected_pack_ref=pack.ref)


def test_prep_is_detached_and_requires_full_wrapper_and_bounded_output(positive, monkeypatch):
    from vrae.rules import trust01
    pack, original = positive
    altered = run(pack)
    altered['rows'][0]['rule_metadata'].clear()
    altered['rows'][0]['source_facts']['pages'].clear()
    assert RULE == {'rule_id': 'TRUST-01', 'rule_version': '1.0.0', 'buyer_task': 'TRUST'}
    assert run(pack) == original
    with pytest.raises(EvidenceError):
        verify_preparation(original['rows'][0]['observation'], pack, expected_pack_ref=pack.ref)
    large = deepcopy(original)
    large['padding'] = 'x' * 8_000_001
    with pytest.raises(EvidenceError):
        verify_preparation(large, pack, expected_pack_ref=pack.ref)
    monkeypatch.setattr(trust01, 'MAX_BYTES', 1)
    with pytest.raises(EvidenceError):
        prepare(pack, expected_pack_ref=pack.ref)


def test_phase_a_never_changes_or_enables_existing_dispatch(positive):
    from vrae.rules import execute
    pack, _ = positive
    for version in ('ra2b0-1.0.0', 'ra2b1-1.0.0', 'ra2b3-1.0.0', 'ra2b4-1.0.0'):
        before = execute(pack, expected_pack_ref=pack.ref, evaluator_version=version)
        run(pack)
        assert execute(pack, expected_pack_ref=pack.ref, evaluator_version=version) == before
        trust = next(e for e in before['executions'] if e['rule_id'] == 'TRUST-01')
        assert not trust['enabled'] and all(r['observation']['result'] == 'UNKNOWN' for r in trust['observations'])


def test_new_evaluator_is_explicit_and_inherits_five_accepted_checks(positive):
    from vrae.rules import execute, verify_execution
    pack, _ = positive
    old = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b4-1.0.0')
    new = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b6-1.0.0')
    enabled = {e['rule_id'] for e in new['executions'] if e['enabled']}
    assert enabled == {'DISC-01', 'DISC-02', 'INFO-01', 'TRUST-01', 'CTA-02', 'SEO-01'}
    assert [e for e in new['executions'] if e['rule_id'] != 'TRUST-01'] == [
        e for e in old['executions'] if e['rule_id'] != 'TRUST-01']
    assert new['journeys'] == old['journeys'] and new['coverage'] == old['coverage']
    assert new['recorded_capture_scope'] == old['recorded_capture_scope']
    assert len(new['executions']) == 16 and new['catalog_version'] == '1.0.0'
    assert all(e['rule_version'] == '1.0.0' for e in new['executions'])
    assert execute(pack, expected_pack_ref=pack.ref) == execute(
        pack, expected_pack_ref=pack.ref, evaluator_version='ra2b0-1.0.0')
    verify_execution(new, pack, expected_pack_ref=pack.ref, expected_evaluator_version='ra2b6-1.0.0')


def preparation_cases():
    """New fixed synthetic packs only; no live transport or historical fixture writes."""
    missing_intro = (b'<html><table><tr><th>Company name</th><td>Heshan Meridian Valve Works</td></tr></table>'
                     b'<a href="/contact">Contact</a></html>')
    brand = (b'<html><table><tr><th>Brand name</th><td>Harbor Motion</td></tr></table>'
             b'<section><h2>Company profile</h2><p>We describe our industrial drives.</p></section>'
             b'<a href="/contact">Contact</a></html>')
    brand_contact = b'<html><table><tr><th>Brand name</th><td>Harbor Motion</td></tr></table></html>'
    home = (b'<html><table><tr><th>Company name</th><td>Fictional Pump Works</td></tr></table>'
            b'<section><h2>About us</h2><p>We self-describe as a pump parts supplier.</p></section>'
            b'<a href="mailto:sales@pumps.example">Email sales</a></html>')
    return [
        ('complete-source-scope', trust_pack(), 'PASS'),
        ('extracted-but-no-introduction', trust_pack(about=missing_intro), 'UNKNOWN'),
        ('brand-only-is-not-company', trust_pack(about=brand, contact=brand_contact), 'UNKNOWN'),
        ('robots-block-not-rescued-by-contact', trust_pack(blocked='robots'), 'ACCESS_BLOCKED'),
        ('contact-404-keeps-literal-not-inquiry', trust_pack(contact_status=404), 'UNKNOWN'),
        ('single-home-mailto-literal', trust_pack(home=home), 'PASS'),
        ('dynamic-about', trust_pack('js'), 'UNKNOWN'),
        ('no-original-bodies', trust_pack(retained=False), 'UNKNOWN'),
    ]


def test_sealed_preparation_examples_replay_without_enabling_dispatch():
    import base64
    from pathlib import Path
    data = json.loads((Path(__file__).parent / 'fixtures/trust01-preparation.json').read_text(encoding='utf-8'))
    assert data['phase'] == 'PREP_ONLY' and data['trust01_enabled'] is False
    for case in data['cases']:
        pack = EvidencePack.load(case['document'], {
            k: base64.b64decode(v, validate=True) for k, v in case['objects_base64'].items()
        }, expected_ref=case['expected_pack_ref'])
        output = case['preparation']
        verify_preparation(output, pack, expected_pack_ref=case['expected_pack_ref'])
        assert output['preparation_ref'] == case['expected_preparation_ref']
        assert result(output) == case['expected_result']


def combined_pack():
    home = (b'<html><head><title>Industrial valves &amp; actuators</title>'
            b'<link rel="canonical" href="https://example.org/"></head><body><nav>'
            b'<a href="/about">About us</a><a href="/contact">Contact</a></nav></body></html>')
    return trust_pack(home=home)


def execution_cases():
    return preparation_cases() + [('seo-and-trust-source-positives', combined_pack(), 'PASS')]


@pytest.mark.parametrize('index', range(9))
def test_new_execution_status_matrix_and_old_five_rows_preserved(index):
    from vrae.rules import execute, verify_execution
    _, pack, expected = execution_cases()[index]
    output = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b6-1.0.0')
    baseline = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b4-1.0.0')
    trust = next(e for e in output['executions'] if e['rule_id'] == 'TRUST-01')
    assert trust['enabled'] and trust['buyer_task'] == 'TRUST'
    assert trust['observations'][0]['observation']['result'] == expected
    assert [e for e in output['executions'] if e['rule_id'] != 'TRUST-01'] == [
        e for e in baseline['executions'] if e['rule_id'] != 'TRUST-01']
    if expected != 'PASS':
        assert trust['observations'][0]['observation']['evidence_ids'] == []
    if index == 8:
        seo = next(e for e in output['executions'] if e['rule_id'] == 'SEO-01')
        assert seo['observations'][0]['observation']['result'] == 'PASS'
    verify_execution(output, pack, expected_pack_ref=pack.ref, expected_evaluator_version='ra2b6-1.0.0')


@pytest.fixture(scope='module')
def integrated():
    from vrae.rules import execute
    pack = combined_pack()
    return pack, execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b6-1.0.0')


@pytest.mark.parametrize('mutation', ['text', 'paragraph', 'href', 'line', 'hash', 'time',
    'target_status', 'target_missing', 'trace', 'source', 'snapshot', 'coverage', 'tenant',
    'policy', 'unvisited', 'statement', 'evidence', 'version', 'fail'])
def test_complete_resealed_execution_forgery_rejected(integrated, mutation):
    from vrae.rules import verify_execution
    pack, original = integrated
    output = deepcopy(original)
    row = next(e for e in output['executions'] if e['rule_id'] == 'TRUST-01')['observations'][0]
    citation = next(c for c in row['citations'] if c['fact_kind'] == 'DECLARED_NAME' and c['citation_role'] == 'VALUE')
    link = next(f for p in row['source_facts']['pages'] for f in p['facts']
                if f['kind'] == 'STATIC_CONTACT_LINK' and f['raw_href'] == '/contact')
    if mutation in {'text', 'paragraph'}:
        kind = 'DECLARED_NAME' if mutation == 'text' else 'SELF_DESCRIPTION'
        next(c for c in row['citations'] if c['fact_kind'] == kind)['text'] = 'Forged value'
    elif mutation == 'href':
        link['raw_href'] = '/invented'
    elif mutation == 'line':
        citation['element']['line'] = 999
    elif mutation in {'hash', 'time', 'source', 'snapshot'}:
        citation[{'hash': 'content_sha256', 'time': 'observed_at',
                  'source': 'source_ref', 'snapshot': 'snapshot_ref'}[mutation]] = 'fake'
    elif mutation == 'target_status':
        link['target_responses'][0]['http_status'] = 404
    elif mutation == 'target_missing':
        del link['target_responses']
    elif mutation == 'trace':
        link['target_responses'][0]['redirect_trace'] = []
    elif mutation == 'coverage':
        row['coverage'] = []
    elif mutation in {'tenant', 'policy'}:
        row['recorded_capture_scope'][0]['tenant_id' if mutation == 'tenant' else 'policy_id'] = 'other'
    elif mutation == 'unvisited':
        row['unvisited_candidates'] = [{'url': 'https://example.org/fake'}]
    elif mutation == 'statement':
        row['observation']['statement'] = 'Certified legitimate factory; inquiries succeed.'
    elif mutation == 'evidence':
        row['observation']['evidence_ids'] = ['ev-' + '0' * 64]
    elif mutation == 'version':
        output['evaluator_version'] = 'ra2b4-1.0.0'
    else:
        row['observation']['result'] = 'FAIL_WITH_EVIDENCE'
    facts = row['source_facts']
    facts['facts_ref'] = 'tf-' + document_hash({k: v for k, v in facts.items() if k != 'facts_ref'})
    row['observation'].pop('observation_id', None)
    row['observation']['observation_id'] = 'obs-' + document_hash(row)
    output['execution_ref'] = 'rx-' + document_hash({k: v for k, v in output.items() if k != 'execution_ref'})
    with pytest.raises(EvidenceError):
        verify_execution(output, pack, expected_pack_ref=pack.ref, expected_evaluator_version='ra2b6-1.0.0')
    with pytest.raises(EvidenceError):
        verify_execution(output, pack, expected_pack_ref=pack.ref)


@pytest.mark.parametrize('builder,evaluator', [('ra2c0-1.0.0', 'ra2b1-1.0.0'), ('ra2c1-1.0.0', 'ra2b3-1.0.0')])
def test_accepted_finding_builders_reject_actual_new_execution_and_version_spoof(integrated, builder, evaluator):
    from vrae.findings import build_findings, FindingError
    pack, execution = integrated
    with pytest.raises(FindingError):
        build_findings(pack, execution, expected_pack_ref=pack.ref,
            expected_execution_ref=execution['execution_ref'], expected_evaluator_version='ra2b6-1.0.0',
            expected_builder_version=builder)
    fake = deepcopy(execution)
    fake['evaluator_version'] = evaluator
    fake['execution_ref'] = 'rx-' + document_hash({k: v for k, v in fake.items() if k != 'execution_ref'})
    with pytest.raises(FindingError):
        build_findings(pack, fake, expected_pack_ref=pack.ref, expected_execution_ref=fake['execution_ref'],
                       expected_evaluator_version=evaluator, expected_builder_version=builder)


def test_new_execution_requires_pack_and_expected_version_pins(integrated):
    from vrae.rules import execute, verify_execution
    pack, execution = integrated
    for pin in (None, '', 'ep-' + '0' * 64):
        with pytest.raises(EvidenceError):
            execute(pack, expected_pack_ref=pin, evaluator_version='ra2b6-1.0.0')
        with pytest.raises(EvidenceError):
            verify_execution(execution, pack, expected_pack_ref=pin,
                             expected_evaluator_version='ra2b6-1.0.0')
    with pytest.raises(EvidenceError):
        verify_execution(execution, pack, expected_pack_ref=pack.ref,
                         expected_evaluator_version='ra2b4-1.0.0')


def test_sealed_new_executions_and_all_historical_refs_replay():
    import base64
    from pathlib import Path
    from vrae.rules import execute, verify_execution
    data = json.loads((Path(__file__).parent / 'fixtures/trust01-execution.json').read_text(encoding='utf-8'))
    assert data['evaluator_version'] == 'ra2b6-1.0.0' and len(data['cases']) == 9
    for case in data['cases']:
        pack = EvidencePack.load(case['document'], {
            k: base64.b64decode(v, validate=True) for k, v in case['objects_base64'].items()
        }, expected_ref=case['expected_pack_ref'])
        verify_execution(case['execution'], pack, expected_pack_ref=case['expected_pack_ref'],
                         expected_evaluator_version='ra2b6-1.0.0')
        for version, ref in case['historical_execution_refs'].items():
            assert execute(pack, expected_pack_ref=pack.ref, evaluator_version=version)['execution_ref'] == ref

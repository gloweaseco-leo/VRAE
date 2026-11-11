"""INFO-01 positive source facts only; legacy evaluators and FindingBuilder stay pinned."""
import base64
from copy import deepcopy
import json
from pathlib import Path

import pytest

from tests.rules.test_product_facts import product_pack
from vrae.collection.manifest import CaptureBundle, document_hash
from vrae.domain.contracts import validate_contract
from vrae.evidence import EvidenceError, EvidencePack, build_pack
from vrae.rules import execute, verify_execution
from vrae.rules.product_facts import extract

VERSION = 'ra2b3-1.0.0'


def run(pack):
    return execute(pack, expected_pack_ref=pack.ref, evaluator_version=VERSION)


def info(output):
    return next(r for r in output['executions'] if r['rule_id'] == 'INFO-01')


def test_pinned_product_name_and_specs_become_single_bounded_positive():
    pack = product_pack()
    output = run(pack)
    rule = info(output)
    assert rule['enabled'] and rule['buyer_task'] == 'UNDERSTAND'
    assert rule['rule_version'] == '1.0.0'
    assert len(rule['observations']) == 1
    row = rule['observations'][0]
    observation = row['observation']
    validate_contract('Observation', observation)
    assert observation['result'] == 'PASS' and observation['kind'] == 'OBJECTIVE'
    assert 'static HTML' in observation['statement']
    assert row['source_page']['url'] == 'https://example.org/products/sv-40'
    assert row['source_page']['http_status'] == 200
    facts = extract(pack, expected_pack_ref=pack.ref)['pages'][0]
    citations = row['citations']
    assert citations[0]['fact_role'] == 'NAME'
    assert citations[0]['text'] == facts['name']['text']
    assert len(citations) == 7
    for citation in citations:
        resolved = pack.resolve(citation['evidence_ref'], expected_pack_ref=pack.ref)
        pos = citation['element']
        raw = resolved['content'].decode('utf-8')
        assert raw.splitlines()[pos['line'] - 1][pos['column']:].startswith(
            pos['start_tag'] + citation['text'] + '</')
        assert citation['content_sha256'] == resolved['evidence']['content_sha256']
    assert observation['evidence_ids'] == sorted({c['evidence_ref'] for c in citations})
    assert [c['text'] for c in citations if c['fact_role'] == 'SPEC_VALUE'] == [
        'Stainless steel 316L', 'PN 40 (4.0 MPa)', 'DN 50']
    assert output == run(pack)
    verify_execution(output, pack, expected_pack_ref=pack.ref, expected_evaluator_version=VERSION)


@pytest.mark.parametrize('fixture,kwargs,expected', [
    ('empty', {}, 'UNKNOWN'), ('conflict', {}, 'UNKNOWN'),
    ('variant', {}, 'UNKNOWN'), ('no-parameters', {}, 'UNKNOWN'),
    ('valve', {'retained': False}, 'UNKNOWN'), ('valve', {'max_pages': 1}, 'UNKNOWN'),
    ('valve', {'status': 403}, 'ACCESS_BLOCKED'), ('valve', {'blocked': 'waf'}, 'ACCESS_BLOCKED'),
    ('valve', {'blocked': 'robots'}, 'ACCESS_BLOCKED'), ('valve', {'status': 404}, 'UNKNOWN'),
    ('valve', {'status': 500}, 'UNKNOWN'),
    ('valve', {'markup': b'<html><h1>Valve</h1><table><tr><th>Size</th><td>50'}, 'UNKNOWN'),
    ('valve', {'markup': b'<html><h1>Valve</h1><script>render()</script></html>'}, 'UNKNOWN'),
    ('valve', {'markup': b'<html><h1>Valve</h1><table><tr><th>Size</th><td>50</td></tr>'
                           b'<tr><th>Size</th><td>50</td></tr></table></html>'}, 'UNKNOWN'),
])
def test_gaps_and_blocked_never_become_fail(fixture, kwargs, expected):
    pack = product_pack(fixture, **kwargs)
    output = run(pack)
    for row in info(output)['observations']:
        observation = row['observation']
        validate_contract('Observation', observation)
        assert observation['result'] == expected
        assert observation['kind'] == 'UNKNOWN' and observation['evidence_ids'] == []
    verify_execution(output, pack, expected_pack_ref=pack.ref)


def test_one_nonempty_field_is_sufficient_without_industry_guessing():
    pack = product_pack(markup=b'<html><h1>Valve V1</h1><table><tr><th>X-17</th>'
                              b'<td>42</td></tr></table></html>')
    assert info(run(pack))['observations'][0]['observation']['result'] == 'PASS'


def test_mixed_pages_remain_page_scoped():
    from tests.rules.test_journey import journey_pack
    from tests.rules.test_product_facts import FIXTURES
    html = (FIXTURES / 'product-info-valve.html').read_bytes().replace(
        b'</main>', b'<a href="/products/broken">Other valve</a></main>')
    pack = journey_pack(stage=3, markup=html)
    rows = info(run(pack))['observations']
    assert {r['observation']['result'] for r in rows} == {'PASS', 'UNKNOWN'}
    assert len({r['source_page']['snapshot_ref'] for r in rows}) == 2


def test_old_versions_keep_full_rows_and_twelve_deferred_rules_stay_unknown():
    pack = product_pack()
    old = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b1-1.0.0')
    new = run(pack)
    assert execute(pack, expected_pack_ref=pack.ref) == execute(
        pack, expected_pack_ref=pack.ref, evaluator_version='ra2b0-1.0.0')
    assert not info(old)['enabled']
    for before, after in zip(old['executions'], new['executions']):
        if before['rule_id'] != 'INFO-01':
            assert before == after
    assert sum(r['enabled'] for r in new['executions']) == 4
    assert all(r['observations'][0]['observation']['result'] == 'UNKNOWN'
               for r in new['executions'] if not r['enabled'])


@pytest.mark.parametrize('mutation', ['name', 'label', 'value', 'line', 'column', 'path',
    'evidence_id', 'citation_ref', 'source', 'snapshot', 'hash', 'time', 'url',
    'tenant', 'run', 'policy', 'policy_version', 'rule_version', 'evaluator', 'statement',
    'result', 'missing_citation', 'missing_source', 'coverage'])
def test_resealed_execution_cannot_forge_product_facts(mutation):
    pack = product_pack()
    output = deepcopy(run(pack))
    row = info(output)['observations'][0]
    obs = row['observation']
    citation = row['citations'][1]
    if mutation in ('name', 'label', 'value'):
        row['citations'][{'name': 0, 'label': 1, 'value': 2}[mutation]]['text'] = 'fabricated'
    elif mutation in ('line', 'column', 'path'):
        citation['element'][mutation] = '/fake' if mutation == 'path' else 999
    elif mutation == 'evidence_id':
        obs['evidence_ids'] = ['ev-' + '0' * 64]
    elif mutation == 'citation_ref':
        citation['evidence_ref'] = 'ev-' + '0' * 64
    elif mutation in ('source', 'snapshot', 'hash', 'time', 'url'):
        citation[{'source': 'source_ref', 'snapshot': 'snapshot_ref', 'hash': 'content_sha256',
                  'time': 'observed_at', 'url': 'url'}[mutation]] = 'fabricated'
    elif mutation in ('tenant', 'run'):
        obs[mutation + '_id'] = 'other-scope'
    elif mutation in ('policy', 'policy_version'):
        output['recorded_capture_scope'][0][mutation + '_id' if mutation == 'policy' else mutation] = 'other'
    elif mutation == 'rule_version':
        obs['rule_version'] = '9.0.0'
    elif mutation == 'evaluator':
        output['evaluator_version'] = 'ra2b1-1.0.0'
    elif mutation == 'statement':
        obs['statement'] = 'Certified complete and accurate product information'
    elif mutation == 'result':
        obs['result'] = 'FAIL_WITH_EVIDENCE'
    elif mutation == 'missing_citation':
        row['citations'].pop()
    elif mutation == 'missing_source':
        del row['source_page']
    else:
        output['coverage'] = []
    output['execution_ref'] = 'rx-' + document_hash({k: v for k, v in output.items() if k != 'execution_ref'})
    with pytest.raises(EvidenceError):
        verify_execution(output, pack, expected_pack_ref=pack.ref, expected_evaluator_version=VERSION)
    with pytest.raises(EvidenceError):
        verify_execution(output, pack, expected_pack_ref=pack.ref)


@pytest.mark.parametrize('field', ['tenant_id', 'run_id', 'policy_id', 'policy_version', 'blob'])
def test_tampered_source_pack_refused(field):
    pack = product_pack()
    doc, objects = pack.document, dict(pack.objects)
    if field == 'blob':
        item = extract(pack, expected_pack_ref=pack.ref)['pages'][0]['name']
        ev = next(e for e in doc['evidence'] if e['evidence_ref'] == item['evidence_ref'])
        objects[ev['blob_ref']] = b'<html>fabricated source</html>'
    else:
        doc[field] = 2 if field == 'policy_version' else 'other-scope'
    doc['pack_ref'] = 'ep-' + document_hash({k: v for k, v in doc.items() if k != 'pack_ref'})
    forged = EvidencePack(json.dumps(doc).encode(), tuple(sorted(objects.items())))
    with pytest.raises(EvidenceError):
        execute(forged, expected_pack_ref=forged.ref, evaluator_version=VERSION)


@pytest.mark.parametrize('pin', [None, '', 'ep-' + '0' * 64])
def test_wrong_or_missing_pin(pin):
    with pytest.raises(EvidenceError):
        execute(product_pack(), expected_pack_ref=pin, evaluator_version=VERSION)


def test_valid_cross_scope_and_old_packs_do_not_match_trusted_pin():
    pack = product_pack()
    source = pack.document['sources'][0]
    for field, value in [('tenant_id', 'other-tenant'), ('run_id', 'other-run'),
                         ('policy_id', 'other-policy'), ('policy_version', 2)]:
        doc = deepcopy(source['document'])
        def rescope(node):
            if isinstance(node, dict):
                for key in node:
                    if key == field:
                        node[key] = value
                    else:
                        rescope(node[key])
            elif isinstance(node, list):
                for item in node:
                    rescope(item)
        rescope(doc)
        doc['manifest_sha256'] = document_hash({k: v for k, v in doc.items() if k != 'manifest_sha256'})
        other = build_pack([CaptureBundle(doc, {k: pack.objects[v] for k, v in source['object_refs'].items()})])
        with pytest.raises(EvidenceError):
            execute(other, expected_pack_ref=pack.ref, evaluator_version=VERSION)
    with pytest.raises(EvidenceError):
        execute(product_pack('empty'), expected_pack_ref=pack.ref, evaluator_version=VERSION)


def test_finding_builder_does_not_accept_new_evaluator():
    from vrae.findings import build_findings, FindingError
    pack = product_pack()
    output = run(pack)
    for requested in (VERSION, 'ra2b1-1.0.0'):
        with pytest.raises(FindingError):
            build_findings(pack, output, expected_pack_ref=pack.ref,
                expected_execution_ref=output['execution_ref'], expected_evaluator_version=requested)


def test_browser_only_pack_is_unknown_and_wrong_version_is_refused():
    from tests.evidence.synthetic import browser
    pack = build_pack([browser(True)])
    output = run(pack)
    row = info(output)['observations'][0]
    assert row['observation']['result'] == 'UNKNOWN'
    assert row['citations'] == [] and row['observation']['evidence_ids'] == []
    verify_execution(output, pack, expected_pack_ref=pack.ref, expected_evaluator_version=VERSION)
    with pytest.raises(EvidenceError):
        verify_execution(output, pack, expected_pack_ref=pack.ref,
                         expected_evaluator_version='ra2b1-1.0.0')
    with pytest.raises(EvidenceError):
        execute(pack, expected_pack_ref=pack.ref, evaluator_version='future-9.0.0')


def test_new_sealed_example_replays_without_changing_historical_versions():
    data = json.loads((Path(__file__).parent /
        'fixtures/info01-product-observation.json').read_text(encoding='utf-8'))
    pack = EvidencePack.load(data['document'], {k: base64.b64decode(v, validate=True)
        for k, v in data['objects_base64'].items()}, expected_ref=data['expected_pack_ref'])
    assert run(pack) == data['expected_execution']
    for version, expected in data['historical_execution_refs'].items():
        assert execute(pack, expected_pack_ref=pack.ref, evaluator_version=version)['execution_ref'] == expected

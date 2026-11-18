"""Mandatory explicit Batch2 suite; preserve the frozen default CI inventory."""
from copy import deepcopy
import hashlib
import json

import pytest

from tests.s2_contract.batch2_fixtures import fixture, identity, table, DIRECTORY
from vrae.collection.manifest import document_hash
from vrae.evidence import EvidenceError
from vrae.industry.l2_v1 import pack as configuration
from vrae.rules import s2

VERSION = 's2-projection-1.2.0'


def scope(pack):
    return {k: pack.document[k] for k in ('tenant_id', 'run_id', 'policy_id', 'policy_version')}


def pins(pack, profile_id='industrial'):
    config = configuration.load_s2(tenant_id=pack.document['tenant_id'], profile_id=profile_id)
    return s2.IndustryPins(config['industry_ref'], pack.document['tenant_id'],
                           profile_id=profile_id)


def evaluate(pack, profile_id='industrial'):
    return s2.evaluate_s2(pack, expected_pack_ref=pack.ref, trusted_scope=scope(pack),
                         projection_version=VERSION, industry_pins=pins(pack, profile_id))


def rows(out, rule, model=None):
    return [r for r in out['industrial_projection']['rows']
            if r['observation']['rule_id'] == rule and (model is None or r['model'] == model)]


@pytest.fixture(scope='module')
def baseline():
    pack = fixture()
    return pack, evaluate(pack)


def test_three_rules_replay_from_original_bytes_and_configuration(baseline):
    pack, out = baseline
    for rule in ('INFO-02', 'TRUST-02', 'TRUST-03'):
        assert any(r['observation']['result'] == 'PASS' for r in rows(out, rule))
    for row in out['industrial_projection']['rows']:
        for c in row['citations']:
            raw = pack.resolve(c['evidence_ref'], expected_pack_ref=pack.ref)['content']
            assert raw[c['byte_start']:c['byte_end']].decode() == c['quote']
            assert hashlib.sha256(raw).hexdigest() == c['content_sha256']
    s2.verify_s2_projection(out, pack, expected_pack_ref=pack.ref, trusted_scope=scope(pack),
        expected_projection_ref=out['projection_ref'], expected_projection_version=VERSION,
        industry_pins=pins(pack))
    assert out['projection_ref'].startswith('s2p-')
    assert len(out['s2_capabilities']) == 16
    assert sum(r['enabled'] for r in out['baseline_execution']['executions']) == 6
    assert out['industrial_projection']['engineering_fit'] == 'UNKNOWN'
    assert out['industrial_projection']['authentication'] == 'UNKNOWN'


def test_industry_v1_default_bytes_and_parent_remain_unchanged():
    before = configuration.load()
    current = configuration.load_s2()
    assert configuration.load() == before
    assert current['industry_pack']['version'] == current['profile']['version'] == '1.1.0'
    assert current['parent_industry_ref'] == before['industry_ref']
    assert current['profile']['families'] == before['profile']['families']
    assert current['profile']['units'] == before['profile']['units']


def test_no_independent_config_pin_is_unknown_not_an_inferred_default():
    pack = fixture()
    out = s2.evaluate_s2(pack, expected_pack_ref=pack.ref, trusted_scope=scope(pack), projection_version=VERSION)
    assert {r['observation']['result'] for r in out['industrial_projection']['rows']} == {'UNKNOWN'}
    assert out['industrial_projection']['industry_ref'] is None


@pytest.mark.parametrize('value', ['10 psi', '10-20 bar', 'PN10', '1e9 bar', '400 V'])
def test_unsupported_or_wrong_dimension_units_are_unknown(value):
    raw = (DIRECTORY / 'pump.html').read_bytes().replace(b'10 bar', value.encode())
    raw = raw.replace(b'</table>', b'<tr><th>Data revision</th><td>R1</td></tr><tr><th>Specification conditions</th><td>Water 20 degC</td></tr></table>')
    out = evaluate(fixture(overrides={'/products/p40': raw}))
    assert {r['observation']['result'] for r in rows(out, 'INFO-02', 'P40')} == {'UNKNOWN'}


def test_equivalent_units_and_model_beyond_demo_are_bounded_not_engineering_fit():
    raw = (DIRECTORY / 'pump.html').read_bytes().replace(b'P40', b'P80').replace(b'12 m3/h', b'200 L/min')
    raw = raw.replace(b'</table>', b'<tr><th>Data revision</th><td>R2</td></tr><tr><th>Specification conditions</th><td>Water 20 degC</td></tr></table>')
    out = evaluate(fixture(overrides={'/products/p40': raw}))
    info = rows(out, 'INFO-02', 'P80')[0]
    assert info['observation']['result'] == 'PASS'
    assert info['details']['normalized_quantities']['flow'] == {'dimension': 'flow', 'value': '12.00'}
    assert info['details']['engineering_fit'] == 'UNKNOWN'
    assert rows(out, 'TRUST-02', 'P80')[0]['observation']['result'] == 'UNKNOWN'


@pytest.mark.parametrize('missing', ['Data revision', 'Specification conditions', 'Rated flow'])
def test_missing_revision_conditions_or_pdf_only_attribute_is_unknown(missing):
    pack = fixture()
    # Copy saved producer input for the counterfactual, not the projected DTO.
    raw = next(pack.resolve(e['evidence_ref'], expected_pack_ref=pack.ref)['content']
               for e in pack.document['evidence']
               if next(s for s in pack.document['snapshots'] if s['snapshot_ref'] == e['snapshot_ref'])['url'].endswith('/p40'))
    import re
    raw = re.sub(b'<tr><th>' + missing.encode() + b'</th><td>[^<]*</td></tr>', b'', raw)
    raw = raw.replace(b'</body>', b'<a href="/data.pdf">Technical datasheet</a><img src="/curve.png"></body>')
    out = evaluate(fixture(overrides={'/products/p40': raw}))
    assert rows(out, 'INFO-02', 'P40')[0]['observation']['result'] == 'UNKNOWN'
    assert not any(r['observation']['result'] == 'FAIL_WITH_EVIDENCE' for r in rows(out, 'INFO-02'))


def test_duplicate_model_revisions_are_not_merged():
    raw = (DIRECTORY / 'valve.html').read_bytes().replace(b'V25', b'P40')
    out = evaluate(fixture(overrides={'/products/v25': raw}))
    assert {r['observation']['result'] for r in rows(out, 'INFO-02', 'P40')} == {'UNKNOWN'}


@pytest.mark.parametrize('kind,fields', [
    ('certificate', {'Certificate issuer': 'Demo issuer', 'Certificate reference': 'DEMO-01', 'Certificate valid until': '2025-01-01'}),
    ('case', {'Case issuer': 'Demo author', 'Case reference': 'CASE-01', 'Case date': '2025-01-01'}),
    ('factory', {'Factory statement issuer': 'Demo operator', 'Factory statement reference': 'FACTORY-01', 'Factory statement date': '2025-01-01'}),
])
def test_proof_display_context_never_authenticates_or_invalidates(kind, fields):
    proof = table('Supplier proof', {'Proof type': kind, 'Applicable models': 'P40', **fields})
    out = evaluate(fixture(overrides={'/products/proof': proof}))
    row = rows(out, 'TRUST-02', 'P40')[0]
    assert row['observation']['result'] == 'PASS'
    assert row['details']['authentication'] == 'UNKNOWN'
    assert row['details']['date_relation'] == 'BEFORE_CAPTURE'
    assert row['details']['human_review_required'] is True


@pytest.mark.parametrize('change', ['wrong-model', 'missing-issuer', 'bad-date', 'unknown-kind'])
def test_proof_unresolved_context_remains_unknown(change):
    fields = {'Proof type': 'certificate', 'Applicable models': 'P40',
              'Certificate issuer': 'Demo issuer', 'Certificate reference': 'DEMO-01',
              'Certificate valid until': '2027-01-01'}
    if change == 'wrong-model':
        fields['Applicable models'] = 'P400'
    elif change == 'missing-issuer':
        del fields['Certificate issuer']
    elif change == 'bad-date':
        fields['Certificate valid until'] = 'yesterday'
    else:
        fields['Proof type'] = 'authenticated certification'
    out = evaluate(fixture(overrides={'/products/proof': table('Supplier proof', fields)}))
    assert rows(out, 'TRUST-02', 'P40')[0]['observation']['result'] == 'UNKNOWN'


def test_cited_conflicting_address_is_candidate_for_human_review():
    out = evaluate(fixture(overrides={'/contact': identity(address='20 Other Demo Road')}))
    row = rows(out, 'TRUST-03')[0]
    assert row['observation']['result'] == 'UNKNOWN'
    assert row['details']['literal_conflicts'] == ['address']
    assert row['details']['identity_assurance'] == 'SOURCE_DECLARED_IDENTIFIER_ONLY'
    assert len({c['snapshot_ref'] for c in row['citations']}) == 2


@pytest.mark.parametrize('args', [{'entity': 'OTHER-002'}, {'entity': ''}, {'namespace': 'unconfigured-registry'}])
def test_same_name_does_not_merge_unresolved_entities(args):
    out = evaluate(fixture(overrides={'/contact': identity(**args)}))
    row = rows(out, 'TRUST-03')[0]
    assert row['observation']['result'] == 'UNKNOWN'
    assert row['details']['literal_conflicts'] == []


def test_not_applicable_requires_independently_pinned_explicit_configuration():
    pack = fixture()
    industrial = evaluate(pack)
    assert rows(industrial, 'INFO-02', 'V25')[0]['observation']['result'] == 'PASS'
    pump_only = evaluate(pack, 'pump-only')
    for rule in ('INFO-02', 'TRUST-02'):
        row = rows(pump_only, rule, 'V25')[0]
        assert row['observation']['result'] == 'NOT_APPLICABLE'
        assert row['details']['configuration_locator']
    technical = evaluate(pack, 'technical-only')
    for rule in ('TRUST-02', 'TRUST-03'):
        assert {r['observation']['result'] for r in rows(technical, rule)} == {'NOT_APPLICABLE'}


@pytest.mark.parametrize('rule,path', [('INFO-02', '/products/p40'), ('TRUST-02', '/products/proof'), ('TRUST-03', '/contact')])
def test_access_blocked_is_not_website_fault(rule, path):
    out = evaluate(fixture(statuses={path: 403}))
    assert any(r['observation']['result'] == 'ACCESS_BLOCKED' for r in rows(out, rule))


def test_unretained_sources_cannot_assert_pass_or_not_applicable():
    out = evaluate(fixture(retain=False))
    assert {r['observation']['result'] for r in out['industrial_projection']['rows']} == {'UNKNOWN'}


@pytest.mark.parametrize('field', ['quote', 'byte_start', 'byte_end', 'element_path', 'evidence_ref',
                                   'source_ref', 'result', 'version', 'configuration'])
def test_self_rehash_and_fake_source_location_are_rejected(baseline, field):
    pack, original = baseline
    out = deepcopy(original)
    row = next(r for r in rows(out, 'INFO-02') if r['citations'])
    if field in ('quote', 'source_ref', 'element_path', 'evidence_ref'):
        row['citations'][0][field] = 'forged'
    elif field in ('byte_start', 'byte_end'):
        row['citations'][0][field] += 1
    elif field == 'result':
        row['observation']['result'] = 'FAIL_WITH_EVIDENCE'
    elif field == 'version':
        row['observation']['rule_version'] = 'forged'
    else:
        out['industrial_projection']['industry_ref'] = 'ip-' + '0' * 64
    out['projection_ref'] = 's2p-' + document_hash({k: v for k, v in out.items() if k != 'projection_ref'})
    with pytest.raises(EvidenceError):
        s2.verify_s2_projection(out, pack, expected_pack_ref=pack.ref, trusted_scope=scope(pack),
            industry_pins=pins(pack), expected_projection_ref=out['projection_ref'], expected_projection_version=VERSION)


@pytest.mark.parametrize('field', ['tenant_id', 'run_id', 'policy_id', 'policy_version'])
def test_cross_scope_cannot_replay(baseline, field):
    pack, _ = baseline
    invalid = {**scope(pack), field: 99 if field == 'policy_version' else 'foreign'}
    with pytest.raises(EvidenceError):
        s2.evaluate_s2(pack, expected_pack_ref=pack.ref, trusted_scope=invalid,
                       projection_version=VERSION, industry_pins=pins(pack))


def test_configuration_ref_tenant_profile_and_version_cannot_be_rebound(baseline):
    from dataclasses import replace
    pack, _ = baseline
    held = pins(pack)
    for bad in (replace(held, industry_ref='ip-' + '0' * 64), replace(held, tenant_id='foreign'),
                replace(held, profile_id='pump-only'), replace(held, version='9.0.0')):
        with pytest.raises(EvidenceError):
            s2.evaluate_s2(pack, expected_pack_ref=pack.ref, trusted_scope=scope(pack),
                           projection_version=VERSION, industry_pins=bad)


def test_no_native_finding_or_execution_admission(baseline):
    from vrae.rules import verify_execution
    from vrae.findings import build_findings, FindingError
    pack, out = baseline
    with pytest.raises(EvidenceError):
        verify_execution(out, pack, expected_pack_ref=pack.ref, expected_evaluator_version=VERSION)
    with pytest.raises(FindingError):
        build_findings(pack, out, expected_pack_ref=pack.ref, expected_execution_ref=out['projection_ref'],
            expected_evaluator_version=VERSION, expected_builder_version='ra2c3-1.0.0')


def test_missing_buyer_conditions_do_not_turn_into_website_fault():
    # No buyer duty scenario was provided by this archive at all.
    out = evaluate(fixture())
    assert not any(r['observation']['result'] == 'FAIL_WITH_EVIDENCE' for r in out['industrial_projection']['rows'])
    assert json.dumps(out['industrial_projection']['engineering_fit']) == '"UNKNOWN"'


def test_unknown_family_is_not_an_inferred_not_applicable():
    raw = (DIRECTORY / 'pump.html').read_bytes().replace(b'<td>pump</td>', b'<td>unknown family</td>')
    out = evaluate(fixture(overrides={'/products/p40': raw}), 'pump-only')
    assert rows(out, 'INFO-02', 'P40')[0]['observation']['result'] == 'UNKNOWN'


def test_same_run_different_saved_pack_cannot_replay_projection(baseline):
    pack, out = baseline
    other = fixture(overrides={'/contact': identity(address='Changed address')})
    with pytest.raises(EvidenceError):
        s2.verify_s2_projection(out, other, expected_pack_ref=other.ref, trusted_scope=scope(other),
            industry_pins=pins(other), expected_projection_ref=out['projection_ref'], expected_projection_version=VERSION)
    with pytest.raises(EvidenceError):
        s2.evaluate_s2(pack, expected_pack_ref=other.ref, trusted_scope=scope(pack),
            projection_version=VERSION, industry_pins=pins(pack))


@pytest.mark.parametrize('change', ['duplicate-alias', 'two-tables', 'hidden', 'script', 'invalid-utf8'])
def test_ambiguous_or_unsupported_source_never_claims_product_coverage(change):
    pack = fixture()
    body = next(pack.resolve(e['evidence_ref'], expected_pack_ref=pack.ref)['content']
        for e in pack.document['evidence'] if next(s for s in pack.document['snapshots']
        if s['snapshot_ref'] == e['snapshot_ref'])['url'].endswith('/p40'))
    if change == 'duplicate-alias':
        body = body.replace(b'</table>', b'<tr><th>Datasheet revision</th><td>R2</td></tr></table>')
    elif change == 'two-tables':
        body = body.replace(b'</body>', b'<table><tr><th>Data revision</th><td>R2</td></tr></table></body>')
    elif change == 'hidden':
        body = body.replace(b'<table>', b'<table hidden>')
    elif change == 'script':
        body = body.replace(b'</body>', b'<script>window.scope="certified"</script></body>')
    else:
        body = body.replace(b'<body>', b'<body>\xff')
    out = evaluate(fixture(overrides={'/products/p40': body}))
    target_rows = [r for r in rows(out, 'INFO-02') if any(s['url'].endswith('/p40') for s in r['source_pages'])]
    assert target_rows and {r['observation']['result'] for r in target_rows} == {'UNKNOWN'}


def test_original_utf8_offsets_with_unicode_prefix_and_entity_text():
    raw = identity(address='演示地址 &amp; 工厂')
    raw = raw.replace(b'<h1>', '前缀\n<h1>'.encode())
    pack = fixture(overrides={'/contact': raw, '/about': raw})
    out = evaluate(pack)
    row = rows(out, 'TRUST-03')[0]
    assert row['observation']['result'] == 'PASS'
    assert any('演示'.encode() in c['quote'].encode() for c in row['citations'])
    for c in row['citations']:
        body = pack.resolve(c['evidence_ref'], expected_pack_ref=pack.ref)['content']
        assert body[c['byte_start']:c['byte_end']].decode() == c['quote']


def test_accepted_batch1_projection_bytes_remain_unchanged(tmp_path):
    import importlib.util
    from pathlib import Path
    from tests.s2_contract.p1_static_cases import git_blob
    raw = (Path(__file__).parent / 'fixtures/accepted-batch1-contract.txt').read_bytes()
    assert git_blob(raw) == 'd1d2fbe98528b2bf7f702c264aaa9076425314e0'
    path = tmp_path / 'accepted_batch1.py'
    path.write_bytes(raw)
    spec = importlib.util.spec_from_file_location('vrae.rules.s2._accepted_batch1', path)
    accepted = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(accepted)
    pack = fixture()
    arguments = {'expected_pack_ref': pack.ref, 'trusted_scope': scope(pack),
                 'projection_version': 's2-projection-1.1.0'}
    assert json.dumps(s2.evaluate_s2(pack, **arguments), sort_keys=True) == json.dumps(
        accepted.evaluate_s2(pack, **arguments), sort_keys=True)

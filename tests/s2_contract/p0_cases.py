from copy import deepcopy
import importlib.util
import json
import subprocess

import pytest

from vrae.collection.manifest import document_hash, sha256
from vrae.evidence import EvidenceError, build_pack
from vrae.findings import build_findings, FindingError
from vrae.rules import execute, verify_execution
from vrae.rules.execution import S2_VERSION
from vrae.rules.s2 import adapter_request, verify_adapter_request, resolve_input, UX_RULES
from tests.evidence.synthetic import http, browser
from tests.rules.synthetic import site

BASE = '84276325befdcf858852a1ec791e8b0695a515eb'
VERSIONS = ('ra2b0-1.0.0', 'ra2b1-1.0.0', 'ra2b3-1.0.0', 'ra2b4-1.0.0', 'ra2b6-1.0.0')


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode()


@pytest.fixture(scope='module')
def frozen(tmp_path_factory):
    # Accepted Git source, not a copy of the current implementation as oracle.
    raw = subprocess.check_output(['git', 'show', BASE + ':vrae/rules/execution.py'])
    path = tmp_path_factory.mktemp('frozen-executor') / 'execution.py'
    path.write_bytes(raw)
    spec = importlib.util.spec_from_file_location('vrae.rules._s2_p0_frozen', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('version', VERSIONS)
@pytest.mark.parametrize('case', ['observed', 'missing', 'blocked', 'unretained', 'browser'])
def test_old_execution_bytes_equal_accepted_source(frozen, version, case):
    pack = (build_pack([http(), browser(observed=True)]) if case == 'browser'
            else site(404 if case == 'missing' else 403 if case == 'blocked' else 200,
                      retained=case != 'unretained'))
    expected = frozen.execute(pack, expected_pack_ref=pack.ref, evaluator_version=version)
    actual = execute(pack, expected_pack_ref=pack.ref, evaluator_version=version)
    assert encoded(actual) == encoded(expected)
    verify_execution(actual, pack, expected_pack_ref=pack.ref, expected_evaluator_version=version)


@pytest.mark.parametrize('version', ['ra2b2-1.0.0', 'ra2b5-1.0.0', 's2-unknown'])
def test_unsupported_versions_stay_rejected(frozen, version):
    pack = site()
    for implementation in (frozen,):
        with pytest.raises(EvidenceError, match='RULE_VERSION_UNSUPPORTED'):
            implementation.execute(pack, expected_pack_ref=pack.ref, evaluator_version=version)
    with pytest.raises(EvidenceError, match='RULE_VERSION_UNSUPPORTED'):
        execute(pack, expected_pack_ref=pack.ref, evaluator_version=version)


def test_default_execution_is_still_original_version_and_bytes(frozen):
    pack = site()
    assert encoded(execute(pack, expected_pack_ref=pack.ref)) == encoded(
        frozen.execute(pack, expected_pack_ref=pack.ref))


def test_s2_dispatch_is_real_replayable_and_honest_about_ten_pending_rules():
    pack = site()
    output = execute(pack, expected_pack_ref=pack.ref, evaluator_version=S2_VERSION)
    verify_execution(output, pack, expected_pack_ref=pack.ref, expected_evaluator_version=S2_VERSION)
    assert len(output['executions']) == len(output['s2_capabilities']) == 16
    assert sum(r['enabled'] for r in output['executions']) == 6
    pending = [r for r in output['s2_capabilities'] if r['implementation'] == 'NOT_IMPLEMENTED_P0']
    assert len(pending) == 10
    assert sum(r['owner'] == 'C1' for r in pending) == 6
    assert sum(r['owner'] == 'C2' for r in pending) == 4
    assert set(output['adapter_requests']) == set(UX_RULES)
    assert 'HUMAN_GOLD_PENDING_NO_QUALITY_METRIC' in output['limitations']
    legacy = execute(pack, expected_pack_ref=pack.ref, evaluator_version=VERSIONS[-1])
    assert encoded(output['executions']) == encoded(legacy['executions'])


@pytest.mark.parametrize('field', ['enabled', 'owner', 'claim', 'coverage', 'input', 'version'])
def test_s2_replay_rejects_self_rehashed_contract_or_capability_forgery(field):
    pack = site()
    out = execute(pack, expected_pack_ref=pack.ref, evaluator_version=S2_VERSION)
    if field == 'enabled':
        out['executions'][2]['enabled'] = True
    elif field == 'owner':
        out['s2_capabilities'][0]['owner'] = 'C2'
    elif field == 'claim':
        out['s2_capabilities'][2]['implementation'] = 'FULLY_IMPLEMENTED'
    elif field == 'coverage':
        out['adapter_requests']['CTA-03']['coverage_denominator'] = 100
    elif field == 'input':
        out['adapter_requests']['CTA-01']['evidence'].clear()
    else:
        out['adapter_contract_version'] = 'unapproved'
    out['execution_ref'] = 'rx-' + document_hash({k: v for k, v in out.items() if k != 'execution_ref'})
    with pytest.raises(EvidenceError):
        verify_execution(out, pack, expected_pack_ref=pack.ref, expected_evaluator_version=S2_VERSION)


@pytest.fixture
def inputs():
    pack = build_pack([http(), browser(observed=True)])
    scope = {k: pack.document[k] for k in ('tenant_id', 'run_id', 'policy_id', 'policy_version')}
    request = adapter_request(pack, expected_pack_ref=pack.ref, rule_id='CTA-01', expected_scope=scope)
    pins = dict(expected_pack_ref=pack.ref, expected_rule_id='CTA-01', expected_scope=scope,
                expected_request_ref=request['input_ref'])
    return pack, request, pins


@pytest.mark.parametrize('kind', ['HTTP_BODY', 'BROWSER_DOM', 'BROWSER_SCREENSHOT'])
def test_actual_pack_refs_resolve_and_body_strings_are_not_authority(inputs, kind):
    pack, request, pins = inputs
    item = next(e for e in request['evidence'] if e['kind'] == kind)
    got = resolve_input(request, pack, evidence_ref=item['evidence_ref'], **pins)
    assert got == pack.resolve(item['evidence_ref'], expected_pack_ref=pack.ref)
    assert request['coverage_denominator'] is None


@pytest.mark.parametrize('kind', ['snapshot', 'object_hash', 'invented_dom_string'])
def test_non_evidence_metadata_object_or_browser_strings_cannot_resolve(inputs, kind):
    pack, request, pins = inputs
    value = (request['snapshots'][0]['snapshot_ref'] if kind == 'snapshot' else
             request['evidence'][0]['blob_ref'] if kind == 'object_hash' else 'ev-' + '0' * 64)
    with pytest.raises(EvidenceError):
        resolve_input(request, pack, evidence_ref=value, **pins)


@pytest.mark.parametrize('pin', ['pack', 'input', 'rule'])
def test_independent_caller_pins_are_required(inputs, pin):
    pack, request, original = inputs
    pins = dict(original)
    if pin == 'pack':
        pins['expected_pack_ref'] = 'ep-' + '0' * 64
    elif pin == 'input':
        pins['expected_request_ref'] = 's2i-' + '0' * 64
    else:
        pins['expected_rule_id'] = 'CTA-03'
    with pytest.raises(EvidenceError):
        verify_adapter_request(request, pack, **pins)


def test_actual_dom_field_injection_never_creates_pack_identity():
    source = browser(observed=True)
    item = source.manifest['observations'][0]
    dom = json.loads(source.objects.pop(item['dom_ref']))
    invented = 'ev-' + '0' * 64
    dom['elements'] = [{'tag': 'a', 'text': 'synthetic', 'visible': True,
                        'evidence_ref': invented, 'snapshot_ref': 'page-forged',
                        'href': 'forged-dom-field', 'geometry': {'width': 1}}]
    raw = encoded(dom)
    item['dom_ref'] = sha256(raw)
    source.objects[item['dom_ref']] = raw
    source.manifest['sha256'] = document_hash({k: v for k, v in source.manifest.items() if k != 'sha256'})
    source.verify()
    pack = build_pack([http(), source])
    scope = {k: pack.document[k] for k in ('tenant_id', 'run_id', 'policy_id', 'policy_version')}
    request = adapter_request(pack, expected_pack_ref=pack.ref, rule_id='CTA-01', expected_scope=scope)
    assert invented not in {e['evidence_ref'] for e in request['evidence']}
    assert 'geometry' not in encoded(request).decode()
    with pytest.raises(EvidenceError):
        resolve_input(request, pack, expected_pack_ref=pack.ref, expected_rule_id='CTA-01',
            expected_scope=scope, expected_request_ref=request['input_ref'], evidence_ref=invented)


@pytest.mark.parametrize('field', ['tenant_id', 'run_id', 'policy_id', 'policy_version'])
def test_foreign_server_scope_never_matches(inputs, field):
    pack, _, pins = inputs
    scope = deepcopy(pins['expected_scope'])
    scope[field] = 99 if field == 'policy_version' else 'other-scope'
    with pytest.raises(EvidenceError):
        adapter_request(pack, expected_pack_ref=pack.ref, rule_id='CTA-01', expected_scope=scope)


def test_bool_is_not_a_policy_version(inputs):
    pack, _, pins = inputs
    scope = {**pins['expected_scope'], 'policy_version': True}
    with pytest.raises(EvidenceError):
        adapter_request(pack, expected_pack_ref=pack.ref, rule_id='CTA-01', expected_scope=scope)


@pytest.mark.parametrize('field', ['ref', 'locator', 'scope', 'metadata', 'contract'])
def test_self_rehashed_dto_forgery_rejected(inputs, field):
    pack, original, pins = inputs
    req = deepcopy(original)
    if field == 'ref':
        req['evidence'][0]['evidence_ref'] = 'ev-' + '0' * 64
    elif field == 'locator':
        req['evidence'][0]['locator'] = '/invented'
    elif field == 'scope':
        req['scope']['tenant_id'] = 'other-tenant'
    elif field == 'metadata':
        req['response_metadata'][0]['evidence_ref'] = req['evidence'][0]['evidence_ref']
    else:
        req['contract_version'] = 'unapproved'
    req['input_ref'] = 's2i-' + document_hash({k: v for k, v in req.items() if k != 'input_ref'})
    with pytest.raises(EvidenceError):
        verify_adapter_request(req, pack, **{**pins, 'expected_request_ref': req['input_ref']})
    assert pack.document['tenant_id'] == original['scope']['tenant_id']


def test_metadata_only_blocked_response_has_no_fabricated_evidence_ref():
    pack = site(403)
    scope = {k: pack.document[k] for k in ('tenant_id', 'run_id', 'policy_id', 'policy_version')}
    req = adapter_request(pack, expected_pack_ref=pack.ref, rule_id='TECH-02', expected_scope=scope)
    blocked = next(m for m in req['response_metadata'] if m['http_status'] == 403)
    assert 'evidence_ref' not in blocked
    assert not any(e['snapshot_ref'] == blocked['snapshot_ref'] for e in req['evidence'])


def test_http_only_capture_cannot_acquire_browser_capability():
    pack = site()
    scope = {k: pack.document[k] for k in ('tenant_id', 'run_id', 'policy_id', 'policy_version')}
    req = adapter_request(pack, expected_pack_ref=pack.ref, rule_id='CTA-03', expected_scope=scope)
    assert not any(e['kind'].startswith('BROWSER_') for e in req['evidence'])
    assert req['state'] == 'INPUT_CONSISTENCY_ONLY_ADAPTER_NOT_ENABLED_P0'


def test_legacy_finding_builder_rejects_s2_until_separate_reviewed_integration():
    pack = site(404)
    output = execute(pack, expected_pack_ref=pack.ref, evaluator_version=S2_VERSION)
    with pytest.raises(FindingError):
        build_findings(pack, output, expected_pack_ref=pack.ref,
            expected_execution_ref=output['execution_ref'], expected_evaluator_version=S2_VERSION,
            expected_builder_version='ra2c3-1.0.0')

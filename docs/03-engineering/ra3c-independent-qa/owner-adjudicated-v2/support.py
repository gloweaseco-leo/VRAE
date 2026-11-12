"""OWNER_ADJUDICATED_RA3C_QA_V2: separate requests, immutable V1 evidence."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V1_PATH = ROOT/'tests/reporting/test_ra3c_independent_acceptance.py'
assert hashlib.sha256(V1_PATH.read_bytes().replace(b'\r\n',b'\n')).hexdigest() == '300f3a877684c3a174fec7c8e0feb2fcc7809479f4ccd201098fed6ed61afedc'
spec = importlib.util.spec_from_file_location('ra3c_v1_immutable_source_support',V1_PATH)
v1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v1)
CASES = json.loads((HERE/'fixtures/cases.json').read_text(encoding='utf-8'))
assert CASES == v1.CASES and len(CASES) == 64
VERSION = 'OWNER_ADJUDICATED_RA3C_QA_V2'
AUTHORITY = 'https://github.com/gloweaseco-leo/VRAE/pull/48#issuecomment-6815825564'


def fixture():
    return json.loads((HERE/'fixtures/admissible-requests.json').read_text(encoding='utf-8'))


def original_context(scenario,profile='truthful'):
    # The original submitted strings/guard/ref are neither edited nor omitted.
    old = v1.prepare_context(scenario,profile)
    pins = {k:deepcopy(v) for k,v in old['pins'].items() if k != 'expected_guard_ref'}
    pins['expected_guard_refs'] = [old['pins']['expected_guard_ref']]
    return dict(pack=old['pack'],package=old['package'],execution=old['execution'],
        guard_inputs=[dict(interpretation=deepcopy(old['interpretation']),
            bindings=deepcopy(old['bindings']),guard=old['guard'].document)],
        pins=pins,scenario=scenario,request_revision=1,caller_scope=old['caller_scope'],
        verified_findings=old['verified_findings'],request_kind='ORIGINAL_UNMODIFIED_NEGATIVE')


def request_context(key):
    held = fixture()['requests'][key]
    old = v1.prepare_context(held['scenario'])
    original_source = {k:v for k,v in old['pins'].items() if k != 'expected_guard_ref'}
    assert held['source_pins'] == original_source, 'V2_SOURCE_PINS_CHANGED'
    bundles = [{k:deepcopy(b[k]) for k in ('interpretation','bindings','guard')} for b in held['bundles']]
    pins = dict(deepcopy(held['source_pins']),expected_guard_refs=[b['expected_guard_ref'] for b in held['bundles']])
    return dict(pack=old['pack'],package=old['package'],execution=old['execution'],
        guard_inputs=bundles,pins=pins,scenario=held['scenario'],request_revision=1,
        caller_scope=old['caller_scope'],verified_findings=old['verified_findings'],
        request_kind=key)


def positive_context(scenario):
    return request_context('positive/'+scenario)


def attack_context(scenario,profile):
    return request_context('attack/'+scenario+'/'+profile)


def guard_claims(context):
    return [claim for bundle in context['guard_inputs'] for claim in bundle['guard']['claims']]


def denied_nodes():
    return fixture()['original_denials']

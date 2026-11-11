"""Explicit ra2b6 execution replay after accepted SEO main integration; synthetic only."""
import argparse
import base64
import hashlib
from html import unescape
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from tests.rules.test_trust01 import execution_cases  # noqa: E402
from vrae.evidence import EvidencePack  # noqa: E402
from vrae.findings import build_findings, FindingError  # noqa: E402
from vrae.rules import execute, verify_execution  # noqa: E402
from vrae.rules.trust01 import PASS_STATEMENT  # noqa: E402

VERSION = 'ra2b6-1.0.0'
HISTORICAL = ('ra2b0-1.0.0', 'ra2b1-1.0.0', 'ra2b3-1.0.0', 'ra2b4-1.0.0')
parser = argparse.ArgumentParser()
parser.add_argument('--write-example', action='store_true', help='Write only the new opt-in execution fixture.')
args = parser.parse_args()
path = root / 'tests/rules/fixtures/trust01-execution.json'
if args.write_example:
    cases = []
    for name, pack, expected in execution_cases():
        output = execute(pack, expected_pack_ref=pack.ref, evaluator_version=VERSION)
        cases.append({'name': name, 'expected_result': expected, 'expected_pack_ref': pack.ref,
            'expected_execution_ref': output['execution_ref'], 'document': pack.document,
            'objects_base64': {k: base64.b64encode(v).decode('ascii') for k, v in pack.objects.items()},
            'execution': output, 'historical_execution_refs': {v: execute(
                pack, expected_pack_ref=pack.ref, evaluator_version=v)['execution_ref'] for v in HISTORICAL}})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'synthetic_only': True, 'evaluator_version': VERSION,
                               'cases': cases}, sort_keys=True, indent=2) + '\n', encoding='utf-8')

data = json.loads(path.read_text(encoding='utf-8'))
assert data['synthetic_only'] is True and data['evaluator_version'] == VERSION
fresh = {name: (pack, expected) for name, pack, expected in execution_cases()}
assert len(data['cases']) == len(fresh) == 9
report = []
positive_proof = None
for case in data['cases']:
    pack = EvidencePack.load(case['document'], {
        k: base64.b64decode(v, validate=True) for k, v in case['objects_base64'].items()
    }, expected_ref=case['expected_pack_ref'])
    output = case['execution']
    assert output['execution_ref'] == case['expected_execution_ref']
    verify_execution(output, pack, expected_pack_ref=case['expected_pack_ref'], expected_evaluator_version=VERSION)
    reproduced, expected = fresh[case['name']]
    assert reproduced.ref == pack.ref and execute(reproduced, expected_pack_ref=pack.ref,
                                                 evaluator_version=VERSION) == output
    trust = next(e for e in output['executions'] if e['rule_id'] == 'TRUST-01')
    row = trust['observations'][0]
    assert trust['enabled'] and row['observation']['result'] == case['expected_result'] == expected
    assert {e['rule_id'] for e in output['executions'] if e['enabled']} == {
        'DISC-01', 'DISC-02', 'INFO-01', 'TRUST-01', 'CTA-02', 'SEO-01'}
    if expected == 'PASS':
        assert row['observation']['statement'] == PASS_STATEMENT and row['observation']['evidence_ids']
    else:
        assert row['observation']['evidence_ids'] == []
    for citation in row['citations']:
        raw = pack.resolve(citation['evidence_ref'], expected_pack_ref=pack.ref)['content']
        assert hashlib.sha256(raw).hexdigest() == citation['content_sha256']
        source, pos = raw.decode('utf-8'), citation['element']
        offset = sum(len(s) + 1 for s in source.split('\n')[:pos['line'] - 1]) + pos['column']
        assert source[offset:].startswith(citation['raw_element'])
        assert citation['raw_element'].startswith(pos['start_tag'])
        assert unescape(citation['raw_element'].split('>', 1)[1].rsplit('</', 1)[0]) == citation['text']
    for version, ref in case['historical_execution_refs'].items():
        historical = execute(pack, expected_pack_ref=pack.ref, evaluator_version=version)
        assert historical['execution_ref'] == ref
        old_trust = next(e for e in historical['executions'] if e['rule_id'] == 'TRUST-01')
        assert not old_trust['enabled']
        if version == 'ra2b4-1.0.0':
            assert [e for e in output['executions'] if e['rule_id'] != 'TRUST-01'] == [
                e for e in historical['executions'] if e['rule_id'] != 'TRUST-01']
    if case['name'] == 'seo-and-trust-source-positives':
        seo = next(e for e in output['executions'] if e['rule_id'] == 'SEO-01')
        assert seo['observations'][0]['observation']['result'] == 'PASS'
        for builder in ('ra2c0-1.0.0', 'ra2c1-1.0.0'):
            try:
                build_findings(pack, output, expected_pack_ref=pack.ref,
                    expected_execution_ref=output['execution_ref'], expected_evaluator_version=VERSION,
                    expected_builder_version=builder)
            except FindingError:
                pass
            else:
                raise AssertionError('Old FindingBuilder must refuse the new evaluator')
        positive_proof = row
    report.append({'scenario': case['name'], 'expected_pack_ref': pack.ref,
        'execution_ref': output['execution_ref'], 'trust_result': expected,
        'missing': row['missing_prerequisites'], 'blocked': row['blocked_page_indices'],
        'unknown': row['unknown_page_indices'], 'unvisited': row['unvisited_candidates']})
print(json.dumps({'status': 'VERIFIED_EXPLICIT_OPT_IN_TRUST01_SOURCE_ONLY', 'evaluator_version': VERSION,
    'cases': report, 'positive_source_proof': positive_proof,
    'limits': ['NO_LEGAL_ENTITY_FACTORY_CERTIFICATE_QUALIFICATION_OR_CONTACT_VALIDITY_AUTHENTICATION',
               'SOURCE_PRESENCE_NOT_TRUSTWORTHINESS_OR_SUCCESSFUL_INQUIRY', 'NO_NEW_FINDING_BUILDER']},
    sort_keys=True, indent=2))

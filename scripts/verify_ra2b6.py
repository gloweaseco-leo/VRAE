"""Phase A offline adapter preparation, never an enabled TRUST-01 evaluator claim."""
import argparse
import base64
import hashlib
from html import unescape
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from tests.rules.test_trust01 import preparation_cases  # noqa: E402
from vrae.evidence import EvidencePack  # noqa: E402
from vrae.rules import execute  # noqa: E402
from vrae.rules.trust01 import prepare, verify_preparation, VERSION, PASS_STATEMENT  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--write-example', action='store_true', help='Write only the new Phase A preparation fixture.')
args = parser.parse_args()
path = root / 'tests/rules/fixtures/trust01-preparation.json'
if args.write_example:
    cases = []
    for name, pack, expected in preparation_cases():
        output = prepare(pack, expected_pack_ref=pack.ref)
        cases.append({'name': name, 'expected_result': expected, 'expected_pack_ref': pack.ref,
            'expected_preparation_ref': output['preparation_ref'], 'document': pack.document,
            'objects_base64': {k: base64.b64encode(v).decode('ascii') for k, v in pack.objects.items()},
            'preparation': output})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'synthetic_only': True, 'phase': 'PREP_ONLY',
        'trust01_enabled': False, 'adapter_version': VERSION, 'cases': cases},
        sort_keys=True, indent=2) + '\n', encoding='utf-8')

data = json.loads(path.read_text(encoding='utf-8'))
assert data['phase'] == 'PREP_ONLY' and data['trust01_enabled'] is False
assert data['adapter_version'] == VERSION and data['synthetic_only'] is True
fresh = {name: (pack, status) for name, pack, status in preparation_cases()}
assert len(data['cases']) == len(fresh) == 8
report = []
for case in data['cases']:
    pack = EvidencePack.load(case['document'], {
        k: base64.b64decode(v, validate=True) for k, v in case['objects_base64'].items()
    }, expected_ref=case['expected_pack_ref'])
    output = case['preparation']
    verify_preparation(output, pack, expected_pack_ref=case['expected_pack_ref'])
    assert output['preparation_ref'] == case['expected_preparation_ref']
    reproduced, expected = fresh[case['name']]
    assert reproduced.ref == pack.ref and prepare(reproduced, expected_pack_ref=pack.ref) == output
    row = output['rows'][0]
    assert row['observation']['result'] == case['expected_result'] == expected
    if expected == 'PASS':
        assert row['observation']['statement'] == PASS_STATEMENT
        assert row['observation']['evidence_ids']
        assert not row['unknown_page_indices'] and not row['blocked_page_indices']
    else:
        assert row['observation']['evidence_ids'] == []
    for citation in row['citations']:
        raw = pack.resolve(citation['evidence_ref'], expected_pack_ref=pack.ref)['content']
        assert hashlib.sha256(raw).hexdigest() == citation['content_sha256']
        source = raw.decode('utf-8')
        pos = citation['element']
        offset = sum(len(s) + 1 for s in source.split('\n')[:pos['line'] - 1]) + pos['column']
        assert source[offset:].startswith(citation['raw_element'])
        assert citation['raw_element'].startswith(pos['start_tag'])
        assert unescape(citation['raw_element'].split('>', 1)[1].rsplit('</', 1)[0]) == citation['text']
    # Frozen accepted opt-in remains unchanged: preparation has no dispatch side effect.
    execution = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b3-1.0.0')
    trust = next(e for e in execution['executions'] if e['rule_id'] == 'TRUST-01')
    assert not trust['enabled'] and all(r['observation']['result'] == 'UNKNOWN' for r in trust['observations'])
    report.append({'scenario': case['name'], 'expected_pack_ref': pack.ref,
        'preparation_ref': output['preparation_ref'], 'prepared_result': expected,
        'phase': 'PREP_ONLY', 'trust01_enabled': False, 'row': row})
print(json.dumps({'status': 'VERIFIED_PREPARATION_ONLY_TRUST01_NOT_ENABLED',
                  'cases': report}, sort_keys=True, indent=2))

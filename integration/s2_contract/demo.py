"""Actual P0 execution on accepted eight-page offline bytes, not a new live task."""
import argparse
import base64
import hashlib
import json
from pathlib import Path

from vrae.evidence import EvidencePack
from vrae.rules import execute, verify_execution
from vrae.rules.execution import S2_VERSION

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_SHA256 = '33554c61ffd561dd88e38c7d832a47fe4dbc210d5756d570fd61be8c8c6707fe'


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    source = json.loads((ROOT / 'docs/03-engineering/l2-industrial-v1/example/source.json').read_bytes())
    assert hashlib.sha256(encode(source)).hexdigest() == FIXTURE_SHA256
    pack = EvidencePack.load(source['pack'], {key: base64.b64decode(value, validate=True)
        for key, value in source['objects_base64'].items()}, expected_ref=source['pack']['pack_ref'])
    output = execute(pack, expected_pack_ref=pack.ref, evaluator_version=S2_VERSION)
    verify_execution(output, pack, expected_pack_ref=pack.ref, expected_evaluator_version=S2_VERSION)
    summary = {'kind': 'OFFLINE_ACCEPTED_INDUSTRIAL_BYTES_P0_NOT_NEW_APP_OR_WORKER_COMMIT',
        'fixture_canonical_sha256': FIXTURE_SHA256, 'pack_ref': pack.ref,
        'evaluator_version': S2_VERSION, 'execution_ref': output['execution_ref'],
        'execution_bytes_sha256': hashlib.sha256(encode(output)).hexdigest(),
        'snapshot_count': len(pack.document['snapshots']),
        'rules': [{'rule_id': r['rule_id'], 'buyer_task': r['buyer_task'], 'enabled': r['enabled'],
                   'results': [row['observation']['result'] for row in r['observations']]}
                  for r in output['executions']],
        's2_capabilities': output['s2_capabilities'],
        'adapter_refs': {rule: request['input_ref'] for rule, request in output['adapter_requests'].items()},
        'coverage_denominator': None, 'model_calls': 0,
        'business_limit': 'Six legacy bounded checks only; ten new generic rules pending P1. Missing evidence is not a website defect. Industrial IND six are separate and not counted as generic rules.',
        'guard_limit': 'Legacy FindingPackage rejects S2; no S2 report/review authority granted.'}
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'execution.json').write_bytes(encode(output))
    (args.out / 'summary.json').write_bytes(encode(summary))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()

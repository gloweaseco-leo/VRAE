"""Actual P0 execution on accepted eight-page offline bytes, not a new live task."""
import argparse
import base64
import hashlib
import json
from pathlib import Path

from vrae.evidence import EvidencePack
from vrae.rules.s2 import evaluate_s2, verify_s2_projection, PROJECTION_VERSION

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
    scope = {k: pack.document[k] for k in ('tenant_id', 'run_id', 'policy_id', 'policy_version')}
    output = evaluate_s2(pack, expected_pack_ref=pack.ref, trusted_scope=scope)
    verify_s2_projection(output, pack, expected_pack_ref=pack.ref, trusted_scope=scope,
                         expected_projection_ref=output['projection_ref'])
    summary = {'kind': 'OFFLINE_ACCEPTED_INDUSTRIAL_BYTES_P0_NOT_NEW_APP_OR_WORKER_COMMIT',
        'fixture_canonical_sha256': FIXTURE_SHA256, 'pack_ref': pack.ref,
        'projection_version': PROJECTION_VERSION, 'projection_ref': output['projection_ref'],
        'baseline_execution_ref': output['baseline_execution_ref'],
        'projection_bytes_sha256': hashlib.sha256(encode(output)).hexdigest(),
        'snapshot_count': len(pack.document['snapshots']),
        'rules': [{'rule_id': r['rule_id'], 'buyer_task': r['buyer_task'], 'enabled': r['enabled'],
                   'results': [row['observation']['result'] for row in r['observations']]}
                  for r in output['baseline_execution']['executions']],
        's2_capabilities': output['s2_capabilities'],
        'adapter_refs': {rule: request['input_ref'] for rule, request in output['adapter_requests'].items()},
        'coverage_denominator': None, 'model_calls': 0,
        'business_limit': 'Six legacy bounded checks only; ten new generic rules pending P1. Missing evidence is not a website defect. Industrial IND six are separate and not counted as generic rules.',
        'guard_limit': 'S2 projection is not native RuleExecution; old FindingPackage/Guard authority is not granted.'}
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'projection.json').write_bytes(encode(output))
    (args.out / 'summary.json').write_bytes(encode(summary))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()

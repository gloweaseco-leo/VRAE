"""Accepted-core source/guard replay only; not a reporting candidate test."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0,str(ROOT))
spec = importlib.util.spec_from_file_location('v2_independent_source_audit',HERE/'support.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out',required=True)
    args = parser.parse_args()
    out = Path(args.out)
    assert not out.exists() and out.parent.resolve() == HERE
    assert 'vrae.reporting' not in sys.modules
    rows = []
    for key,request in support.fixture()['requests'].items():
        context = support.request_context(key)
        pins = {k:v for k,v in context['pins'].items() if k != 'expected_guard_refs'}
        source_facts = set()
        statuses = []
        for index,bundle in enumerate(context['guard_inputs']):
            guard = support.v1.GuardResult.load(bundle['guard'],bundle['interpretation'],bundle['bindings'],
                context['pack'],context['package'],expected_guard_ref=context['pins']['expected_guard_refs'][index],**pins)
            assert guard.document == bundle['guard']
            by_pointer = {b['pointer']:b for b in bundle['bindings']}
            for claim in guard.document['claims']:
                statuses.append(claim['status'])
                binding = by_pointer[claim['pointer']]
                if claim['status'] == 'SOURCE_FACT_BINDING_VERIFIED' and binding['fact']['proof_kind'] == 'CAPTURED_CTA_HTTP_FAILURE':
                    source_facts.add(binding['fact']['observation_id'])
        if key.startswith('positive/'):
            assert source_facts == {f['observation_id'] for f in context['verified_findings']}
        if key.startswith('attack/'):
            assert 'REJECTED' in statuses
        rows.append(dict(request=key,scenario=request['scenario'],source_pins=pins,
            external_guard_refs=context['pins']['expected_guard_refs'],claim_statuses=dict(Counter(statuses)),
            actual_native_failure_count=len(context['verified_findings']),bound_failure_observations=sorted(source_facts)))
    assert len(rows) == 19 and 'vrae.reporting' not in sys.modules
    result = dict(kind='ACCEPTED_CORE_SOURCE_GUARD_REPLAY_NOT_REPORTING_PASS',python=sys.version,
        requests=rows,reporting_imported=False,model_calls=0,real_network_calls=0,
        admissible_fixture_sha256=hashlib.sha256((HERE/'fixtures/admissible-requests.json').read_bytes()).hexdigest(),
        original_input_git_sha256=hashlib.sha256(support.v1.INPUT_PATH.read_bytes().replace(b'\r\n',b'\n')).hexdigest())
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Accepted-core only:',len(rows),'independent source/guard requests replayed; no reporting import')


if __name__ == '__main__':
    main()

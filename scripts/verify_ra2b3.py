"""Replay pinned offline product HTML through the opt-in INFO-01 Observation."""
import argparse
import base64
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vrae.evidence import EvidencePack  # noqa: E402
from vrae.rules import execute, verify_execution  # noqa: E402
from vrae.rules.product_facts import extract  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'tests/rules/fixtures/info01-product-observation.json'
VERSION = 'ra2b3-1.0.0'


def load(data):
    return EvidencePack.load(data['document'], {k: base64.b64decode(v, validate=True)
        for k, v in data['objects_base64'].items()}, expected_ref=data['expected_pack_ref'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-example', action='store_true')
    args = parser.parse_args()
    if args.write_example:
        # Reuse the already accepted original synthetic pack; never rewrite it.
        prior = json.loads((ROOT / 'docs/03-engineering/ra2b2-evidence/product-facts.json').read_text(encoding='utf-8'))
        pack = load(prior)
        data = {k: prior[k] for k in ('expected_pack_ref', 'document', 'objects_base64')}
        data['expected_facts_ref'] = prior['expected_facts']['facts_ref']
        data['historical_execution_refs'] = {version: execute(pack,
            expected_pack_ref=pack.ref, evaluator_version=version)['execution_ref']
            for version in ('ra2b0-1.0.0', 'ra2b1-1.0.0')}
        data['expected_execution'] = execute(pack, expected_pack_ref=pack.ref, evaluator_version=VERSION)
        EXAMPLE.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    data = json.loads(EXAMPLE.read_text(encoding='utf-8'))
    pack = load(data)
    pin = data['expected_pack_ref']  # Trusted local synthetic fixture, not remote authorization.
    facts = extract(pack, expected_pack_ref=pin)
    assert facts['facts_ref'] == data['expected_facts_ref']
    verify_execution(data['expected_execution'], pack, expected_pack_ref=pin,
                     expected_evaluator_version=VERSION)
    for version, ref in data['historical_execution_refs'].items():
        assert execute(pack, expected_pack_ref=pin, evaluator_version=version)['execution_ref'] == ref
    info = next(r for r in data['expected_execution']['executions'] if r['rule_id'] == 'INFO-01')
    row = info['observations'][0]
    assert row['observation']['result'] == 'PASS'
    assert row['citations'][0]['text'] == facts['pages'][0]['name']['text']
    # Independent code path: inspect exact original response lines, not parser output alone.
    for citation in row['citations']:
        resolved = pack.resolve(citation['evidence_ref'], expected_pack_ref=pin)
        pos = citation['element']
        line = resolved['content'].decode('utf-8').splitlines()[pos['line'] - 1]
        assert line[pos['column']:].startswith(pos['start_tag'] + citation['text'] + '</')
    print(json.dumps({'status': 'PASS_BOUNDED_OFFLINE_STATIC_INFO01', 'pack_ref': pin,
        'facts_ref': facts['facts_ref'], 'execution_ref': data['expected_execution']['execution_ref'],
        'evaluator_version': VERSION, 'observation': row['observation'],
        'source_page': row['source_page'], 'citations': row['citations'],
        'historical_execution_refs': data['historical_execution_refs']}, indent=2))


if __name__ == '__main__':
    main()

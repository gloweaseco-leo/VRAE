"""Offline replay and independent source-line review of synthetic product facts."""
import argparse
import base64
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vrae.evidence import EvidencePack  # noqa: E402
from vrae.rules.product_facts import extract, verify_facts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'docs/03-engineering/ra2b2-evidence/product-facts.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-example', action='store_true')
    args = parser.parse_args()
    if args.write_example:
        from tests.rules.test_product_facts import product_pack
        pack = product_pack()
        data = {'expected_pack_ref': pack.ref, 'document': pack.document,
                'objects_base64': {k: base64.b64encode(v).decode() for k, v in pack.objects.items()},
                'expected_facts': extract(pack, expected_pack_ref=pack.ref)}
        EXAMPLE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    data = json.loads(EXAMPLE.read_text(encoding='utf-8'))
    pin = data['expected_pack_ref']  # Trusted committed synthetic input, not remote authorization.
    pack = EvidencePack.load(data['document'], {k: base64.b64decode(v, validate=True)
        for k, v in data['objects_base64'].items()}, expected_ref=pin)
    verify_facts(data['expected_facts'], pack, expected_pack_ref=pin)
    output = extract(pack, expected_pack_ref=pin)
    page = output['pages'][0]
    assert page['status'] == 'EXTRACTED'
    # Independent reviewer uses original source lines, not the extractor parser.
    for field in page['fields']:
        for kind in ('label', 'value'):
            citation = field[kind]
            resolved = pack.resolve(citation['evidence_ref'], expected_pack_ref=pin)
            element = citation['element']
            line = resolved['content'].decode('utf-8').splitlines()[element['line'] - 1]
            assert line[element['column']:].startswith(element['start_tag'] + citation['text'] + '</')
    print(json.dumps({'status': 'PASS', 'scope': 'OFFLINE_SOURCE_LINE_REVIEW_ONLY',
        'expected_pack_ref': pin, 'facts_ref': output['facts_ref'],
        'name': page['name'], 'pressure': page['fields'][1],
        'info01_enabled': False}, indent=2))


if __name__ == '__main__':
    main()

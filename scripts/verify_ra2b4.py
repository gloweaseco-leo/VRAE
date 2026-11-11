"""Replay sealed offline synthetic HOME head evidence, including bounded unknowns."""
import argparse
import base64
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from vrae.evidence import EvidencePack  # noqa: E402
from vrae.rules import execute, verify_execution  # noqa: E402

VERSION = 'ra2b4-1.0.0'
path = root / 'tests/rules/fixtures/seo01-static-signals.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-example', action='store_true', help='Write only the new SEO fixture.')
    args = parser.parse_args()
    if args.write_example:
        from tests.rules.test_seo01 import seo_pack, head
        variants = [
            ('industrial-home', {}, 'PASS'),
            ('title-only', {'markup': head(b'<title>Industrial components</title>')}, 'UNKNOWN'),
            ('conflicting-canonical', {'markup': head(b'<title>Valves</title><link rel="canonical" href="/"><link rel="canonical" href="/catalog">')}, 'UNKNOWN'),
            ('external-canonical', {'markup': head(b'<title>Valves</title><link rel="canonical" href="https://outside.example/">')}, 'UNKNOWN'),
            ('js-only', {'markup': head(b'<script>document.title="Valves"</script>')}, 'UNKNOWN'),
            ('raw-not-retained', {'retained': False}, 'UNKNOWN'),
            ('http-403', {'status': 403}, 'ACCESS_BLOCKED'),
            ('robots-denied', {'blocked': 'robots'}, 'ACCESS_BLOCKED'),
            ('waf', {'blocked': 'waf'}, 'ACCESS_BLOCKED'),
        ]
        cases = []
        for name, kwargs, expected in variants:
            pack = seo_pack(**kwargs)
            cases.append({'name': name, 'expected_result': expected, 'expected_pack_ref': pack.ref,
                'document': pack.document,
                'objects_base64': {k: base64.b64encode(v).decode('ascii') for k, v in pack.objects.items()},
                'expected_execution': execute(pack, expected_pack_ref=pack.ref, evaluator_version=VERSION),
                'historical_execution_refs': {version: execute(pack, expected_pack_ref=pack.ref,
                    evaluator_version=version)['execution_ref'] for version in
                    ('ra2b0-1.0.0', 'ra2b1-1.0.0', 'ra2b3-1.0.0')}})
        path.write_text(json.dumps({'synthetic_only': True, 'cases': cases}, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['synthetic_only'] is True
    results = []
    for case in data['cases']:
        pin = case['expected_pack_ref']
        pack = EvidencePack.load(case['document'], {k: base64.b64decode(v, validate=True)
            for k, v in case['objects_base64'].items()}, expected_ref=pin)
        output = case['expected_execution']
        verify_execution(output, pack, expected_pack_ref=pin, expected_evaluator_version=VERSION)
        for version, ref in case['historical_execution_refs'].items():
            assert execute(pack, expected_pack_ref=pin, evaluator_version=version)['execution_ref'] == ref
        row = next(r for r in output['executions'] if r['rule_id'] == 'SEO-01')['observations'][0]
        assert row['observation']['result'] == case['expected_result']
        for citation in row['citations']:
            content = pack.resolve(citation['evidence_ref'], expected_pack_ref=pin)['content']
            pos = citation['element']
            text = content.decode('utf-8-sig')
            assert text[pos['character_start']:pos['character_end']] == pos['raw_element']
            assert text.splitlines()[pos['line'] - 1][pos['column']:].startswith('<')
        results.append({'case': case['name'], 'pack_ref': pin, 'execution_ref': output['execution_ref'],
            'observation': row['observation'], 'reason': row['reason'], 'source_page': row['source_page'],
            'seo_signals': row['seo_signals'], 'citations': row['citations']})
    print(json.dumps({'status': 'VERIFIED_OFFLINE_SOURCE_TAGS_ONLY', 'evaluator_version': VERSION,
        'limitations': ['NO_LIVE_COLLECTION', 'NO_INDEXING_RANKING_OR_HEALTH_CLAIM',
                        'ROBOTS_SITEMAP_UNKNOWN_NO_RESOLVABLE_BODY'], 'cases': results}, indent=2))


if __name__ == '__main__':
    main()

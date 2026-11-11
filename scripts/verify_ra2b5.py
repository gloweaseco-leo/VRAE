"""Offline replay of three fictional industrial self-description evidence packs."""
import argparse
import base64
import hashlib
from html import unescape
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from tests.rules.test_trust_facts import trust_pack  # noqa: E402
from vrae.evidence import EvidencePack  # noqa: E402
from vrae.rules.trust_facts import extract, verify_facts, VERSION  # noqa: E402

SCENARIOS = {'declared-valve-manufacturer': ('about', {}),
             'mixed-drivetrain-brands': ('mixed', {'contact': b'<html></html>'}),
             'js-only-automation-supplier': ('js', {'contact': b'<html></html>'})}
parser = argparse.ArgumentParser()
parser.add_argument('--write-examples', action='store_true', help='Write only the new trust facts fixture.')
args = parser.parse_args()
path = root / 'tests/rules/fixtures/trust-source-facts.json'
if args.write_examples:
    cases = []
    for name, (fixture, kwargs) in SCENARIOS.items():
        pack = trust_pack(fixture, **kwargs)
        facts = extract(pack, expected_pack_ref=pack.ref)
        cases.append({'name': name, 'expected_pack_ref': pack.ref, 'expected_facts_ref': facts['facts_ref'],
            'document': pack.document,
            'objects_base64': {k: base64.b64encode(v).decode('ascii') for k, v in pack.objects.items()},
            'facts': facts})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'synthetic_only': True, 'expected_extractor_version': VERSION,
                              'cases': cases}, sort_keys=True, indent=2) + '\n', encoding='utf-8')

data = json.loads(path.read_text(encoding='utf-8'))
assert data['synthetic_only'] is True and data['expected_extractor_version'] == VERSION
assert [c['name'] for c in data['cases']] == list(SCENARIOS)
report = []
for case in data['cases']:
    pack = EvidencePack.load(case['document'], {
        k: base64.b64decode(v, validate=True) for k, v in case['objects_base64'].items()
    }, expected_ref=case['expected_pack_ref'])
    facts = case['facts']
    assert facts['facts_ref'] == case['expected_facts_ref']
    verify_facts(facts, pack, expected_pack_ref=case['expected_pack_ref'])
    fixture, kwargs = SCENARIOS[case['name']]
    fresh = trust_pack(fixture, **kwargs)
    assert fresh.ref == pack.ref and extract(fresh, expected_pack_ref=fresh.ref) == facts
    assert facts['trust01_enabled'] is False and facts['trust01_result'] == 'UNKNOWN'
    for page in facts['pages']:
        if page['status'] != 'EXTRACTED':
            assert page['evidence_ids'] == []
        for fact in page['facts']:
            for citation in (fact['citation'], fact.get('label_citation')):
                if citation is None:
                    continue
                raw = pack.resolve(citation['evidence_ref'], expected_pack_ref=pack.ref)['content']
                assert hashlib.sha256(raw).hexdigest() == citation['content_sha256']
                text = raw.decode('utf-8')
                element = citation['element']
                offset = sum(len(s) + 1 for s in text.split('\n')[:element['line'] - 1]) + element['column']
                assert text[offset:].startswith(citation['raw_element'])
                assert citation['raw_element'].startswith(element['start_tag'])
                inner = citation['raw_element'].split('>', 1)[1].rsplit('</', 1)[0]
                assert unescape(inner) == citation['text']
    if case['name'] == 'declared-valve-manufacturer':
        assert facts['status'] == 'EXTRACTED'
        about = next(p for p in facts['pages'] if p['source_page']['url'].endswith('/about'))
        name = next(f['citation'] for f in about['facts'] if f['kind'] == 'DECLARED_NAME')
        assert name['text'] == 'Heshan Meridian Valve Works'
        assert name['element']['line'] == 3 and name['element']['column'] == 0
        assert name['element']['path'] == '/html[1]/main[1]/h1[1]'
    else:
        assert facts['status'] == 'UNKNOWN'
    report.append({'scenario': case['name'], 'expected_pack_ref': pack.ref,
        'facts_ref': facts['facts_ref'], 'status': facts['status'],
        'pages': facts['pages'], 'limitations': facts['limitations']})
print(json.dumps({'status': 'VERIFIED_OFFLINE_SELF_DECLARED_SOURCE_TEXT_ONLY',
    'extractor_version': VERSION, 'trust01_enabled': False, 'cases': report}, sort_keys=True, indent=2))

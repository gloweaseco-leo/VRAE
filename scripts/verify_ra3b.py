"""Fixed offline RA-3B replay and private buyer-task review queue; never a report."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.interpretation.synthetic import proposal, source  # noqa: E402
from vrae.evidence import EvidencePack  # noqa: E402
from vrae.findings import FindingPackage  # noqa: E402
from vrae.interpretation import GuardError, GuardResult, catalog, validate  # noqa: E402

ARCHIVE = ROOT / 'tests/interpretation/fixtures/fixed-replay.json'
EVIDENCE = ROOT / 'docs/03-engineering/ra3b-offline'


def case(status):
    p, f, k = source(status)
    facts = catalog(p, f, **k)['facts']
    rule = 'TRUST-01' if status == 200 else 'CTA-02'
    fact = next(x for x in facts if x['rule_id'] == rule)
    i, b = proposal(p, f, k, fact=fact)
    h, hb = proposal(p, f, k, fact=fact, claim_type='HYPOTHESIS',
                     text='A buyer may need human help confirming the captured contact route.')
    r, rb = proposal(p, f, k, fact=fact, claim_type='RECOMMENDATION',
                     text='A human should review the captured route before suggesting a change.')
    return {'status': status, 'pins': k, 'pack': p.document,
            'objects_base64': {key: base64.b64encode(value).decode() for key, value in p.objects.items()},
            'package': f.document, 'interpretation': i, 'bindings': b,
            'guard': validate(i, b, p, f, **k).document,
            'review_queue': [{'interpretation': obj, 'bindings': bs,
                              'guard': validate(obj, bs, p, f, **k).document}
                             for obj, bs in [(h, hb), (r, rb)]]}


def replay(data, *, minimal_isolated_layout=False):
    output = []
    for c in data['cases']:
        k = c['pins']
        p = EvidencePack.load(c['pack'], {key: base64.b64decode(value, validate=True)
            for key, value in c['objects_base64'].items()}, expected_ref=k['expected_pack_ref'])
        f = FindingPackage.load(c['package'], p, **{key: value for key, value in k.items()
            if key not in ('expected_scope', 'expected_guard_version')})
        g = GuardResult.load(c['guard'], c['interpretation'], c['bindings'], p, f,
                             expected_guard_ref=c['guard']['guard_ref'], **k)
        assert g.document['claims'][0]['status'] == 'SOURCE_FACT_BINDING_VERIFIED'
        for row in c['review_queue']:
            reviewed = GuardResult.load(row['guard'], row['interpretation'], row['bindings'], p, f,
                                        expected_guard_ref=row['guard']['guard_ref'], **k)
            assert reviewed.document['claims'][0]['status'] == 'HUMAN_REVIEW_REQUIRED'
        fresh = case(c['status'])
        assert fresh == c  # Fixed capture bytes, refs, statements and replay, no regenerated expectations.
        output.append({'contact_status': c['status'], **k, 'guard_ref': g.ref,
                       'source_rules': sorted({x['rule_id'] for x in catalog(p, f, **k)['facts']}),
                       'human_review_queue': [{'pointer': row['bindings'][0]['pointer'],
                           'text': row['bindings'][0]['text'], 'status': 'HUMAN_REVIEW_REQUIRED'}
                                             for row in c['review_queue']]})
    # Historical contract/Gold bytes are pinned independently from new fixtures.
    for path, digest in data['historical_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == digest
    preserved = json.loads((ROOT / 'tests/interpretation/fixtures/preserved-history.json').read_text(
        encoding='utf-8'))
    unavailable = []
    for path, digest in preserved['sha256'].items():
        if (minimal_isolated_layout and os.environ.get('VRAE_ISOLATED_LAB') == '1'
                and path.startswith('docs/') and not (ROOT / path).exists()):
            unavailable.append(path)
            continue  # The unchanged HTTP image excludes docs; no source/evidence check is skipped.
        assert hashlib.sha256((ROOT / path).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == digest
    # Red/green: genuine citation + unrelated objective assertion, same valid IDs.
    p, f, k = source()
    i, b = proposal(p, f, k, text='This certified factory loses $100000 in sales.')
    rejected = validate(i, b, p, f, **k).document['claims'][0]
    assert rejected['reason'] == 'UNSUPPORTED_OBJECTIVE_ASSERTION'
    try:
        validate('{invalid json', [], p, f, **k)
    except GuardError as exc:
        assert str(exc) == 'INPUT_INTEGRITY'
    else:
        raise AssertionError('INVALID_JSON_ACCEPTED')
    return {'status': 'OFFLINE_PRIVATE_REPLAY_PASS', 'cases': output, 'negative_red_green': rejected,
            'historical_files_verified': len(preserved['sha256']) - len(unavailable),
            'history_unavailable_in_minimal_isolated_layout': unavailable,
            'human_gold': '0/26_UNEVALUATED',
            'no_provider_calls': True, 'no_customer_report': True, 'shareable': False,
            'limitations': ['SOURCE_CONSISTENCY_NOT_AUTHENTICITY', 'NO_SEMANTIC_APPROVAL',
                           'INJECTION_LEXICON_IS_CONSERVATIVE_NOT_A_UNIVERSAL_DETECTOR']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-new-fixtures', action='store_true')
    parser.add_argument('--write-evidence', action='store_true')
    args = parser.parse_args()
    if args.freeze_new_fixtures:
        assert not ARCHIVE.exists(), 'FIXTURE_ALREADY_FROZEN'
        historical = [*sorted((ROOT / 'contracts/v1').glob('*.json')),
                      *sorted((ROOT / 'tests/findings/fixtures').glob('*.json')),
                      *sorted((ROOT / 'gold').rglob('*'))] if (ROOT / 'gold').exists() else [
                          *sorted((ROOT / 'contracts/v1').glob('*.json')),
                          *sorted((ROOT / 'tests/findings/fixtures').glob('*.json'))]
        ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
        ARCHIVE.write_text(json.dumps({'synthetic_only': True, 'cases': [case(s) for s in (200, 404, 410)],
            'historical_sha256': {p.relative_to(ROOT).as_posix(): hashlib.sha256(
                p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                                  for p in historical if p.is_file()}}, indent=2, sort_keys=True) + '\n',
                           encoding='utf-8')
    result = replay(json.loads(ARCHIVE.read_text(encoding='utf-8')))
    if args.write_evidence:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        (EVIDENCE / 'fixed-replay-result.json').write_text(
            json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()

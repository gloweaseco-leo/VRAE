"""Reproducible private HTML, full-content hashes and fixed source replay; no networking."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.reporting.synthetic import inputs  # noqa: E402
from vrae.evidence import EvidencePack  # noqa: E402
from vrae.findings import FindingPackage  # noqa: E402
from vrae.reporting import ReportDraft, build_draft  # noqa: E402

FIXTURES = ROOT / 'tests/reporting/fixtures'
DEFAULT_OUT = ROOT / 'docs/03-engineering/ra3c-offline/p1-mobile-legibility/preview'
CASES = (200, 404, 410, 403, 500, 'robots', 'unretained', 'waf')


def freeze():
    source_path, pin_path = FIXTURES / 'sources.json', FIXTURES / 'caller-pins.json'
    assert not source_path.exists() and not pin_path.exists(), 'NEW_FIXTURES_ALREADY_SEALED'
    source_cases, pins = {}, {}
    for mode in CASES:
        p, f, guards, metadata, expected = inputs(mode)
        d = build_draft(p, f, guards, metadata, **expected)
        source_cases[str(mode)] = {'pack': p.document,
            'objects_base64': {k: base64.b64encode(v).decode() for k, v in p.objects.items()},
            'package': f.document, 'guard_inputs': guards, 'metadata': metadata}
        pins[str(mode)] = {'pins': expected, 'expected_draft_ref': d.ref,
                           'expected_html_sha256': d.document['html_sha256'],
                           'expected_issue_count': len(d.document['issues'])}
    FIXTURES.mkdir(parents=True, exist_ok=True)
    source_path.write_text(json.dumps(source_cases, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    pin_path.write_text(json.dumps(pins, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def load_case(name):
    c = json.loads((FIXTURES / 'sources.json').read_text(encoding='utf-8'))[str(name)]
    held = json.loads((FIXTURES / 'caller-pins.json').read_text(encoding='utf-8'))[str(name)]
    pins = held['pins']
    p = EvidencePack.load(c['pack'], {k: base64.b64decode(v, validate=True)
        for k, v in c['objects_base64'].items()}, expected_ref=pins['expected_pack_ref'])
    f = FindingPackage.load(c['package'], p, **{k: pins[k] for k in (
        'expected_pack_ref', 'expected_execution_ref', 'expected_package_ref',
        'expected_builder_version', 'expected_evaluator_version')})
    return p, f, c['guard_inputs'], c['metadata'], pins, held


def replay(name):
    p, f, g, m, k, held = load_case(name)
    d = build_draft(p, f, g, m, **k)
    assert d.ref == held['expected_draft_ref']
    assert d.document['html_sha256'] == held['expected_html_sha256']
    assert len(d.document['issues']) == held['expected_issue_count']
    assert bool(d.document['native_report_version']) == bool(d.document['issues'])
    assert ReportDraft.load(d.document, d.html_bytes, p, f, g, m,
                             expected_draft_ref=held['expected_draft_ref'], **k).ref == d.ref
    return d


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-new-fixtures', action='store_true')
    parser.add_argument('--security-preview', action='store_true')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if args.freeze_new_fixtures:
        freeze()
    out = args.output.resolve()
    allowed = (ROOT / 'docs/03-engineering/ra3c-offline').resolve()
    if not out.is_relative_to(allowed):
        raise ValueError('OUTPUT_OUTSIDE_RA3C_EVIDENCE')
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for mode in CASES:
        d = replay(mode)
        prefix = 'contact-' + str(mode)
        (out / (prefix + '.html')).write_bytes(d.html_bytes)
        (out / (prefix + '.draft.json')).write_text(json.dumps(d.document, sort_keys=True, indent=2) + '\n', encoding='utf-8')
        rows.append({'case': str(mode), 'draft_ref': d.ref, 'issues': len(d.document['issues']),
            'kind': d.document['kind'], 'html_sha256': hashlib.sha256(d.html_bytes).hexdigest(),
            'native_report_version': d.document['native_report_version'],
            'trust_outcomes': next(t['observations'] for t in d.document['buyer_journey'] if t['task'] == 'TRUST'),
            'html': prefix + '.html'})
    result = {'status': 'PRIVATE_OFFLINE_REPLAY_PASS', 'private': True, 'approval_status': 'NOT_APPROVED',
              'shareable': False, 'real_model_calls': 0, 'human_gold': '0/26_UNEVALUATED', 'cases': rows}
    (out / 'replay-summary.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    if args.security_preview:
        from tests.reporting.synthetic import PRODUCT
        product = PRODUCT.replace('LINKS', '<script>window.PWNED=1</script>'
            '<a href="/contact" onclick="window.PWNED=1">Contact</a>'
            '<img src="https://trap.invalid/pixel" onerror="window.PWNED=1">')
        p, f, g, m, k = inputs(404, use_accepted=False, product=product)
        d = build_draft(p, f, g, m, **k)
        (out / 'contact-xss.html').write_bytes(d.html_bytes)
        (out / 'contact-xss.draft.json').write_text(json.dumps(d.document, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        (out / 'security-inputs.json').write_text(json.dumps({'pins': k, 'metadata': m,
            'pack': p.document, 'objects_base64': {key: base64.b64encode(v).decode() for key, v in p.objects.items()},
            'package': f.document, 'guard_inputs': g, 'expected_draft_ref': d.ref}, sort_keys=True, indent=2) + '\n', encoding='utf-8')
        p, f, g, m, k = inputs(404, use_accepted=False, contacts=4)
        d = build_draft(p, f, g, m, **k)
        (out / 'contact-multi.html').write_bytes(d.html_bytes)
        (out / 'contact-multi.draft.json').write_text(json.dumps(d.document, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        (out / 'multi-inputs.json').write_text(json.dumps({'pins': k, 'metadata': m,
            'pack': p.document, 'objects_base64': {key: base64.b64encode(v).decode() for key, v in p.objects.items()},
            'package': f.document, 'guard_inputs': g, 'expected_draft_ref': d.ref}, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

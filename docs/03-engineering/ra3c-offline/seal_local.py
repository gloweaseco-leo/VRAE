"""Verify completed real local records and expose reviewable JUnit/summary files."""
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
FUNCTIONAL = 'd238e8e4b3ec97787ec0016f7669aba7af04c6cd'


def status(c):
    return ('failed' if c.find('failure') is not None else 'error' if c.find('error') is not None
            else 'skipped' if c.find('skipped') is not None else 'passed')


for name in ('python311-utf8-final', 'python313-utf8-final'):
    folder = OUT / '.checks' / name
    summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    assert len(summary['results']) == 25 and all(r['matches'] for r in summary['results'])
    cases = ET.parse(folder / 'full.xml').findall('.//testcase')
    counts = {s: sum(status(c) == s for c in cases) for s in ('passed', 'failed', 'error', 'skipped')}
    assert counts == {'passed': 1942, 'failed': 0, 'error': 0, 'skipped': 25}, counts
    groups = {}
    for label, classname, expected in (
        ('reporting', 'tests.reporting.test_draft', 70),
        ('frozen_qa44', 'tests.interpretation.test_ra3b_independent_adversarial', 224),
        ('prior_frozen_qa', 'tests.findings.test_ra2c3_independent_adversarial', 139)):
        selected = [c for c in cases if c.get('classname') == classname]
        assert len(selected) == expected and all(status(c) == 'passed' for c in selected)
        groups[label] = expected
    skipped = [{'classname': c.get('classname'), 'name': c.get('name'),
                'reason': c.find('skipped').get('message')} for c in cases if status(c) == 'skipped']
    assert all(s['classname'] in ('tests.collection.test_isolated',
                                  'tests.browser.test_isolated_browser') for s in skipped)
    summary.update({'full_counts': counts, 'groups_passed': groups, 'skips': skipped,
                    'functional_commit': FUNCTIONAL,
                    'note': 'Final frozen functional source; later evidence/docs-only commits do not alter it.'})
    dest = OUT / 'local' / name
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'full.xml').write_bytes((folder / 'full.xml').read_bytes())
    (dest / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(name, counts, groups)

changed_function = subprocess.check_output(['git', 'diff', FUNCTIONAL, '--',
    'vrae/reporting', 'tests/reporting', 'scripts/verify_ra3c.py'], cwd=ROOT)
assert not changed_function
browser = json.loads((OUT / 'ui/browser-acceptance.json').read_text(encoding='utf-8'))
assert len(browser['results']) == 12 and not browser['external_requests'] and not browser['runtime_exceptions']
assert sum(r['evidence_anchors_clicked'] for r in browser['results']) == 72
for row in browser['results']:
    html = (OUT / 'preview' / ('contact-' + row['case'] + '.html')).read_bytes()
    assert hashlib.sha256(html).hexdigest() == row['html_sha256']
    if row['printProof']:
        pdf = (OUT / 'ui' / ('contact-' + row['case'] + '-A4.pdf')).read_bytes()
        assert row['printProof']['pages'] == 1
        assert hashlib.sha256(pdf).hexdigest() == row['printProof']['pdf_sha256']
records = []
for folder in ('preview', 'ui', 'local'):
    for p in sorted((OUT / folder).rglob('*')):
        if p.is_file():
            raw = p.read_bytes()
            records.append({'path': p.relative_to(OUT).as_posix(), 'bytes': len(raw),
                            'sha256': hashlib.sha256(raw).hexdigest()})
(OUT / 'artifact-index.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
(OUT / 'LOCAL_RESULTS.md').write_text('''# Frozen-code latest-main local results

Both actual completed runs use the functional source from
`d238e8e4b3ec97787ec0016f7669aba7af04c6cd`, based on accepted QA44 main
`2429be6dc5d7dcb48221ab179f063b93ce4b1956`. Subsequent commits add only owned
evidence/recorder/docs. Original core, QA44 and reporting functional/test blobs unchanged.

| Runtime | Full actual result | Reporting | QA44 frozen | Prior independent QA | Commands |
| --- | --- | --- | --- | --- | --- |
| Python 3.11.15 | 1942 passed /25 host skips /0 failures /0 errors | 70 passed | 224 passed | 139 passed | 25/25 expected exits |
| Python 3.13.13 | 1942 passed /25 host skips /0 failures /0 errors | 70 passed | 224 passed | 139 passed | 25/25 expected exits |

The 25 original host skips require disposable HTTP/browser containers; original hosted
jobs execute those security cases. No reporting or frozen QA skip/xfail. Full JUnit
and exact skip names/reasons in [3.11](local/python311-utf8-final/summary.json) /
[3.13](local/python313-utf8-final/summary.json); full XMLs adjacent. Raw 25-command
logs and JUnit ZIPs have per-entry bytes/SHA in archive-index.json. Original GBK/development
REDs remain separately archived and are not included in these green totals.

Each runtime actually ran compile/Ruff/mypy/full pytest/pip, every 18 sealed RA2A,
B0-B6/B6-execution/C0-C3/D0-D1/RA3A/RA3B/RA3C verifier, simulated-Gold expected success
and forged-Gold expected refusal exit 1. Process UTF-8 mode fixes Windows source
decoding only; no original policy, test, fixture or assertion changed.

Actual local Chromium: 12 views, 72 original evidence-link clicks, zero external
requests/runtime exceptions, 6 exact one-page A4 PDFs, desktop/mobile screenshots.
Final artifact-index.json independently binds preview HTML, JSON, screenshots/PDFs
and local records; browser HTML/PDF hashes were compared again after both runs.

First hosted functional run [43152015757](https://github.com/gloweaseco-leo/VRAE/actions/runs/43152015757)
has four real successes, checkout fa92a4e7a23ea510cb8198a92fa37f61564efdec with exact
base+head parents and head-identical tree. See ci-functional/proof.json and security-proof.json,
functional-ci-raw.zip. Browser 245 commands/16 worker lifecycles, worker-kill 137,
48 negative exit-1 probes retain original meanings. Final HEAD's new four hosted checks
and exact checkout/parents are independently recorded in Draft PR #47 after the
last evidence commit; those raw files remain in ignored .checks/ci-<run> to avoid moving
the tested HEAD.

Private synthetic engineering candidate only. Human Gold 0/26, quality N/A. No actual
customer report, approval/share, live model/site, deployment or RA3D. STOP Owner review.
''', encoding='utf-8')

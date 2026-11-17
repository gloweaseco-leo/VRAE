"""Copy only synthetic public artifacts; profiles are never published."""
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


def main():
    runtime = ROOT / 'integration/s2_ux/.runtime'
    out = ROOT / 'integration/s2_ux/evidence/p0'
    out.mkdir(parents=True, exist_ok=False)
    allowed = {'.json', '.png', '.xml', '.log'}
    labels = ['p0-dev-01', 'p0-diagnostic-02', 'p0-renderer-diagnostic-03',
              'p0-browser-permission-04']
    files = []
    for label in labels:
        folder = runtime / label
        for src in sorted(folder.iterdir()):
            if src.is_file() and src.suffix in allowed:
                dest = out / label / src.name
                dest.parent.mkdir(exist_ok=True)
                shutil.copyfile(src, dest)
                files.append({'file': str(dest.relative_to(out)).replace('\\', '/'),
                              'sha256': hashlib.sha256(dest.read_bytes()).hexdigest()})
    tests = []
    for minor, phase in ((m, p) for m in ('311', '313') for p in ('final', 'focused')):
        src = runtime / f'p0-{phase}-{minor}.xml'
        suite = ET.parse(src).getroot().find('testsuite')
        assert suite is not None
        tests.append({'minor': minor, 'phase': phase, **suite.attrib})
        dest = out / src.name
        shutil.copyfile(src, dest)
        files.append({'file': src.name, 'sha256': hashlib.sha256(dest.read_bytes()).hexdigest()})
    actual = json.loads((out / labels[-1] / 'browser.json').read_text())
    assert len(actual['records']) == 24 and all(a['pass'] for a in actual['assertions'])
    (out / 'receipt.json').write_text(json.dumps({
        'stage': 'C2_P0_COMPONENT_CANDIDATE_NOT_S2_EXIT',
        'base': '84276325befdcf858852a1ec791e8b0695a515eb',
        'tests': tests, 'chrome': actual['version'], 'browser_cases': 24,
        'browser_assertions': len(actual['assertions']),
        'historical_red': 'Three sandbox runs failed before measurement. Diagnostic stderr '
                          'records GPU subprocess ACCESS_DENIED and fatal crash. '
                          'Same fixture completed outside sandbox with explicit permission.',
        'gold': '0/26 GOLD_LABEL_PENDING', 'model_calls': 0,
        'pending': ['C1 accepted adapter/dispatch', 'rich DOM authority',
                    'four real rule evaluations', 'five-dimensional signed SSR integration',
                    'same-task PG/Chrome S2 E2E'], 'files': files,
    }, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()

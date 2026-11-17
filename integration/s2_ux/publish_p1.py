"""Publish only allowlisted synthetic proof; no profiles, JWTs or databases."""
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    runtime = ROOT/'integration/s2_ux/.runtime'
    out = ROOT/'integration/s2_ux/evidence/p1'
    out.mkdir(parents=True, exist_ok=False)
    manifest = []
    tests = []
    runs = []

    def save(src, relative):
        dest = out/relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        manifest.append({'file': dest.relative_to(out).as_posix(), 'sha256': digest(dest),
                         'bytes': dest.stat().st_size})

    for src in sorted(runtime.glob('p1-*.xml')):
        save(src, 'junit/'+src.name)
        suite = ET.parse(src).getroot().find('testsuite')
        if suite is not None:
            tests.append({'file': src.name, **suite.attrib})
    for minor in ('311', '313'):
        for suffix in ('', '-native'):
            label = 's2-p1-final-'+minor+suffix
            folder = ROOT/'integration/l2/.runtime'/label
            browser = json.loads((folder/'browser.json').read_text(encoding='utf-8'))
            process = json.loads((folder/'process-cleanup.json').read_text(encoding='utf-8'))
            cleanup = json.loads((folder/'browser-cleanup.json').read_text(encoding='utf-8'))
            assert all(r['pass'] for r in browser['records'])
            assert all(process.values()) and cleanup['exitObserved']
            for name in ('browser.json', 'assertions.json', 'run.json', 'process-cleanup.json', 'browser-cleanup.json'):
                save(folder/name, label+'/'+name)
            for src in sorted(folder.glob('s2-*.png')):
                save(src, label+'/'+src.name)
            if suffix:
                for name in ('l2-deep-report.pdf', 'l2-rebuild-blueprint.pdf'):
                    save(folder/name, label+'/'+name)
            runs.append({'label': label, 'checks': len(browser['records']),
                         'result': 'PASS', 'process_cleanup': process, 'chrome_cleanup': cleanup})
    for label in ('p1-rich-poc-01', 'p1-rich-poc-02'):
        for src in sorted((runtime/label).iterdir()):
            if src.is_file() and src.suffix in ('.json', '.log'):
                save(src, label+'/'+src.name)
    poc = json.loads((runtime/'p1-rich-poc-02/browser.json').read_text(encoding='utf-8'))
    assert len(poc['records']) == 24 and all(r['pass'] for r in poc['assertions'])
    (out/'receipt.json').write_text(json.dumps({
        'stage': 'C2_P1_READING_AND_BOUNDED_SUBSET_CANDIDATE_NOT_S2_EXIT',
        'base': '94a58b9867d96f104941874e07a2c4a4c84ec27f',
        'tests': tests, 'live_same_ssr_runs': runs,
        'ordinary_full_regression_at_publication': {
            minor: ('COMPLETE_SEE_JUNIT' if (runtime/('p1-full-'+minor+'.xml')).exists()
                    else 'IN_PROGRESS_FINAL_COMMENT_WILL_REPORT') for minor in ('311', '313')},
        'poc': {'cases': len(poc['records']), 'checks': len(poc['assertions']),
                'authority': 'NONE_NO_EV_REF', 'production_enabled': False},
        'gold': '0/26 GOLD_LABEL_PENDING', 'model_calls': 0,
        'limitations': ['NOT_FOUR_RULES_FULLY_ENABLED', 'NO_NEW_S2_GUARD_RESULT',
                        'NOT_NEW_APP202_WORKER_OR_S2_E2E', 'CONTROLLED_NOT_FORMAL_HUMAN',
                        'NO_CUSTOMER_SHARING', 'UNKNOWN_WHOLE_SITE_DENOMINATOR'],
        'files': manifest,
    }, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()

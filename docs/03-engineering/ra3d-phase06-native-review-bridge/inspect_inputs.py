"""Read fixed accepted Git objects, not a mutable foreign worktree."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASE = '696d4ae695041f0eeefa56d22039682a989380b2'


def read(name):
    return json.loads(subprocess.check_output(['git', 'show', f'{BASE}:{name}'], cwd=ROOT))


if __name__ == '__main__':
    d = read('docs/03-engineering/ra3c-offline/p1-mobile-legibility/preview/contact-404.draft.json')
    print('PROPOSAL_KEYS', list(d['issues'][0]['proposals']))
    sources = read('tests/reporting/fixtures/sources.json')
    for case in ('404', '200'):
        c = sources[case]
        rows = next(r for r in c['package']['rule_execution']['executions'] if r['rule_id'] == 'CTA-02')
        print(case, json.dumps(rows, ensure_ascii=False, indent=2))

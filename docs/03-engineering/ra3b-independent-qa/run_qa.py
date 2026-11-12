"""Record genuine RED/GREEN, never turn a missing implementation into green.

baseline: expected exit 2 (missing vrae.interpretation) is an explicit RED record.
candidate: requires exact source HEAD, frozen blobs, zero failure/skip/xfail.
Only run candidate mode after Owner/Codex-2 final-ready notification.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
QA = 'tests/interpretation/test_ra3b_independent_adversarial.py'
BASE = '8379e5f63d3feaa66a646d8a19d866a693162c99'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=('baseline', 'candidate'), required=True)
    p.add_argument('--expected-source', required=True)
    p.add_argument('--out', required=True)
    args = p.parse_args()
    assert git('rev-parse', 'HEAD') == args.expected_source
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    freeze = json.loads((Path(__file__).parent/'FREEZE.json').read_text())
    for path, record in freeze['files'].items():
        content = (ROOT/path).read_bytes().replace(b'\r\n', b'\n')
        assert hashlib.sha256(content).hexdigest() == record['sha256_lf'], path
        assert git('hash-object', path) == record['git_blob'], path
    commands = [(['docs/03-engineering/ra3b-independent-qa/audit_inputs.py'], 0),
        (['-m', 'compileall', '-q', 'vrae', QA], 0),
        (['-m', 'ruff', 'check', 'vrae', 'tests', 'docs/03-engineering/ra3b-independent-qa',
          '--select', 'E4,E7,E9,F'], 0),
        (['-m', 'mypy', 'vrae'], 0),
        (['-m', 'pytest', '-q', QA, '--tb=short', '--junitxml='+str(out/'qa.xml')],
         2 if args.mode == 'baseline' else 0),
        (['-m', 'pytest', '-q', '--tb=short', '--junitxml='+str(out/'full.xml')],
         2 if args.mode == 'baseline' else 0),
        (['-m', 'pip', 'check'], 0),
        *[([f'scripts/verify_{s}.py'], 0) for s in (
            'ra2a', 'ra2b0', 'ra2b1', 'ra2b2', 'ra2b3', 'ra2b4', 'ra2b5', 'ra2b6',
            'ra2b6_execution', 'ra2c0', 'ra2c1', 'ra2c2', 'ra2c3', 'ra2d0', 'ra2d1', 'ra3a')],
        (['scripts/verify_ra2d1.py', '--reviews',
          'docs/03-engineering/ra2d1-review/negative-forged-gold.json'], 1)]
    results = []
    for i, (cmd, expected) in enumerate(commands, 1):
        started = datetime.now(timezone.utc).isoformat()
        r = subprocess.run([sys.executable, *cmd], cwd=ROOT, capture_output=True,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        raw = r.stdout+r.stderr
        (out/f'{i:02}.log').write_bytes(raw)
        matches = r.returncode == expected
        if expected == 2:
            matches = matches and b"No module named 'vrae.interpretation'" in raw
        results.append(dict(command=[sys.executable, *cmd], exit_code=r.returncode,
            expected_exit=expected, expected_outcome='PREREQUISITE_RED' if expected == 2 else 'EXPECTED_EXIT',
            matches=matches, started_utc=started, ended_utc=datetime.now(timezone.utc).isoformat(),
            log=f'{i:02}.log', sha256=hashlib.sha256(raw).hexdigest()))
        print(i, cmd[:4], r.returncode, 'expected', expected, flush=True)
    counts = {}
    for name in ('qa', 'full'):
        tree = ET.parse(out/f'{name}.xml')
        cases = tree.findall('.//testcase')
        counts[name] = {'testcases': len(cases), 'failure': sum(c.find('failure') is not None for c in cases),
            'error': sum(c.find('error') is not None for c in cases),
            'skipped': sum(c.find('skipped') is not None for c in cases)}
    ok = all(r['matches'] for r in results)
    if args.mode == 'candidate':
        ok = ok and counts['qa']['testcases'] == 224 and all(counts['qa'][k] == 0
                                                         for k in ('failure', 'error', 'skipped'))
    summary = dict(python=sys.version, source_head=args.expected_source, accepted_base=BASE,
        mode=args.mode, outcome=('PREREQUISITE_RED_CONFIRMED' if args.mode == 'baseline'
                                else 'CANDIDATE_GREEN') if ok else 'UNEXPECTED_FAILURE',
        feature_qa_pass=False if args.mode == 'baseline' else ok, counts=counts,
        freeze=freeze, commands=results)
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    # baseline process exit 0 means records match the expected RED, not test PASS.
    return int(not ok)


if __name__ == '__main__':
    sys.exit(main())

"""Read-only accepted replays; every new output stays in Codex1 QA evidence."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag',required=True,choices=('py311','py313'))
    args = parser.parse_args()
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    out = HERE/'runs'/head/args.tag/'sealed-replays'
    assert not out.exists()
    out.mkdir(parents=True)
    assert not subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=ROOT).strip()
    env = dict(os.environ,PYTHONPATH=str(ROOT),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
    stages = ('ra2a','ra2b0','ra2b1','ra2b2','ra2b3','ra2b4','ra2b5','ra2b6',
        'ra2b6_execution','ra2c0','ra2c1','ra2c2','ra2c3','ra2d0','ra2d1','ra3a','ra3b')
    commands = [([f'scripts/verify_{stage}.py'],0) for stage in stages]+[
        (['scripts/verify_ra2d1.py','--reviews','docs/03-engineering/ra2d1-review/SIMULATED_NOT_HUMAN_GOLD.json'],0),
        (['scripts/verify_ra2d1.py','--reviews','docs/03-engineering/ra2d1-review/negative-forged-gold.json'],1)]
    rows = []
    for index,(command,expected) in enumerate(commands):
        started = datetime.now(timezone.utc).isoformat()
        argv = [sys.executable,*command]
        r = subprocess.run(argv,cwd=ROOT,env=env,capture_output=True)
        (out/(f'{index:02}-'+Path(command[0]).stem+'.log')).write_bytes(r.stdout+r.stderr)
        rows.append(dict(argv=argv,expected_exit=expected,actual_exit=r.returncode,
            matches=r.returncode == expected,started_at=started,finished_at=datetime.now(timezone.utc).isoformat()))
        (out/'results.json').write_text(json.dumps(dict(qa_head=head,python=sys.version,commands=rows),indent=2)+'\n',encoding='utf-8')
        print(args.tag,command,r.returncode,'expected',expected,flush=True)
        assert r.returncode == expected
    # The existing RA3C CLI restricts --output to Codex2's evidence directory.
    # Import its unchanged public replay routine instead: it verifies all old
    # held hashes/build/load, then save returned artifacts only in our own docs.
    sys.path.insert(0,str(ROOT))
    script = ROOT/'scripts/verify_ra3c.py'
    spec = importlib.util.spec_from_file_location('accepted_ra3c_read_only_sealed_replay',script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    native = out/'ra3c-native'
    native.mkdir()
    records = []
    for case in module.CASES:
        draft = module.replay(case)
        (native/(str(case)+'.html')).write_bytes(draft.html_bytes)
        (native/(str(case)+'.json')).write_text(json.dumps(draft.document,sort_keys=True,indent=2)+'\n',encoding='utf-8')
        records.append(dict(case=str(case),draft_ref=draft.ref,issues=len(draft.document['issues']),
            html_sha256=draft.document['html_sha256'],private=draft.document['private']))
    assert len(records) == 8
    assert not subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=ROOT).strip()
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip() == head
    (out/'results.json').write_text(json.dumps(dict(qa_head=head,python=sys.version,commands=rows,
        ra3c_sealed_native=records,source_unchanged=True,foreign_evidence_written=False),indent=2)+'\n',encoding='utf-8')
    print(args.tag,'19 actual commands matched, including forged-Gold exit1; all8 sealed RA3C build/load replays passed',flush=True)


if __name__ == '__main__':
    main()

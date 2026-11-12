"""Actual Phase-A RED + accepted controls; never reclassifies RED as PASS."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE = '2429be6dc5d7dcb48221ab179f063b93ce4b1956'


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag',required=True,choices=('py311','py313'))
    args = parser.parse_args()
    out = HERE/'phase-a'/args.tag
    assert not out.exists(), 'Preserve prior runs; choose an explicitly versioned rerun directory'
    out.mkdir(parents=True)
    env = dict(os.environ,PYTHONPATH=str(ROOT),PYTHONDONTWRITEBYTECODE='1')
    assert not any(k.startswith('VRAE_RA3C_QA_') for k in env), 'Phase A must not bind a candidate adapter'
    selected = ['tests/interpretation/test_ra3b_independent_adversarial.py',
        'tests/findings/test_ra2c3_independent_adversarial.py','tests/test_domain.py',
        'tests/test_contracts.py','tests/test_ra0f_regressions.py','tests/collection/test_security.py']
    jobs = [
        ('input-audit',[str(HERE/'audit_inputs.py')],0),
        ('ruff',['-m','ruff','check','tests/reporting/test_ra3c_independent_acceptance.py',
            str(HERE/'audit_inputs.py'),str(HERE/'make_inputs.py'),str(HERE/'run_phase_a.py'),
            '--select','E4,E7,E9,F'],0),
        ('prerequisite-red',['-m','pytest','-q','tests/reporting/test_ra3c_independent_acceptance.py',
            '--junitxml='+str(out/'prerequisite-red.xml'),'-o','junit_family=legacy'],1),
        ('accepted-controls',['-m','pytest','-q',*selected,'--junitxml='+str(out/'accepted-controls.xml')],0),
        ('ra3a-replay',['scripts/verify_ra3a.py'],0),
        ('ra3b-replay',['scripts/verify_ra3b.py'],0),
        ('pip-check',['-m','pip','check'],0)]
    report = dict(phase='A_PREREQUISITE_RED',base_sha=BASE,qa_source_sha=git('rev-parse','HEAD'),
        python=sys.version,executable=sys.executable,started_at=datetime.now(timezone.utc).isoformat(),
        reporting_feature_pass=False,visual='VISUAL_NOT_VERIFIED',adapter='NOT_BOUND',
        gold='OWNER_AUTHORIZED_GOLD_DEFERRED_0_OF_26',jobs=[])
    for name,command,expected in jobs:
        started = time.monotonic()
        result = subprocess.run([sys.executable,*command],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (out/(name+'.log')).write_bytes(result.stdout)
        entry = dict(name=name,argv=[sys.executable,*command],returncode=result.returncode,
            expected_returncode=expected,seconds=round(time.monotonic()-started,3),
            log_sha256=hashlib.sha256(result.stdout).hexdigest())
        junit = out/(name+'.xml')
        if junit.exists():
            suites = ET.parse(junit).getroot().findall('testsuite')
            counts = {k:sum(int(s.get(k,'0')) for s in suites) for k in ('tests','errors','failures','skipped')}
            counts['passed'] = counts['tests']-counts['errors']-counts['failures']-counts['skipped']
            entry['junit'] = counts
            entry['junit_sha256'] = hashlib.sha256(junit.read_bytes()).hexdigest()
        report['jobs'].append(entry)
        (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(args.tag,name,result.returncode,entry.get('junit',''),flush=True)
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    report['expected_phase_a_outcomes'] = all(j['returncode'] == j['expected_returncode'] for j in report['jobs'])
    red = next(j for j in report['jobs'] if j['name'] == 'prerequisite-red')
    assert red['junit'] == dict(tests=64,errors=64,failures=0,skipped=0,passed=0)
    raw = (out/'prerequisite-red.log').read_text(encoding='utf-8')
    assert "No module named 'vrae.reporting'" in raw
    (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert report['expected_phase_a_outcomes'], 'Unexpected failure; see preserved raw logs'


if __name__ == '__main__':
    main()

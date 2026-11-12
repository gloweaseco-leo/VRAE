"""Exact-final-SHA attempt; mapping setup errors are not feature verdicts."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
QA_ROOT = HERE.parents[3]
CANDIDATE_ROOT = QA_ROOT.parent/'ra3c-qa-phaseb-6a7a3d3a'
CANDIDATE = '6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2'
FREEZE = 'fa645b58549dfd21a6b80656d403f672b790acd8'
ADAPTER = HERE.parent/'adapter-preflight-v1/adapter_draft.py'
OVERLAYS = ['tests/reporting/test_ra3c_independent_acceptance.py',
    'tests/reporting/fixtures/ra3c_codex1_cases.json',
    'tests/reporting/fixtures/ra3c_codex1_inputs.json']


def git(*args):
    return subprocess.check_output(['git',*args],cwd=CANDIDATE_ROOT)


def verify():
    assert git('rev-parse','HEAD').decode().strip() == CANDIDATE
    assert not git('diff','--name-only').strip(), 'No unstaged candidate edits allowed'
    native = {line.split('\t',1)[1]:line.split('\t',1)[0].split()[2]
        for line in git('ls-tree','-r',CANDIDATE).decode().splitlines()}
    index = {line.split('\t',1)[1]:line.split('\t',1)[0].split()[1]
        for line in git('ls-files','--stage').decode().splitlines()}
    assert len(native) == 1506 and all(index[p] == b for p,b in native.items())
    assert set(index)-set(native) == set(OVERLAYS)
    for path in OVERLAYS:
        assert index[path] == git('rev-parse',FREEZE+':'+path).decode().strip()
    return dict(candidate_blobs_unchanged=1506,frozen_overlay_blobs={p:index[p] for p in OVERLAYS})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag',choices=('py311','py313'),required=True)
    args = parser.parse_args()
    out = HERE/args.tag
    assert not out.exists(), 'Preserve original attempt'
    proof = verify()
    out.mkdir()
    command = [sys.executable,'-m','pytest','-q',OVERLAYS[0],
        '--junitxml='+str(out/'mapping-not-bound.xml'),'-o','junit_family=legacy']
    env = dict(os.environ,PYTHONPATH=str(CANDIDATE_ROOT),PYTHONUTF8='1',
        PYTHONDONTWRITEBYTECODE='1',VRAE_RA3C_QA_ADAPTER_PATH=str(ADAPTER),
        VRAE_RA3C_EXPECTED_CANDIDATE_SHA=CANDIDATE)
    began = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command,cwd=CANDIDATE_ROOT,env=env,
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (out/'pytest.log').write_bytes(result.stdout)
    suites = ET.parse(out/'mapping-not-bound.xml').getroot().findall('testsuite')
    counts = {k:sum(int(s.get(k,'0')) for s in suites) for k in ('tests','errors','failures','skipped')}
    counts['passed'] = counts['tests']-counts['errors']-counts['failures']-counts['skipped']
    report = dict(kind='PHASE_B_ATTEMPT_QA_MAPPING_NOT_BOUND_NOT_FEATURE_FAILURE',
        candidate_sha=CANDIDATE,frozen_qa_sha=FREEZE,adapter_sha256=hashlib.sha256(ADAPTER.read_bytes()).hexdigest(),
        python=sys.version,argv=command,cwd=str(CANDIDATE_ROOT),started_at=began,
        finished_at=datetime.now(timezone.utc).isoformat(),returncode=result.returncode,junit=counts,
        substantive_business_cases_executed=0,confirmed_production_defects=0,
        visual='VISUAL_NOT_VERIFIED',customer_share='NO_GO',source_proof_before=proof,
        source_proof_after=verify(),log_sha256=hashlib.sha256(result.stdout).hexdigest(),
        junit_sha256=hashlib.sha256((out/'mapping-not-bound.xml').read_bytes()).hexdigest())
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    assert result.returncode == 1 and counts == dict(tests=64,errors=64,failures=0,skipped=0,passed=0)
    assert b'QA_MAPPING_NOT_BOUND' in result.stdout
    assert b"No module named 'vrae.reporting'" not in result.stdout
    print(args.tag,counts,'QA integration NOT_READY; 0 substantive feature results')


if __name__ == '__main__':
    main()

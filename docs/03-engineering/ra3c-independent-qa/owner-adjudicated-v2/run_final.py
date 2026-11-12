"""Exact final SHA dual-runtime runner, with truthful historical V1 RED retained."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
PREFIX = 'docs/03-engineering/ra3c-independent-qa/'
V1 = 'tests/reporting/test_ra3c_independent_acceptance.py'
V2 = PREFIX+'owner-adjudicated-v2/test_acceptance_v2.py'


def source_proof(root,sha):
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=root)
    assert git('rev-parse','HEAD').decode().strip() == sha
    assert not git('diff','--name-only').strip(), 'No unstaged source changes'
    native = {line.split('\t',1)[1]:line.split('\t',1)[0].split()[2]
        for line in git('ls-tree','-r',sha).decode().splitlines()}
    index = {line.split('\t',1)[1]:line.split('\t',1)[0].split()[1]
        for line in git('ls-files','--stage').decode().splitlines()}
    assert all(index[p] == b for p,b in native.items())
    overlays = {p:b for p,b in index.items() if p not in native}
    assert all(p == V1 or p.startswith('tests/reporting/fixtures/ra3c_codex1_') or p.startswith(PREFIX) for p in overlays)
    return dict(native_blob_count=len(native),all_native_blobs_unchanged=True,overlays=overlays)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worktree',required=True)
    parser.add_argument('--tag',choices=('py311','py313'),required=True)
    parser.add_argument('--mode',choices=('v2','legacy','full'),required=True)
    parser.add_argument('--observations',required=True)
    args = parser.parse_args()
    root = Path(args.worktree).resolve()
    src = root/(PREFIX+'owner-adjudicated-v2')
    binding = json.loads((src/'fixtures/candidate-binding.json').read_text(encoding='utf-8'))
    sha = binding['candidate_sha']
    before = source_proof(root,sha)
    out = HERE/'runs'/sha/args.tag/args.mode
    assert not out.exists(), 'Preserve complete earlier runs'
    out.mkdir(parents=True)
    paths = [V2] if args.mode == 'v2' else [V1] if args.mode == 'legacy' else ['tests',V2]
    command = [sys.executable,'-m','pytest','-q',*paths,'--junitxml='+str(out/'junit.xml'),'-o','junit_family=legacy']
    env = dict(os.environ,PYTHONPATH=str(root),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',
        VRAE_RA3C_QA_V2_CANDIDATE_SHA=sha,VRAE_RA3C_QA_V2_OBSERVATIONS_PATH=args.observations,
        VRAE_RA3C_QA_ADAPTER_PATH=str(src/'legacy_transport.py'))
    started = datetime.now(timezone.utc).isoformat()
    with (out/'stdout.log').open('wb') as log:
        result = subprocess.run(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
    nodes = []
    for node in ET.parse(out/'junit.xml').getroot().iter('testcase'):
        classname = node.get('classname','')
        name = node.get('name','')
        group = 'v2_objectives' if 'test_owner_adjudicated_business_objective' in name else \
            'v2_denials' if 'test_companion_original_invalid_request_denial' in name else \
            'legacy_v1' if 'test_ra3c_independent_acceptance' in classname else 'accepted_regression'
        error,failure,skipped = node.find('error'),node.find('failure'),node.find('skipped')
        status = 'error' if error is not None else 'failed' if failure is not None else \
            'xfail' if skipped is not None and skipped.get('type') == 'pytest.xfail' else 'skipped' if skipped is not None else 'passed'
        problem = error if error is not None else failure
        nodes.append(dict(group=group,name=name,status=status,
            message=None if problem is None else problem.get('message'),
            properties={p.get('name'):p.get('value') for p in node.findall('properties/property')}))
    counts = {g:dict(Counter(n['status'] for n in nodes if n['group'] == g))
        for g in ('v2_objectives','v2_denials','legacy_v1','accepted_regression')}
    report = dict(version='OWNER_ADJUDICATED_RA3C_QA_V2',candidate_sha=sha,python=sys.version,
        mode=args.mode,started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),
        argv=command,cwd=str(root),returncode=result.returncode,counts=counts,nodes=nodes,
        source_before=before,source_after=source_proof(root,sha),
        stdout_sha256=hashlib.sha256((out/'stdout.log').read_bytes()).hexdigest(),
        junit_sha256=hashlib.sha256((out/'junit.xml').read_bytes()).hexdigest(),
        v2_source_sha256=hashlib.sha256((src/'test_acceptance_v2.py').read_bytes()).hexdigest(),
        binding_sha256=hashlib.sha256((src/'fixtures/candidate-binding.json').read_bytes()).hexdigest())
    (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(args.tag,args.mode,'raw pytest exit',result.returncode,counts)


if __name__ == '__main__':
    main()

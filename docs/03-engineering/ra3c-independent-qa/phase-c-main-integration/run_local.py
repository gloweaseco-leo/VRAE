"""Real dual-runtime current/default, exact V2, and explicit historical V1 runs."""
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
ROOT = HERE.parents[3]
V1 = 'tests/reporting/test_ra3c_independent_acceptance.py'
V2 = 'tests/reporting/test_ra3c_owner_adjudicated_v2.py'
MAIN = '61b88eb31d1dec668e7e05495b88fe2d8a5b25fe'


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)


def tree(ref):
    return {s.split('\t',1)[1]:s.split('\t',1)[0] for s in git('ls-tree','-r',ref).decode().splitlines()}


def source_proof(expected):
    assert git('rev-parse','HEAD').decode().strip() == expected
    assert not git('diff','HEAD','--name-only').strip(), 'Tracked source must remain unchanged during execution'
    current,accepted,prior = tree(expected),tree(MAIN),tree('48cd0052c0edfe09c0bc00791ecdd8e5f29888c2')
    changed = [p for p,v in accepted.items() if current.get(p) != v]
    assert changed == ['pyproject.toml'], changed
    historical_changed = [p for p,v in prior.items() if current.get(p) != v]
    assert historical_changed == ['pyproject.toml'], historical_changed
    return dict(accepted_main=MAIN,main_blob_modes_verified=len(accepted)-1,
        prior_qa_blob_modes_verified=len(prior)-1,only_authorized_existing_file_changed=changed,
        v1_blob=git('rev-parse','HEAD:'+V1).decode().strip(),
        frozen_v2_blob=git('rev-parse','HEAD:docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/test_acceptance_v2.py').decode().strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag',choices=('py311','py313'),required=True)
    args = parser.parse_args()
    head = git('rev-parse','HEAD').decode().strip()
    out = HERE/'runs'/head/args.tag
    assert not out.exists(), 'Never overwrite an actual run'
    out.mkdir(parents=True)
    before = source_proof(head)
    env = dict(os.environ,PYTHONPATH=str(ROOT),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',
        VRAE_RA3C_QA_ADAPTER_PATH=str(ROOT/'docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/legacy_transport.py'))
    env.pop('PYTEST_ADDOPTS',None)
    rows = []
    for mode,extra,expected_total in (('v2',[V2],118),('historical',['-o','addopts=-ra',V1],64),('default',[],2086)):
        target = out/mode
        target.mkdir()
        collect = [sys.executable,'-m','pytest','--collect-only','-q',*extra]
        collected = subprocess.run(collect,cwd=ROOT,env=env,capture_output=True)
        (target/'collection.log').write_bytes(collected.stdout+collected.stderr)
        ids = [s for s in collected.stdout.decode('utf-8').splitlines() if '::test_' in s]
        assert collected.returncode == 0 and len(ids) == expected_total, (mode,len(ids))
        if mode == 'default':
            assert not any('test_ra3c_independent_acceptance.py::' in s for s in ids)
            assert sum('test_ra3c_owner_adjudicated_v2.py::' in s for s in ids) == 118
        argv = [sys.executable,'-m','pytest','-q',*extra,'--junitxml='+str(target/'junit.xml'),'-o','junit_family=legacy']
        started = datetime.now(timezone.utc).isoformat()
        with (target/'stdout.log').open('wb') as log:
            result = subprocess.run(argv,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        nodes = []
        for n in ET.parse(target/'junit.xml').getroot().iter('testcase'):
            error,failure,skip = n.find('error'),n.find('failure'),n.find('skipped')
            status = 'error' if error is not None else 'failed' if failure is not None else \
                'xfail' if skip is not None and skip.get('type') == 'pytest.xfail' else 'skipped' if skip is not None else 'passed'
            problem = error if error is not None else failure
            group = 'v2' if 'test_owner_adjudicated_business_objective' in n.get('name','') or \
                'test_companion_original_invalid_request_denial' in n.get('name','') else 'historical' if mode == 'historical' else 'accepted'
            nodes.append(dict(name=n.get('name'),classname=n.get('classname'),group=group,status=status,
                message=problem.get('message') if problem is not None else None))
        counts = dict(Counter(n['status'] for n in nodes))
        groups = {g:dict(Counter(n['status'] for n in nodes if n['group'] == g)) for g in ('v2','historical','accepted')}
        row = dict(qa_source_head=head,mode=mode,python=sys.version,argv=argv,collection_argv=collect,
            started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),returncode=result.returncode,
            collected=len(ids),counts=counts,groups=groups,nodes=nodes,source_before=before,source_after=source_proof(head),
            junit_sha256=hashlib.sha256((target/'junit.xml').read_bytes()).hexdigest(),
            stdout_sha256=hashlib.sha256((target/'stdout.log').read_bytes()).hexdigest())
        (target/'results.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        rows.append({k:v for k,v in row.items() if k != 'nodes'})
        (out/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(args.tag,mode,'actual pytest exit',result.returncode,counts,flush=True)
        assert len(nodes) == expected_total
        if mode == 'historical':
            assert result.returncode == 1 and counts == {'passed':11,'failed':53}
            assert Counter(n['message'] for n in nodes if n['status'] == 'failed') == {
                'vrae.reporting.common.ReportError: REPORT_UNSUPPORTED_PROSE':52,
                'vrae.reporting.common.ReportError: REPORT_GUARD_NOT_VALIDATED':1}
        else:
            assert result.returncode == 0
            assert counts == ({'passed':118} if mode == 'v2' else {'passed':2061,'skipped':25})
            assert groups['v2'] == {'passed':118}
            text = (target/'stdout.log').read_text(encoding='utf-8')
            assert 'OWNER_RA3C_V2_ACTUAL_COLLECTION ' in text and 'OWNER_RA3C_V2_ACTUAL_CALL_REPORTS ' in text


if __name__ == '__main__':
    main()

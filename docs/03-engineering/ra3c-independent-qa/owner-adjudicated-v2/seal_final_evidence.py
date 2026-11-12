"""Seal actual completed runs; preserve raw RED and all original source blobs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PREFIX = HERE.relative_to(ROOT).as_posix()+'/'
PRIOR = '61b9173a32789185bd7fcaf750adb6118ec4bc43'
FROZEN = '00655091ac06ede0a26233feb6ff75da9fe642bb'
BOUND = 'f6956dd7d62f86d611f2164197c5436e43876764'
MAIN = '60dbe1e1acfc84ad0849e84f3abe3712ad8ebccd'


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)


def tree(sha):
    return {s.split('\t',1)[1]:s.split('\t',1)[0].split()[2]
        for s in git('ls-tree','-r',sha).decode().splitlines()}


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate',required=True)
    args = parser.parse_args()
    run = HERE/'runs'/args.candidate
    target = run/'SUMMARY.json'
    assert not target.exists(), 'Never overwrite sealed evidence'
    index = {s.split('\t',1)[1]:s.split('\t',1)[0].split()[1]
        for s in git('ls-files','--stage').decode().splitlines()}
    prior,frozen,bound,base,candidate = (tree(x) for x in (PRIOR,FROZEN,BOUND,MAIN,args.candidate))
    assert all(index[p] == b for p,b in prior.items())
    frozen_own = {p:b for p,b in frozen.items() if p.startswith(PREFIX)}
    assert all(index[p] == b for p,b in frozen_own.items())
    binding_path = PREFIX+'fixtures/candidate-binding.json'
    assert index[binding_path] == bound[binding_path]
    historic_code = {p:b for p,b in base.items() if p.startswith(('vrae/','tests/'))}
    assert all(candidate[p] == b for p,b in historic_code.items())
    reports = {tag:{mode:read(run/tag/mode/'results.json') for mode in ('full','v2')}
        for tag in ('py311','py313')}
    cases = read(HERE/'fixtures/cases.json')
    counts = {}
    for tag,modes in reports.items():
        for mode,row in modes.items():
            assert row['candidate_sha'] == args.candidate
            assert row['source_before']['all_native_blobs_unchanged']
            assert row['source_after']['all_native_blobs_unchanged']
            assert row['counts']['v2_objectives'] == {'passed':64}
            assert row['counts']['v2_denials'] == {'passed':54}
            ids = [n['name'].split('[',1)[1].split(']',1)[0].split('-',1)[0]
                for n in row['nodes'] if n['group'] == 'v2_objectives']
            assert set(ids) == {c['id'] for c in cases} and len(ids) == 64
            assert sha256((run/tag/mode/'junit.xml').read_bytes()) == row['junit_sha256']
            assert sha256((run/tag/mode/'stdout.log').read_bytes()) == row['stdout_sha256']
            if mode == 'full':
                assert row['returncode'] == 1 and row['counts']['legacy_v1'] == {'passed':11,'failed':53}
                assert not set(row['counts']['accepted_regression'])-{'passed','skipped'}
            else:
                assert row['returncode'] == 0
            counts[tag+'/'+mode] = row['counts']
    binding = read(HERE/'fixtures/candidate-binding.json')
    assert binding['candidate_sha'] == args.candidate
    source_files = ['tests/reporting/test_ra3c_independent_acceptance.py',
        'tests/reporting/fixtures/ra3c_codex1_cases.json',
        'tests/reporting/fixtures/ra3c_codex1_inputs.json']+list(frozen_own)+[binding_path]
    inventory = {p:dict(git_blob=index[p],git_sha256=sha256(git('show',':'+p)),
        worktree_sha256=sha256((ROOT/p).read_bytes())) for p in source_files}
    ci = read(run/'candidate-ci/run.json')
    jobs = read(run/'candidate-ci/jobs.json')['jobs']
    assert ci['head_sha'] == args.candidate and ci['conclusion'] == 'success' and len(jobs) == 4
    merge = 'f476078717985e68d34177106e161cffe90eb967'
    parents = git('show','-s','--format=%P',merge).decode().strip().split()
    assert parents == [MAIN,args.candidate]
    for job in jobs:
        assert job['conclusion'] == 'success'
        text = (run/'candidate-ci'/(str(job['id'])+'.log')).read_text(encoding='utf-8')
        assert merge in text and args.candidate in text and MAIN in text
    browser = read(run/'browser/browser-observations.json')
    assert browser['candidate_sha'] == args.candidate and len(browser['views']) == 4
    assert not browser['exceptions']
    assert all(v['privacy_font_px'] >= 12 and not v['external_requests'] for v in browser['views'])
    dossier = read(run/'observations.json')
    assert dossier['not_customer_approval'] and dossier['candidate_sha'] == args.candidate
    summary = dict(version='OWNER_ADJUDICATED_RA3C_QA_V2',candidate_sha=args.candidate,
        sealed_at=datetime.now(timezone.utc).isoformat(),qa_source_freeze=FROZEN,
        candidate_binding_source=BOUND,prior_head=PRIOR,prior_blobs_unchanged=len(prior),
        initial_v2_blobs_unchanged=len(frozen_own),historic_main_code_blobs_unchanged=len(historic_code),
        candidate_native_blobs_unchanged=len(candidate),counts=counts,source_hashes=inventory,
        feature_ci=dict(run=ci['html_url'],merge_ref=merge,parents=parents,
            jobs=[dict(id=j['id'],name=j['name'],conclusion=j['conclusion'],
                url=ci['html_url']+'/job/'+str(j['id'])) for j in jobs],
            decoded_logs=True,qa_phase_c_not_performed=True),
        browser=dict(views=4,actual_internal_clicks=sum(len(v['citation_clicks']) for v in browser['views']),
            external_page_requests=0,privacy_font_px=[v['privacy_font_px'] for v in browser['views']],
            screenshot_owner='CODEX1_LOCAL_QA',human_customer_approval=False),
        risks=['Human Gold 0/26; QUALITY_GATE_NOT_EVALUABLE; real customer NO_GO',
            'Closed editorial vocabulary does not establish arbitrary semantic truth',
            'Synthetic source domain proves 0/1 issue and dedupe, not three distinct real defects or commercial ROI',
            'Native private draft is not RA0 approval/share authority',
            'Host/container skips retain separate real isolated feature CI evidence',
            'Chromium process warnings retained; page request observations are not kernel egress proof',
            'Preserved V1 remains 11/53 RED; combined pytest exits 1; Phase C main integration awaits Owner'])
    target.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    files = [p for p in run.rglob('*') if p.is_file()]
    assert not (run/'RAW_MANIFEST.json').exists() and not (run/'raw-v2-evidence.zip').exists()
    archive = run/'raw-v2-evidence.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(files):
            z.write(p,p.relative_to(run).as_posix())
    manifest = dict(version=summary['version'],candidate_sha=args.candidate,
        files={p.relative_to(run).as_posix():dict(bytes=p.stat().st_size,sha256=sha256(p.read_bytes())) for p in sorted(files)},
        archive=dict(file=archive.name,bytes=archive.stat().st_size,sha256=sha256(archive.read_bytes())))
    (run/'RAW_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(counts=counts,archive=manifest['archive'],prior_blobs=len(prior)),ensure_ascii=False))


if __name__ == '__main__':
    main()

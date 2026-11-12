"""Seal completed local Phase C evidence before final exact-HEAD hosted CI."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCE = '57e865d8522a98347e64bd31a34412d677469087'
OLD_SOURCE = 'dadc19b421b79875c443284d60422dc28d422e73'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip() == SOURCE
    assert not subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=ROOT).strip()
    target = HERE/'LOCAL_FINAL_SUMMARY.json'
    assert not target.exists()
    final,prior = {},{}
    for tag in ('py311','py313'):
        final[tag] = {}
        for mode in ('v2','historical'):
            p = HERE/'runs'/SOURCE/tag/mode
            row = read(p/'results.json')
            assert row['qa_source_head'] == SOURCE
            assert row['counts'] == ({'passed':118} if mode == 'v2' else {'passed':11,'failed':53})
            assert row['returncode'] == (0 if mode == 'v2' else 1)
            assert row['collected'] == (118 if mode == 'v2' else 64)
            assert sha(p/'junit.xml') == row['junit_sha256'] and sha(p/'stdout.log') == row['stdout_sha256']
            final[tag][mode] = {k:v for k,v in row.items() if k != 'nodes'}
        prior[tag] = read(HERE/'runs'/OLD_SOURCE/tag/'default/results.json')
        assert prior[tag]['counts'] == {'passed':2061,'skipped':25} and prior[tag]['returncode'] == 0
        prior[tag] = {k:v for k,v in prior[tag].items() if k != 'nodes'}
        sealed = read(HERE/'runs'/SOURCE/tag/'sealed-replays/results.json')
        old = read(HERE/'runs'/SOURCE/tag/'prior-engine/results.json')
        assert len(sealed['commands']) == 19 and all(r['matches'] for r in sealed['commands'])
        assert len(sealed['ra3c_sealed_native']) == 8 and len(old['prior_cases']) == 8
        assert old['actual_exit'] == 0 and old['current_renderer_stale_pin_rejection'] == 'REPORT_PIN_VERSION'
    browser = ROOT/'docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/runs'/SOURCE/'browser'
    observed = read(browser/'browser-observations.json')
    assert observed['candidate_sha'] == SOURCE and len(observed['views']) == 4 and not observed['exceptions']
    assert sum(len(v['citation_clicks']) for v in observed['views']) == 18
    assert all(v['privacy_font_px'] >= 12 and not v['external_requests'] for v in observed['views'])
    source = read(HERE/'source-audits'/SOURCE/'SOURCE_PROOF.json')
    lab = read(HERE/'local-minimal-docker/summary.json')
    assert lab['lab_exit'] == lab['build_exit'] == 0 and lab['docs_member_count'] == 23
    assert len(lab['actual_v2_call_reports']['actual_call_reports']) == 118
    result = dict(version='OWNER_AUTHORIZED_RA3C_QA_PHASE_C_FINAL',local_source_head=SOURCE,
        accepted_main='696d4ae695041f0eeefa56d22039682a989380b2',sealed_at=datetime.now(timezone.utc).isoformat(),
        final_main_explicit_runs=final,previous_main_full_runs=prior,
        final_main_default_full_location='REQUIRED_TRUE_NEW_HOSTED_PYTHON311_AND_313_ON_FINAL_QA_HEAD',
        historical_v1_default_omitted_nodes=64,historical_v1_default_omitted_failed_nodes=53,
        v1_was_not_rewritten_skipped_xfailed_or_called_green=True,
        source_proof=source,real_minimal_lab=dict(exit=0,passed=2085,skipped=1,v2_actual_passed=118,docs=23),
        final_main_browser=dict(source_head=SOURCE,views=4,actual_clicks=18,page_external_requests=0,privacy_font_px=12),
        historical_replays_each_python=dict(commands=19,current_ra3c_cases=8,original_renderer_cases=8,forged_gold_actual_exit=1),
        final_ci_status='PENDING_EXTERNAL_POST_FREEZE_RECEIPT_NOT_INHERITED_FROM_OLD_RUN',
        no_customer_or_report_approval=True,human_gold='0/26_QUALITY_GATE_NOT_EVALUABLE')
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    files = [p for p in HERE.rglob('*') if p.is_file()]
    files += [p for p in browser.rglob('*') if p.is_file()]
    for name in ('raw-phase-c-local-evidence.zip','RAW_LOCAL_MANIFEST.json'):
        assert not (HERE/name).exists()
    archive = HERE/'raw-phase-c-local-evidence.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(files):
            z.write(p,p.relative_to(ROOT).as_posix())
    manifest = dict(local_source=SOURCE,accepted_main=result['accepted_main'],
        members={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(files)},
        archive=dict(path=archive.relative_to(ROOT).as_posix(),bytes=archive.stat().st_size,sha256=sha(archive)))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert set(z.namelist()) == set(manifest['members'])
        for name,row in manifest['members'].items():
            assert hashlib.sha256(z.read(name)).hexdigest() == row['sha256']
    (HERE/'RAW_LOCAL_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(archive=manifest['archive'],members=len(files),source_preserved=source['accepted_main_blob_modes_preserved'])))


if __name__ == '__main__':
    main()

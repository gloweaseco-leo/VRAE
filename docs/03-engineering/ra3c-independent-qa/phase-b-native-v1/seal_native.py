"""Seal raw first-round evidence; does not turn native RED into acceptance."""
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads((HERE/path).read_text(encoding='utf-8'))


def main():
    target = HERE/'raw-native-evidence.zip'
    assert not target.exists(), 'Preserve original native run'
    results = [read(tag+'/results.json') for tag in ('py311','py313')]
    expected = dict(passed=11,failed=53,error=0,skipped=0,xfail=0)
    for tag,result in zip(('py311','py313'),results):
        assert result['counts'] == expected and result['returncode'] == 1
        assert len(result['nodes']) == 64
        assert hashlib.sha256((HERE/tag/'pytest.log').read_bytes()).hexdigest() == result['log_sha256']
        assert hashlib.sha256((HERE/tag/'frozen-64.xml').read_bytes()).hexdigest() == result['junit_sha256']
        source_paths = {'adapter.py':HERE/'adapter.py','request-pins.json':HERE/'request-pins.json',
            'adapter_draft.py':HERE.parent/'adapter-preflight-v1/adapter_draft.py'}
        assert all(hashlib.sha256(source_paths[n].read_bytes()).hexdigest() == h for n,h in result['source_files'].items())
    assert [(n['name'],n['status']) for n in results[0]['nodes']] == [(n['name'],n['status']) for n in results[1]['nodes']]
    for tag in ('py311','py313'):
        diag = read('diagnostic-'+tag+'/results.json')
        assert diag['observations_complete'] and len(diag['calls']) == 10
        assert all(c['outcome'] == 'NATIVE_REJECTION' for c in diag['calls'])
        assert not diag['actual_score_fields_found']
        controls = read('controls-'+tag+'/results.json')
        assert not controls.get('completed',False)
        assert controls['calls'][-1]['label'] == 'false_certificate'
        assert controls['calls'][-1]['code'] == 'REPORT_CLAIM_REJECTED'
    browser = read('ui-supplement/browser-observations.json')
    assert browser['status'] == 'OBSERVATIONS_CAPTURED_NOT_ACCEPTANCE'
    assert len(browser['views']) == 4 and sum(len(v['citation_clicks']) for v in browser['views']) == 10
    assert not browser['exceptions'] and all(not v['external_requests'] for v in browser['views'])
    for view in browser['views']:
        file = HERE/'ui-supplement'/view['screenshot']['file']
        assert hashlib.sha256(file.read_bytes()).hexdigest() == view['screenshot']['sha256']
    spec = importlib.util.spec_from_file_location('codex1_final_source_check',HERE.parent/'phase-b-initial-6a7a3d3a/attempt.py')
    proof = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proof)
    summary = dict(kind='FIRST_NATIVE_ROUND_RED_NOT_ACCEPTANCE',candidate_sha=proof.CANDIDATE,
        original_frozen_source=proof.FREEZE,counts_per_runtime=expected,
        provisional_classifications=dict(Counter(n['classification'] for n in results[0]['nodes'])),
        raw_failures_not_relabelled=True,confirmed_production_security_bugs=0,
        auxiliary_control_exits=dict(py311=1,py313=1),
        auxiliary_expected_code='REPORT_UNSUPPORTED_PROSE',auxiliary_actual_code='REPORT_CLAIM_REJECTED',
        auxiliary_original_runs_not_relabelled_success=True,
        actual_remaining_diagnostic_rejections_per_runtime=10,
        measured_ui_gate_gaps=['375px privacy font11 below frozen12'],
        native_control_browser_views=4,native_control_actual_evidence_clicks=10,
        customer_share='NO_GO',source_proof=proof.verify())
    (HERE/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    files = [p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts
        and p.suffix != '.zip' and p.name != 'RAW_MANIFEST.json']
    records = {p.relative_to(HERE).as_posix():dict(bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(files)}
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in records:
            archive.write(HERE/name,name)
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert all(hashlib.sha256(archive.read(n)).hexdigest() == v['sha256'] for n,v in records.items())
    (HERE/'RAW_MANIFEST.json').write_text(json.dumps(dict(archive_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        files=records),indent=2)+'\n',encoding='utf-8')
    print('Native RED evidence sealed:',len(records),'files;',target.stat().st_size,'bytes')


if __name__ == '__main__':
    main()

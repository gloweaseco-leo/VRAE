"""Preserve original error/JUnit/browser bytes independently of Git CRLF."""
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent


def main():
    target = HERE/'raw-attempt-evidence.zip'
    assert not target.exists(), 'Preserve original evidence'
    for tag in ('py311','py313'):
        result = json.loads((HERE/tag/'results.json').read_text(encoding='utf-8'))
        assert result['substantive_business_cases_executed'] == 0
        assert result['junit'] == dict(tests=64,errors=64,failures=0,skipped=0,passed=0)
        assert hashlib.sha256((HERE/tag/'pytest.log').read_bytes()).hexdigest() == result['log_sha256']
        assert hashlib.sha256((HERE/tag/'mapping-not-bound.xml').read_bytes()).hexdigest() == result['junit_sha256']
    data = json.loads((HERE/'ui-supplement-r3/browser-observations.json').read_text(encoding='utf-8'))
    assert data['status'] == 'OBSERVATIONS_CAPTURED_NOT_ACCEPTANCE'
    assert len(data['views']) == 4 and sum(len(v['citation_clicks']) for v in data['views']) == 18
    assert data['frozen_64_case_visual_verdict'] == 'VISUAL_NOT_VERIFIED'
    assert not data['exceptions'] and all(not v['external_requests'] for v in data['views'])
    for view in data['views']:
        image = HERE/'ui-supplement-r3'/view['screenshot']['file']
        assert hashlib.sha256(image.read_bytes()).hexdigest() == view['screenshot']['sha256']
    files = [p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts
             and p.suffix not in ('.zip',) and p.name != 'RAW_MANIFEST.json']
    records = {p.relative_to(HERE).as_posix():dict(bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(files)}
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in records:
            archive.write(HERE/name,name)
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert all(hashlib.sha256(archive.read(n)).hexdigest() == v['sha256'] for n,v in records.items())
    manifest = dict(kind='QA_MAPPING_ERRORS_AND_SEPARATE_UI_OBSERVATIONS_NOT_FEATURE_PASS',
        candidate_sha='6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2',files=records,
        archive_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    (HERE/'RAW_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Raw evidence sealed:',len(records),'files;',target.stat().st_size,'bytes')


if __name__ == '__main__':
    main()

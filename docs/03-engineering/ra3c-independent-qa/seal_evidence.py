"""Lossless Phase-A log/JUnit archive so Git line endings cannot alter raw proof."""
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent


def main():
    phase = HERE/'phase-a'
    target = phase/'raw-evidence.zip'
    assert not target.exists(), 'Preserve existing archives'
    records = {}
    for tag in ('py311','py313'):
        result = json.loads((phase/tag/'results.json').read_text(encoding='utf-8'))
        assert result['expected_phase_a_outcomes'] and len(result['jobs']) == 7
        for job in result['jobs']:
            log = phase/tag/(job['name']+'.log')
            assert hashlib.sha256(log.read_bytes()).hexdigest() == job['log_sha256']
            if 'junit_sha256' in job:
                xml = phase/tag/(job['name']+'.xml')
                assert hashlib.sha256(xml.read_bytes()).hexdigest() == job['junit_sha256']
        for file in sorted((phase/tag).iterdir()):
            assert file.is_file()
            records[str(file.relative_to(phase)).replace('\\','/')] = dict(
                bytes=file.stat().st_size,sha256=hashlib.sha256(file.read_bytes()).hexdigest())
    for file in sorted((phase/'ci-source-freeze').iterdir()):
        records[str(file.relative_to(phase)).replace('\\','/')] = dict(
            bytes=file.stat().st_size,sha256=hashlib.sha256(file.read_bytes()).hexdigest())
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in records:
            archive.write(phase/path,path)
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        for path,info in records.items():
            assert hashlib.sha256(archive.read(path)).hexdigest() == info['sha256']
    manifest = dict(kind='ACTUAL_RAW_LOCAL_EVIDENCE_NOT_FEATURE_PASS',
        archive=target.name,archive_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),files=records)
    (phase/'RAW_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Lossless evidence sealed:',len(records),'files;',target.stat().st_size,'bytes')


if __name__ == '__main__':
    main()

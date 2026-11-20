"""Disposable PG and network-none regression; never operate a running service.

Stage Git-visible source on container tmpfs so Windows bind-mount latency does
not consume the original Guard's unchanged five-second validation deadline.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'vrae.automatic-diagnosis-test'


def run(*args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=True, **kwargs).stdout


def main():
    identity = 'vrae-auto-' + uuid.uuid4().hex[:12]
    output = ROOT / 'infra/authorized_targets/.private' / identity
    output.mkdir(parents=True)
    archive = output / 'source.tar'
    paths = run('git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z').decode().split('\0')
    included = []
    with tarfile.open(archive, 'w') as tar:
        for path in sorted(set(paths)):
            if not path or path.startswith(('docs/', '.git/')) or not (ROOT / path).is_file():
                continue
            tar.add(ROOT / path, arcname=path, recursive=False)
            included.append(path)
    results = {'source_files': len(included), 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'real_website_access': False, 'real_model_calls': 0, 'shared_model_ledger_access': False,
        'label': {LABEL: identity}, 'checks': []}
    pg = identity + '-pg'
    created = False
    try:
        run('docker', 'run', '-d', '--network', 'none', '--name', pg, '--label', LABEL + '=' + identity,
            '-e', 'POSTGRES_PASSWORD=synthetic-automatic-pg-only', '-e', 'POSTGRES_DB=vrae_ra4a_p1',
            'postgres:16-alpine')
        created = True
        for _ in range(30):
            if subprocess.run(['docker', 'exec', pg, 'pg_isready', '-U', 'postgres'],
                              capture_output=True).returncode == 0:
                break
            time.sleep(1)
        suites = [
            ('pg', ['--network', 'container:' + pg, '-e', 'VRAE_AUTOMATIC_PG_TEST=1'],
             'python -B -m pytest -q -p no:cacheprovider integration/authorized_targets/checks/test_automatic_pg.py'),
            ('regression', ['--network', 'none'],
             'python -B -m pytest -q -p no:cacheprovider infra/windows_service/checks '
             'infra/linux_service/checks/test_qwen_runtime.py integration/authorized_targets/checks/test_source_authority.py '
             'tests/intelligence/qwen_provider_cases.py tests/intelligence/qwen_committed_cases.py '
             'tests/intelligence/qwen_postcommit_cases.py'),
            ('types', ['--network', 'none'],
             'python -m mypy vrae/intelligence/s3/offline.py vrae/intelligence/qwen/session.py'),
        ]
        for name, network, command in suites:
            print('RUN ' + name, flush=True)
            process = subprocess.run(['docker', 'run', '--rm', *network,
                '--label', LABEL + '=' + identity, '--tmpfs', '/work', '--tmpfs', '/tmp', '--tmpfs', '/run',
                '-v', str(archive) + ':/source.tar:ro', '--entrypoint', 'sh', 'vrae-g1:313', '-c',
                'tar -xf /source.tar -C /work && cd /work && ' + command],
                cwd=ROOT, capture_output=True)
            (output / (name + '.log')).write_bytes(process.stdout + process.stderr)
            results['checks'].append({'name': name, 'exit_code': process.returncode})
            print(name + ': ' + str(process.returncode), flush=True)
            if process.returncode:
                print(process.stdout.decode(errors='replace')[-6000:], flush=True)
                raise RuntimeError('AUTOMATIC_DIAGNOSIS_CHECK_FAILED')
    finally:
        if created:
            state = json.loads(run('docker', 'inspect', pg))[0]
            if state['Config']['Labels'].get(LABEL) != identity:
                raise RuntimeError('OWNED_RESOURCE_REQUIRED')
            run('docker', 'rm', '-fv', pg)
            results['owned_pg_removed'] = True
        (output / 'summary.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
        print(str(output / 'summary.json'), flush=True)


if __name__ == '__main__':
    main()

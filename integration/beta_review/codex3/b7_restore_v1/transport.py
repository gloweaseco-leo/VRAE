"""Real pg_dump/pg_restore and isolated native Worker transport; no shell strings."""
import json
from pathlib import Path
import time
import subprocess

from integration.ra4e.lab import DB, ROOT, digest, docker, encode, invoke
from .environment import LABEL
from .output import prepare_output, decode_failure


class Transport:
    def __init__(self, private, proof):
        self.private, self.proof, self.records = private, proof, []
        self.source = private / 'worker-source'
        self.source.mkdir()
        prefixes = ('industry-packs/', 'contracts/', 'vrae/', 'worker/ra4b/', 'apps/api/', 'integration/ra4a/',
                    'integration/ra4b/', 'integration/b3_p0/', 'integration/ra4e/',
                    'integration/beta_review/codex3/b7_restore_v1/', 'tests/reviewing/',
                    'tests/identity/', 'infra/ra4a/', 'db/migrations/')
        names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
        inventory = {}
        for name in names:
            if not name.startswith(prefixes) or any(part.startswith('.') for part in Path(name).parts):
                continue
            origin = ROOT / name
            if origin.suffix not in ('.py', '.sql', '.json', '.txt'):
                continue
            destination = self.source / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            raw = origin.read_bytes()
            destination.write_bytes(raw)
            inventory[name] = digest(raw)
        assert 'integration/beta_review/codex3/b7_restore_v1/worker_probe.py' in inventory
        (proof / 'worker-source.json').write_bytes(encode(inventory))

    def preflight(self, minor):
        name = 'vrae-b7rv1-preflight-' + self.private.name
        assert invoke('container', 'inspect', name).returncode != 0
        self.command('worker-source-preflight', ['run', '--rm', '--name', name,
            '--label', LABEL + '=' + self.private.name, '--network', 'none',
            '--cap-drop=ALL', '--read-only', '--user', '10002:10002',
            '--mount', 'type=bind,src=' + str(self.source) + ',dst=/work,readonly',
            '-w', '/work', '--env', 'PYTHONDONTWRITEBYTECODE=1',
            'vrae-ra4b-p1:' + minor, 'python', '-B', '-c',
            'from integration.ra4a.support import references; assert len(references())==2; '
            'import integration.beta_review.codex3.b7_restore_v1.worker_probe; '
            'print("ACCEPTED_SOURCE_BUNDLE_PASS")'])
        assert invoke('container', 'inspect', name).returncode != 0

    def command(self, label, args, *, data=None, expected=0, timeout=90):
        started = time.monotonic()
        p = invoke(*args, data=data, timeout=timeout)
        (self.private / (label + '.stdout')).write_bytes(p.stdout)
        (self.private / (label + '.stderr')).write_bytes(p.stderr)
        self.records.append({'command': label, 'native_returncode': p.returncode,
                             'stdout_sha256': digest(p.stdout), 'stderr_sha256': digest(p.stderr),
                             'elapsed_seconds': time.monotonic() - started})
        self.save()
        if expected == 'nonzero':
            assert p.returncode != 0, label + '_UNEXPECTED_SUCCESS'
        elif expected is not None:
            assert p.returncode == expected, label + '_NATIVE_FAILURE'
        return p

    def save(self):
        (self.proof / 'native-processes.json').write_bytes(encode(self.records))

    def backup(self, env, label):
        p = self.command(label, ['exec', env.name, 'pg_dump', '-U', 'postgres', '-d', DB,
                                 '--format=custom', '--create'])
        assert p.stdout[:5] == b'PGDMP'
        archive = self.private / (label + '.dump')
        archive.write_bytes(p.stdout)
        return archive

    def restore(self, env, archive, label, *, schemas=None, expected=0):
        raw = archive.read_bytes()
        remote = '/tmp/b7rv1.dump'
        docker('cp', str(archive), env.name + ':' + remote)
        try:
            self.command(label + '-list', ['exec', env.name, 'pg_restore', '--list', remote],
                         expected=0 if raw[:5] == b'PGDMP' else 'nonzero')
            args = ['exec', env.name, 'pg_restore', '-U', 'postgres', '--dbname=postgres',
                    '--create', '--exit-on-error']
            for schema in schemas or []:
                args += ['--schema', schema]
            return self.command(label, [*args, remote], expected=expected)
        finally:
            docker('exec', env.name, 'rm', '-f', remote)

    def worker(self, env, phase, minor, label):
        image = 'vrae-ra4b-p1:' + minor
        image_id = docker('image', 'inspect', '--format', '{{.Id}}', image).decode().strip()
        logs = self.private / label
        logs.mkdir()
        output_group = prepare_output(logs)
        name = env.name + '-worker-' + label
        assert invoke('container', 'inspect', name).returncode != 0
        args = ['run', '--rm', '-i', '--name', name, '--label', LABEL + '=' + env.name,
                '--network', 'container:' + env.name, '--cap-drop=ALL',
                '--cap-add=SETUID', '--cap-add=SETGID', '--cap-add=CHOWN',
                '--security-opt=no-new-privileges', '--memory', '256m', '--cpus', '1',
                '--pids-limit', '64', '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=32m',
                '--mount', 'type=bind,src=' + str(self.source) + ',dst=/work,readonly',
                *output_group, '--mount', 'type=bind,src=' + str(logs) + ',dst=/evidence',
                '-w', '/work', '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'PYTHONPATH=/work',
                image_id, 'python', '-m', 'integration.beta_review.codex3.b7_restore_v1.worker_probe']
        try:
            p = self.command(label, args, data=encode({'state': json.loads(env.state.read_bytes()),
                                                      'phase': phase, 'minor': minor}), expected=None, timeout=45)
            if p.returncode:
                record = decode_failure(p.stdout)
                record['supervisor_native_exit'] = p.returncode
                (self.proof / (label + '-failure.json')).write_bytes(encode(record))
                raise AssertionError(label + '_NATIVE_FAILURE')
            result = json.loads(p.stdout)
            result['dependency_image_id'] = image_id
            (self.proof / (label + '.json')).write_bytes(encode(result))
            return result
        finally:
            inspected = invoke('container', 'inspect', '--format', '{{json .Config.Labels}}', name)
            if not inspected.returncode:
                assert json.loads(inspected.stdout).get(LABEL) == env.name
                docker('rm', '-f', name)
            assert invoke('container', 'inspect', name).returncode != 0

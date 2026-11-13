"""Owner-authorized reproduction; retains --internal, always cleans owned lab.

No migration, UI, role/grant modification or global Docker mutation.
"""
import hashlib
import json
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
import uuid

from integration.ra4c3.lab import ROOT, bounded


def diagnose(output, explicit_port=False):
    output = bounded(output)
    output.mkdir(parents=True, exist_ok=False)
    ident = 'vrae-ra4c3-' + uuid.uuid4().hex[:12]
    resources = [('container', ident), ('network', ident + '-local'),
                 ('volume', ident + '-data')]
    password = secrets.token_urlsafe(32)
    wrong = secrets.token_urlsafe(32)
    events = []

    def run(event, *args, data=None, check=True):
        result = subprocess.run(['docker', *args], input=data, capture_output=True,
                                timeout=30)
        raw = result.stdout + result.stderr
        for secret in (password, wrong):
            raw = raw.replace(secret.encode(), b'[REDACTED]')
        name = f'{len(events):03d}-{event}.log'
        (output / name).write_bytes(raw)
        events.append({'event': event, 'command': ['docker', *args],
                       'returncode': result.returncode, 'file': name,
                       'sha256': hashlib.sha256(raw).hexdigest()})
        if check and result.returncode:
            raise RuntimeError('DIAGNOSTIC_COMMAND_FAILED_' + event)
        return result

    def sql(event, credential):
        # Secret travels only over stdin; never process arguments/logged Env.
        return run(event, 'exec', '-i', ident, 'sh', '-c',
                   'IFS= read -r PGPASSWORD; export PGPASSWORD; exec "$@"',
                   'ra4c3-readiness', 'psql', '-h', '127.0.0.1', '-U', 'postgres',
                   '-d', 'vrae_ra4a_p1', '-v', 'ON_ERROR_STOP=1', '-At', '-c',
                   "SELECT current_database(),current_setting('server_version_num'),current_user",
                   data=(credential + '\n').encode(), check=False)

    failure = None
    cleanup = []
    requested_port = ''
    if explicit_port:
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            requested_port = str(reservation.getsockname()[1])
    try:
        run('engine', 'version', '--format', '{{json .}}')
        run('engine-os', 'info', '--format',
            '{{json .OSType}} {{json .OperatingSystem}} {{json .KernelVersion}} {{json .ServerVersion}}')
        run('network-create', 'network', 'create', '--internal', '--label',
            'vrae.ra4c3=TEST_ONLY', ident + '-local')
        run('network-inspect', 'network', 'inspect', ident + '-local')
        run('volume-create', 'volume', 'create', '--label', 'vrae.ra4c3=TEST_ONLY', ident + '-data')
        image = (ROOT / 'infra/ra4a/image.txt').read_text().strip()
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as cfg:
            cfg.write('POSTGRES_PASSWORD=' + password + '\nPOSTGRES_DB=vrae_ra4a_p1\n'
                      'POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256\n')
            config = Path(cfg.name)
        try:
            # Same original publication and isolation; no security-model change.
            run('container-run', 'run', '-d', '--name', ident, '--network', ident + '-local',
                '--label', 'vrae.ra4c3=TEST_ONLY', '--env-file', str(config),
                '-p', '127.0.0.1:' + requested_port + ':5432', '--mount',
                'type=volume,src=' + ident + '-data,dst=/var/lib/postgresql/data',
                '--memory', '512m', '--cpus', '1', '--pids-limit', '128', image)
        finally:
            config.unlink()
        run('host-port-bindings', 'inspect', '--format', '{{json .HostConfig.PortBindings}}', ident)
        run('effective-published-ports', 'inspect', '--format', '{{json .NetworkSettings.Ports}}', ident)
        run('docker-port', 'port', ident, '5432/tcp', check=False)
        deadline = time.monotonic() + 60
        while True:
            result = sql('authenticated-target-sql', password)
            if result.returncode == 0:
                assert b'vrae_ra4a_p1|16' in result.stdout and b'|postgres' in result.stdout
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('DIAGNOSTIC_TARGET_READINESS_TIMEOUT')
            time.sleep(.5)
        rejected = sql('wrong-password-negative', wrong)
        assert rejected.returncode != 0 and b'password authentication failed' in rejected.stderr
        run('final-published-ports', 'inspect', '--format', '{{json .NetworkSettings.Ports}}', ident)
        port = run('final-docker-port', 'port', ident, '5432/tcp', check=False)
        if port.returncode:
            failure = 'INTERNAL_PG_AUTHENTICATED_BUT_NO_HOST_PUBLICATION'
        else:
            binding = port.stdout.decode().strip()
            assert binding.startswith('127.0.0.1:') and '\n' not in binding
            # TCP transport proof only, not an authenticated host SQL PASS.
            with socket.create_connection(('127.0.0.1', int(binding.rsplit(':', 1)[1])), timeout=3):
                pass
    except BaseException as exc:
        failure = type(exc).__name__ + ':' + str(exc)
        raise
    finally:
        for kind, name in resources:
            template = '{{json .Config.Labels}}' if kind == 'container' else '{{json .Labels}}'
            present = run('cleanup-inspect-' + kind, kind, 'inspect', '--format', template, name, check=False)
            if present.returncode == 0:
                assert json.loads(present.stdout).get('vrae.ra4c3') == 'TEST_ONLY'
                run('cleanup-remove-' + kind, *(['rm', '-f', name] if kind == 'container' else [kind, 'rm', name]))
            else:
                assert b'no such' in present.stderr.lower() or b'not found' in present.stderr.lower()
            absent = run('cleanup-absence-' + kind, kind, 'inspect', name, check=False)
            assert absent.returncode and (b'no such' in absent.stderr.lower() or b'not found' in absent.stderr.lower())
            cleanup.append({'kind': kind, 'name': name, 'absent_after': True})
        receipt = {'authority': 'PR74 issuecomment-6842716924 bounded diagnosis GO',
                   'internal_network_unchanged': True, 'events': events,
                   'requested_host_ip': '127.0.0.1', 'requested_host_port': requested_port,
                   'outcome': failure or 'HOST_TCP_ONLY_NOT_ACCEPTANCE', 'cleanup': cleanup,
                   'migrations_executed': False, 'host_authenticated_sql_verified': False,
                   'restricted_principal_verified': False, 'http_started': False}
        (output / 'receipt.json').write_bytes(json.dumps(receipt, indent=2).encode() + b'\n')
        print(json.dumps({'outcome': receipt['outcome'], 'owned_resources_absent': len(cleanup) == 3}))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--explicit-port', action='store_true')
    args = parser.parse_args()
    diagnose(args.output, args.explicit_port)

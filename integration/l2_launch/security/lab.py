"""Owned disposable Docker lab. Never enumerate/stop another task's resources."""
import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OWN = Path(__file__).resolve().parent


def command(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, timeout=kwargs.pop('timeout', 180), **kwargs)


def main():
    if sys.flags.optimize:
        raise RuntimeError('OPTIMIZED_VERIFICATION_NOT_ALLOWED')
    if sys.argv[1:] == ['--child']:
        # Remain unprivileged through pytest AND export; tmpfs disappears at exit.
        done = subprocess.run([sys.executable, '-B', '-m', 'pytest', '-q', '-s', '-p', 'no:cacheprovider',
            'integration/l2_launch/security/isolated_cases.py', 'tests/collection/test_isolated.py',
            '--junitxml=/tmp/r1a-isolated.xml'], check=False)
        path = Path('/tmp/r1a-isolated.xml')
        if path.is_file():
            print('R1A_JUNIT_BASE64='+base64.b64encode(path.read_bytes()).decode(), flush=True)
        raise SystemExit(done.returncode)
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--base', required=True, help='Trusted dependency image; no target URLs')
    args = parser.parse_args()
    if not re.fullmatch('[a-z0-9-]{3,40}', args.label) or not re.fullmatch('[A-Za-z0-9./:@_-]+', args.base):
        raise ValueError('OWNED_LABEL_AND_BASE_REQUIRED')
    out = OWN / '.runtime' / args.label
    out.mkdir(parents=True, exist_ok=False)
    token = uuid.uuid4().hex
    name, image = 'vrae-r1a-c1-'+token, 'vrae-r1a-c1:'+token
    owner_key = 'vrae.r1a.c1.owner'
    context = out / 'build'
    context.mkdir()
    shutil.copyfile(OWN/'Dockerfile', context/'Dockerfile')
    shutil.copyfile(ROOT/'requirements-ra1a.lock', context/'requirements-ra1a.lock')
    # shell-normalize the setup in a private minimal mount; never edit source.
    script = out / 'setup.sh'
    script.write_bytes((OWN/'setup.sh').read_bytes().replace(b'\r\n', b'\n'))
    result = {'status': 'R1A_OFFLINE_SECURITY_CANDIDATE_LIVE_GATE_PENDING',
              'pass': False, 'owner': token, 'live_enabled': False, 'target_network': 'NONE',
              'api_probe': 'SIMULATED_API_INSIDE_DISPOSABLE_NAMESPACE', 'customer_connections': 0}
    created = False
    try:
        build = subprocess.run(['docker', 'build', '--pull=false', '--build-arg', 'BASE='+args.base,
            '--label', owner_key+'='+token, '-t', image, str(context)], check=False, capture_output=True, timeout=900)
        (out/'build.log').write_bytes(build.stdout+build.stderr)
        build.check_returncode()
        created_id = command(['docker', 'create', '--name', name, '--label', owner_key+'='+token,
            '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--cap-add', 'NET_ADMIN',
            '--cap-add', 'SETUID', '--cap-add', 'SETGID', '--cap-add', 'SETPCAP', '--cap-add', 'NET_BIND_SERVICE',
            '--security-opt', 'no-new-privileges', '--tmpfs', '/tmp:rw,nosuid,nodev,size=128m',
            '--tmpfs', '/run:rw,nosuid,nodev,size=8m', '--memory', '512m', '--cpus', '1', '--pids-limit', '128',
            '--mount', 'type=bind,source='+str(ROOT)+',target=/candidate,readonly',
            '--mount', 'type=bind,source='+str(script)+',target=/r1a-setup.sh,readonly',
            '--entrypoint', '/bin/sh', image, '/r1a-setup.sh']).stdout.decode().strip()
        created = True
        info = json.loads(command(['docker', 'inspect', name]).stdout)[0]
        assert info['Id'] == created_id and info['Config']['Labels'][owner_key] == token
        assert info['HostConfig']['NetworkMode'] == 'none' and info['HostConfig']['ReadonlyRootfs']
        assert all(not mount['RW'] for mount in info['Mounts'] if mount['Type'] == 'bind')
        result['inspected_network_mode'] = info['HostConfig']['NetworkMode']
        run = subprocess.run(['docker', 'start', '-a', name], check=False, capture_output=True, timeout=600)
        (out/'kernel-and-tests.log').write_bytes(run.stdout+run.stderr)
        info = json.loads(command(['docker', 'inspect', name]).stdout)[0]
        result['exit_code'] = info['State']['ExitCode']
        result['kernel_api_metadata_denials'] = run.stdout.count(b'R1A_KERNEL_DENIAL')
        markers = [line.removeprefix(b'R1A_JUNIT_BASE64=') for line in run.stdout.splitlines()
                   if line.startswith(b'R1A_JUNIT_BASE64=')]
        assert len(markers) == 1 and len(markers[0]) < 2_000_000
        (out/'isolated.xml').write_bytes(base64.b64decode(markers[0], validate=True))
        suites = list(ET.parse(out/'isolated.xml').iter('testsuite'))
        result['junit'] = [suite.attrib for suite in suites]
        assert run.returncode == 0 and info['State']['ExitCode'] == 0
        assert result['kernel_api_metadata_denials'] == 4 and suites
        assert all(int(s.attrib.get('failures', 0)) == 0 and int(s.attrib.get('errors', 0)) == 0
                   and int(s.attrib.get('skipped', 0)) == 0 for s in suites)
        result['pass'] = True
    finally:
        if created:
            info = json.loads(command(['docker', 'inspect', name]).stdout)[0]
            if info['Config']['Labels'].get(owner_key) != token:
                raise ValueError('OWNERSHIP_CHANGED_NO_REMOVAL')
            command(['docker', 'rm', '-f', name])
            result['owned_container_removed'] = subprocess.run(['docker', 'inspect', name], check=False, capture_output=True).returncode != 0
        # Only this unique labelled image. Existing dependency images remain.
        image_info = subprocess.run(['docker', 'image', 'inspect', image], check=False, capture_output=True)
        if image_info.returncode == 0:
            metadata = json.loads(image_info.stdout)[0]
            if metadata['Config']['Labels'].get(owner_key) != token:
                raise ValueError('IMAGE_OWNERSHIP_CHANGED_NO_REMOVAL')
            command(['docker', 'image', 'rm', image])
            result['owned_image_removed'] = True
        result['unknown_or_owner_uat_resources'] = 'UNTOUCHED_NO_PRUNE'
        result['source_sha'] = command(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).stdout.decode().strip()
        result['source_tree_dirty'] = bool(command(['git', '-C', str(ROOT), 'status', '--porcelain']).stdout.strip())
        result['candidate_source_hashes'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in OWN.iterdir() if p.is_file() and (p.suffix in ('.py', '.sh') or p.name == 'Dockerfile')}
        result['log_sha256'] = hashlib.sha256((out/'kernel-and-tests.log').read_bytes()).hexdigest() if (out/'kernel-and-tests.log').exists() else None
        (out/'receipt.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()

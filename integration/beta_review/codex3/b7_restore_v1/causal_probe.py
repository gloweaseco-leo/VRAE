"""Owner6893257876: finite Linux DAC causal pair on the frozen first-RED Worker.

Actual private stderr must match the official first hosted hash, not just a
similar error label. The same untouched PG state then runs with output access.
"""
import json
from pathlib import Path
import sys
import subprocess
import time

from integration.ra4e.lab import ROOT, digest, docker, encode, invoke
from .business import seed
from .environment import Environment, LABEL
from .snapshot import capture, compare, evidence
from .transport import Transport
from vrae.application.ra4b import store

EXPECTED = {
    '311': 'bf357c05cf11ca8da54866388252bc05e251c1def225fca90f89f95586ab9c76',
    '313': '053eda5874346b8a4d2cc7e3c6fc2b3c8a18f24d8191e227c9473bed29ffd48c',
}
DOCS = ROOT / 'docs/03-engineering/beta-closure/codex3/b7_restore_v1'


class FocusComplete(Exception):
    pass


class Pair:
    def __init__(self, transport, private, proof):
        self.transport, self.private, self.proof = transport, private, proof
        self.observed = None

    def worker(self, env, phase, minor, label):
        assert phase == 'complete' and label == 'source-old-done' and self.observed is None
        image = docker('image', 'inspect', '--format', '{{.Id}}', 'vrae-ra4b-p1:' + minor).decode().strip()
        volume = env.name + '-causal-output'
        env.resources.append(('volume', volume))
        (env.proof / 'ownership.json').write_bytes(encode({'name': env.name, 'label': LABEL,
            'resources': env.resources, 'additional_volume_purpose': 'Linux output DAC only'}))
        assert not env.owned('volume', volume)
        docker('volume', 'create', '--label', LABEL + '=' + env.name, volume)
        source_mount = 'type=bind,src=' + str(self.transport.source) + ',dst=/work,readonly'
        output_mount = 'type=volume,src=' + volume + ',dst=/evidence'

        def run(name, argv, *, data=None, expected=0):
            full = env.name + '-' + name
            assert invoke('container', 'inspect', full).returncode != 0
            try:
                return self.transport.command(name, ['run', '--rm', '-i', '--name', full,
                    '--label', LABEL + '=' + env.name, *argv], data=data, expected=expected, timeout=45)
            finally:
                check = invoke('container', 'inspect', '--format', '{{json .Config.Labels}}', full)
                if check.returncode == 0:
                    assert json.loads(check.stdout).get(LABEL) == env.name
                    docker('rm', '-f', full)
                assert invoke('container', 'inspect', full).returncode != 0

        # Real Linux volume, simulating a non-root hosted runner's fresh 0755 dir.
        setup = "import os,json; p='/evidence'; os.chmod(p,0o755); os.chown(p,1001,1001); s=os.stat(p); print(json.dumps({'uid':s.st_uid,'gid':s.st_gid,'mode':oct(s.st_mode&0o777)}))"
        initialized = run('dac-initialize', ['--network', 'none', '--cap-drop=ALL', '--cap-add=CHOWN',
            '--mount', output_mount, image, 'python', '-c', setup])
        initial = json.loads(initialized.stdout)
        assert initial == {'uid': 1001, 'gid': 1001, 'mode': '0o755'}
        before = capture(env)
        (self.private / 'before-worker.json').write_bytes(encode(before))
        with env.connect() as c:
            jobs = c.execute('SELECT request_id FROM ra4a.requests').fetchall()
            assert len(jobs) == 1
            request_id = jobs[0][0]
        app = env.config()
        with store.connect(app) as c:
            status_before = store.status(c, app, request_id)
        base = ['--network', 'container:' + env.name, '--cap-drop=ALL',
            '--cap-add=SETUID', '--cap-add=SETGID', '--cap-add=CHOWN',
            '--security-opt=no-new-privileges', '--memory', '256m', '--cpus', '1',
            '--pids-limit', '64', '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=32m',
            '--mount', source_mount, '--mount', output_mount,
            '-w', '/work', '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'PYTHONPATH=/work']
        inspect = "import os,json,pathlib; s=os.stat('/evidence'); p=pathlib.Path('/proc/self/status').read_text(); print(json.dumps({'uid':os.getuid(),'gid':os.getgid(),'groups':os.getgroups(),'output_uid':s.st_uid,'output_gid':s.st_gid,'output_mode':oct(s.st_mode&0o777),'cap_eff':next(x.split()[1] for x in p.splitlines() if x.startswith('CapEff:'))}))"
        process_environment = json.loads(run('dac-process-environment', [*base, image, 'python', '-c', inspect]).stdout)
        assert process_environment['uid'] == 0 and 1001 not in process_environment['groups']
        assert int(process_environment['cap_eff'], 16) & 2 == 0  # No CAP_DAC_OVERRIDE.
        payload = encode({'state': json.loads(env.state.read_bytes()), 'phase': phase, 'minor': minor})
        command = [image, 'python', '-m', 'integration.beta_review.codex3.b7_restore_v1.worker_probe']
        failed = run('frozen-source-old-done-red', [*base, *command], data=payload, expected=1)
        assert failed.stdout == b''
        observed_hash = digest(failed.stderr)
        # This equality confirms the original private hosted diagnostic bytes.
        assert observed_hash == EXPECTED[minor], 'ORIGINAL_STDERR_HASH_NOT_REPRODUCED_STOP'
        assert failed.stderr.rstrip().endswith(b"PermissionError: [Errno 13] Permission denied: '/evidence/worker-0.log'")
        after_red = capture(env)
        compare(before, after_red)
        with store.connect(app) as c:
            assert store.status(c, app, request_id) == status_before
        red = {'native_exit': failed.returncode, 'stdout_bytes': len(failed.stdout),
            'stderr_sha256': observed_hash, 'official_first_hosted_stderr_sha256': EXPECTED[minor],
            'byte_identical_to_original_hosted_stderr': True, 'exception_class': 'PermissionError',
            'errno': 13, 'operation': 'OPEN_WORKER_LOG', 'path': '/evidence/worker-0.log',
            'original_worker_spawned': False, 'database_unchanged': True,
            'actual_environment': process_environment, 'database_before': evidence(before)}
        (self.proof / 'confirmed-native-red.json').write_bytes(encode(red))
        # One causal configuration change: the accepted output-directory group
        # access mechanism, restricted to this new, owned disposable volume.
        repair = "import os,json; assert os.getuid()==1001; s=os.stat('/evidence'); assert (s.st_uid,s.st_gid)==(1001,1001); os.chmod('/evidence',0o770); s=os.stat('/evidence'); print(json.dumps({'uid':s.st_uid,'gid':s.st_gid,'mode':oct(s.st_mode&0o777)}))"
        repaired = json.loads(run('dac-output-only-repair', ['--network', 'none', '--cap-drop=ALL',
            '--user', '1001:1001', '--mount', output_mount, image, 'python', '-c', repair]).stdout)
        assert repaired == {'uid': 1001, 'gid': 1001, 'mode': '0o770'}
        fixed_environment = json.loads(run('dac-fixed-environment', [*base, '--group-add', '1001', image, 'python', '-c', inspect]).stdout)
        assert 1001 in fixed_environment['groups'] and int(fixed_environment['cap_eff'], 16) & 2 == 0
        positive = run('same-state-original-worker-done', [*base, '--group-add', '1001', *command], data=payload)
        actual = json.loads(positive.stdout)
        assert actual['done'] and actual['uid'] == 10002 and actual['native_returncode'] == 0
        assert actual['child_admin_credentials'] is False
        after_done = capture(env)
        assert after_done['catalog_root'] == before['catalog_root']
        for name in before['tables']:
            if name.startswith(('b3_p0.', 'ra4a_bytes.', 'ra4a_review_test.')):
                assert before['tables'][name] == after_done['tables'][name]
        with store.connect(app) as c:
            status_after = store.status(c, app, request_id)
            assert status_after['status'] == 'TEST_ONLY_CONSUMED' and status_after['share_grant'] is None
        self.observed = {'root_cause': 'NEW_FIXTURE_OUTPUT_DIRECTORY_DAC',
            'original_red_confirmed': red, 'output_only_change': repaired,
            'corrected_environment': fixed_environment, 'actual_original_worker': actual,
            'same_database_state_used': True, 'catalog_unchanged': True,
            'worker_semantics_changed': False, 'new_uuid_ordering_experiments': 0}
        (self.proof / 'causal-pair.json').write_bytes(encode(self.observed))
        raise FocusComplete


def main():
    minor = str(sys.version_info.major) + str(sys.version_info.minor)
    assert minor in EXPECTED
    name = 'causal-' + minor + '-v1'
    private = Path(__file__).resolve().parent / '.private' / name
    proof = DOCS / name
    private.mkdir(parents=True, exist_ok=False)
    proof.mkdir(parents=True, exist_ok=False)
    transport = Transport(private, proof)
    env = Environment('source', private / 'source', proof / 'source')
    started = time.monotonic()
    pair = Pair(transport, private, proof)
    try:
        transport.preflight(minor)
        env.start()
        env.initialize()
        try:
            seed(env, pair, minor)
        except FocusComplete:
            assert pair.observed is not None
        else:
            raise AssertionError('FOCUS_DID_NOT_STOP_AT_FIRST_WORKER')
    finally:
        credentials = [env.admin_password, *env.runtime_passwords.values()]
        (private / 'scan-credentials.json').write_bytes(encode(credentials))
        env.stop()
    from integration.ra4e.run import publication
    (proof / 'receipt.json').write_bytes(encode({'native_host_python': sys.version,
        'probe_head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        'original_pr_head': 'fa35b8f4e1b5440fbd04a5fd5b349d905558d961',
        'original_hosted_merge': '9ed725fef7d9e518dd6364241bd5ebf2aef124f5',
        'worker_source_inventory_sha256': digest((proof/'worker-source.json').read_bytes()),
        'elapsed_seconds': time.monotonic() - started, 'causal_pair_pass': pair.observed is not None,
        'frozen_worker_probe_sha256': digest((Path(__file__).resolve().parent / 'worker_probe.py').read_bytes().replace(b'\r\n', b'\n')),
        'probe_sha256': digest(Path(__file__).read_bytes().replace(b'\r\n', b'\n')),
        'full_B7_EXIT': False, 'old_A1': 'PAUSED/MAX3 0/3 unchanged'}))
    publication(proof, private)
    print(json.dumps({'minor': minor, 'root_cause_confirmed': True, 'causal_pair_pass': True}))


if __name__ == '__main__':
    main()

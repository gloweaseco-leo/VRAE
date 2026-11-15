"""Linux-only supervisor of the unchanged, unprivileged B4 Worker executable."""
import json
import os
from pathlib import Path
import signal
import sys

from integration.ra4a import support as old
from integration.ra4b import runtime_check as accepted


def main():
    assert os.geteuid() == 0
    routes = Path('/proc/net/route').read_text().splitlines()[1:]
    assert not any(row.split()[1] == '00000000' for row in routes if row.split())
    supplied = json.load(sys.stdin)
    assert str(sys.version_info.major) + str(sys.version_info.minor) == supplied['minor']
    state = supplied['state']
    state['port'] = 5432
    private = Path('/tmp/b7rv1')
    private.mkdir(mode=0o700)
    old.STATE = private / 'state.json'
    old.STATE.write_text(json.dumps(state))
    old.STATE.chmod(0o600)
    accepted.SECRET_VALUES.extend([state['admin_password'], *state['runtime_passwords'].values()])
    accepted.OUT = Path('/evidence')
    path, cfg = accepted.provision('WORKER', 10002)
    child = None
    try:
        args = ['--once', '--lease-seconds', '1']
        if supplied['phase'] == 'kill':
            args += ['--hold-seconds', '30']
        child, log = accepted.spawn('WORKER', path, *args)
        accepted.wait_for(lambda: b'"LEASED"' in log.read_bytes() or child.poll() is not None)
        assert b'"LEASED"' in log.read_bytes(), 'WORKER_NEVER_LEASED'
        if child.poll() is None:
            status = Path(f'/proc/{child.pid}/status').read_text()
            assert 'CapEff:\t0000000000000000' in status
            assert 'Uid:\t10002\t10002\t10002\t10002' in status
        if supplied['phase'] == 'kill':
            accepted.signal_child(child, signal.SIGKILL)
            assert child.wait(timeout=5) == -signal.SIGKILL
        else:
            assert child.wait(timeout=8) == 0
            assert b'"TEST_ONLY_DONE"' in log.read_bytes(), 'WORKER_EXIT_WITHOUT_DONE'
        result = {'phase': supplied['phase'], 'pid': child.pid, 'uid': child.b4_uid,
                  'native_returncode': child.returncode, 'leased': True,
                  'done': b'"TEST_ONLY_DONE"' in log.read_bytes(), 'no_default_route': True,
                  'python': sys.version, 'original_module': 'worker.ra4b.main', 'child_admin_credentials': False}
        print(json.dumps(result), flush=True)
    finally:
        if child is not None and child.poll() is None:
            accepted.signal_child(child, signal.SIGKILL)
            child.wait(timeout=5)
        old.STATE.unlink(missing_ok=True)
        # UID-owned config is on the container's private tmpfs; --rm destroys
        # it without adding DAC capabilities or changing the frozen ownership.


if __name__ == '__main__':
    main()

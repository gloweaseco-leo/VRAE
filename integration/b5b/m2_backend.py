"""Test supervisor: original UID10001 APP and UID10002 M1 Worker only.

Full DB state stays in this isolated backend supervisor. SSR receives only the
separate API bearer. No migrations, seed or fabricated Reviewer assignments.
"""

from contextlib import closing
import http.client
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time

from integration.ra4a import support
from integration.ra4b import support as bootstrap
from integration.ra4b.runtime_check import signal_child


def main():
    private = Path('/tmp/m2-backend')
    private.mkdir(mode=0o700)
    support.STATE = private / 'state.json'
    support.STATE.write_bytes(Path('/run/m1-state.json').read_bytes())
    support.STATE.chmod(0o600)
    children = []
    serial = 0

    def spawn(kind):
        nonlocal serial
        serial += 1
        uid = 10001 if kind == 'APP' else 10002
        cfg = bootstrap.config(kind)
        if kind == 'APP':
            cfg['bearer'] = secrets.token_urlsafe(40)
        folder = Path('/tmp/m2-' + kind.lower() + '-' + str(serial))
        folder.mkdir(mode=0o700)
        path = folder / 'config.json'
        path.write_text(json.dumps(cfg))
        path.chmod(0o600)
        os.chown(path, uid, uid)
        os.chown(folder, uid, uid)
        log = (private / ('process-' + str(serial) + '.log')).open('wb')
        p = subprocess.Popen([sys.executable, '-B', '-m', 'apps.api.ra4b' if kind == 'APP'
            else 'vrae.application.ra4b_p2.m1.runtime', '--config', str(path)],
            user=uid, group=uid, extra_groups=[], stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            env={'PATH':'/usr/local/bin:/usr/bin:/bin', 'PYTHONPATH':'/work',
                 'PYTHONDONTWRITEBYTECODE':'1', 'VRAE_RA4B_TEST_ONLY':'1', 'PYTHONUNBUFFERED':'1'})
        p.b4_uid = uid
        children.append((p, log))
        return p, cfg, private / ('process-' + str(serial) + '.log')

    try:
        app, cfg, _ = spawn('APP')
        deadline = time.monotonic() + 8
        while True:
            try:
                with closing(http.client.HTTPConnection('127.0.0.1', 8765, timeout=1)) as c:
                    c.connect()
                break
            except OSError:
                assert app.poll() is None and time.monotonic() < deadline
                time.sleep(.05)
        print(json.dumps({'ready':True, 'api_bearer':cfg['bearer']}), flush=True)
        for line in sys.stdin:
            message = json.loads(line)
            if message.get('stop'):
                break
            assert message == {'worker':True}
            worker, _, logpath = spawn('WORKER')
            worker.wait(timeout=90)
            assert worker.returncode == 0
            result = json.loads(logpath.read_bytes().splitlines()[-1])
            print(json.dumps(result), flush=True)
    finally:
        for p, log in children:
            if p.poll() is None:
                signal_child(p, signal.SIGTERM)
            p.wait(timeout=15)
            log.close()


if __name__ == '__main__':
    main()

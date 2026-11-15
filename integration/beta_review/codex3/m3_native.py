"""Own Linux supervisor: original API plus actual independent M1 Worker."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from integration.ra4a import support as old
from integration.ra4b import runtime_check as native


def main():
    assert os.geteuid() == 0 and not Path("/var/run/docker.sock").exists()
    state = json.load(sys.stdin)
    state["port"] = 5432
    private = Path("/tmp/beta-supervisor")
    private.mkdir(mode=0o700)
    old.STATE = private / "state.json"
    old.STATE.write_text(json.dumps(state))
    old.STATE.chmod(0o600)
    native.OUT = Path("/evidence")
    try:
        app_path, _ = native.provision("APP", 10001)
        worker_path, _ = native.provision("WORKER", 10002)
        api, _ = native.spawn("APP", app_path)
        native.wait_for(lambda: native.LOGS[0].exists() and b"READY" in native.LOGS[0].read_bytes())
        stream = (native.OUT / "m1-worker.log").open("ab")
        worker = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-m",
                "integration.beta_review.codex3.m3_worker",
                "--config",
                str(worker_path),
            ],
            cwd="/work",
            stdin=subprocess.PIPE,
            stdout=stream,
            stderr=stream,
            user=10002,
            group=10002,
            extra_groups=[],
            env={
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "PYTHONPATH": "/work",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1",
                "VRAE_RA4B_TEST_ONLY": "1",
            },
        )
        stream.close()
        worker.b4_uid = 10002
        native.CHILDREN.append(worker)
        native.wait_for(lambda: b"M1_WORKER_READY" in (native.OUT / "m1-worker.log").read_bytes())
        (native.OUT / "native-result.json").write_text(
            json.dumps(
                {
                    "native_python": sys.version.split()[0],
                    "mode": "M1_REAL_GENERATION",
                    "app_uid": 10001,
                    "worker_uid": 10002,
                    "worker_entry": "integration.beta_review.codex3.m3_worker",
                    "accepted_processing": "vrae.application.ra4b_p2.m1.runtime",
                    "generated_rows_seeded": 0,
                    "records": [],
                }
            )
        )
        (native.OUT / "ready.json").write_text('{"actual_api_worker_ready":true}')
        handled = set()
        end = time.monotonic() + 1800
        while not (native.OUT / "stop.json").exists() and time.monotonic() < end:
            assert api.poll() is None and worker.poll() is None, "M3_RUNTIME_CHILD_EXIT"
            for wake in sorted(native.OUT.glob("*.wake.json")):
                if wake.name in handled:
                    continue
                assert json.loads(wake.read_bytes()) == {"process_one": True}
                worker.stdin.write(b'{"process_one":true}\n')
                worker.stdin.flush()
                handled.add(wake.name)
            time.sleep(0.2)
    finally:
        for child in reversed(native.CHILDREN):
            native.signal_child(child, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                native.signal_child(child, signal.SIGKILL)
                child.wait(timeout=5)
        old.STATE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

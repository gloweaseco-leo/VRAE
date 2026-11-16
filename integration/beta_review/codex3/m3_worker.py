"""Event scheduler for the accepted canonical M1 CLI; no second Worker engine."""

import argparse
import json
import os
import signal
import subprocess
import sys

from vrae.application.ra4b import store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    assert os.geteuid() == 10002
    store.load_config(args.config, "WORKER")
    child = None

    def stop(_number, _frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    try:
        print(json.dumps({"state": "M1_WORKER_READY", "uid": os.geteuid()}), flush=True)
        for line in sys.stdin:
            assert json.loads(line) == {"process_one": True}
            child = subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "vrae.application.ra4b_p2.m1.runtime",
                    "--config",
                    args.config,
                ],
                stdin=subprocess.DEVNULL,
            )
            print(
                json.dumps(
                    {
                        "state": "M3_CANONICAL_WORKER_STARTED",
                        "uid": os.geteuid(),
                        "pid": child.pid,
                        "module": "vrae.application.ra4b_p2.m1.runtime",
                    }
                ),
                flush=True,
            )
            code = child.wait()
            assert code == 0, "M3_CANONICAL_WORKER_EXIT"
            child = None
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


if __name__ == "__main__":
    main()

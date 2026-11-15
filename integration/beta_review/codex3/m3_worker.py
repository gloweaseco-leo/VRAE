"""UID10002 event-driven adapter using the accepted M1 load/build/commit functions."""

import argparse
import json
import os
import sys

from vrae.application.ra4b import store
from vrae.application.ra4b_p2.m1.runtime import build, commit, load


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    assert os.geteuid() == 10002
    cfg = store.load_config(args.config, "WORKER")
    print(json.dumps({"state": "M1_WORKER_READY", "uid": os.geteuid()}), flush=True)
    for line in sys.stdin:
        assert json.loads(line) == {"process_one": True}
        with store.connect(cfg) as c:
            lease = store.claim(c, cfg, 30)
            if lease is None:
                print(json.dumps({"state": "NO_LEGAL_PENDING_JOB"}), flush=True)
                continue
            output = build(load(c, cfg["tenant"], lease), lease)
            receipt = commit(c, cfg["tenant"], lease, output)
        print(
            json.dumps(
                {"state": "M1_GENERATED_COMMITTED", "locator": receipt, "uid": os.geteuid()}
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()

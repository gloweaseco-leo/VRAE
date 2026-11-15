"""Low-UID draft producer using original claim; final graph seal/finish is HOLD."""

import time

import argparse
import base64
import json
import os
from pathlib import Path

IMPORT_START = time.monotonic()


def main():
    from vrae.application.ra4b import store
    from .source_adapter import build, stage

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--private-receipt")
    args = parser.parse_args()
    config = store.load_config(args.config, "WORKER")
    print(
        json.dumps({"stage": "WORKER_READY", "startup_seconds": time.monotonic() - IMPORT_START}),
        flush=True,
    )
    with store.connect(config) as c:
        lease = store.claim(c, config, 30)
        if lease is None:
            return
        started = time.monotonic()
        candidate, _ = build(c, config["tenant"], lease)
        receipt = stage(c, config["tenant"], lease, candidate)
        receipt["generation_and_draft_commit_seconds"] = time.monotonic() - started
        if args.private_receipt:
            path = Path(args.private_receipt)
            directory = Path(args.config).resolve().parent
            if (
                path.resolve().parent != directory
                or directory.stat().st_uid != getattr(os, "geteuid", lambda: -1)()
                or directory.stat().st_mode & 0o077
            ):
                raise ValueError("S2_PRIVATE_WORKER_IPC_REQUIRED")
            record = {
                "lease": [str(v) if i != 3 else v for i, v in enumerate(lease)],
                "candidate": base64.b64encode(candidate._payload).decode(),
                "source": base64.b64encode(candidate._source).decode(),
                "html": base64.b64encode(candidate._html).decode(),
            }
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as stream:
                json.dump(record, stream)
        print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()

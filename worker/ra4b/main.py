"""Independent test-only lease consumer; receives only its own narrow role."""

import argparse
import json
import time

import psycopg

from vrae.application.ra4b import store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--hold-seconds", type=float, default=0)
    parser.add_argument("--lease-seconds", type=int, default=5)
    args = parser.parse_args()
    if not 0 <= args.hold_seconds <= 30 or not 1 <= args.lease_seconds <= 30:
        raise ValueError("RA4B_BOUNDED_TEST_DELAY_REQUIRED")
    cfg = store.load_config(args.config, "WORKER")
    while True:
        try:
            with store.connect(cfg) as c:
                lease = store.claim(c, cfg, args.lease_seconds)
                if lease:
                    print(json.dumps({"state": "LEASED", "job_id": str(lease[0]), "lease_seq": lease[3]}), flush=True)
                    time.sleep(args.hold_seconds)
                    store.finish(c, cfg, lease)
                    print(json.dumps({"state": "TEST_ONLY_DONE", "job_id": str(lease[0])}), flush=True)
        except psycopg.Error:
            print("RA4B_WORKER_CURRENT_AUTHORITY_OR_STORE_DENIED", flush=True)
        if args.once:
            return
        time.sleep(0.25)


if __name__ == "__main__":
    main()

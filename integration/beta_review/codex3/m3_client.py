"""UID10003 canonical TaskClient, with only a private HTTP service profile."""

import argparse
import json
import os
import stat
from dataclasses import asdict
from pathlib import Path

from vrae.application.ra4b_p2.m1.consumer import AppEndpoint, ConsumerDenied, TaskClient, TaskHandle

PROFILE = Path("/tmp/m3-consumer/config.json")


def client():
    assert os.geteuid() == 10003
    for path, mode in ((PROFILE.parent, 0o700), (PROFILE, 0o600)):
        info = path.lstat()
        assert info.st_uid == 10003 and stat.S_IMODE(info.st_mode) == mode
        assert not stat.S_ISLNK(info.st_mode)
    profile = json.loads(PROFILE.read_bytes())
    assert set(profile) == {"bearer", "tenant_id", "source_refs"}
    assert profile["tenant_id"] == "tenant-test"
    assert profile["source_refs"] == ["accepted-404", "accepted-200"]
    return TaskClient(
        AppEndpoint(profile["bearer"], profile["tenant_id"], frozenset(profile["source_refs"]))
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("submit", "status", "configuration"))
    parser.add_argument("--source", choices=("404", "200"))
    parser.add_argument("--key")
    parser.add_argument("--handle")
    args = parser.parse_args()
    port = client()
    try:
        if args.action == "configuration":
            for path in (
                "/tmp/b4-app/config.json",
                "/tmp/b4-worker/config.json",
                "/tmp/beta-supervisor/state.json",
            ):
                try:
                    Path(path).read_bytes()
                except PermissionError:
                    continue
                raise AssertionError("M3_CONSUMER_MUST_NOT_READ_DATABASE_CONFIG")
            result = {
                "profile_fields": ["bearer", "tenant_id", "source_refs"],
                "database_configs_unreadable": True,
                "directory_mode": "0700",
                "file_mode": "0600",
            }
            code = None
        elif args.action == "submit":
            assert args.source and args.key
            task = port.create("accepted-" + args.source, idempotency_key=args.key)
            result, code = asdict(task), 202
        else:
            assert args.handle
            result, code = port.status(TaskHandle(**json.loads(args.handle))), 200
        print(
            json.dumps(
                {
                    "http_status": code,
                    "body": result,
                    "uid": os.geteuid(),
                    "adapter": "vrae.application.ra4b_p2.m1.consumer.TaskClient",
                }
            ),
            flush=True,
        )
    except ConsumerDenied:
        print(
            json.dumps({"decision": "DENIED", "reason": "M1_CONSUMER_DENIED", "uid": os.geteuid()}),
            flush=True,
        )
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()

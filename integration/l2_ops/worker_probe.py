"""UID10003 exercise of real APP HTTP and signed low-role Worker result read.

No APP/Worker/admin database profile is consumed. Read credentials are supplied
only over private stdin by the disposable TEST_ONLY operator, never by HTTP.
"""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import stat
import sys

import psycopg

from vrae.application.ra4b_p2.m1.consumer import AppEndpoint, TaskClient, TaskHandle
from vrae.application.ra4b_p2.m1.reader import JobAssignment, SignedGeneratedReader
from vrae.identity.boundary import TrustAnchor
from vrae.l2_ops.ingest import load_source
from vrae.l2_ops.native_input import load_native
from vrae.l2_ops.tasks import L2Tasks, RegisteredSource

from .catalog import SOURCE_REF


def adapter():
    assert os.geteuid() == 10003
    path = Path("/tmp/m3-consumer/config.json")
    for item, mode in ((path.parent, 0o700), (path, 0o600)):
        info = item.lstat()
        assert info.st_uid == 10003 and stat.S_IMODE(info.st_mode) == mode and not stat.S_ISLNK(info.st_mode)
    profile = json.loads(path.read_bytes())
    assert set(profile) == {"bearer", "tenant_id", "source_refs"}
    assert profile["source_refs"] == ["accepted-404", "accepted-200", SOURCE_REF]
    client = TaskClient(AppEndpoint(profile["bearer"], profile["tenant_id"], frozenset(profile["source_refs"])))
    bundle = load_source(Path(__file__).parent / "fixtures/native-offline_synthetic.json")
    native = load_native(bundle, "industrial-native",
        expected_pack_ref="ep-735db2c276030e018f21ba7124fb61db6d46f3e922eca1b99df254512064582e",
        expected_capture_run_id="l2-industrial-capture-v1")
    return L2Tasks(client, [RegisteredSource(SOURCE_REF, native)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("create", "read", "status"))
    args = parser.parse_args()
    port = adapter()
    private = json.load(sys.stdin)
    if args.action == "create":
        result = {"http_status": 202, "task": asdict(port.create(SOURCE_REF, idempotency_key=private["key"]))}
    else:
        task = TaskHandle(**private["task"])
        if args.action == "status":
            result = port.status(task)
        else:
            cfg = private["reviewer"]
            assert cfg["role"] == "p2b1_test_a_reviewer" and cfg["host"] == "127.0.0.1" and cfg["port"] == 5432

            def connect(role):
                assert role == cfg["role"]
                return psycopg.connect(host=cfg["host"], port=cfg["port"], dbname="vrae_ra4a_p1",
                    user=role, password=cfg["password"], autocommit=True, connect_timeout=5,
                    options="-c statement_timeout=2000 -c lock_timeout=1500")

            anchor = private["anchor"]
            reader = SignedGeneratedReader(anchor=TrustAnchor(anchor["issuer"], anchor["audience"],
                json.dumps(anchor["jwks"]).encode(), anchor["expires"]),
                assignments=[JobAssignment(**private["assignment"])], connect=connect)
            evidence = port.read_worker(task, reader, private["bearer"], nonce=private["nonce"])
            result = evidence.metadata()
    print(json.dumps({"uid": os.geteuid(), "result": result}), flush=True)


if __name__ == "__main__":
    main()

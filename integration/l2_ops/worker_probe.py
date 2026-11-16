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
from vrae.l2_ops.tasks import L2Tasks, RegisteredSource

from .source_profiles import PROFILES, selected


def adapter(profile_name):
    assert os.geteuid() == 10003
    path = Path("/tmp/m3-consumer/config.json")
    for item, mode in ((path.parent, 0o700), (path, 0o600)):
        info = item.lstat()
        assert info.st_uid == 10003 and stat.S_IMODE(info.st_mode) == mode and not stat.S_ISLNK(info.st_mode)
    profile = json.loads(path.read_bytes())
    assert set(profile) == {"bearer", "tenant_id", "source_refs"}
    source_ref, bundle, native = selected(profile_name)
    assert profile["source_refs"] == ["accepted-404", "accepted-200", source_ref]
    client = TaskClient(AppEndpoint(profile["bearer"], profile["tenant_id"], frozenset(profile["source_refs"])))
    return L2Tasks(client, [RegisteredSource(source_ref, native)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("create", "read", "status", "diagnose", "diagnose-current"))
    parser.add_argument("--source-profile", choices=tuple(PROFILES), default="industrial-v1")
    args = parser.parse_args()
    port = adapter(args.source_profile)
    private = json.loads(sys.stdin.readline())
    if args.action == "create":
        result = {"http_status": 202, "task": asdict(port.create(PROFILES[args.source_profile][0], idempotency_key=private["key"]))}
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
            if args.action == "diagnose-current":
                from datetime import datetime
                from apps.operator_console.b5b_m2_sessions import GeneratedSessions
                from vrae.l2_ops.native_diagnosis import analyze
                sessions = GeneratedSessions(reader)
                sessions.bind_task(JobAssignment(**private["assignment"]), port.client, task)
                challenge, nonce, csrf = sessions.challenge(task.tenant_id, task.job_id)
                print(json.dumps({"uid": os.geteuid(), "signing_nonce": nonce}), flush=True)
                signed = json.loads(sys.stdin.readline())
                sid = sessions.login(challenge, signed["bearer"], csrf)
                with port.current_worker(task, sessions, sid,
                        policy_expires_at=datetime.fromisoformat(private["policy_expires_at"])) as (evidence, deadline):
                    diagnosis = analyze(evidence)
                    result = diagnosis.metadata()
                    result["original_pg_authority_held_during_full_verify"] = True
                    result["original_authority_deadline"] = deadline.isoformat()
                print(json.dumps({"uid": os.geteuid(), "result": result}), flush=True)
                return
            evidence = port.read_worker(task, reader, private["bearer"], nonce=private["nonce"])
            if args.action == "diagnose":
                from vrae.l2_ops.native_diagnosis import analyze
                diagnosis = analyze(evidence)
                result = diagnosis.metadata()
            else:
                result = evidence.metadata()
    print(json.dumps({"uid": os.geteuid(), "result": result}), flush=True)


if __name__ == "__main__":
    main()

"""UID0-only local Owner fixture console. Every business call is real HTTPS."""

import argparse
import hashlib
import json
import os
import socket
import struct
from datetime import datetime, UTC, timedelta

SOCKET = "/evidence/.private-root/owner.sock"


def serve(old, authority, ca, tls, owner_token, worker, hydrate, spawn):
    from integration.l2_launch.g1.client import Client
    from integration.l2_launch.g1.fixtures import submission, return_grant
    from psycopg.types.json import Jsonb

    assert os.geteuid() == 0
    contexts = {}
    owner = Client(8766, str(ca), tls["facade"]["der_sha256"], owner_token=owner_token)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET)
    os.chmod(SOCKET, 0o600)
    server.listen(2)
    while True:
        connection, _ = server.accept()
        with connection:
            connection.settimeout(120)
            stop = False
            try:
                _, uid, _ = struct.unpack(
                    "3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
                )
                if uid != 0:
                    raise ValueError("OWNER_FIXTURE_UID0_REQUIRED")
                value = json.loads(connection.makefile("rb").readline(4097))
                op = value["operation"]
                if op == "stop":
                    result = {"owned_test_stopped": True}
                    stop = True
                elif op == "new":
                    kind = value["kind"]
                    if (
                        kind
                        not in ("manufacturer", "distributor", "forbidden", "robots", "unknown")
                        or len(contexts) >= 20
                    ):
                        raise ValueError("BOUNDED_FIXTURE_ONLY")
                    with old.connect() as c:
                        plan = hydrate(
                            c.execute(
                                "SELECT document FROM g1_http.sourceplans WHERE source_ref=%s",
                                ("g1-recorded-" + kind,),
                            ).fetchone()[0]
                        )
                    body, invitation = submission(plan, authority)
                    with old.connect() as c:
                        c.execute(
                            "INSERT INTO g1_http.invitations VALUES(%s,%s,%s)",
                            (body["invitation_ref"], "tenant-test", Jsonb(invitation)),
                        )
                    client = Client(8767, str(ca), tls["vf"]["der_sha256"])
                    code, accepted, _ = client.request("POST", "/v1/audit-requests", body)
                    if code != 202:
                        result = {"http_status": code, "body": accepted}
                    else:
                        ref = accepted["audit_ref"]
                        token, grant, proof = return_grant(
                            ref, body["subject_ref"], plan.policy, authority
                        )
                        code, _, _ = owner.request(
                            "POST",
                            "/__fixture__/return-grants/" + ref,
                            {"grant": grant, "proof": proof},
                            owner=True,
                        )
                        if code != 201:
                            raise ValueError("OWNER_RETURN_INSTALL_DENIED")
                        if client.request("GET", "/v1/return-challenge")[0] != 200:
                            raise ValueError("CHALLENGE_DENIED")
                        if (
                            client.request(
                                "POST",
                                "/v1/audits/" + ref + "/return/exchange",
                                {"return_token": token},
                            )[0]
                            != 200
                        ):
                            raise ValueError("RETURN_DENIED")
                        contexts[ref] = (client, body)
                        result = {
                            "http_status": 202,
                            "body": accepted,
                            "next": "status, work, status, preview; synthetic only",
                        }
                elif op == "work":
                    child, log = spawn(
                        "owner-worker", 10002, worker, "integration.l2_launch.g1.worker"
                    )
                    child.wait(timeout=30)
                    result = {
                        "worker_exit": child.returncode,
                        "private_log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
                    }
                elif op in ("status", "preview"):
                    ref = value["audit_ref"]
                    if ref not in contexts:
                        raise ValueError("OWNER_CREATED_REF_REQUIRED")
                    client, body = contexts[ref]
                    if op == "status":
                        code, result, _ = client.request("GET", "/v1/audits/" + ref)
                        result = {"http_status": code, "body": result}
                    else:
                        code, pins, _ = owner.request(
                            "GET", "/__fixture__/audits/" + ref + "/pins", owner=True
                        )
                        if code != 200:
                            result = {"http_status": code, "body": pins}
                        else:
                            code, response, _ = owner.request(
                                "POST",
                                "/__fixture__/audits/" + ref + "/review",
                                {"pins": pins, "action": "APPROVE_SYNTHETIC_ONLY"},
                                owner=True,
                            )
                            if code != 200:
                                raise ValueError("CONTROLLED_REVIEW_DENIED")
                            permit = {
                                "tenant_id": "tenant-test",
                                "audit_ref": ref,
                                "subject_ref": body["subject_ref"],
                                "purpose": "SYNTHETIC_PREVIEW_ONLY",
                                "pins": pins,
                                "expires_at": (
                                    datetime.now(UTC) + timedelta(minutes=3)
                                ).isoformat(),
                            }
                            code, _, _ = owner.request(
                                "POST",
                                "/__fixture__/audits/" + ref + "/preview-permit",
                                {
                                    "document": permit,
                                    "proof": authority.sign("owner", "share", permit),
                                },
                                owner=True,
                            )
                            if code != 201:
                                raise ValueError("OWNER_PREVIEW_DENIED")
                            code, response, _ = client.request(
                                "GET",
                                "/__synthetic__/audits/" + ref + "/preview",
                                headers={"If-Match": pins["view_sha256"]},
                            )
                            result = {
                                "http_status": code,
                                "pins": pins,
                                "body": response,
                                "formal_human_review": False,
                                "ai_state": "NO_MODEL",
                            }
                else:
                    raise ValueError("UNKNOWN_OPERATION")
                output = {"scope": "OWNER_LOCAL_SYNTHETIC_ONLY_NOT_G1_PASS", "result": result}
            except Exception as error:
                output = {
                    "scope": "OWNER_LOCAL_SYNTHETIC_ONLY_NOT_G1_PASS",
                    "error": type(error).__name__,
                }
            connection.sendall(json.dumps(output, ensure_ascii=False).encode() + b"\n")
        if stop:
            break
    server.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("new", "work", "status", "preview", "stop"))
    parser.add_argument("value", nargs="?")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError("LOCAL_OWNER_UID0_REQUIRED")
    value = {"operation": args.operation}
    if args.operation == "new":
        value["kind"] = args.value or "manufacturer"
    if args.operation in ("status", "preview"):
        value["audit_ref"] = args.value
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(120)
        client.connect(SOCKET)
        client.sendall(json.dumps(value).encode() + b"\n")
        response = client.makefile("rb").readline(2000001)
    print(json.dumps(json.loads(response), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

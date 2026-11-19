"""Minimal external-service consumer proof, not a frontend/client product."""

import hashlib
import http.client
import json
import ssl
import sys
import socket
from pathlib import Path
from contracts.l2_launch.contract import canonical
from integration.l2_launch.g1.http_server import MEDIA

CFG = json.loads(Path("/client/config.json").read_bytes())
STATE = Path("/state/session.json")
checks = []
events = []


def context(role="client"):
    c = ssl.create_default_context(cafile="/client/ca.pem")
    if role:
        c.load_cert_chain("/client/" + role + ".pem", "/client/" + role + "-key.pem")
    return c


def check(value, label):
    if not value:
        raise AssertionError(label)
    checks.append(label)


def call(method, path, body=None, session=None, role="client", bearer=True):
    headers = {
        "Accept": "application/json"
        if path.startswith("/health/") or path in ("/v1/errors", "/v1/openapi.json")
        else MEDIA,
        "Content-Type": MEDIA,
    }
    if bearer:
        headers["Authorization"] = "Bearer " + CFG["bearer"]
    if session:
        headers.update(Cookie=session["cookie"], **{"X-CSRF-Token": session["csrf"]})
    c = http.client.HTTPSConnection(CFG["host"], CFG["port"], context=context(role), timeout=10)
    c.request(method, path, None if body is None else canonical(body), headers)
    r = c.getresponse()
    raw = r.read()
    hs = dict(r.getheaders())
    c.close()
    value = json.loads(raw)
    # Record status and a body digest, never Cookie/CSRF/return token or raw input.
    events.append(
        {
            "method": method,
            "path": path,
            "status": r.status,
            "response_sha256": hashlib.sha256(raw).hexdigest(),
        }
    )
    return r.status, value, hs


def session(headers):
    return {"cookie": headers["Set-Cookie"].split(";")[0], "csrf": headers["X-CSRF-Token"]}


def main(phase):
    if phase == "submit":
        try:
            call("GET", "/health/live", role=None)
        except (ssl.SSLError, ConnectionError, OSError):
            check(True, "missing client certificate rejected at TLS")
        else:
            raise AssertionError("MTLS_NOT_REQUIRED")
        try:
            s = socket.create_connection((CFG["host"], 5432), timeout=0.5)
            s.close()
        except OSError:
            check(True, "PostgreSQL is not exposed to independent service network")
        else:
            raise AssertionError("PG_LISTENING_OUTSIDE_LOOPBACK")
        check(
            call("GET", "/health/ready", role="other-client")[0] == 403,
            "service bearer is bound to certificate fingerprint",
        )
        check(
            call("GET", "/health/live", bearer=False)[1]["status"] == "LIVE",
            "independent process liveness",
        )
        check(
            call("GET", "/health/ready")[1]["status"] == "READY",
            "authenticated current PG readiness",
        )
        check(
            call("GET", "/v1/openapi.json")[1]["info"]["title"] == "VRAE Diagnosis API",
            "versioned independent API document",
        )
        check(len(call("GET", "/v1/errors")[1]["errors"]) >= 4, "safe error catalog")
        state = {"subjects": []}
        for request in CFG["requests"]:
            code, _, hs = call(
                "POST", "/v1/invitation-session", {"invitation_token": request["invitation_token"]}
            )
            check(code == 200, "fresh external invitation exchange")
            s = session(hs)
            check(
                all(x in hs["Set-Cookie"] for x in ("Secure", "HttpOnly", "SameSite=Strict")),
                "external secure session cookie",
            )
            check(
                call(
                    "POST",
                    "/v1/invitation-session",
                    {"invitation_token": request["invitation_token"]},
                )[0]
                == 403,
                "invitation replay denied",
            )
            code, frame, _ = call("GET", "/v1/source-plans/" + request["target_id"], session=s)
            check(
                code == 200 and frame["contract"] == "vrae.authorized-source-context.v1",
                "external service obtains its current source signing context",
            )
            from copy import deepcopy
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from integration.authorized_targets.checks.issuer import Issuer
            from contracts.l2_launch.contract import permission_document
            from contracts.l2_launch.vf_b import submission_document

            signer = Issuer(frame["tenant_id"])
            signer.key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(CFG["permission_key"]))
            value = deepcopy(request["submit"])
            value["subject_ref"] = frame["subject_ref"]
            value["invitation_ref"] = frame["invitation_ref"]
            value["command"]["permission_reference"]["proof"] = signer.sign(
                "permission",
                "permission",
                permission_document(value["command"], frame["source_policy"]),
            )
            value["submission_proof"] = signer.sign(
                "permission", "permission", submission_document(value)
            )
            request["submit"] = value
            variant = deepcopy(value)
            variant["language"] = "en"
            variant["submission_proof"] = signer.sign(
                "permission", "permission", submission_document(variant)
            )
            request["variant"] = variant
            code, accepted, _ = call("POST", "/v1/audit-requests", request["submit"], s)
            check(code == 202, "external independent task admitted after COMMIT")
            check(
                call("POST", "/v1/audit-requests", request["submit"], s)[1] == accepted,
                "external same-body idempotency",
            )
            check(
                call("POST", "/v1/audit-requests", request["variant"], s)[0] == 409,
                "external signed intent conflict",
            )
            check(
                call("GET", "/v1/audits/" + accepted["audit_ref"], session=s)[1]["display_state"]
                == "accepted",
                "external pending status is not completed",
            )
            state["subjects"].append(
                {"session": s, "accepted": accepted, "submit": request["submit"]}
            )
        a, b = state["subjects"]
        check(
            call("GET", "/v1/audits/" + a["accepted"]["audit_ref"], session=b["session"])[0] == 403,
            "external cross-subject task read denied",
        )
        STATE.write_bytes(canonical(state))
        STATE.chmod(0o600)
    else:
        state = json.loads(STATE.read_bytes())
        for request, subject in zip(CFG["requests"], state["subjects"]):
            ref = subject["accepted"]["audit_ref"]
            s = subject["session"]
            path = "/v1/audits/" + ref
            if phase == "outage":
                check(
                    call("GET", "/health/live", bearer=False)[0] == 200,
                    "liveness survives actual PG stop",
                )
                check(call("GET", "/health/ready")[0] == 503, "readiness reports actual PG outage")
                check(
                    call("GET", path, session=s)[0] == 503,
                    "task error is safe503 during actual PG outage",
                )
            else:
                code, current, _ = call("GET", path, session=s)
                check(
                    code == 200 and current["task"]["run_id"] == subject["accepted"]["run_id"],
                    "external status preserves real run after restart",
                )
                check(
                    current["task"]["status"] == "DRAFT_READY"
                    and current["display_state"] != "completed",
                    "real completed Worker remains unpublished",
                )
                check(
                    call("GET", path + "/report", session=s)[0] == 403,
                    "unapproved external report remains403",
                )
                check(
                    call("POST", "/v1/audit-requests", subject["submit"], s)[1]
                    == subject["accepted"],
                    "external idempotency survives PG/API process restart",
                )
                if phase == "read":
                    code, recovery, _ = call(
                        "POST", path + "/return-tokens", {"ttl_seconds": 180}, s
                    )
                    check(
                        code == 201 and recovery["grants_report_access"] is False,
                        "task recovery token is not report grant",
                    )
                    code, restored, hs = call(
                        "POST", "/v1/return-sessions", {"return_token": recovery["return_token"]}
                    )
                    check(code == 200, "fresh one-use task recovery without old cookie")
                    check(
                        call(
                            "POST",
                            "/v1/return-sessions",
                            {"return_token": recovery["return_token"]},
                        )[0]
                        == 403,
                        "task recovery replay denied",
                    )
                    subject["session"] = session(hs)
        STATE.write_bytes(canonical(state))
        STATE.chmod(0o600)
    print(
        json.dumps(
            {
                "contract": "vrae.external-service-probe.v1",
                "phase": phase,
                "passed": True,
                "checks": checks,
                "http": events,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main(sys.argv[1])

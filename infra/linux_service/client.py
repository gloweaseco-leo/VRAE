"""Controlled external service probe of persistent task and original report APIs."""

import hashlib
import http.client
import json
from pathlib import Path
import ssl
import sys
from contracts.l2_launch.contract import canonical
from integration.authorized_targets.report_api import MEDIA, BASE
from integration.l2.support import Issuer
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

CFG = json.loads(Path("/client/service-report.json").read_bytes())
EVENTS = []


def call(method, path, body=None, sid=None, headers=None, expected=200):
    ctx = ssl.create_default_context(cafile="/client/ca.pem")
    ctx.load_cert_chain("/client/client.pem", "/client/client-key.pem")
    c = http.client.HTTPSConnection("vrae-api", 8770, context=ctx, timeout=10)
    h = {"Authorization": "Bearer " + CFG["bearer"], "Accept": MEDIA, "Content-Type": MEDIA}
    if CFG.get("verified"):
        h["X-Report-Profile"] = "VERIFIED_HUMAN_CUSTOMER_REPORT"
    if sid:
        h["X-Report-Session"] = sid
    h.update(headers or {})
    c.request(method, BASE + path, None if body is None else canonical(body), h)
    r = c.getresponse()
    raw = r.read()
    c.close()
    EVENTS.append(
        {
            "method": method,
            "path": path,
            "status": r.status,
            "response_sha256": hashlib.sha256(raw).hexdigest(),
        }
    )
    assert r.status == expected, (path, r.status, expected)
    return json.loads(raw)


def main(phase):
    call("GET", "/health")
    issuer = Issuer()
    issuer.kid = CFG["issuer_kid"]
    issuer.jwks = CFG["jwks"]
    issuer.key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(CFG["issuer_key"]))
    sids = {}
    for person in ("owner", "reviewer", "reader"):
        ch = call("POST", "/challenge", {})
        sids[person] = call(
            "POST",
            "/session",
            {
                "responsible_bearer": issuer.token(CFG.get("reader_subject", person) if person == "reader" else person, ch["nonce"], acr="VERIFIED_PERSON_MFA" if CFG.get("verified") else "CONTROLLED_TEST_PERSON"),
                "nonce": ch["nonce"],
                "csrf": ch["csrf"],
            },
        )["report_session"]
    if CFG.get("verified"):
        wrong = call("GET", "/health", headers={"X-Report-Profile": "CONTROLLED_NATIVE_REPORT_ONLY"}, expected=406)
        assert "report" not in wrong
    path = "/jobs/" + CFG["job"]
    view = call("GET", path + "/report", sid=sids["owner"])
    assert view["formal_human_review"] is False and view["external_release"] is False
    if phase == "prepare":

        def action(op, body, view, sid):
            token = call("POST", path + "/actions", {"operation": op}, sid=sid)["action_token"]
            return call(
                "POST",
                path + "/" + op,
                body,
                sid=sid,
                headers={"X-Report-Action": token, "If-Match": '"' + view["display_hash"] + '"'},
            )

        items = {x["id"]: "ACK" for name in ("findings", "blueprint") for x in view["report"][name]}
        action(
            "decisions",
            {
                "action": "APPROVE",
                "reason": "Controlled service persistence exercise, not human approval.",
                "items": items,
                "attest": True,
            },
            view,
            sids["reviewer"],
        )
        call("GET", path + "/report", sid=sids["reader"], expected=403)
        grant = action("grants", {"recipient_id": "reader", "ttl": 300}, view, sids["owner"])
        gh = {"X-Report-Grant": grant["grant"]["grant_id"], "X-Report-Token": grant["access_token"]}
        released = call("GET", path + "/report", sid=sids["reader"], headers=gh)
        assert released["external_release"] is bool(CFG.get("verified"))
        action("revocations", {"grant_id": grant["grant"]["grant_id"]}, view, sids["owner"])
        call("GET", path + "/report", sid=sids["reader"], headers=gh, expected=403)
        action(
            "revisions",
            {
                "changes": {
                    view["report"]["blueprint"][0][
                        "id"
                    ]: "Controlled persistent revision: retain original source and UNKNOWN."
                }
            },
            view,
            sids["reviewer"],
        )
        call(
            "GET",
            path + "/report",
            sid=sids["owner"],
            headers={"If-Match": '"' + view["display_hash"] + '"'},
            expected=409,
        )
    else:
        assert view["report_version"]["version"] == 2
        assert view["report_version"]["status"] == "REVIEW_REQUIRED"
    print(json.dumps({"phase": phase, "passed": True, "controlled_only": not CFG.get("verified", False), "isolated_protocol_test_not_customer_signoff": True, "http": EVENTS}))


if __name__ == "__main__":
    try:
        main(sys.argv[1])
    except Exception as error:
        import traceback
        print(json.dumps({
            "failure_type": type(error).__name__,
            "frames": [{"file": Path(f.filename).name, "line": f.lineno}
                       for f in traceback.extract_tb(error.__traceback__)],
            "http": EVENTS,
        }), flush=True)
        raise

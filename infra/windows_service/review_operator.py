"""Trusted local operator: fresh actual MFA -> original report API. No auto review."""

import argparse
import hashlib
import json
from pathlib import Path
from infra.windows_service.private_host import invoke, put_private
from infra.windows_service.pair_reviewer import action, dialog
from infra.windows_service.windows_credentials import current_sid, current_account_name, verify

BASE = "/v1/report-authority"
RPC = r"""import os,json,pathlib,ssl,socket,http.client,hashlib
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
root=pathlib.Path(os.environ['VRAE_PRIVATE_ROOT'])
cfg=json.loads((root/'caller.json').read_bytes());request=json.load(__import__('sys').stdin)
context=ssl.create_default_context();context.load_cert_chain(cfg['certificate'],cfg['key'])
c=http.client.HTTPSConnection(cfg['host'],8443,context=context,timeout=15)
sock=socket.create_connection(('127.0.0.1',8770),timeout=15)
c.sock=context.wrap_socket(sock,server_hostname=cfg['host'])
certificate=x509.load_pem_x509_certificate((root/'server.pem').read_bytes())
assert hashlib.sha256(c.sock.getpeercert(binary_form=True)).digest()==hashlib.sha256(certificate.public_bytes(Encoding.DER)).digest()
media='application/vnd.vrae.report+json; profile="vrae.report-authority.v1"'
headers={'Authorization':'Bearer '+cfg['review_bearer'],'Accept':media,'X-Report-Profile':'VERIFIED_HUMAN_CUSTOMER_REPORT'}
if request.get('sid'):headers['X-Report-Session']=request['sid']
headers.update(request.get('headers',{}))
body=request.get('body')
if body is not None:headers['Content-Type']=media
assert request['path'].startswith('/v1/report-authority/')
c.request(request['method'],request['path'],None if body is None else json.dumps(body).encode(),headers)
r=c.getresponse();raw=r.read(2000001)
assert len(raw)<=2000000 and r.getheader('X-VRAE-Source-SHA')==cfg['source_sha']
assert 'no-store' in r.getheader('Cache-Control','')
print(json.dumps({'status':r.status,'body':json.loads(raw),'response_sha256':hashlib.sha256(raw).hexdigest()}))
c.close()
"""


class Port:
    def __init__(self, image, name):
        self.image, self.name = image, name
        self.events = []

    def call(self, method, path, body=None, sid=None, headers=None, expected=200):
        result = json.loads(
            invoke(
                self.image,
                self.name,
                "python",
                "-B",
                "-c",
                RPC,
                data=json.dumps(
                    {
                        "method": method,
                        "path": path,
                        "body": body,
                        "sid": sid,
                        "headers": headers or {},
                    }
                ).encode(),
                network="container:" + self.name + "-pg",
            )
        )
        self.events.append(
            {
                "method": method,
                "path": path,
                "status": result["status"],
                "expected": expected,
                "response_sha256": result["response_sha256"],
            }
        )
        if result["status"] != expected:
            raise PermissionError("ORIGINAL_REPORT_API_STATUS_" + str(result["status"]))
        return result["body"]

    def private(self, filename):
        program = "import os,pathlib,sys;sys.stdout.buffer.write((pathlib.Path(os.environ['VRAE_PRIVATE_ROOT'])/sys.argv[1]).read_bytes())"
        return json.loads(invoke(self.image, self.name, "python", "-B", "-c", program, filename))


def visible_primary(nonce, sid):
    import tkinter as tk
    from tkinter import messagebox

    window = tk.Tk()
    window.title("VRAE - actual Reviewer Windows verification")
    window.geometry("650x210")
    window.attributes("-topmost", True)
    result = {}
    tk.Label(
        window,
        text="Account: "
        + current_account_name()
        + "\nVerify with the account PASSWORD, not a PIN.\nThe next step uses the enrolled VRAE phone code.",
        pady=20,
    ).pack()

    def authenticate():
        button.configure(state="disabled")
        window.update()
        try:
            result["primary"] = verify(nonce, sid, window.winfo_id())
        except Exception as error:
            messagebox.showerror("VRAE", str(error), parent=window)
            button.configure(state="normal")
            return
        window.destroy()

    button = tk.Button(window, text="Open actual Windows verification", command=authenticate)
    button.pack()
    window.lift()
    window.focus_force()
    window.mainloop()
    if "primary" not in result:
        raise PermissionError("ACTUAL_REVIEWER_AUTHENTICATION_CANCELLED")
    return result["primary"]


def login(port):
    sid = current_sid()
    pending = action(port.image, port.name, "begin", {"sid": sid})
    primary = visible_primary(pending["nonce"], sid)
    label = port.private("pairing-label.json")["account_label"]
    code = dialog({"mode": "otp", "account_label": label})["code"]
    suffix = hashlib.sha256(sid.encode()).hexdigest()[:20]
    challenges = {
        role: port.call("POST", BASE + "/challenge", {}) for role in ("reviewer", "owner")
    }
    requests = [
        {"subject": role + "-" + suffix, "nonce": challenges[role]["nonce"]} for role in challenges
    ]
    tokens = action(
        port.image, port.name, "issue", {"primary": primary, "code": code, "requests": requests}
    )
    del primary, code
    sessions = {}
    for role, token in zip(challenges, tokens):
        ch = challenges[role]
        sessions[role] = port.call(
            "POST",
            BASE + "/session",
            {
                "responsible_bearer": token["responsible_bearer"],
                "nonce": ch["nonce"],
                "csrf": ch["csrf"],
            },
        )["report_session"]
    return sessions


def pins_match(draft, view):
    if (
        draft["display_hash"] != view["display_hash"]
        or draft["report"] != view["report"]
        or draft["report_version"]["report_version_id"]
        != view["report_version"]["report_version_id"]
        or draft["report_version"]["content_hash"] != view["report_version"]["content_hash"]
    ):
        raise PermissionError("HUMAN_REVIEWED_REPORT_CHANGED")


def mutate(port, path, sid, operation, view, body):
    token = port.call("POST", path + "/actions", {"operation": operation}, sid)["action_token"]
    return port.call(
        "POST",
        path + "/" + operation,
        body,
        sid,
        {"If-Match": '"' + view["display_hash"] + '"', "X-Report-Action": token},
    )


def approve(port):
    pending = port.private("review-pending.json")
    human = port.private("review-actions.json")
    if human["windows_sid_sha256"] != hashlib.sha256(current_sid().encode()).hexdigest():
        raise PermissionError("SAME_ACTUAL_WINDOWS_REVIEWER_REQUIRED")
    if not human["grant_current_invited_acceptance_recipients"] or len(human["reviews"]) != len(
        pending
    ):
        raise PermissionError("EXPLICIT_HUMAN_REVIEW_AND_DIRECTED_GRANT_REQUIRED")
    for draft, review in zip(pending, human["reviews"]):
        expected = {x["id"] for x in draft["report"]["findings"] + draft["report"]["blueprint"]}
        if (
            review["audit_ref"] != draft["audit_ref"]
            or review["display_hash"] != draft["display_hash"]
            or review["decision"]["items"] != {i: "ACK" for i in expected}
            or review["decision"]["action"] != "APPROVE"
            or review["decision"]["attest"] is not True
        ):
            raise PermissionError("EXACT_HUMAN_ACKNOWLEDGEMENTS_REQUIRED")
    sessions = login(port)
    grants = {}
    decisions = []
    for draft, review in zip(pending, human["reviews"]):
        path = BASE + "/audits/" + draft["audit_ref"]
        view = port.call("GET", path + "/report", sid=sessions["reviewer"])
        pins_match(draft, view)
        result = mutate(port, path, sessions["reviewer"], "decisions", view, review["decision"])
        owner = port.call("GET", path + "/report", sid=sessions["owner"])
        pins_match(draft, owner)
        grant = mutate(
            port,
            path,
            sessions["owner"],
            "grants",
            owner,
            {"recipient_id": owner["current_recipient"]["recipient_id"], "ttl": 900},
        )
        grants[draft["subject_ref"]] = {
            "audit_ref": draft["audit_ref"],
            "grant_id": grant["grant"]["grant_id"],
            "grant_token": grant["access_token"],
            "display_hash": view["display_hash"],
            "report_version_id": view["report_version"]["report_version_id"],
            "content_hash": view["report_version"]["content_hash"],
            "native_context": view["report"]["native_context"],
            "pack_ref": view["report"]["producer"]["source_descriptor"]["pack_ref"],
            "reviewer_id": "reviewer-" + hashlib.sha256(current_sid().encode()).hexdigest()[:20],
        }
        decisions.append(
            {
                "subject_ref": draft["subject_ref"],
                "audit_ref": draft["audit_ref"],
                "receipt": result["receipt"],
                "grant": grant["grant"],
                "display_hash": view["display_hash"],
            }
        )
    put_private(port.image, port.name, "acceptance-grants.json", json.dumps(grants).encode())
    put_private(
        port.image, port.name, "review-operator-sessions.json", json.dumps(sessions).encode()
    )
    return {
        "actual_human_decisions": decisions,
        "events": port.events,
        "grants_stored_privately": True,
    }



def revoke(port):
    human=port.private("review-actions.json")
    if not human["grant_current_invited_acceptance_recipients"] or human["windows_sid_sha256"]!=hashlib.sha256(current_sid().encode()).hexdigest():
        raise PermissionError("ACTUAL_OWNER_REVOCATION_CONSENT_REQUIRED")
    grants=port.private("acceptance-grants.json")
    sessions=login(port)
    revoked=[]
    for subject,grant in grants.items():
        path=BASE+"/audits/"+grant["audit_ref"]
        view=port.call("GET",path+"/report",sid=sessions["owner"])
        if view["display_hash"]!=grant["display_hash"]:
            raise PermissionError("HUMAN_REVIEWED_REPORT_CHANGED")
        result=mutate(port,path,sessions["owner"],"revocations",view,{"grant_id":grant["grant_id"]})
        revoked.append({"subject_ref":subject,"grant":result["grant"]})
    put_private(port.image,port.name,"acceptance-revoked.json",json.dumps(revoked).encode())
    return {"actual_owner_revocations":revoked,"events":port.events}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--operator-image", required=True)
    p.add_argument("--name", default="vrae-windows")
    p.add_argument("--receipt", required=True)
    p.add_argument("--mode", choices=("approve","revoke"), default="approve")
    a = p.parse_args()
    port = Port(a.operator_image, a.name)
    target = Path(a.receipt)
    try:
        target.write_text(json.dumps(approve(port) if a.mode=="approve" else revoke(port)), encoding="utf8")
    except Exception as error:
        target.write_text(
            json.dumps(
                {
                    "complete": False,
                    "error_type": type(error).__name__,
                    "reason": str(error)
                    if isinstance(error, PermissionError)
                    else "PRIVATE_OPERATION_FAILED",
                    "events": port.events,
                }
            ),
            encoding="utf8",
        )
        raise


if __name__ == "__main__":
    main()

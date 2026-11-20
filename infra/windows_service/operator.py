"""Explicit local root operations, never reachable over HTTP."""
import argparse
from datetime import datetime, UTC
import json
import os
from pathlib import Path
import secrets
import psycopg
from psycopg.types.json import Jsonb
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from contracts.l2_launch.contract import canonical
from integration.authorized_targets.authority import token_hash


def root():
    p=Path(os.environ["VRAE_PRIVATE_ROOT"])
    if os.geteuid()!=0 or p.is_symlink() or p.stat().st_uid!=0 or p.stat().st_mode&0o077:
        raise PermissionError("ROOT_EXT4_OPERATOR_REQUIRED")
    return p


def save(p,value):
    if p.is_symlink():
        raise PermissionError("REGULAR_PRIVATE_INPUT_REQUIRED")
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(canonical(value))


def sign(p,name,doc):
    key=Ed25519PrivateKey.from_private_bytes(bytes.fromhex((p/(name+"-key")).read_text()))
    return {"key_id":name,"document":doc,"signature":key.sign(canonical(doc)).hex()}


def enable_intake(p):
    manifest=json.loads((p/"manifest.json").read_bytes())
    intent=json.loads((p/"deployment-intent.json").read_bytes())["document"]
    doc={"contract":"vrae.dns-target-enrollment.v1","source_class":manifest["source_class"],
         "purpose":"READONLY_DIAGNOSIS","proof":"DNS_TXT_OR_OPERATOR_OWNED_SOURCE_AND_EXPLICIT_CONSENT",
         "max_pages":4,"not_before":intent["not_before"],"expires_at":intent["expires_at"]}
    save(p/"enrollment-delegation.json",sign(p,"deployment",doc))
    if not (p/"enrollment-hmac-key").exists():
        fd=os.open(p/"enrollment-hmac-key",os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as f:
            f.write(secrets.token_bytes(32))
    api=json.loads((p/"api.json").read_bytes())
    api["target_intake_enabled"]=True
    save(p/"api.json",api)
    manifest["intake_enabled"]=True
    save(p/"manifest.json",manifest)
    return {"target_enrollment":"DNS_PROOF_AND_CURRENT_INVITATION_REQUIRED","customer_permission_issued":False}


def invite(p,subject):
    import re
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,127}",subject):
        raise ValueError("OPAQUE_SUBJECT_REQUIRED")
    cfg=json.loads((p/"api.json").read_bytes())
    tenant=cfg["bindings"][0]["tenant_id"]
    end=json.loads((p/"deployment-intent.json").read_bytes())["document"]["expires_at"]
    if datetime.now(UTC)>=datetime.fromisoformat(end):
        raise PermissionError("CURRENT_OPERATOR_AUTHORITY_REQUIRED")
    token=secrets.token_urlsafe(32)
    ref="inv-"+secrets.token_hex(16)
    doc={"tenant_id":tenant,"reference":ref,"subject_ref":subject,"target_ids":[],
         "expires_at":end,"revoked":False}
    with psycopg.connect(host="127.0.0.1",dbname="vrae_ra4a_p1",user="postgres",
        password=(p/"pg-password").read_text(),autocommit=True) as c:
        c.execute("INSERT INTO target_v1.invitations VALUES(%s,%s,%s,%s,%s,false,false)",
                  (tenant,ref,subject,token_hash(token),Jsonb(doc)))
    save(p/(ref+".json"),{"invitation_token":token,"document":doc})
    return {"reference":ref,"subject_ref":subject,"expires_at":end,"private_handoff":ref+".json"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=["enable-intake","invite"])
    p.add_argument("--subject")
    a=p.parse_args()
    base=root()
    result=enable_intake(base) if a.action=="enable-intake" else invite(base,a.subject)
    print(json.dumps(result))


if __name__=="__main__":
    main()

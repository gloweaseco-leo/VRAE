"""Small root-local Windows/TOTP authority. Not a public IdP or HTTP endpoint."""
import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import struct
import time
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from contracts.l2_launch.contract import canonical
from vrae.l2.verified import CURRENT_REPORTS


def totp(seed,step):
    raw=hmac.new(base64.b32decode(seed),struct.pack(">Q",step),hashlib.sha1).digest()
    offset=raw[-1]&15
    return str((struct.unpack(">I",raw[offset:offset+4])[0]&0x7fffffff)%1000000).zfill(6)


class Store:
    def __init__(self,path,clock=time.time):
        self.path,self.clock=Path(path),clock
        if self.path.is_symlink() or self.path.parent.stat().st_mode&0o077:
            raise PermissionError("PRIVATE_MFA_DIRECTORY_REQUIRED")
        if self.path.exists() and (self.path.stat().st_uid!=os.geteuid() or self.path.stat().st_mode&0o077):
            raise PermissionError("PRIVATE_MFA_DATABASE_REQUIRED")
        fd=os.open(self.path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        os.close(fd)
        with self.connect() as c:
            c.executescript("""CREATE TABLE IF NOT EXISTS accounts(
                sid text PRIMARY KEY,seed text NOT NULL,last_step integer NOT NULL,active integer NOT NULL);
                CREATE TABLE IF NOT EXISTS challenges(
                nonce text PRIMARY KEY,sid text NOT NULL,seed text,expires integer NOT NULL,used integer NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS primary_used(
                authentication_id text PRIMARY KEY,nonce text NOT NULL,used_at integer NOT NULL);
                CREATE TABLE IF NOT EXISTS failures(sid text PRIMARY KEY,count integer NOT NULL,until integer NOT NULL);
                CREATE TABLE IF NOT EXISTS nonces(nonce text PRIMARY KEY,used_at integer NOT NULL);""")

    def connect(self):
        c=sqlite3.connect(self.path,timeout=3)
        c.execute("PRAGMA journal_mode=DELETE")
        c.execute("PRAGMA synchronous=FULL")
        return c

    def begin(self,sid,pair=False):
        now=int(self.clock())
        with self.connect() as c:
            if pair and c.execute("SELECT 1 FROM accounts WHERE sid=? AND active=1",(sid,)).fetchone():
                raise PermissionError("EXISTING_MFA_MUST_NOT_BE_REPLACED")
            if not pair and not c.execute("SELECT 1 FROM accounts WHERE sid=? AND active=1",(sid,)).fetchone():
                raise PermissionError("ACTUAL_MFA_ENROLLMENT_REQUIRED")
            c.execute("DELETE FROM challenges WHERE expires<?",(now-3600,))
            nonce=secrets.token_urlsafe(32)
            pending=c.execute("SELECT seed FROM challenges WHERE sid=? AND seed IS NOT NULL AND used=0 AND expires>? ORDER BY expires DESC LIMIT 1",(sid,now-86400)).fetchone() if pair else None
            seed=(pending[0] if pending else base64.b32encode(secrets.token_bytes(20)).decode()) if pair else None
            expiry=now+(900 if pair else 300)
            if pair:
                c.execute("UPDATE challenges SET used=1 WHERE sid=? AND seed IS NOT NULL",(sid,))
            c.execute("INSERT INTO challenges VALUES(?,?,?,?,0)",(nonce,sid,seed,expiry))
        return {"nonce":nonce,"seed":seed,"expires":expiry,"sid":sid}

    def finish(self,primary,code,pair=False,report_nonces=()):
        now=int(self.clock())
        if (set(primary)!={"verifier","sid","authentication_id","verified_at","nonce"}
            or primary["verifier"]!="WINDOWS_LOGONUSER_W" or type(primary["verified_at"]) is not int
            or not now-60<=primary["verified_at"]<=now+5 or not primary["authentication_id"]):
            raise PermissionError("FRESH_ACTUAL_WINDOWS_PASSWORD_VERIFICATION_REQUIRED")
        if type(code) is not str or len(code)!=6 or not code.isascii() or not code.isdigit():
            raise PermissionError("ACTUAL_TOTP_REQUIRED")
        c=self.connect()
        try:
            c.execute("BEGIN IMMEDIATE")
            row=c.execute("SELECT sid,seed,expires,used FROM challenges WHERE nonce=?",(primary["nonce"],)).fetchone()
            if not row or row[0]!=primary["sid"] or row[2]<=now or row[3]:
                raise PermissionError("MFA_CHALLENGE_REPLAY_OR_EXPIRY")
            if c.execute("SELECT 1 FROM primary_used WHERE authentication_id=?",(primary["authentication_id"],)).fetchone():
                raise PermissionError("WINDOWS_PRIMARY_AUTHENTICATION_REPLAY")
            blocked=c.execute("SELECT count,until FROM failures WHERE sid=?",(row[0],)).fetchone()
            if blocked and blocked[0]>=5 and blocked[1]>now:
                raise PermissionError("MFA_RATE_LIMITED")
            account=c.execute("SELECT seed,last_step,active FROM accounts WHERE sid=?",(row[0],)).fetchone()
            if pair:
                if account and account[2]:
                    raise PermissionError("EXISTING_MFA_MUST_NOT_BE_REPLACED")
                seed,last=row[1],-1
            else:
                if not account or not account[2] or row[1] is not None:
                    raise PermissionError("ACTUAL_MFA_ENROLLMENT_REQUIRED")
                seed,last=account[:2]
            step=next((s for s in (now//30,now//30-1,now//30+1) if hmac.compare_digest(totp(seed,s),code)),None)
            if step is None:
                count=(blocked[0] if blocked and blocked[1]>now else 0)+1
                c.execute("INSERT INTO failures VALUES(?,?,?) ON CONFLICT(sid) DO UPDATE SET count=excluded.count,until=excluded.until",
                          (row[0],count,now+300))
                c.commit()
                raise PermissionError("TOTP_VERIFICATION_FAILED")
            if step<=last:
                raise PermissionError("TOTP_TIME_STEP_REPLAY")
            for nonce in report_nonces:
                if type(nonce) is not str or not 16<=len(nonce)<=128:
                    raise PermissionError("BOUNDED_REPORT_NONCE_REQUIRED")
                c.execute("INSERT INTO nonces VALUES(?,?)",(nonce,now))
            c.execute("INSERT INTO accounts VALUES(?,?,?,1) ON CONFLICT(sid) DO UPDATE SET last_step=excluded.last_step",
                      (row[0],seed,step))
            c.execute("INSERT INTO primary_used VALUES(?,?,?)",(primary["authentication_id"],primary["nonce"],now))
            c.execute("UPDATE challenges SET used=1 WHERE nonce=?",(primary["nonce"],))
            c.execute("DELETE FROM failures WHERE sid=?",(row[0],))
            c.commit()
            return {"sid_sha256":hashlib.sha256(row[0].encode()).hexdigest(),"verified_at":now,
                    "verification_ref":"WINDOWS_PASSWORD_AND_TOTP-"+hashlib.sha256((row[0]+primary["nonce"]).encode()).hexdigest()}
        except Exception:
            if c.in_transaction:
                c.rollback()
            raise
        finally:
            c.close()


def enroll_directory(root,proof):
    p=root/"report-authority.json"
    envelope=json.loads(p.read_bytes())
    people=envelope["document"]["directory"]["people"]
    for role in ("OWNER","REVIEWER"):
        subject=role.lower()+"-"+proof["sid_sha256"][:20]
        if any(person["subject"]==subject for person in people):
            continue
        people.append({"actor_id":subject,"subject":subject,"name":"Verified local Windows "+role,
            "tenant_id":json.loads((root/"api.json").read_bytes())["bindings"][0]["tenant_id"],
            "role":role,"report_ids":[CURRENT_REPORTS],"verification_ref":proof["verification_ref"]})
    key=Ed25519PrivateKey.from_private_bytes(bytes.fromhex((root/"report-key").read_text()))
    envelope["signature"]=key.sign(canonical(envelope["document"])).hex()
    p.write_bytes(canonical(envelope))
    p.chmod(0o600)
    return {"enrolled_roles":["OWNER","REVIEWER"],"sid_sha256":proof["sid_sha256"],
            "report_authority_restart_required":True}


def issue(root,proof,requests):
    authority=json.loads((root/"report-authority.json").read_bytes())["document"]["directory"]
    key=Ed25519PrivateKey.from_private_bytes(bytes.fromhex((root/"identity-key").read_text()))
    people={p["subject"]:p for p in authority["people"]}
    tokens=[]
    for request in requests:
        subject=request["subject"]
        if (subject not in people or not subject.endswith(proof["sid_sha256"][:20])
            or people[subject]["role"] not in ("OWNER","REVIEWER")):
            raise PermissionError("CURRENT_ENROLLED_WINDOWS_ROLE_REQUIRED")
        now=int(proof["verified_at"])
        header={"alg":"EdDSA","kid":"windows-identity","typ":"vrae-responsible-review+jwt"}
        claims={"iss":authority["issuer"],"aud":authority["audience"],"sub":subject,"iat":now,"nbf":now,
                "exp":now+180,"jti":secrets.token_urlsafe(24),"nonce":request["nonce"],"acr":"VERIFIED_PERSON_MFA"}
        def enc(v):
            return base64.urlsafe_b64encode(canonical(v)).decode().rstrip("=")
        hp=enc(header)+"."+enc(claims)
        signature=base64.urlsafe_b64encode(key.sign(hp.encode())).decode().rstrip("=")
        tokens.append({"subject":subject,"responsible_bearer":"Bearer "+hp+"."+signature})
    return tokens


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["begin-pair","finish-pair","begin","issue"])
    a=parser.parse_args()
    root=Path(os.environ["VRAE_PRIVATE_ROOT"])
    if os.geteuid()!=0 or root.stat().st_uid!=0 or root.stat().st_mode&0o077:
        raise PermissionError("ROOT_LOCAL_IDENTITY_ISSUER_REQUIRED")
    data=json.load(__import__("sys").stdin)
    state=Store(root/"identity.sqlite")
    if a.action in ("begin-pair","begin"):
        result=state.begin(data["sid"],a.action=="begin-pair")
    else:
        requests=data.get("requests",[])
        if type(requests) is not list or len(requests)>4:
            raise PermissionError("BOUNDED_ENROLLED_ROLES_REQUIRED")
        proof=state.finish(data["primary"],data["code"],a.action=="finish-pair",
                           [r["nonce"] for r in requests])
        result=enroll_directory(root,proof) if a.action=="finish-pair" else issue(root,proof,requests)
    print(json.dumps(result))


if __name__=="__main__":
    main()

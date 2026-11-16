"""Responsible-person directory + closed signed login, separate from TEST_ONLY M1.

No discovery, private key or user-supplied role. Formal attribution requires an
out-of-band verified directory and its configured signed assurance claim. Demo
issuers/directories cannot produce formal human review, even if a name is typed.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import re
import secrets
import threading
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from vrae.identity.boundary import decode, document
from .report import deny


@dataclass(frozen=True)
class Person:
    actor_id: str
    subject: str
    name: str
    tenant_id: str
    role: str
    report_ids: tuple
    verification_ref: str | None = None
    active: bool = True

    @property
    def actor(self):
        return {'actor_id':self.actor_id,'tenant_id':self.tenant_id,'role':self.role}


@dataclass
class Session:
    person: Person
    expires: float
    key_id: str
    generation: str
    grant_claims: dict


class Directory:
    def __init__(self, *, issuer, audience, jwks, people, expires, mode='CONTROLLED', clock=time.time):
        if mode not in ('CONTROLLED','VERIFIED_DIRECTORY') or not issuer.startswith('https://'):
            deny('L2_IDENTITY_CONFIGURATION_DENIED')
        if mode=='VERIFIED_DIRECTORY' and any(not p.verification_ref for p in people):
            deny('L2_VERIFIED_PERSON_DIRECTORY_REQUIRED')
        self.issuer,self.audience,self.jwks,self.expires = issuer,audience,jwks,expires
        self.people = {p.subject:p for p in people}
        if (len(self.people)!=len(people) or len({p.actor_id for p in people})!=len(people)
                or any(type(p) is not Person or p.role not in ('OWNER','REVIEWER','READER')
                       or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{2,127}',p.actor_id)
                       or not re.fullmatch('[a-z][a-z0-9_-]{2,63}',p.tenant_id)
                       or not p.name.strip() or not p.subject or not p.report_ids for p in people)):
            deny('L2_IDENTITY_CONFIGURATION_DENIED')
        self.mode,self.clock = mode,clock
        self.revoked_keys=set()
        self.sessions,self.challenges,self.actions,self.seen = {},{},{},{}
        self.boot=secrets.token_hex(32)
        self.last=0
        self.lock=threading.RLock()

    def now(self):
        now=self.clock()
        if type(now) not in (int,float) or not math.isfinite(now) or now<=0 or now<self.last:
            deny('L2_IDENTITY_UNAVAILABLE')
        self.last=now
        if self.expires<=now:
            deny('L2_IDENTITY_UNAVAILABLE')
        self.sessions={k:v for k,v in self.sessions.items() if v.expires>now}
        self.challenges={k:v for k,v in self.challenges.items() if v[1]>now}
        self.actions={k:v for k,v in self.actions.items() if v[2]>now}
        self.seen={k:v for k,v in self.seen.items() if v>now}
        return now

    def generation(self):
        return hashlib.sha256((self.boot+self.issuer+self.audience+self.mode+json.dumps(self.jwks,sort_keys=True)).encode()).hexdigest()

    def challenge(self):
        with self.lock:
            now=self.now()
            if len(self.challenges)>=128:
                deny()
            nonce,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
            self.challenges[nonce]=(csrf,now+60)
            return nonce,csrf

    def login(self, bearer, nonce, csrf):
        try:
            with self.lock:
                now=self.now()
                challenge=self.challenges.pop(nonce,None)
                if challenge is None or not secrets.compare_digest(challenge[0],csrf) or challenge[1]<=now:
                    deny()
                if not bearer.startswith('Bearer ') or len(bearer)>8192:
                    deny()
                h,p,sig=bearer[7:].split('.')
                header,claims=document(decode(h)),document(decode(p))
                if set(header)!={'alg','kid','typ'} or header['alg']!='EdDSA' or header['typ']!='vrae-responsible-review+jwt':
                    deny()
                keys=[k for k in self.jwks['keys'] if k['kid']==header['kid']]
                if len(keys)!=1 or header['kid'] in self.revoked_keys:
                    deny()
                key=keys[0]
                if key['kty']!='OKP' or key['crv']!='Ed25519' or key.get('use')!='sig' or key.get('alg')!='EdDSA':
                    deny()
                Ed25519PublicKey.from_public_bytes(decode(key['x'])).verify(decode(sig),(h+'.'+p).encode())
                required={'iss','aud','sub','iat','nbf','exp','jti','nonce','acr'}
                if set(claims)!=required or any(type(claims[k]) is not int for k in ('iat','nbf','exp')):
                    deny()
                if (claims['iss']!=self.issuer or claims['aud']!=self.audience or claims['nonce']!=nonce
                        or not now-300<=claims['iat']<=now+5 or claims['nbf']>now+5
                        or not claims['iat']<=claims['nbf']<claims['exp']
                        or not now<claims['exp']<=claims['iat']+300):
                    deny()
                expected='CONTROLLED_TEST_PERSON' if self.mode=='CONTROLLED' else 'VERIFIED_PERSON_MFA'
                if claims['acr']!=expected or type(claims['jti']) is not str or not 16<=len(claims['jti'])<=128:
                    deny()
                replay=hashlib.sha256((self.issuer+'\0'+claims['jti']).encode()).digest()
                if replay in self.seen or len(self.seen)>=4096 or len(self.sessions)>=64:
                    deny()
                self.seen[replay]=claims['exp']
                person=self.people.get(claims['sub'])
                if person is None or not person.active:
                    deny()
                if self.mode=='VERIFIED_DIRECTORY' and not person.verification_ref:
                    deny()
                sid=secrets.token_urlsafe(32)
                self.sessions[hashlib.sha256(sid.encode()).digest()]=Session(
                    person,min(claims['exp'],self.expires),header['kid'],self.generation(),{})
                return sid
        except Exception:
            deny('L2_LOGIN_DENIED')

    def require(self, sid, report_id=None):
        with self.lock:
            self.now()
            if type(sid) is not str or not 32<=len(sid)<=128:
                deny()
            s=self.sessions.get(hashlib.sha256(sid.encode()).digest())
            if (s is None or s.key_id in self.revoked_keys or s.generation!=self.generation()
                    or self.people.get(s.person.subject)!=s.person or not s.person.active
                    or (report_id is not None and report_id not in s.person.report_ids)):
                deny()
            return s

    def action(self,sid,path):
        with self.lock:
            session=self.require(sid)
            if len(self.actions)>=512:
                deny()
            value=secrets.token_urlsafe(32)
            self.actions[hashlib.sha256(value.encode()).digest()]=(sid,path,session.expires)
            return value

    def consume(self,sid,path,value):
        with self.lock:
            self.require(sid)
            if type(value) is not str or len(value)>128:
                deny()
            held=self.actions.pop(hashlib.sha256(value.encode()).digest(),None)
            if held is None or held[:2]!=(sid,path):
                deny('L2_ACTION_DENIED')

"""CONTROLLED fixture issuer outside SSR; no real-person assurance is asserted."""
import base64
import json
from pathlib import Path
import secrets
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from vrae.identity.boundary import TrustAnchor
from vrae.l2.identity import Directory, Person
from vrae.l2.ledger import Ledger
from vrae.l2.report import OfflineSource
from apps.operator_console.l2_http import DeepConsole
from apps.operator_console.b5a_http import Application as Base
from apps.operator_console.b5a_sessions import SessionStore
from apps.operator_console.b5p0_http import RehearsalApplication
from apps.operator_console.b5p0_journal import Journal
from apps.operator_console.b5b_http import Application
from vrae.b6_p0.reader import PrivateHandoffReader

ROOT=Path(__file__).resolve().parents[2]
PIN='0734221083be47b3e91bbb8e3bb3c790af2577c1b2a922e509eba85c486768b7'
REPORT='l2-pump-maker'


def b64(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


class Issuer:
    issuer='https://l2-controlled-issuer.invalid'
    audience='vrae-l2-private-review'

    def __init__(self,clock=time.time):
        self.key=Ed25519PrivateKey.generate()
        self.clock=clock
        self.kid='controlled-'+secrets.token_hex(8)
        self.jwks={'keys':[{'kty':'OKP','crv':'Ed25519','alg':'EdDSA','use':'sig','kid':self.kid,
            'x':b64(self.key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw))}]}

    def token(self,subject,nonce,**overrides):
        now=int(self.clock())
        claims={'iss':self.issuer,'aud':self.audience,'sub':subject,'iat':now,'nbf':now,'exp':now+300,
            'jti':secrets.token_urlsafe(24),'nonce':nonce,'acr':'CONTROLLED_TEST_PERSON',**overrides}
        header={'alg':'EdDSA','kid':self.kid,'typ':'vrae-responsible-review+jwt'}
        h,p=(b64(json.dumps(v,separators=(',',':')).encode()) for v in (header,claims))
        return 'Bearer '+h+'.'+p+'.'+b64(self.key.sign((h+'.'+p).encode()))


def people():
    return [Person('owner-demo','owner-demo','受控负责人（虚构身份）','tenant-example','OWNER',(REPORT,)),
        Person('reviewer-demo','reviewer-demo','受控专业审阅员（虚构身份）','tenant-example','REVIEWER',(REPORT,)),
        Person('recipient-a','recipient-a','受控接收者 A（虚构身份）','tenant-example','READER',(REPORT,)),
        Person('recipient-b','recipient-b','受控接收者 B（虚构身份）','tenant-example','READER',(REPORT,)),
        Person('other-tenant','other-tenant','其他租户受控身份','tenant-beta','REVIEWER',(REPORT,))]


def create(folder,clock=time.time):
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    issuer=Issuer(clock)
    directory=Directory(issuer=issuer.issuer,audience=issuer.audience,jwks=issuer.jwks,
        people=people(),expires=int(clock())+3600,clock=clock)
    source=OfflineSource(ROOT/'fixtures/l2/pump-maker-v1',PIN)
    ledger=Ledger(folder/'l2.sqlite',source,directory)
    deep=DeepConsole(directory,{REPORT:ledger})
    # Empty original lanes: no counterfeit M1 job, assignment, report or PG grant.
    anchor=TrustAnchor(issuer.issuer,issuer.audience,json.dumps(issuer.jwks).encode(),int(clock())+3600)
    legacy=SessionStore(anchor=anchor,bindings={},readers={})
    base=Base(legacy,{})
    rehearsal=RehearsalApplication(base,{},Journal(folder/'legacy-empty.sqlite'),key_secret=secrets.token_bytes(32))
    app=Application(rehearsal,PrivateHandoffReader(legacy,{}),deep=deep)
    return issuer,directory,ledger,app


def login(issuer,directory,subject):
    nonce,csrf=directory.challenge()
    return directory.login(issuer.token(subject,nonce),nonce,csrf)


def pins(view):
    return {'version':view.version['version'],'content_hash':view.version['content_hash'],'display_hash':view.display_hash}


def approve(issuer,directory,ledger,subject='reviewer-demo',action='APPROVE'):
    sid=login(issuer,directory,subject)
    view=ledger.read(sid,REPORT)
    receipt=ledger.review(sid,REPORT,**pins(view),action=action,
        reason='受控演练：逐项核对来源、假设、UNKNOWN和蓝图边界；不是真实人审。',
        items={r['id']:'ACK' for r in view.document['findings']+view.document['blueprint']},attest=True)
    return sid,view,receipt

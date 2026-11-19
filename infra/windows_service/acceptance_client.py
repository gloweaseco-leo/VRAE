"""External sequential live capture; private session state is sealed to operator key."""
import base64
from datetime import datetime,UTC
import hashlib
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import secrets
import ssl
import tempfile
import time
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey,X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes,serialization
from infra.windows_service.external_probe import Connection

from integration.l2_launch.g1.http_server import MEDIA


def seal(public,state):
    key=X25519PrivateKey.generate()
    peer=X25519PublicKey.from_public_bytes(bytes.fromhex(public))
    secret=HKDF(algorithm=hashes.SHA256(),length=32,salt=None,info=b'vrae-acceptance-session-v1').derive(key.exchange(peer))
    nonce=secrets.token_bytes(12)
    raw=AESGCM(secret).encrypt(nonce,json.dumps(state).encode(),b'vrae-acceptance-session-v1')
    return {'ephemeral_public':key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex(),
            'nonce':nonce.hex(),'ciphertext':base64.b64encode(raw).decode()}


def execute(cfg,root,events,state):
    ctx=ssl.create_default_context()
    ctx.load_cert_chain(root/'certificate.pem',root/'key.pem')
    def call(name,method,path,body=None,subject=None,expect=200,media=MEDIA):
        c=Connection(cfg['host'],443,ctx)
        headers={'Accept':media,'Authorization':'Bearer '+cfg['api_bearer']}
        if subject and subject.get('cookie'):
            headers.update({'Cookie':subject['cookie'],'X-CSRF-Token':subject['csrf']})
        if body is not None:
            headers['Content-Type']=MEDIA
        try:
            c.connect()
            peer=c.sock.getpeername()[0]
            cert=hashlib.sha256(c.sock.getpeercert(binary_form=True)).hexdigest()
            c.request(method,path,None if body is None else json.dumps(body).encode(),headers)
            r=c.getresponse()
            raw=r.read(262145)
            assert len(raw)<=262144
            doc=json.loads(raw)
            event={'case':name,'status':r.status,'expected':expect,'passed':r.status==expect,
                   'response_sha256':hashlib.sha256(raw).hexdigest(),'peer':peer,'server_certificate_sha256':cert}
            if r.status!=expect:
                event['error_code']=doc.get('reason',doc.get('error',{}).get('code') if isinstance(doc.get('error'),dict) else doc.get('code'))
            events.append(event)
            assert r.status==expect,name+' status '+str(r.status)
            return doc,dict(r.getheaders())
        finally:
            c.close()
    contract,_=call('intake-contract','GET','/v1/target-intake-contract',media='application/json')
    assert contract['limits']['concurrent_worker']==1
    for invited in cfg['acceptance_invitations']:
        subject=state.setdefault(invited['subject_ref'],{})
        if not subject.get('cookie'):
            _,h=call('invitation-'+invited['subject_ref'],'POST','/v1/invitation-session',{'invitation_token':invited['invitation_token']})
            cookie=SimpleCookie()
            cookie.load(h['Set-Cookie'])
            subject.update(cookie='__Host-vrae-targets='+cookie['__Host-vrae-targets'].value,csrf=h['X-CSRF-Token'])
        if not subject.get('authorized'):
            app,_=call('application-'+invited['subject_ref'],'POST','/v1/target-applications',{
                'url':cfg['acceptance_source'],'paths':cfg.get('acceptance_paths',['/products','/contact']),
                'consent':{'version':contract['consent_version'],'read_only_authorized':True,'model_data_notice':True}},subject,201)
            assert app['proof']['type']=='OPERATOR_OWNED_PUBLIC_ORIGIN'
            auth,_=call('authorize-'+invited['subject_ref'],'POST','/v1/target-applications/authorize',
                        {'application_token':app['application_token']},subject,201)
            subject['authorized']=auth['target_id']
        if 'submission' not in subject:
            subject['submission']={'url':cfg['acceptance_source'],'idempotency_key':'live-'+secrets.token_hex(16),
                'accepted_at':datetime.now(UTC).isoformat(),'consent_version':contract['consent_version'],'language':'zh'}
        accepted,_=call('submit-'+invited['subject_ref'],'POST','/v1/diagnoses',subject['submission'],subject,202)
        subject['audit_ref']=accepted['audit_ref']
        repeated,_=call('same-intent-'+invited['subject_ref'],'POST','/v1/diagnoses',subject['submission'],subject,202)
        assert repeated==accepted
        call('changed-intent-'+invited['subject_ref'],'POST','/v1/diagnoses',{**subject['submission'],'language':'en'},subject,409)
        deadline=time.monotonic()+150
        while True:
            status,_=call('status-'+invited['subject_ref'],'GET','/v1/audits/'+accepted['audit_ref'],subject=subject)
            subject['last_status']=status
            # Inspect the original nested task status, never infer completion from HTTP200.
            value=status['task']['status']
            if value=='DRAFT_READY':
                break
            if value=='FAILED' or time.monotonic()>deadline:
                raise RuntimeError('ACTUAL_WORKER_NOT_DRAFT_READY')
            time.sleep(5)
        call('historical-report-denied-'+invited['subject_ref'],'GET','/v1/audits/'+accepted['audit_ref']+'/report',subject=subject,expect=403)
        for previous,old in state.items():
            if previous!=invited['subject_ref'] and old.get('audit_ref'):
                call('cross-subject-denied-'+invited['subject_ref'],'GET','/v1/audits/'+old['audit_ref'],subject=subject,expect=403)
    return {'sequential_subjects':list(state),'real_customer_sources':False,'complete':True}


def main():
    cfg=json.loads(os.environ.pop('VRAE_WINDOWS_PUBLIC_MTLS'))
    events=[]
    state=cfg.get('acceptance_state',{})
    root=Path('public-receipts')
    root.mkdir(exist_ok=True)
    result={'contract':'vrae.actual-public-capture.v1','complete':False,'events':events}
    try:
        with tempfile.TemporaryDirectory(prefix='vrae-live-') as temp:
            private=Path(temp)
            private.chmod(0o700)
            for field in ('certificate','key'):
                p=private/(field+'.pem')
                p.write_text(cfg[field+'_pem'])
                p.chmod(0o600)
            result.update(execute(cfg,private,events,state))
    except Exception as error:
        result['failure_type']=type(error).__name__
        raise
    finally:
        (root/'capture.json').write_text(json.dumps(result))
        (root/'sessions-sealed.json').write_text(json.dumps(seal(cfg['acceptance_public_key'],state)))


if __name__=='__main__':
    main()

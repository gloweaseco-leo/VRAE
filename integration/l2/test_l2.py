"""Meaningful content/provenance, actual durable CAS and directed access checks."""
import copy
from dataclasses import replace
import hashlib
import json
import shutil

import pytest

from vrae.domain.errors import DomainError
from vrae.l2.report import OfflineSource, L2Denied, encoded
from .support import ROOT, REPORT, PIN, create, login, pins, approve


def test_committed_review_artifacts_preserve_original_byte_hashes():
    root=ROOT/'docs/03-engineering/l2-deep-audit/sample'
    manifest=json.loads((root/'publication.json').read_text(encoding='utf-8'))
    for name,meta in manifest['files'].items():
        raw=(root/name).read_bytes()
        assert len(raw)==meta['bytes'] and hashlib.sha256(raw).hexdigest()==meta['sha256'],name


def test_deep_content_is_actionable_and_unknown_is_not_failure(tmp_path):
    issuer,directory,ledger,_=create(tmp_path)
    sid=login(issuer,directory,'reviewer-demo')
    view=ledger.read(sid,REPORT)
    d=view.document
    assert len(d['journey'])==5 and len(d['blueprint'])==6
    assert {f['id'] for f in d['findings'] if f['priority']=='P1'}=={'f-rfq404','f-curve'}
    assert all(f['priority']=='UNRANKED' and not f['evidence_ids'] and f['severity'] is None
               for f in d['findings'] if f['kind']=='UNKNOWN')
    assert all(b['customer_inputs'] and b['acceptance'] and b['finding_ids'] and b['owner_role'] for b in d['blueprint'])
    assert d['service_catalog']['price']=='UNKNOWN' and '承诺' in d['service_catalog']['verification']
    assert {b['service_fit'] for b in d['blueprint']}=={'STANDARD_CANDIDATE','CUSTOM_ASSESSMENT'}


def test_source_change_and_forged_quote_are_not_trusted(tmp_path):
    root=tmp_path/'source'
    shutil.copytree(ROOT/'fixtures/l2/pump-maker-v1',root)
    source=OfflineSource(root,PIN)
    source.read()
    path=root/'snapshots/contact.html'
    path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises(L2Denied,match='SOURCE_CHANGED'):
        source.read()
    source=OfflineSource(ROOT/'fixtures/l2/pump-maker-v1',PIN)
    d=source.read().document
    d['findings'][0]['statement']='虚构损失和客户结论'
    with pytest.raises(L2Denied,match='SOURCE_FACTS_IMMUTABLE'):
        source.validate(d)
    d=source.read().document
    d['evidence'][0]['quote']='not in source'
    with pytest.raises(L2Denied):
        source.validate(d)


def test_authentication_replay_and_claimed_role_cannot_set_authority(tmp_path):
    issuer,directory,ledger,_=create(tmp_path)
    nonce,csrf=directory.challenge()
    token=issuer.token('reviewer-demo',nonce,role='OWNER')
    with pytest.raises(L2Denied,match='LOGIN_DENIED'):
        directory.login(token,nonce,csrf)
    nonce,csrf=directory.challenge()
    token=issuer.token('reviewer-demo',nonce)
    sid=directory.login(token,nonce,csrf)
    with pytest.raises(L2Denied):
        directory.login(token,nonce,csrf)
    with pytest.raises(L2Denied):
        ledger.read(login(issuer,directory,'other-tenant'),REPORT)
    with pytest.raises(L2Denied):
        ledger.read(login(issuer,directory,'recipient-a'),REPORT)
    directory.people['reviewer-demo']=replace(directory.people['reviewer-demo'],active=False)
    with pytest.raises(L2Denied):
        ledger.read(sid,REPORT)


def test_each_item_and_exact_full_view_hash_are_required(tmp_path):
    issuer,directory,ledger,_=create(tmp_path)
    sid=login(issuer,directory,'reviewer-demo')
    view=ledger.read(sid,REPORT)
    item_keys={r['id']:'ACK' for r in view.document['findings']+view.document['blueprint']}
    for override in [dict(version=2),dict(content_hash='0'*64),dict(display_hash='0'*64)]:
        with pytest.raises(L2Denied,match='STALE_VERSION'):
            ledger.review(sid,REPORT,**{**pins(view),**override},action='APPROVE',reason='测试',items=item_keys,attest=True)
    with pytest.raises(L2Denied,match='EVERY_ITEM'):
        ledger.review(sid,REPORT,**pins(view),action='APPROVE',reason='测试',items={},attest=True)
    with pytest.raises(L2Denied,match='UNRESOLVED'):
        ledger.review(sid,REPORT,**pins(view),action='APPROVE',reason='测试',items={**item_keys,'f-curve':'REJECT'},attest=True)
    assert not ledger.history(sid,REPORT)[1]


def test_controlled_review_never_becomes_formal_human_approval(tmp_path):
    issuer,directory,ledger,_=create(tmp_path)
    _,_,receipt=approve(issuer,directory,ledger)
    assert receipt['scope']=='CONTROLLED_REVIEW_SIMULATION'
    assert receipt['formal_human_review'] is False and receipt['identity_verification_ref'] is None
    assert receipt['identity_subject']=='reviewer-demo' and receipt['identity_issuer']==issuer.issuer
    nonce,csrf=directory.challenge()
    with pytest.raises(L2Denied):
        directory.login(issuer.token('reviewer-demo',nonce,acr='VERIFIED_PERSON_MFA'),nonce,csrf)


def test_revision_is_append_only_and_new_version_invalidates_old_access(tmp_path):
    issuer,directory,ledger,_=create(tmp_path)
    _,view,receipt=approve(issuer,directory,ledger)
    owner=login(issuer,directory,'owner-demo')
    grant,token=ledger.issue(owner,REPORT,**pins(view),recipient_id='recipient-a')
    reader=login(issuer,directory,'recipient-a')
    token_hash=hashlib.sha256(token.encode()).hexdigest()
    assert ledger.access(reader,REPORT,grant['grant_id'],token_hash).payload==view.payload
    updated=ledger.revise(owner,REPORT,**pins(view),changes={'bp-rfq':'先由销售确认收件路径；只调整已获准的产品模板与型号上下文，投递仍另行授权。'})
    assert updated.version['version']==2 and updated.display_hash!=view.display_hash
    assert updated.version['content_hash']!=view.version['content_hash']
    assert updated.document['evidence']==view.document['evidence']
    assert ledger.read(owner,REPORT,1).payload==view.payload
    assert ledger.history(owner,REPORT)[1][0]==receipt
    with pytest.raises(L2Denied):
        ledger.access(reader,REPORT,grant['grant_id'],token_hash)
    with pytest.raises(L2Denied,match='STALE_VERSION'):
        ledger.revise(owner,REPORT,**pins(view),changes={'bp-rfq':'旧版本重复提交'})


def test_revocation_expiry_wrong_recipient_and_no_plaintext_token(tmp_path):
    clock=[1_800_000_000]
    issuer,directory,ledger,_=create(tmp_path,clock=lambda:clock[0])
    _,view,_=approve(issuer,directory,ledger)
    owner=login(issuer,directory,'owner-demo')
    grant,token=ledger.issue(owner,REPORT,**pins(view),recipient_id='recipient-a',ttl=30)
    digest=hashlib.sha256(token.encode()).hexdigest()
    reader=login(issuer,directory,'recipient-a')
    other=login(issuer,directory,'recipient-b')
    with pytest.raises(L2Denied):
        ledger.access(other,REPORT,grant['grant_id'],digest)
    with pytest.raises(L2Denied):
        ledger.access(reader,REPORT,grant['grant_id'],'0'*64)
    ledger.access(reader,REPORT,grant['grant_id'],digest)
    assert token.encode() not in ledger.path.read_bytes()
    clock[0]+=31
    with pytest.raises(DomainError):
        ledger.access(reader,REPORT,grant['grant_id'],digest)
    grant,token=ledger.issue(owner,REPORT,**pins(view),recipient_id='recipient-a')
    ledger.revoke(owner,REPORT,grant['grant_id'])
    with pytest.raises(DomainError):
        ledger.access(reader,REPORT,grant['grant_id'],hashlib.sha256(token.encode()).hexdigest())


def test_rejected_or_changed_decision_cannot_keep_old_grant(tmp_path):
    issuer,directory,ledger,_=create(tmp_path)
    _,view,_=approve(issuer,directory,ledger)
    owner=login(issuer,directory,'owner-demo')
    grant,token=ledger.issue(owner,REPORT,**pins(view),recipient_id='recipient-a')
    approve(issuer,directory,ledger,action='REQUEST_CHANGES')
    with pytest.raises(DomainError):
        ledger.access(login(issuer,directory,'recipient-a'),REPORT,grant['grant_id'],hashlib.sha256(token.encode()).hexdigest())
    approve(issuer,directory,ledger)
    with pytest.raises(L2Denied,match='STALE_GRANT'):
        ledger.access(login(issuer,directory,'recipient-a'),REPORT,grant['grant_id'],hashlib.sha256(token.encode()).hexdigest())


def test_restart_reads_same_versions_decisions_and_revocation(tmp_path):
    issuer,directory,ledger,_=create(tmp_path)
    _,view,receipt=approve(issuer,directory,ledger)
    old=login(issuer,directory,'owner-demo')
    grant,_=ledger.issue(old,REPORT,**pins(view),recipient_id='recipient-a')
    ledger.revoke(old,REPORT,grant['grant_id'])
    issuer2,directory2,ledger2,_=create(tmp_path)
    with pytest.raises(L2Denied):
        ledger2.read(old,REPORT)
    fresh=login(issuer2,directory2,'owner-demo')
    assert ledger2.read(fresh,REPORT).payload==view.payload
    assert ledger2.history(fresh,REPORT)[1][0]==receipt
    assert ledger2.history(fresh,REPORT)[2][0]['status']=='REVOKED'


def test_formal_mode_requires_separate_verified_directory_and_cannot_share_externally(tmp_path):
    from vrae.l2.identity import Directory
    from .support import Issuer,people
    issuer=Issuer()
    with pytest.raises(L2Denied,match='VERIFIED_PERSON_DIRECTORY_REQUIRED'):
        Directory(issuer=issuer.issuer,audience=issuer.audience,jwks=issuer.jwks,
                  people=people(),expires=2_000_000_000,mode='VERIFIED_DIRECTORY')


def test_verified_directory_protocol_branch_is_attributed_but_external_access_stays_closed(tmp_path):
    """A mock IdP/directory branch test, NOT evidence of any actual human review."""
    import time
    from vrae.l2.identity import Directory
    from vrae.l2.ledger import Ledger
    from .support import Issuer,people
    issuer=Issuer()
    registered=[replace(p,verification_ref='fixture-directory-attestation-not-real-person') for p in people()]
    directory=Directory(issuer=issuer.issuer,audience=issuer.audience,jwks=issuer.jwks,people=registered,
                        expires=int(time.time())+3600,mode='VERIFIED_DIRECTORY')
    source=OfflineSource(ROOT/'fixtures/l2/pump-maker-v1',PIN)
    ledger=Ledger(tmp_path/'verified-protocol.sqlite',source,directory)
    def signed(subject):
        nonce,csrf=directory.challenge()
        return directory.login(issuer.token(subject,nonce,acr='VERIFIED_PERSON_MFA'),nonce,csrf)
    reviewer=signed('reviewer-demo')
    view=ledger.read(reviewer,REPORT)
    receipt=ledger.review(reviewer,REPORT,**pins(view),action='APPROVE',reason='协议分支单元测试，不是实际人审。',
        items={r['id']:'ACK' for r in view.document['findings']+view.document['blueprint']},attest=True)
    assert receipt['scope']=='RESPONSIBLE_PERSON_REVIEW' and receipt['identity_subject']=='reviewer-demo'
    assert receipt['identity_verification_ref']=='fixture-directory-attestation-not-real-person'
    with pytest.raises(L2Denied,match='EXTERNAL_ACCESS_NOT_ENABLED'):
        ledger.issue(signed('owner-demo'),REPORT,**pins(view),recipient_id='recipient-a')


def test_actual_existing_ssr_headers_and_signed_http_entry(tmp_path):
    from contextlib import closing
    from http.client import HTTPConnection
    import re
    import threading
    from urllib.parse import urlencode
    from apps.operator_console.b5a_http import server
    issuer,directory,_,app=create(tmp_path)
    http=server(app)
    thread=threading.Thread(target=http.serve_forever,daemon=True)
    thread.start()
    def call(method,path,body=b'',headers=None):
        with closing(HTTPConnection('127.0.0.1',http.server_port,timeout=10)) as conn:
            conn.request(method,path,body,{'Origin':app.origin,**(headers or {})})
            response=conn.getresponse()
            return response.status,response.read(),dict(response.getheaders())
    try:
        status,body,headers=call('GET','/b5a/l2/')
        assert status==200 and headers['Cache-Control']=='no-store'
        assert "script-src 'none'" in headers['Content-Security-Policy'] or "default-src 'none'" in headers['Content-Security-Policy']
        csrf=re.search(rb'name="_csrf" value="([^"]+)"',body)[1].decode()
        status,body,_=call('POST','/b5a/l2/challenge',urlencode({'_csrf':csrf}).encode(),{'Content-Type':'application/x-www-form-urlencoded'})
        assert status==200
        challenge=json.loads(body)
        bearer=issuer.token('reviewer-demo',challenge['nonce'])
        status,body,headers=call('POST','/b5a/l2/session',b'{}',{'Content-Type':'application/json',
            'Authorization':bearer,'X-L2-Nonce':challenge['nonce'],'X-L2-CSRF':challenge['csrf']})
        assert status==303 and bearer.encode() not in body
        cookie=headers['Set-Cookie'].split(';')[0]
        assert 'HttpOnly' in headers['Set-Cookie'] and 'SameSite=Strict' in headers['Set-Cookie']
        status,body,_=call('GET','/b5a/l2/r/'+REPORT,headers={'Cookie':cookie})
        assert status==200 and '工业采购商实际要完成什么'.encode() in body and '<script'.encode() not in body
        assert call('GET','/b5a/l2/r/'+REPORT,headers={'Cookie':cookie,'X-Role':'OWNER'})[0]==403
        assert call('POST','/b5a/l2/r/'+REPORT+'/review',b'',{'Cookie':cookie,'Origin':'https://forged.invalid'})[0]==403
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=5)


def test_l1_l2_navigation_share_one_original_application_without_forged_job(tmp_path):
    from vrae.identity.boundary import TrustAnchor
    from vrae.application.ra4b_p2.m1.reader import SignedGeneratedReader
    from apps.operator_console.b5b_m2_sessions import GeneratedSessions
    from apps.operator_console.b5b_m2_http import GeneratedConsole
    from apps.operator_console.b5b_http import Application
    issuer,directory,_,old=create(tmp_path)
    anchor=TrustAnchor(issuer.issuer,issuer.audience,json.dumps(issuer.jwks).encode(),2_000_000_000)
    def no_db(_):
        raise AssertionError('NO_M1_JOB_OR_ASSIGNMENT_MAY_BE_FABRICATED')
    generated=GeneratedConsole(GeneratedSessions(SignedGeneratedReader(anchor=anchor,assignments=[],connect=no_db)),{})
    app=Application(old.rehearsal,old.handoff,generated=generated,deep=old.deep)
    app.origin='http://127.0.0.1:11111'
    headers={'Host':'127.0.0.1:11111'}
    reply=app.handle('GET','/b5a/m2/',headers)
    assert reply.response.status==200 and b'data-key="l2-entry"' in reply.response.body
    reply=app.handle('GET','/b5a/l2/',headers)
    assert reply.response.status==200 and b'data-key="l2-back-to-l1"' in reply.response.body
    assert not generated.sessions.reader.assignments


def test_approval_bytes_cannot_be_edited_in_sqlite_without_detection(tmp_path):
    issuer,directory,ledger,_=create(tmp_path)
    sid=login(issuer,directory,'owner-demo')
    view=ledger.read(sid,REPORT)
    mutated=copy.deepcopy(view.document)
    mutated['findings'][0]['statement']='unsupported change'
    with ledger.connection() as c:
        c.execute('UPDATE versions SET payload=?,display_hash=?',(encoded(mutated),hashlib.sha256(encoded(mutated)).hexdigest()))
    with pytest.raises(L2Denied,match='SOURCE_FACTS_IMMUTABLE'):
        ledger.read(sid,REPORT)


def test_consumer_fixture_bytes_and_hash_pin_are_deterministic():
    path=ROOT/'fixtures/l2/pump-maker-v1/result.json'
    assert hashlib.sha256(path.read_bytes()).hexdigest()==PIN
    assert json.loads(path.read_bytes())['meta']['source_mode']=='SYNTHETIC_OFFLINE'

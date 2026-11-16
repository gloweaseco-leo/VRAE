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
from .support import Issuer, people
import sqlite3
from integration.industry_l2.fixture import evidence_pack, DIRECTORY
from vrae.collection.manifest import document_hash
from vrae.evidence import EvidencePack
from vrae.industry.l2_v1 import diagnose, load
from vrae.l2.identity import Directory
from vrae.l2.ledger import Ledger
from vrae.l2.report import sha
from vrae.l2.native import NativeSource, NativeTask, ASSURANCE, current_report


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


# Native production component checks remain in the existing explicit CI entrypoint.
def assemble(pack):
    industry=load(tenant_id=pack.document['tenant_id'])
    diagnosis=diagnose(pack,expected_pack_ref=pack.ref,expected_industry_ref=industry['industry_ref'])
    held=NativeTask(pack.document['tenant_id'],'component-request-not-app202',pack.document['run_id'],
        'component-job-not-worker','component-event','component-source',pack.ref,industry['industry_ref'],
        diagnosis['diagnosis_ref'],'1'*64,'OFFLINE_SYNTHETIC','2026-11-16T12:00:00+00:00')
    return pack,diagnosis,held,NativeSource(pack,diagnosis,held=held)


@pytest.fixture(scope='module')
def native():
    pack,_,transport=evidence_pack()
    result=assemble(pack)
    assert all(method=='GET' for method,_ in transport.requests)
    return result


def reviewed(tmp_path,source,action='APPROVE'):
    issuer=Issuer()
    rid=source.read().version['report_id']
    directory=Directory(issuer=issuer.issuer,audience=issuer.audience,jwks=issuer.jwks,
        people=[replace(p,report_ids=(rid,)) for p in people()],expires=issuer.clock()+3600)
    ledger=Ledger(tmp_path/'native.sqlite',source,directory)
    sid=login(issuer,directory,'owner-demo')
    view=ledger.read(sid,rid)
    receipt=ledger.review(sid,rid,**pins(view),action=action,
        reason='组件原生数据逐项受控复核；非正式人审，不代表同一Worker E2E。',
        items={r['id']:'ACK' if action=='APPROVE' else action for r in view.document['findings']+view.document['blueprint']},attest=True)
    return issuer,directory,ledger,sid,rid,view,receipt


def test_native_c1_rows_and_all_original_bytes_survive(native):
    pack,data,held,source=native
    view=source.read()
    doc=view.document
    assert view.findings==[a['finding'] for a in data['assessments']]
    assert len(view.findings)==19 and len(doc['snapshots'])==8 and len(data['source_facts'])==81
    assert doc['producer']['assurance']==ASSURANCE
    assert doc['native_context']==json.loads(encoded(held.__dict__))
    assert {o['sha256'] for o in doc['producer']['source_descriptor']['objects']}==set(pack.objects)
    refs={e['id']:e for e in doc['evidence']}
    assert set(e['evidence_ref'] for e in pack.document['evidence'])<=refs.keys()
    for fact in data['source_facts']:
        e=refs[fact['fact_ref']]
        body=source.object_bytes(e['blob_ref'])
        assert body==pack.objects[e['blob_ref']] and sha(body)==e['content_sha256']
        assert body[e['byte_start']:e['byte_end']]==e['quote'].encode()
    assert doc['procurement_chains']==data['procurement_chains']
    assert doc['rfq_packets']==data['rfq_packets']
    assert doc['industry_rule_coverage']==data['industry_rule_coverage']


def test_procurement_semantics_not_mp25_or_four_site_faults(native):
    _,data,_,source=native
    doc=source.read().document
    assert 'MP25' not in source.read().payload.decode()
    assert {a['model'] for a in data['assessments']}=={'P40','V25'}
    assert sum(a['reason']=='EXPLICIT_SOURCE_SCALAR_CONFLICT' for a in data['assessments'])==2
    assert len(doc['findings'])==19 and not any(f['priority']=='P1' for f in doc['findings'])
    for f in doc['findings']:
        if f['native_rule_id']=='IND-DUTY':
            assert '工程' in f['statement'] or f['native_result']=='NOT_APPLICABLE'
        if f['kind']=='UNKNOWN':
            assert f['priority']=='UNRANKED' and f['evidence_ids']==[]
        if f['native_rule_id']=='IND-RFQ':
            assert '不是网站缺陷' in f['statement'] and '未发送' in f['statement']
        if f['native_rule_id']=='IND-PROOF':
            assert '不证明真实证书失效' in f['statement']
    proof=[b for b in doc['blueprint'] if b['title'].startswith('共享供应商')]
    assert len(proof)==1 and len(proof[0]['finding_ids'])==2
    assert all(b['evidence_ids'] and b['customer_inputs'] and b['acceptance'] and b['owner_role'] for b in doc['blueprint'])


@pytest.mark.parametrize('field,value',[
    ('tenant_id','other-tenant'),('run_id','other-run'),('native_pack_ref','ep-'+'0'*64),
    ('industry_ref','ip-'+'0'*64),('diagnosis_ref','l2-'+'0'*64)])
def test_held_refs_are_independent_and_mismatches_refuse(native,field,value):
    pack,data,held,_=native
    with pytest.raises(L2Denied):
        NativeSource(pack,data,held=replace(held,**{field:value}))


def test_forged_rehashed_guard_export_still_fails_full_native_replay(native):
    pack,data,held,_=native
    forged=copy.deepcopy(data)
    forged['source_guard_inputs'][0]['guard']['claims'][0]['status']='FAKE_VALID'
    forged.pop('diagnosis_ref')
    forged['diagnosis_ref']='l2-'+document_hash(forged)
    with pytest.raises(L2Denied,match='NATIVE_REPLAY_DENIED'):
        NativeSource(pack,forged,held=replace(held,diagnosis_ref=forged['diagnosis_ref']))


def test_changed_blob_and_changed_frozen_report_refuse(native,tmp_path):
    pack,data,held,source=native
    objects=dict(pack.objects)
    first=next(iter(objects))
    objects[first]+=b'altered'
    bad=EvidencePack(pack._payload,tuple(sorted(objects.items())))
    with pytest.raises(L2Denied):
        NativeSource(bad,data,held=held)
    edited=source.read().document
    edited['findings'][0]['statement']='MP25询价404'
    with pytest.raises(L2Denied):
        source.validate(edited)
    raw=source.read().payload
    (tmp_path/'result.json').write_bytes(raw)
    with pytest.raises(L2Denied):
        OfflineSource(tmp_path,sha(raw)).read()


@pytest.mark.parametrize('action,mapped',[('APPROVE','APPROVE_INTERNAL'),('REJECT','REJECT_INTERNAL'),('REQUEST_CHANGES','REVISE_INTERNAL')])
def test_actual_durable_receipt_and_c3_current_dto(native,tmp_path,action,mapped):
    # Existing accepted C3 contract is a validator here, not a copied E2E.
    from vrae.l2_ops.briefs import CurrentL2
    _,data,_,source=native
    _,directory,ledger,sid,rid,view,receipt=reviewed(tmp_path,source,action)
    assert not receipt['formal_human_review'] and not receipt['external_delivery']
    with current_report(ledger,sid,rid) as current:
        assert current.payload==data and current.report_bytes==view.payload
        assert current.pins['report_sha256']==view.display_hash
        assert current.pins['report_sha256']!=view.version['content_hash']
        assert current.pins['report_sha256']!=data['diagnosis_ref'][3:]
        assert current.review['receipt_ref']==receipt['decision']['decision_id']
        assert current.review['receipt_sha256']==sha(encoded(receipt))
        assert current.review['decision']==mapped
        dto=CurrentL2(current.pins,current.payload,current.review,current.blueprint,current.authority_expires_at)
        assert dto.snapshot()==(current.pins,current.payload,current.review,current.blueprint)
        with sqlite3.connect(ledger.path,timeout=0) as other:
            with pytest.raises(sqlite3.OperationalError,match='locked'):
                other.execute('BEGIN IMMEDIATE')
    restarted=Ledger(ledger.path,source,directory)
    with current_report(restarted,sid,rid) as current:
        assert current.report_bytes==view.payload and current.review['receipt_sha256']==sha(encoded(receipt))


def test_native_revision_requires_new_decision_and_invalidates_grant(native,tmp_path):
    *_,source=native
    issuer,directory,ledger,sid,rid,view,_=reviewed(tmp_path,source)
    grant,secret=ledger.issue(sid,rid,**pins(view),recipient_id='recipient-a')
    reader=login(issuer,directory,'recipient-a')
    assert ledger.access(reader,rid,grant['grant_id'],sha(secret.encode())).payload==view.payload
    updated=ledger.revise(sid,rid,**pins(view),changes={view.document['blueprint'][0]['id']:'企业确认技术资料版本后再调整资料卡；保持原生事实不变。'})
    assert updated.version['version']==2 and updated.findings==view.findings
    with pytest.raises(L2Denied):
        current_report(ledger,sid,rid).__enter__()
    with pytest.raises(L2Denied):
        ledger.access(reader,rid,grant['grant_id'],sha(secret.encode()))
    with pytest.raises(L2Denied,match='STALE_VERSION'):
        ledger.revise(sid,rid,**pins(view),changes={view.document['blueprint'][0]['id']:'错误版本'})


def test_native_unknown_input_is_not_a_site_failure():
    raw=(DIRECTORY/'pump.html').read_bytes().replace(b'10 bar',b'on request')
    pack,_,_=evidence_pack(overrides={'/products/pump-p40':raw})
    _,data,_,source=assemble(pack)
    native=[a for a in data['assessments'] if a['model']=='P40' and a['details'].get('attribute')=='pressure']
    assert native and all(a['observation']['result']=='UNKNOWN' for a in native)
    assert all(f['priority']=='UNRANKED' for f in source.read().document['findings'] if f['id'] in {a['finding']['finding_id'] for a in native})


def test_native_handoff_refuses_cross_tenant_or_relabelled_formal_receipt(native,tmp_path):
    *_,source=native
    issuer,directory,ledger,sid,rid,_,receipt=reviewed(tmp_path,source)
    wrong=login(issuer,directory,'other-tenant')
    with pytest.raises(L2Denied):
        with current_report(ledger,wrong,rid):
            pytest.fail('cross-tenant DTO must not be yielded')
    receipt['formal_human_review']=True
    with ledger.transaction() as c:
        c.execute('UPDATE decisions SET receipt=?',(encoded(receipt),))
    with pytest.raises(L2Denied,match='CONTROLLED_RECEIPT_REQUIRED'):
        with current_report(ledger,sid,rid):
            pytest.fail('a formal relabel is not a controlled receipt')

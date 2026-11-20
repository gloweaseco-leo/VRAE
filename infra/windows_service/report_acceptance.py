"""External real mTLS report recipient/read/isolation and revocation acceptance."""
import hashlib
import json
import os
from pathlib import Path
import ssl
import tempfile
from infra.windows_service.external_probe import Connection
from infra.windows_service.acceptance_client import seal
from integration.authorized_targets.report_api import MEDIA, BASE


def execute(cfg, private, events, sessions):
    grants=cfg.get('acceptance_grants',{})
    if not grants:
        return {'complete':False,'state':'AWAITING_ACTUAL_HUMAN_REVIEW_AND_DIRECTED_GRANT'}
    assert set(grants)=={'acceptance-a','acceptance-b'}
    state=cfg['acceptance_state']
    revoked=bool(cfg.get('acceptance_revoked'))
    ctx=ssl.create_default_context();ctx.load_cert_chain(private/'certificate.pem',private/'key.pem')
    def call(case,method,path,body=None,headers=None,expect=200,api=False):
        c=Connection(cfg['host'],443 if api else 8443,ctx)
        h={'Authorization':'Bearer '+cfg['api_bearer' if api else 'review_bearer'],
           'Accept':MEDIA,'X-Report-Profile':'VERIFIED_HUMAN_CUSTOMER_REPORT'}
        if body is not None:h['Content-Type']=MEDIA
        h.update(headers or {})
        try:
            c.connect();cert=hashlib.sha256(c.sock.getpeercert(binary_form=True)).hexdigest()
            c.request(method,path,None if body is None else json.dumps(body).encode(),h)
            r=c.getresponse();raw=r.read(2000001)
            assert len(raw)<=2000000
            events.append({'case':case,'status':r.status,'expected':expect,'passed':r.status==expect,
                           'response_sha256':hashlib.sha256(raw).hexdigest(),'server_certificate_sha256':cert})
            assert r.status==expect,case+' status '+str(r.status)
            assert r.getheader('X-VRAE-Source-SHA')==cfg['source_sha']
            assert 'no-store' in r.getheader('Cache-Control','')
            return json.loads(raw)
        finally:c.close()
    def exchange_body(subject,grant):
        s=state[subject]
        return {'audit_ref':grant['audit_ref'],'task_cookie':s['cookie'].split('=',1)[1],
                'task_csrf':s['csrf'],'grant_id':grant['grant_id'],'grant_token':grant['grant_token']}
    pins=[]
    for subject,g in grants.items():
        s=state[subject];assert s['audit_ref']==g['audit_ref']
        path=BASE+'/audits/'+g['audit_ref']
        # A valid task session before revoked-grant denial disambiguates expiry.
        if revoked:
            from integration.l2_launch.g1.http_server import MEDIA as TASK_MEDIA
            call('live-task-session-'+subject,'GET','/v1/audits/'+g['audit_ref'],
                 headers={'Cookie':s['cookie'],'X-CSRF-Token':s['csrf'],'Accept':TASK_MEDIA},api=True)
        call('service-only-report-denied-'+subject,'GET',path+'/report',expect=403)
        body=exchange_body(subject,g)
        result=call(('revoked-grant-denied-' if revoked else 'recipient-session-')+subject,
                    'POST',BASE+'/recipient-session',body,expect=403 if revoked else 200)
        if revoked:
            if subject in sessions:
                call('revoked-reader-denied-'+subject,'GET',path+'/report',headers={
                    'X-Report-Session':sessions[subject],'X-Report-Grant':g['grant_id'],
                    'X-Report-Token':g['grant_token']},expect=403)
            continue
        assert result['assurance']=='PG_INVITED_SUBJECT_AND_DIRECTED_GRANT_V1'
        assert result['grants_review_or_owner_role'] is False
        sid=result['report_session'];sessions[subject]=sid
        h={'X-Report-Session':sid,'X-Report-Grant':g['grant_id'],'X-Report-Token':g['grant_token']}
        report=call('formal-report-'+subject,'GET',path+'/report',headers=h)
        assert report['formal_human_review'] is True and report['external_release'] is True
        assert report['report_version']['status']=='APPROVED'
        assert report['review_decision']['reviewer_id']==g['reviewer_id']
        assert report['display_hash']==g['display_hash']
        assert report['report_version']['report_version_id']==g['report_version_id']
        assert report['report_version']['content_hash']==g['content_hash']
        assert report['report']['native_context']==g['native_context']
        assert report['report']['producer']['source_descriptor']['pack_ref']==g['pack_ref']
        assert report['report']['evidence']
        pins.append({'subject_ref':subject,'audit_ref':g['audit_ref'],'display_hash':g['display_hash'],
                     'pack_ref':g['pack_ref'],'formal_human_review':True,'exact_committed_report_verified':True})
        call('missing-grant-denied-'+subject,'GET',path+'/report',headers={'X-Report-Session':sid},expect=403)
        call('wrong-grant-token-denied-'+subject,'GET',path+'/report',headers={**h,'X-Report-Token':'x'*43},expect=403)
        for operation in ('decisions','grants'):
            call('reader-'+operation+'-denied-'+subject,'POST',path+'/actions',{'operation':operation},h,403)
        other=next(k for k in state if k!=subject)
        call('cross-subject-exchange-denied-'+subject,'POST',BASE+'/recipient-session',exchange_body(other,g),expect=403)
        call('cross-job-reader-denied-'+subject,'GET',BASE+'/audits/'+grants[other]['audit_ref']+'/report',headers=h,expect=403)
    return {'complete':True,'state':'REVOCATION_VERIFIED' if revoked else 'FORMAL_DIRECTED_READ_VERIFIED',
            'reports':pins,'external_network':True,'real_customer_sources':False}


def main():
    cfg=json.loads(os.environ.pop('VRAE_WINDOWS_PUBLIC_MTLS'))
    root=Path('public-receipts');root.mkdir(exist_ok=True)
    events=[];sessions=cfg.get('acceptance_reader_sessions',{})
    result={'contract':'vrae.actual-public-formal-report.v1','complete':False,'events':events}
    try:
        with tempfile.TemporaryDirectory(prefix='vrae-report-') as temp:
            private=Path(temp);private.chmod(0o700)
            for field in ('certificate','key'):
                p=private/(field+'.pem');p.write_text(cfg[field+'_pem']);p.chmod(0o600)
            result.update(execute(cfg,private,events,sessions))
    except Exception as error:
        result['failure_type']=type(error).__name__
        raise
    finally:
        (root/'formal-report.json').write_text(json.dumps(result))
        (root/'reader-sessions-sealed.json').write_text(json.dumps(seal(cfg['acceptance_public_key'],sessions)))


if __name__=='__main__':main()

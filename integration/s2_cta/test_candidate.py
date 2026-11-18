"""Synthetic parser fixtures are not Chrome proof; real capture runs in lab.py."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace as NS
import zlib

import pytest

from vrae.browser.controller import DOM_SCRIPT
from .candidate import ROOT, Receipt, CTADenied, context, sha
from . import views
from integration.s2_buyer_workbench.fixture import application
from integration.s2_buyer_workbench.test_workbench import headers
from integration.l2.support import login, pins
from dataclasses import replace


def png(width,height):
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\xff\xff\xff'*width)*height))+chunk(b'IEND',b'')


@pytest.fixture
def sample():
    runtime=ROOT/'integration/s2_buyer_workbench/.runtime'
    runtime.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='unit-cta-',dir=runtime) as folder:
        folder=Path(folder)
        report=NS(source_digest='s'*64,display_hash='d'*64,version={'report_version_id':'r.v1','content_hash':'c'*64})
        binding=NS(scope={'tenant_id':'unit-tenant','run_id':'unit-run','policy_id':'unit-policy','policy_version':1},
                   source=NS(held=NS(native_pack_ref='ep-'+'a'*64)),pins=NS(industry_ref='ip-'+'b'*64,profile_id='industrial',version='1.1.0'))
        data={'kind':'CONTROLLED_OFFLINE_CTA_SIDECAR','version':'c2-cta-offline-1.0.0',
              'fixtureSha256':sha((ROOT/'integration/s2_ux/fixture.html').read_bytes().replace(b'\r\n', b'\n')),
              'legacyScriptSha256':sha(DOM_SCRIPT.encode()),'observerSha256':sha((ROOT/'integration/s2_cta/capture.mjs').read_bytes()),
              'nativeFactAdmission':'NONE','responseObservation':'UNKNOWN','submission':'UNKNOWN','delivery':'UNKNOWN',
              'checks':[{'name':'UNIT_SYNTHETIC_NOT_CHROME_PROOF','pass':True}],'requests':[], 'records':[]}
        at=datetime.now(timezone.utc)
        for scenario in ('clean','hidden','covered','overflow'):
            for width in (390,375,320,1280):
                height=720 if width==1280 else 844
                url='https://synthetic.invalid/?case='+scenario
                dom={'title':'UNIT_NOT_BROWSER','url':url,'elements':[{'tag':'A','text':'Request a quote','visible':True},{'tag':'BUTTON','text':'Prepare RFQ','visible':True}]}
                targets=[{'id':identity,'tag':tag,'text':text,'href':href,'resolvedHref':'https://synthetic.invalid/rfq' if href else None,
                          'rect':{'x':20,'y':20,'width':150,'height':43},'opacity':0 if scenario=='hidden' else 1,
                          'inViewport':True,'centerOnTarget':scenario!='covered','display':'inline-block','visibility':'visible'}
                         for identity,tag,text,href in [('quote','A','Request a quote','/rfq'),('inquiry','BUTTON','Prepare RFQ',None)]]
                image=png(width,height)
                name=f'{scenario}-{width}.png'
                (folder/name).write_bytes(image)
                data['records'].append({'scenario':scenario,'width':width,'height':height,'url':url,'observedAt':at.isoformat(),
                                       'dom':dom,'domSha256':sha(json.dumps(dom,ensure_ascii=False,separators=(',',':')).encode()),
                                       'metrics':{'clientWidth':width,'scrollWidth':max(width,560) if scenario=='overflow' else width,'innerWidth':width,'innerHeight':height,'targets':targets},
                                       'screenshot':name,'screenshotSha256':sha(image),'legacyV1DimensionsOnly':width in (390,1280)})
        raw=json.dumps(data).encode()
        (folder/'receipt.json').write_bytes(raw)
        reader=Receipt(folder,expected_sha256=sha(raw),held_context=context(binding,report),
                       observed_after=(at-timedelta(seconds=1)).isoformat(),observed_before=(at+timedelta(seconds=1)).isoformat())
        yield reader,binding,report,data


def test_unit_replay_does_not_promote_geometry_or_send_contact(sample):
    reader,binding,report,_=sample
    data=reader.read(binding,report)
    assert data['nativeFactAdmission']=='NONE'
    assert all(not r['legacyV1DimensionsOnly'] for r in data['records'] if r['width'] in (375,320))
    html=views.overview(data,'/same-report')
    assert 'Rebuild修复候选' in html and 'UNKNOWN' in html and '/rfq' in html
    assert 'FAIL_WITH_EVIDENCE' not in html and 'ev-' not in html
    assert 'cta-original-image' in views.detail(data['records'][0],'/same-report')


@pytest.mark.parametrize('field', ['tenant_id','run_id','policy_id','policy_version','pack_ref','report_version','content_hash','display_hash','profile_id','industry_version'])
def test_context_rebinding_is_rejected(sample,field):
    reader,binding,report,_=sample
    reader.held[field]='foreign'
    with pytest.raises(CTADenied):
        reader.read(binding,report)


@pytest.mark.parametrize('mutation', ['href','v1-extension','nan','native-admission','delivery','375-native','image-path','stale','screenshot','request'])
def test_resealed_unsupported_claims_still_rejected(sample,mutation):
    reader,binding,report,data=sample
    data=deepcopy(data)
    row=data['records'][0]
    if mutation=='href':
        row['metrics']['targets'][0]['href']='/send'
    elif mutation=='v1-extension':
        row['dom']['elements'][0]['href']='/rfq'
        row['domSha256']=sha(json.dumps(row['dom'],ensure_ascii=False,separators=(',',':')).encode())
    elif mutation=='nan':
        row['metrics']['targets'][0]['rect']['width']=float('nan')
    elif mutation=='native-admission':
        data['nativeFactAdmission']='GUARD_FACT'
    elif mutation=='delivery':
        data['delivery']='PASS'
    elif mutation=='375-native':
        next(r for r in data['records'] if r['width']==375)['legacyV1DimensionsOnly']=True
    elif mutation=='image-path':
        row['screenshot']='../private-profile.json'
    elif mutation=='stale':
        row['observedAt']='2000-01-01T00:00:00+00:00'
    elif mutation=='screenshot':
        (reader.root/row['screenshot']).write_bytes(b'forged')
    elif mutation=='request':
        data['requests'].append({'url':'https://synthetic.invalid/rfq?x=1','method':'GET','type':'Document','allowed':False})
    raw=json.dumps(data).encode()
    (reader.root/'receipt.json').write_bytes(raw)
    reader.expected=sha(raw)  # extra consistency checks, even if a new hash is supplied
    with pytest.raises(CTADenied):
        reader.read(binding,report)


def test_changed_record_cannot_be_admitted_by_an_outer_hash(sample):
    reader,binding,report,data=sample
    data['records'][0]['metrics']['targets'][0]['centerOnTarget']=False
    (reader.root/'receipt.json').write_text(json.dumps(data))
    with pytest.raises(CTADenied):
        reader.read(binding,report)


def mount_sample(sample, tmp_path, **kwargs):
    # Parser fixture only; the separate live lab supplies actual Chrome bytes.
    reader = sample[0]
    setup = application(tmp_path, **kwargs)
    binding = setup[-2]
    reader.held = context(binding, binding.source.read())
    binding.cta = reader
    return setup


def test_original_signed_scope_protects_details_and_source_png(sample, tmp_path):
    issuer, directory, _, app, _, rid = mount_sample(sample, tmp_path)
    sid = login(issuer, directory, 'reviewer-demo')
    base = '/b5a/l2/r/'+rid+'/source-tasks/cta/covered/390'
    for suffix in ('', '/image'):
        response = app.handle('GET', base+suffix, headers(sid)).response
        assert response.status == 200
        assert response.content_type == 'image/png' if suffix else b'cta-source-detail' in response.body
        assert app.handle('GET', base+suffix, headers()).response.status == 403
        assert app.handle('POST', base+suffix, headers(sid)).response.status == 403
        for subject in ('other-tenant', 'recipient-a'):
            foreign = login(issuer, directory, subject)
            assert app.handle('GET', base+suffix, headers(foreign)).response.status == 403


def test_source_png_does_not_inherit_new_report_version(sample, tmp_path):
    issuer, directory, ledger, app, _, rid = mount_sample(sample, tmp_path)
    sid = login(issuer, directory, 'reviewer-demo')
    current = ledger.read(sid, rid)
    original_bytes = current.payload
    ledger.revise(sid, rid, **pins(current), changes={current.document['blueprint'][0]['id']: '新增原蓝图修订；来源附加样本不能自动作用于新版本。'})
    path = '/b5a/l2/r/'+rid+'/source-tasks/cta/covered/390/image'
    assert app.handle('GET', path, headers(sid)).response.status == 403
    assert ledger.read(sid, rid, 1).payload == original_bytes


def test_source_png_revalidates_revocation_and_expiry(sample, tmp_path):
    clock = [1800000000.0]
    issuer, directory, _, app, _, rid = mount_sample(sample, tmp_path, clock=lambda: clock[0])
    sid = login(issuer, directory, 'reviewer-demo')
    path = '/b5a/l2/r/'+rid+'/source-tasks/cta/hidden/390/image'
    assert app.handle('GET', path, headers(sid)).response.status == 200
    directory.people['reviewer-demo'] = replace(directory.people['reviewer-demo'], active=False)
    assert app.handle('GET', path, headers(sid)).response.status == 403
    directory.people['reviewer-demo'] = replace(directory.people['reviewer-demo'], active=True)
    clock[0] += 7200
    assert app.handle('GET', path, headers(sid)).response.status == 403


def test_bundled_reference_only_accepts_pinned_public_receipt(sample):
    from .candidate import bundled, BUNDLED_ROOT
    _, binding, report, _ = sample
    reader = bundled(binding, report)
    data = reader.read(binding, report)
    assert len(data['records']) == 16 and data['submission'] == data['delivery'] == 'UNKNOWN'
    assert all(row['url'].startswith('https://synthetic.invalid/') for row in data['records'])
    with pytest.raises(CTADenied):
        Receipt(BUNDLED_ROOT, expected_sha256='0'*64, held_context=context(binding, report),
                observed_after=data['startedAt'], observed_before=data['finishedAt'])

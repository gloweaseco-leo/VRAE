"""D1/D2 consumer failures use actual native APIs and independently held pins."""
from copy import deepcopy
from dataclasses import replace
import json
from urllib.parse import urlencode

import pytest

from apps.operator_console.contracts import ConsoleError, canonical
from apps.operator_console.fixtures import make_fixture
from apps.operator_console.interface import ConsoleInterface
from apps.operator_console.ports import Scope
from apps.operator_console.targets import ReviewTargetBridge, FutureRealReviewAdapter
from vrae.reviewing import ReviewError, ReviewTarget, prepare_production_review
from vrae.reviewing.canonical import canonical as dcanonical, SOURCE_LIMIT

DIGESTS={'404':'5705ac9e45e5118bc162bdece42f040a61360cf090b09500f7e9de5c89a9d256',
         '200':'c309bb1878103fdcb71200de644a685a52a04ab38d29325571cbc3a7f2bb4050'}


@pytest.fixture(scope='module')
def samples():
    s,c=make_fixture()
    result={}
    for case in ('404','200'):
        t=s.detail(c,'task-'+case)
        _,d=s.review(c,t['task_id'],1,t['report_pins']['expected_draft_ref'])
        result[case]=(t,d,canonical(s.repository.report_source(case)))
    return result


def args(samples,case='404'):
    t,d,source=samples[case]
    return deepcopy(t),deepcopy(d['review_target']),d['_artifacts']['document'],d['_artifacts']['html'],source


def test_fresh_native_calls_and_external_digest(monkeypatch):
    import vrae.reviewing.target as core
    core._replay_bytes.cache_clear()
    original=core.ReportDraft.load
    calls=[]
    def replay(*a,**kw):
        calls.append(kw['expected_draft_ref'])
        return original(*a,**kw)
    monkeypatch.setattr(core.ReportDraft,'load',replay)
    s,c=make_fixture()
    for case in ('404','200'):
        t=s.detail(c,'task-'+case)
        _,d=s.review(c,t['task_id'],1,t['report_pins']['expected_draft_ref'])
        assert d['review_target']['target_digest']==DIGESTS[case]
        assert t['report_pins']['expected_draft_ref'] in calls
    assert len(calls)>=4  # C0 original native loading AND D1/D2 replay, both real.


@pytest.mark.parametrize('case,count',[('404',1),('200',0)])
def test_complete_native_binding(samples,case,count):
    t,v,document,html,source=args(samples,case)
    loaded=ReviewTargetBridge().load(t,dcanonical(v),document,html,source).document
    assert loaded==v and loaded['target_digest']==DIGESTS[case]
    native=json.loads(document)
    assert len(native['issues'])==count
    assert v['limitations']==native['limitations'] and v['recorded_coverage']==native['recorded_coverage']
    assert v['native_report_version']==native['native_report_version']
    assert (v['native_h0'] is None)==(case=='200')
    assert v['target']['html_sha256']==native['html_sha256']
    assert v['target']['renderer_asset_sha256']==native['renderer_asset_sha256']
    assert v['target']['ordered_guard_refs']==native['pins']['expected_guard_refs']
    assert v['target']['guard_inputs_sha256']==native['guard_inputs_sha256']
    assert v['latest_report_version']==1 and 'NOT_PRODUCTION_LEDGER' in v['latest_version_authority']
    dossier=samples[case][1]
    for claim,ev in zip(v['target']['claims'],dossier['evidence']):
        assert claim['document_pointer']==ev['pointer']
        assert claim['evidence_ref']==ev['citation']['evidence_ref']
        assert ev['body'].encode()[claim['byte_start']:claim['byte_end']]==ev['quote'].encode()
    assert all(c['machine_status']=='HUMAN_REVIEW_REQUIRED' for c in v['target']['claims']
               if c['claim_type'] in ('HYPOTHESIS','RECOMMENDATION'))


@pytest.mark.parametrize('mutation', ['html','footer','css','payload','quote','utf8','guard','foreign_guard','evidence','policy_version','renderer_version'])
def test_actual_bytes_and_source_tamper(samples,mutation):
    t,v,document,html,source=args(samples)
    s=json.loads(source)
    if mutation=='html':
        html+=b'<script>alert(1)</script>'
    elif mutation=='footer':
        html=html.replace(b'</body>',b'<footer>APPROVED</footer></body>')
    elif mutation=='css':
        html=html.replace(b'</style>',b'body{display:none}</style>')
    elif mutation=='payload':
        d=json.loads(document)
        d['private']=False
        document=dcanonical(d,limit=SOURCE_LIMIT)
    elif mutation in ('quote','utf8'):
        f=s['guard_inputs'][0]['bindings'][0]['fact']['source']
        if mutation=='quote':
            f['quote']='设备认证已核实 <script>trust=true</script>'
        else:
            f['byte_end']+=1
    elif mutation in ('guard','foreign_guard'):
        s['guard_inputs'][0]['guard']['guard_ref']=('cg-'+'0'*64 if mutation=='guard'
            else samples['200'][1]['review_target']['target']['ordered_guard_refs'][0])
    elif mutation=='evidence':
        s['guard_inputs'][0]['bindings'][0]['fact']['source']['citation']['evidence_ref']='ev-'+'0'*64
    elif mutation=='policy_version':
        s['pack']['policy_version']=2
    else:
        s['metadata']['version']=2
    source=dcanonical(s,limit=SOURCE_LIMIT)
    with pytest.raises(ConsoleError,match='SOURCE_INTEGRITY'):
        ReviewTargetBridge().load(t,dcanonical(v),document,html,source)


@pytest.mark.parametrize('field', ['html_sha256','renderer_asset_sha256','policy_snapshot_sha256',
    'source_record_sha256','artifact_ref','guard_version','renderer_version','evidence_pack_ref',
    'ordered_guard_refs','claims','native_content_hash','kind'])
def test_self_rehashed_target_cannot_supply_trust(samples,field):
    t,v,document,html,source=args(samples)
    target=v['target']
    if field=='claims':
        target[field][1]['allowed_acceptance']='ACK_LITERAL_FACT'
    elif field=='ordered_guard_refs':
        target[field]=['cg-'+'0'*64]
    else:
        target[field]='FORGED'
    # Actual accepted target digest algorithm, not a hand-written fake hash engine.
    v['target_digest']=ReviewTarget(dcanonical(target)).target_digest
    with pytest.raises(ConsoleError,match='SOURCE_INTEGRITY'):
        ReviewTargetBridge().load(t,dcanonical(v),document,html,source)


@pytest.mark.parametrize('field', ['held','policy','artifact'])
def test_forged_trust_port_is_not_an_authority(samples,field,monkeypatch):
    t,v,document,html,source=args(samples)
    bridge=ReviewTargetBridge()
    trust=bridge._trust('404')
    if field=='policy':
        policy=json.loads(trust.policy)
        policy['current_authorization']='APPROVED'
        forged=replace(trust,policy=dcanonical(policy))
    elif field=='artifact':
        forged=replace(trust,artifact_ref='synthetic-object://tenant-other/forged')
    else:
        held=json.loads(trust.held)
        held['pins']['expected_guard_version']='forged-version'
        forged=replace(trust,held=dcanonical(held))
    monkeypatch.setattr(bridge,'_trust',lambda _:forged)
    with pytest.raises(ConsoleError,match='SOURCE_INTEGRITY'):
        bridge.load(t,dcanonical(v),document,html,source)


def test_renderer_asset_change_misses_native_memo(samples,monkeypatch):
    t,v,document,html,source=args(samples)
    import vrae.reviewing.target as core
    monkeypatch.setattr(core,'asset_hash',lambda:'0'*64)
    with pytest.raises(ConsoleError,match='SOURCE_INTEGRITY'):
        ReviewTargetBridge().load(t,dcanonical(v),document,html,source)


@pytest.mark.parametrize('field,value', [('state','APPROVED'),('trusted',True),
    ('dto_version','future'),('tenant_id','tenant-other'),('latest_report_version',2)])
def test_projection_cannot_self_certify(samples,field,value):
    t,v,document,html,source=args(samples)
    v[field]=value
    with pytest.raises(ConsoleError,match='SOURCE_INTEGRITY'):
        ReviewTargetBridge().load(t,dcanonical(v),document,html,source)


def test_zero_finding_cannot_escalate_or_cross_case(samples):
    t,v,document,html,source=args(samples,'200')
    assert v['native_h0'] is None and v['target']['kind']=='COVERAGE_ONLY'
    v['target']['kind']='L1_NATIVE'
    v['native_h0']='fake'
    with pytest.raises(ConsoleError,match='SOURCE_INTEGRITY'):
        ReviewTargetBridge().load(t,dcanonical(v),document,html,source)
    _,foreign,_,_,_=args(samples,'404')
    with pytest.raises(ConsoleError,match='SOURCE_INTEGRITY'):
        ReviewTargetBridge().load(t,dcanonical(foreign),document,html,source)


@pytest.mark.parametrize('actor',[None,{}, {'role':'OWNER','verified':True,'trusted':True}])
def test_real_review_remains_unconditionally_denied(actor):
    for call in (prepare_production_review,FutureRealReviewAdapter().prepare):
        with pytest.raises(ReviewError,match='D_AUTHENTICATED_PRODUCTION_REVIEW_NOT_IMPLEMENTED'):
            call(actor,trusted=True)


def test_target_route_scopes_and_invalid_inputs():
    s,c=make_fixture()
    ui=ConsoleInterface(s)
    task=s.detail(c,'task-404')
    query=urlencode({'version':1,'draft':task['report_pins']['expected_draft_ref'],'target':DIGESTS['404']})
    path='/tasks/task-404/target?'+query
    assert ui.dispatch(c,'GET',path).status==200
    assert ui.dispatch(None,'GET',path).status==403
    assert ui.dispatch({'role':'OWNER'},'GET',path).status==403
    foreign=s.authority.issue(Scope('tenant-other','ops-synthetic',frozenset({'task-404'}),'SYNTHETIC_TEST_ONLY'))
    assert ui.dispatch(foreign,'GET',path).status==403
    empty=s.authority.issue(Scope('tenant-test','ops-synthetic',frozenset(),'SYNTHETIC_TEST_ONLY'))
    assert ui.dispatch(empty,'GET',path).status==403
    assert ui.dispatch(c,'GET',path.replace('version=1','version=2')).status==409
    assert ui.dispatch(c,'GET',path.replace(DIGESTS['404'],DIGESTS['200'])).status==409
    assert ui.dispatch(c,'GET',path+'&trusted=true').status==400
    for method,suffix in [('POST',''),('GET','&url=https://evil.example'),('GET','&disposition=APPROVED')]:
        response=ui.dispatch(c,method,path+suffix)
        assert response.status in (400,501)
        assert b'ev-' not in response.body
    # Source request must bind the same target, and return no evidence on mismatch.
    bad=ui.dispatch(c,'GET',path.replace('/target?','/evidence/0?').replace(DIGESTS['404'],DIGESTS['200']))
    assert bad.status==409 and b'ev-' not in bad.body


def test_target_200_ui_is_internal_scope_not_pass_approval():
    s,c=make_fixture()
    t=s.detail(c,'task-200')
    query=urlencode({'version':1,'draft':t['report_pins']['expected_draft_ref'],'target':DIGESTS['200']})
    body=ConsoleInterface(s).dispatch(c,'GET','/tasks/task-200/target?'+query).body.decode()
    assert 'native H0 = null' in body and 'native ReportVersion = null' in body
    assert '审核条件尚未满足' in body and '仅内部覆盖核对' in body and '不证明询盘成功' in body
    assert '<button' not in body and '<script' not in body


def test_malformed_duplicate_and_unknown_disposition(samples):
    t,v,document,html,source=args(samples)
    raw=dcanonical(v)
    with pytest.raises(ConsoleError):
        ReviewTargetBridge().load(t,raw[:-1]+b',"trusted":true,"trusted":true}',document,html,source)
    v['target']['claims'][0]['allowed_acceptance']='FACTORY_CERTIFICATION_VERIFIED'
    with pytest.raises(ConsoleError):
        ReviewTargetBridge().load(t,dcanonical(v),document,html,source)


def test_source_pins_and_bytes_use_one_snapshot():
    s,c=make_fixture()
    t=s.detail(c,'task-404')
    original=s.repository.report_source
    calls=[]
    def source(case):
        calls.append(case)
        assert len(calls)==1,'No second source read after target check'
        return original(case)
    s.repository.report_source=source
    query=urlencode({'version':1,'draft':t['report_pins']['expected_draft_ref'],'target':DIGESTS['404']})
    response=ConsoleInterface(s).dispatch(c,'GET','/tasks/task-404/evidence/0?'+query)
    assert response.status==200 and calls==['404']
    assert b'&lt;a href=&quot;/contact&quot;&gt;' in response.body

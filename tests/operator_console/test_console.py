"""Business and trusted-call boundary coverage; all actors/data are synthetic."""
from copy import deepcopy
import hashlib
from urllib.parse import urlencode

import pytest

from apps.operator_console.contracts import ConsoleError, STAGES, TEST_ONLY, TaskRecord
from apps.operator_console.fixtures import FixtureAuthority, make_fixture
from apps.operator_console.interface import ConsoleInterface
from apps.operator_console.ports import Scope
from apps.operator_console.preview import serve


@pytest.fixture
def env():
    service, context = make_fixture()
    return service, context, ConsoleInterface(service)


def review(s, c, case='404'):
    t = s.detail(c,'task-'+case)
    return s.review(c,t['task_id'],1,t['report_pins']['expected_draft_ref'])


def test_pool_eight_real_contract_stage_mappings(env):
    s,c,_ = env
    rows = s.pool(c)
    assert len(rows) == 11
    assert set(t['stage'] for t in rows)==set(STAGES)
    assert all(t['source_kind']==TEST_ONLY for t in rows)


def test_filters_bounded_to_assigned_scope(env):
    s,c,_ = env
    assert [t['task_id'] for t in s.pool(c,'REVIEW_REQUIRED','工业泵')]==['task-404']
    assert not s.pool(c,query='不存在')
    assert s.pool(c,query='TASK-404')[0]['task_id']=='task-404'


@pytest.mark.parametrize('case,count', [('404',1),('200',0)])
def test_accepted_native_replay_and_bytes(env,case,count):
    s,c,_=env
    t,d=review(s,c,case)
    assert len(d['document']['issues'])==count
    assert d['document']['private'] and not d['document']['shareable']
    assert d['document']['approval_status']=='NOT_APPROVED'
    assert d['held']==t['report_pins']
    assert 'ReportDraft.load' in d['public_calls'] and 'GuardResult.load' in d['public_calls']
    for ev in d['evidence']:
        raw=ev['body'].encode('utf-8')
        assert raw[ev['byte_start']:ev['byte_end']]==ev['quote'].encode('utf-8')
        assert hashlib.sha256(raw).hexdigest()==ev['body_sha256']
        assert ev['citation']['observed_at']=='2026-11-10T12:00:00+00:00'


def test_200_does_not_invent_cta_binding(env):
    s,c,_=env
    _,d=review(s,c,'200')
    assert d['contact_capture']['observation']['result']=='PASS'
    assert not d['document']['issues']
    assert all(ev['claim']['fact']['rule_id']!='CTA-02' for ev in d['evidence'])


@pytest.mark.parametrize('context', [None,{}, {'tenant_id':'tenant-test','role':'OWNER'},object()])
def test_unverified_context_rejected_before_lookup(env,context):
    s,_,_=env
    with pytest.raises(ConsoleError,match='UNAUTHORIZED'):
        s.detail(context,'task-404')


def test_cross_tenant_context_denied(env):
    s,_,_=env
    c=s.authority.issue(Scope('tenant-foreign','ops-synthetic',frozenset({'task-404'}),TEST_ONLY))
    with pytest.raises(ConsoleError,match='UNAUTHORIZED'):
        s.detail(c,'task-404')


def test_foreign_owner_scope_denied(env):
    s,_,_=env
    c=s.authority.issue(Scope('tenant-test','ops-foreign',frozenset({'task-404'}),TEST_ONLY))
    with pytest.raises(ConsoleError,match='UNAUTHORIZED'):
        s.detail(c,'task-404')


def test_unassigned_never_looks_up_or_discloses(env):
    s,_,_=env
    c=s.authority.issue(Scope('tenant-test','ops-synthetic',frozenset(),TEST_ONLY))
    s.repository.task=lambda _: pytest.fail('unassigned lookup')
    for task_id in ('task-404','task-doesnotexist'):
        with pytest.raises(ConsoleError,match='UNAUTHORIZED'):
            s.detail(c,task_id)


def test_no_real_adapter_or_fixture_without_guard(env):
    s,_,_=env
    c=s.authority.issue(Scope('tenant-test','ops-synthetic',frozenset({'task-404'}),'PRODUCTION'))
    with pytest.raises(ConsoleError,match='UNAUTHORIZED'):
        s.pool(c)
    with pytest.raises(ConsoleError,match='UNAUTHORIZED'):
        FixtureAuthority()


@pytest.mark.parametrize('status', ['APPROVED','SHARED','BOGUS'])
def test_unsupported_native_status_rejected(env,status):
    s,c,_=env
    s.repository.tasks['task-404']['audit_run']['status']=status
    with pytest.raises(ConsoleError,match='INVALID_DTO'):
        s.detail(c,'task-404')


def test_stage_cannot_mask_native_block(env):
    s,c,_=env
    s.repository.tasks['task-404']['audit_run']['status']='ACCESS_BLOCKED'
    with pytest.raises(ConsoleError,match='INVALID_DTO'):
        s.detail(c,'task-404')


@pytest.mark.parametrize('query', ['https://evil.example/x','//evil.example','/etc/passwd','x'*81,'ab\u202ecd','\ud800'])
def test_illegal_search_refused(env,query):
    s,c,_=env
    with pytest.raises(ConsoleError,match='INVALID_INPUT'):
        s.pool(c,query=query)


@pytest.mark.parametrize('key', ['stage','source_kind','dto_version','owner_scope'])
def test_invalid_dto_fields_cannot_fallback(env,key):
    s,c,_=env
    s.repository.tasks['task-404'][key]='BOGUS'
    with pytest.raises(ConsoleError):
        s.detail(c,'task-404')


def test_version_change_invalidates_handoff(env):
    s,c,_=env
    old=s.detail(c,'task-404')['report_pins']['expected_draft_ref']
    s.repository.tasks['task-404']['report_version']=2
    with pytest.raises(ConsoleError,match='STALE_VERSION'):
        s.review(c,'task-404',1,old)
    with pytest.raises(ConsoleError,match='SOURCE_INTEGRITY'):
        s.review(c,'task-404',2,old)


def test_draft_pin_substitution_refused(env):
    s,c,_=env
    s.repository.tasks['task-404']['report_pins']['expected_html_sha256']='0'*64
    with pytest.raises(ConsoleError,match='SOURCE_INTEGRITY'):
        review(s,c)


def test_cross_case_substitution_refused(env):
    s,c,_=env
    s.repository.tasks['task-404']['report_case']='200'
    with pytest.raises(ConsoleError):
        review(s,c)


@pytest.mark.parametrize('attack', ['source_quote','html_object','guard','metadata','package','remove_guard'])
def test_native_tamper_against_independent_held_pins(env,attack):
    s,c,_=env
    source=s.repository.sources['404']
    if attack=='source_quote':
        source['guard_inputs'][0]['bindings'][0]['fact']['source']['quote']='<script>alert(1)</script>'
    elif attack=='html_object':
        key=next(iter(source['objects_base64']))
        source['objects_base64'][key]='PHNjcmlwdD4='
    elif attack=='guard':
        source['guard_inputs'][0]['guard']['guard_ref']='cg-'+'0'*64
    elif attack=='metadata':
        source['metadata']['version']=2
    elif attack=='package':
        source['package']['package_ref']='fp-'+'0'*64
    else:
        source['guard_inputs']=[]
    with pytest.raises(ConsoleError,match='SOURCE_INTEGRITY'):
        review(s,c)


@pytest.mark.parametrize('task_id', ['task-403','task-robots','task-unknown','task-invalid','task-failed'])
def test_blocked_is_neutral_not_report(env,task_id):
    s,c,ui=env
    response=ui.dispatch(c,'GET','/tasks/'+task_id)
    assert response.status==200
    assert '不能据此判断网站缺陷' in response.body.decode()
    assert 'data-key="review"' not in response.body.decode()
    with pytest.raises(ConsoleError,match='NOT_READY'):
        s.review(c,task_id,1,'rd-'+'0'*64)


def test_title_and_query_html_are_inert(env):
    s,c,ui=env
    s.repository.tasks['task-404']['title']='<script>alert(1)</script> & "采购"'
    body=ui.dispatch(c,'GET','/tasks/task-404').body.decode()
    assert '<script>' not in body and '&lt;script&gt;' in body
    body=ui.dispatch(c,'GET','/?'+urlencode({'q':'<img src=x onerror=alert(1)>'})).body.decode()
    assert '<img' not in body and '&lt;img' in body


def test_bidi_title_cannot_rewrite_ui(env):
    s,c,_=env
    s.repository.tasks['task-404']['title']='安全\u202eAPPROVED'
    with pytest.raises(ConsoleError):
        s.detail(c,'task-404')


def test_contract_detaches_mutable_input(env):
    s,c,_=env
    raw=s.detail(c,'task-404')
    record=TaskRecord.parse(raw)
    raw['title']='changed'
    assert record.document['title']!='changed'
    copy=record.document
    copy['title']='changed'
    assert record.document['title']!='changed'


def test_evidence_exact_pin_and_safe_quote(env):
    s,c,ui=env
    t=s.detail(c,'task-404')
    query=urlencode({'version':1,'draft':t['report_pins']['expected_draft_ref']})
    r=ui.dispatch(c,'GET','/tasks/task-404/evidence/0?'+query)
    assert r.status==200 and b'&lt;a href=&quot;/contact&quot;&gt;' in r.body
    assert b'<a href="/contact">' not in r.body
    assert t['report_pins']['expected_html_sha256'].encode() in r.body
    assert ui.dispatch(c,'GET','/tasks/task-404/review?'+query.replace('version=1','version=2')).status==409
    assert ui.dispatch(c,'GET','/tasks/task-404/review').status==400


@pytest.mark.parametrize('method,path', [('POST','/tasks/task-404/approve'),('DELETE','/tasks/task-404'),('GET','/tasks/task-404/share'),('GET','/download'),('GET','/?url=https://evil.example')])
def test_unauthorized_mutation_download_or_url_no_side_effect(env,method,path):
    s,c,ui=env
    before=deepcopy(s.repository.tasks)
    assert ui.dispatch(c,method,path).status in (400,501)
    assert s.repository.tasks==before
    assert ui.dispatch(None,method,path).status==403


def test_mutation_port_never_approves(env):
    s,c,_=env
    with pytest.raises(ConsoleError,match='NOT_IMPLEMENTED'):
        s.mutate(c,'approve')


def test_duplicate_fields_wrong_route_bad_index(env):
    _,c,ui=env
    for path in ('/?q=a&q=b','/?stage=APPROVED','/tasks/../../etc','/tasks/task-404/evidence/-1?version=1&draft=x'):
        assert ui.dispatch(c,'GET',path).status in (400,501)
    assert ui.dispatch(c,'GET','/?url=https://evil.example').status==400


def test_loopback_requires_both_explicit_test_guards():
    for kwargs in ({},{'test_only':True},{'test_only':True,'synthetic_fixtures':True,'host':'0.0.0.0'}):
        with pytest.raises(ValueError,match='TEST_ONLY_LOOPBACK_REQUIRED'):
            serve(**kwargs)


@pytest.mark.parametrize('change', [{'unexpected':True},{'expected_issue_count':True},
    {'expected_html_sha256':'bad'},{'expected_draft_ref':None}])
def test_malformed_report_pin_envelope_fails_closed(env,change):
    s,c,_=env
    s.repository.tasks['task-404']['report_pins'].update(change)
    with pytest.raises(ConsoleError,match='INVALID_DTO'):
        s.detail(c,'task-404')


def test_native_output_html_cannot_be_substituted(env,monkeypatch):
    s,c,_=env
    import apps.operator_console.native as native
    original=native.render
    monkeypatch.setattr(native,'render',lambda *args,**kwargs:original(*args,**kwargs)+b'<!-- changed -->')
    with pytest.raises(ConsoleError,match='SOURCE_INTEGRITY'):
        review(s,c)

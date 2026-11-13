"""Actual PG read interface tests. Missing PG is an error, never a skip."""
import os
import json
from dataclasses import replace
from urllib.parse import urlencode

import pytest

from apps.operator_console.interface import ConsoleInterface
from apps.operator_console.pg_read import make_pg_fixture
from apps.operator_console.proposals import ProposalPreview, CONTENT_TYPE
from apps.operator_console.views import review_url, target_url
from integration.ra4c3.lab import wire


@pytest.fixture(scope='module')
def sample():
    events = []
    service, context = make_pg_fixture(os.environ['RA4C3_PROFILE'],
        test_only=True, synthetic_fixtures=True, audit_sink=events.append)
    return service, context, events


def interface(sample):
    service, context, _ = sample
    return ConsoleInterface(service, proposal_preview=ProposalPreview(service, context,
        test_only=True, synthetic_fixtures=True))


def test_actual_pg_pool_reads_original_bytes(sample):
    service, context, events = sample
    events.clear()
    response = interface(sample).dispatch(context, 'GET', '/')
    assert response.status == 200, response.body.decode()
    assert any(e['event'] == 'approved_read' for e in events)
    assert any(e['event'] == 'response_current' for e in events)


@pytest.mark.parametrize('case', ['404', '200'])
def test_exact_original_target_source_proposal_and_no_new_draft(sample, case, monkeypatch):
    service, context, events = sample
    def forbidden(*a, **kw):
        raise AssertionError('RUNTIME_DRAFT_REBUILD_FORBIDDEN')
    monkeypatch.setattr(service.native, 'prepare', forbidden)
    task = service.repository.metadata.task('task-' + case)
    events.clear()
    with service.request(context):
        _, d = service.review(context, task['task_id'], 1, task['report_pins']['expected_draft_ref'])
    assert d['origin']['mode'] == 'PG16_TEST_ONLY_READ'
    assert len(d['document']['issues']) == (1 if case == '404' else 0)
    assert (d['document']['native_report_version'] is None) == (case == '200')
    assert (d['review_target']['native_h0'] is None) == (case == '200')
    api = interface(sample)
    for path in (review_url('/', task), target_url('/', task, d),
                 target_url('/', task, d).replace('/target?', '/proposal?'),
                 target_url('/', task, d).replace('/target?', '/evidence/capture?')):
        response = api.dispatch(context, 'GET', path)
        assert response.status == 200, (path, response.body.decode())
    proposal = {'version':'1', 'draft':d['document']['draft_ref'],
                'target':d['review_target']['target_digest'],
                'action':'APPROVE_CANDIDATE' if case == '404' else 'SIMULATED_INTERNAL_SCOPE_ACK',
                'reason':''}
    t = d['review_target']['target']
    for i, claim in enumerate(t['claims']):
        for key, source in [('guard','guard_ref'),('binding','binding_ref'),('pointer','pointer'),
                            ('disposition','allowed_acceptance')]:
            proposal[f'{key}.{i}'] = claim[source]
    proposal.update({'section.'+section:d['review_target']['target_digest'] for section in t['required_sections']})
    preview = ProposalPreview(service,context,test_only=True,synthetic_fixtures=True)
    with service.request(context):
        result = preview.validate(context,task['task_id'], urlencode(proposal).encode(), CONTENT_TYPE)
    assert result[3] == 'CONTRACT_VALID_ONLY'
    if case == '404':
        proposal['disposition.1']='ACK_LITERAL_FACT'
        with service.request(context):
            refused = preview.validate(context,task['task_id'],urlencode(proposal).encode(),CONTENT_TYPE)
        assert refused[3] == 'D_CLAIM_CEILING'
    assert events and all('password' not in json.dumps(e).lower() for e in events)


@pytest.mark.parametrize('path', ['/tasks/not-assigned', '/?tenant=tenant-beta', '/?dsn=postgres://evil', '/tasks/task-404?trusted=true'])
def test_unauthorized_request_has_zero_reads(sample, path):
    _, context, events = sample
    events.clear()
    r = interface(sample).dispatch(context,'GET',path)
    assert r.status in (400,403)
    assert events == []


def admin(sample):
    original, _ = wire(os.environ['RA4C3_STATE'])
    db = sample[0].repository.settings.dbname
    return original.connect(dbname=db)


@pytest.mark.parametrize('table,column,where,new_value', [
    ('ra4a_private.principals','enabled',"db_role='ra4a_test_a_app'",False),
    ('ra4a_private.assignments','active',"db_role='ra4a_test_a_app'",False),
    ('ra4a.policies','status',"tenant_id='tenant-test'",'REVOKED'),
])
def test_committed_revocation_blocks_at_request(sample, table, column, where, new_value):
    # All query identifiers/where clauses are fixed source literals, never inputs.
    with admin(sample) as c:
        old = c.execute(f'SELECT {column} FROM {table} WHERE {where}').fetchone()[0]
        c.execute(f'UPDATE {table} SET {column}=%s WHERE {where}',(new_value,))
        try:
            r = interface(sample).dispatch(sample[1],'GET','/tasks/task-404')
            assert r.status == 403
            assert b'<blockquote>' not in r.body
        finally:
            c.execute(f'UPDATE {table} SET {column}=%s WHERE {where}',(old,))


@pytest.mark.parametrize('kind', ['SOURCE','DRAFT','HTML','GUARD'])
def test_changed_committed_original_bytes_denied(sample, kind):
    with admin(sample) as c:
        where = "kind=%s AND (tenant_id,source_run_id,report_id,report_version)=(SELECT tenant_id,source_run_id,report_id,report_version FROM ra4a_bytes.graphs WHERE ref_id='accepted-404')"
        row = c.execute('SELECT object_key,raw FROM ra4a_bytes.objects WHERE '+where+' LIMIT 1',(kind,)).fetchone()
        assert row is not None
        key, raw = row[0], bytes(row[1])
        c.execute("SET session_replication_role=replica")
        try:
            c.execute('UPDATE ra4a_bytes.objects SET raw=%s WHERE '+where+' AND object_key=%s',(raw+b' ',kind,key))
            r = interface(sample).dispatch(sample[1],'GET','/tasks/task-404')
            assert r.status == 409
            assert b'<blockquote>' not in r.body
        finally:
            c.execute('UPDATE ra4a_bytes.objects SET raw=%s WHERE '+where+' AND object_key=%s',(raw,kind,key))
            c.execute('SET session_replication_role=origin')


def test_uncommitted_source_mutation_rollback_blocks_response(sample, monkeypatch):
    service, context, _ = sample
    original = service.native.load_original
    with admin(sample) as c:
        def during_render(*args):
            value = original(*args)
            c.execute('BEGIN')
            c.execute('SET LOCAL session_replication_role=replica')
            c.execute("UPDATE ra4a_bytes.objects SET raw=raw||decode('20','hex') WHERE kind='SOURCE'")
            return value
        monkeypatch.setattr(service.native,'load_original',during_render)
        task = service.repository.metadata.task('task-404')
        try:
            response = interface(sample).dispatch(context,'GET',review_url('/',task))
            assert response.status == 409
            assert b'<blockquote>' not in response.body
        finally:
            c.rollback()


def test_database_failure_never_uses_fixture_fallback(sample, monkeypatch):
    service, context, _ = sample
    monkeypatch.setattr(service.repository,'settings', replace(service.repository.settings,port=1))
    r = interface(sample).dispatch(context,'GET','/tasks/task-404')
    assert r.status == 503
    assert b'password' not in r.body.lower() and b'postgres' not in r.body.lower()


@pytest.mark.parametrize('path',['/tasks/task-403','/tasks/task-unknown','/?q=not-present'])
def test_no_database_fallback_for_neutral_or_empty_metadata(sample, path, monkeypatch):
    service,context,_=sample
    monkeypatch.setattr(service.repository,'settings',replace(service.repository.settings,port=1))
    r=interface(sample).dispatch(context,'GET',path)
    assert r.status == 503


def test_current_report_version_blocks_old_target(sample):
    original, p2a = wire(os.environ['RA4C3_STATE'])
    with admin(sample) as c:
        g = p2a.add_reference(c, '404', 2)
        try:
            r = interface(sample).dispatch(sample[1],'GET','/tasks/task-404')
            assert r.status == 403
        finally:
            c.execute('SET session_replication_role=replica')
            try:
                c.execute('DELETE FROM ra4a.references WHERE ref_id=%s',(g.ref_id,))
            finally:
                c.execute('SET session_replication_role=origin')


@pytest.mark.parametrize('role',['ra4a_test_b_app','ra4a_test_unassigned'])
def test_wrong_database_principal_never_displays_report(sample, role, monkeypatch):
    service, context, _ = sample
    state = json.loads(__import__('pathlib').Path(os.environ['RA4C3_STATE']).read_text())
    monkeypatch.setattr(service.repository,'settings',replace(service.repository.settings,
        user=role,password=state['runtime_passwords'][role]))
    r=interface(sample).dispatch(context,'GET','/tasks/task-404')
    assert r.status == 403
    assert b'<blockquote>' not in r.body


def test_policy_expired_before_request_denied(sample):
    with admin(sample) as c:
        old=c.execute("SELECT expires_at FROM ra4a.policies WHERE tenant_id='tenant-test'").fetchone()[0]
        c.execute("UPDATE ra4a.policies SET expires_at=clock_timestamp()-interval '1 second' WHERE tenant_id='tenant-test'")
        try:
            assert interface(sample).dispatch(sample[1],'GET','/tasks/task-404').status == 403
        finally:
            c.execute("UPDATE ra4a.policies SET expires_at=%s WHERE tenant_id='tenant-test'",(old,))


def test_login_revoked_during_render_denies_response(sample, monkeypatch):
    service, context, _ = sample
    original=service.native.load_original
    with admin(sample) as c:
        def during(*args):
            value=original(*args)
            c.execute('ALTER ROLE ra4a_test_a_app NOLOGIN')
            return value
        monkeypatch.setattr(service.native,'load_original',during)
        task=service.repository.metadata.task('task-404')
        try:
            r=interface(sample).dispatch(context,'GET',review_url('/',task))
            assert r.status == 403 and b'<blockquote>' not in r.body
        finally:
            c.execute('ALTER ROLE ra4a_test_a_app LOGIN')

"""Accepted source fixtures and true low-role B3/B4 checks; no authority repair."""
from dataclasses import replace
import time

import psycopg

from integration.ra4a import p2a_support, p2b1_support
from integration.ra4e.fixtures import wire
from integration.ra4e.manifest import verify_sources
from integration.b3_p0.support import Case
from vrae.application.ra4b import store
from vrae.b3_p0.contracts import Command, Receipt
from vrae.b3_p0.service import args
from vrae.persistence.private_bytes import ByteGraph, Artifact, locator, verify
from integration.ra4e.lab import digest


def denied(c, statement, parameters, expected='42501'):
    try:
        with c.transaction():
            c.execute(statement, parameters)
            raise AssertionError('NEGATIVE_WAS_ALLOWED')
    except psycopg.Error as exc:
        assert exc.sqlstate == expected, 'WRONG_DENIAL_SQLSTATE:' + str(exc.sqlstate)
        return exc.sqlstate


def admit(env, key):
    cfg = env.config()
    with store.connect(cfg) as c:
        return store.admit(c, cfg, key, 'accepted-404')


def seed(env, transport, minor):
    env.graphs = {case: p2a_support.graph(case) for case in ('404', '200')}
    with wire(env):
        for graph in env.graphs.values():
            p2b1_support.register_graph('vrae_ra4a_p1', graph)
    witnesses, receipts, commands = {}, {}, {}
    with env.connect() as admin:
        case = Case(env, 'vrae_ra4a_p1', admin)
        for kind in ('404', '200'):
            witnesses[kind] = case.witness(kind, ttl=600)
            commands[kind] = Command(p2b1_support.proposal(env.graphs[kind]).payload)
            with env.connect('p2b1_test_a_reviewer') as c, c.transaction():
                receipts[kind] = case.raw(c, witnesses[kind], commands[kind])
            assert Receipt(receipts[kind]).document['effective_approval'] is False
        witnesses['expired'] = case.witness(ttl=-1)
        witnesses['stale_epoch'] = case.witness(epoch=2, ttl=600)
    # Only one eligible task at a time; never an old-epoch eligible poison queue.
    old_done = admit(env, 'b7rv1-old-completed-0001')
    transport.worker(env, 'complete', minor, 'source-old-done')
    with env.connect() as admin:
        from integration.ra4b.epoch_cases import change, version
        old_epoch = version(admin)
        # Original accepted INITIAL fixture authority-cycle hook; no restore repair.
        change(admin, 'cycle')
        assert version(admin) > old_epoch
        assert admin.execute('SELECT state FROM ra4a.jobs WHERE job_id=%s',
                             (old_done['job_id'],)).fetchone() == ('TEST_ONLY_DONE',)
    inflight = admit(env, 'b7rv1-current-inflight-0002')
    transport.worker(env, 'kill', minor, 'source-sigkill')
    with env.connect() as admin:
        lease = admin.execute('SELECT job_id,run_id,lease_token,lease_seq FROM ra4a.jobs WHERE job_id=%s',
                              (inflight['job_id'],)).fetchone()
        assert lease is not None and lease[3] == 1
        end = time.monotonic() + 5
        while not admin.execute('SELECT lease_until<clock_timestamp() FROM ra4a.jobs WHERE job_id=%s', (inflight['job_id'],)).fetchone()[0]:
            assert time.monotonic() < end
            time.sleep(.05)
    return {'graphs': env.graphs, 'witnesses': witnesses, 'commands': commands,
            'receipts': receipts, 'old_done': old_done, 'inflight': inflight, 'lease': lease}


def low_role_checks(env, fixture):
    observations = {'actual_sessions': {}, 'denials': {}, 'receipts': {}}
    for kind in ('APP', 'WORKER'):
        for suffix in ('a', 'b'):
            cfg = env.config(kind, suffix)
            with store.connect(cfg) as c:
                observations['actual_sessions'][cfg['role']] = c.execute('SELECT session_user,current_user,current_database()').fetchone()
                for verb in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE'):
                    statement = {'SELECT': 'SELECT * FROM ra4a.jobs',
                        'INSERT': 'INSERT INTO ra4a.jobs DEFAULT VALUES',
                        'UPDATE': 'UPDATE ra4a.jobs SET attempts=attempts',
                        'DELETE': 'DELETE FROM ra4a.jobs',
                        'TRUNCATE': 'TRUNCATE ra4a.jobs'}[verb]
                    observations['denials'][cfg['role'] + ':' + verb] = denied(c, statement, ())
    with env.connect('p2b1_test_a_reviewer') as c:
        observations['actual_sessions']['p2b1_test_a_reviewer'] = c.execute('SELECT session_user,current_user,current_database()').fetchone()
        for kind in ('404', '200'):
            w, raw = fixture['witnesses'][kind], fixture['receipts'][kind]
            document = Receipt(raw).document
            with c.transaction():
                restored = bytes(c.execute('SELECT b3_p0.get_receipt(%s,%s,%s,%s,%s,%s,%s,%s)',
                    (w.token, *args(w.location), document['idempotency_key'])).fetchone()[0])
            assert restored == raw
            r = Receipt(restored).document
            assert not r['effective_approval'] and r['share_grant'] is r['native_decision'] is None
            observations['receipts'][kind] = {'sha256': digest(restored), 'authority': r['authority'],
                'effective_approval': False, 'share_grant': None, 'version': r['report_version']}
        for label in ('expired', 'stale_epoch'):
            w = fixture['witnesses'][label]
            observations['denials']['B3:' + label] = denied(c,
                'SELECT b3_p0.get_receipt(%s,%s,%s,%s,%s,%s,%s,%s)',
                (w.token, *args(w.location), Receipt(fixture['receipts']['404']).document['idempotency_key']))
        w = fixture['witnesses']['404']
        changed = replace(w.location, version=w.location.version + 1)
        observations['denials']['B3:cross_version'] = denied(c,
            'SELECT b3_p0.get_receipt(%s,%s,%s,%s,%s,%s,%s,%s)',
            (w.token, *args(changed), Receipt(fixture['receipts']['404']).document['idempotency_key']))
    with env.connect('p2b1_test_b_reviewer') as c:
        w = fixture['witnesses']['404']
        observations['denials']['B3:cross_tenant_read'] = denied(c,
            'SELECT b3_p0.get_receipt(%s,%s,%s,%s,%s,%s,%s,%s)',
            (w.token, *args(w.location), Receipt(fixture['receipts']['404']).document['idempotency_key']))
        observations['denials']['B3:cross_tenant_write'] = denied(c,
            'SELECT b3_p0.submit_test(%s,%s,%s,%s,%s,%s,%s,%s)',
            (w.token, *args(w.location), fixture['commands']['404'].payload))
    worker_cfg = env.config('WORKER')
    with store.connect(worker_cfg) as c:
        old = fixture['lease']
        observations['denials']['B4:old_lease_finish'] = denied(c,
            'SELECT ra4b_test.finish(%s,%s,%s,%s)', ('tenant-test', old[0], old[2], old[3]), expected='55000')
    app_cfg = env.config()
    with store.connect(app_cfg) as c:
        observations['denials']['B4:old_epoch_status'] = denied(c,
            'SELECT * FROM ra4b_test.status(%s,%s)', ('tenant-test', fixture['old_done']['request_id']))
        observations['denials']['B4:cross_tenant_write'] = denied(c,
            'SELECT * FROM ra4b_test.admit(%s,%s,%s,%s,%s,%s)',
            ('tenant-beta', 'x', 1, 'cross-tenant-denied-0001', '0' * 64, '{}'))
    with store.connect(env.config('APP', 'b')) as c:
        observations['denials']['B4:cross_tenant_read'] = denied(c,
            'SELECT * FROM ra4b_test.status(%s,%s)', ('tenant-test', fixture['inflight']['request_id']))
    observations['original_bytes'] = verify_sources(env, 'vrae_ra4a_p1', fixture['graphs'])
    observations['identity_scope'] = 'B3 server-held witness expiry/epoch revocation; B2 signed HTTP login NOT_TESTED (different immutable DB-name contract)'
    return observations


def tampered_candidate(env, fixture, private):
    """Corrupt a separately held real byte candidate, never disable DB immutability."""
    graph = fixture['graphs']['404']
    point = locator(graph)
    with env.connect('p2b1_test_a_reviewer') as c, c.transaction():
        rows = c.execute('SELECT * FROM ra4a_review_test.load_target(%s,%s,%s,%s,%s,%s)', args(point)).fetchall()
    target, manifest = bytes(rows[0][0]), bytes(rows[0][1])
    artifacts = [Artifact(kind, key, bytes(raw)) for _, _, kind, key, raw, _, _ in rows]
    index = next(i for i, item in enumerate(artifacts) if item.kind == 'HTML')
    original = artifacts[index]
    artifacts[index] = Artifact(original.kind, original.key, original.raw + b'\n')
    (private / 'tampered-candidate.bin').write_bytes(artifacts[index].raw)
    candidate = ByteGraph(graph.ref_id, target, tuple(artifacts), manifest, graph.trust)
    try:
        verify(candidate, provenance=graph)
    except Exception as exc:
        # Only the original domain verifier's documented rejection is accepted.
        from vrae.persistence.contracts import PersistenceError
        assert isinstance(exc, PersistenceError), type(exc).__name__
        return {'original_sha256': digest(original.raw), 'candidate_sha256': digest(artifacts[index].raw),
                'sealed_manifest_sha256': digest(manifest), 'rejected': True,
                'database_bytes_changed': False, 'candidate_from_actual_reviewer_read': True}
    raise AssertionError('TAMPERED_CANDIDATE_ACCEPTED')

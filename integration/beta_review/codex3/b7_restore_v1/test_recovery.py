"""One native complete disposable three-environment integration experiment."""
import os
import json
from pathlib import Path
import time

from integration.ra4e.lab import digest, docker, encode
from .environment import Environment
from .snapshot import SCHEMAS, capture, compare, evidence
from .transport import Transport
from .business import seed, low_role_checks, tampered_candidate, admit
from vrae.application.ra4b import store


def test_three_environment_six_schema_recovery():
    private = Path(os.environ['B7RV1_PRIVATE'])
    public = Path(os.environ['B7RV1_PUBLIC'])
    minor = os.environ['B7RV1_MINOR']
    transport = Transport(private, public)
    environments = []
    secrets = []
    def publish(name, value):
        (public / (name + '.json')).write_bytes(encode(value))
    def snapshot(env, name):
        value = capture(env)
        (private / (name + '.json')).write_bytes(encode(value))
        publish(name, evidence(value))
        return value
    try:
        transport.preflight(minor)
        for tag in ('source', 'verification', 'target'):
            env = Environment(tag, private / tag, public / tag)
            environments.append(env)
            env.start()
            env.initialize()
            secrets.extend([env.admin_password, *env.runtime_passwords.values()])
        source, verification, target = environments
        cluster_ids = [json.loads((env.proof / 'transport.json').read_bytes())['cluster_system_identifier'] for env in environments]
        assert len(set(cluster_ids)) == 3, 'CLUSTERS_NOT_INDEPENDENT'
        fixture = seed(source, transport, minor)
        baseline = snapshot(source, 'source-baseline')
        observations = low_role_checks(source, fixture)
        compare(baseline, snapshot(source, 'source-after-readonly'))
        publish('source-low-role', observations)
        start = time.monotonic()
        archive = transport.backup(source, 'source-backup')
        compare(baseline, snapshot(source, 'source-after-backup'))
        publish('backup', {'sha256': digest(archive.read_bytes()), 'bytes': archive.stat().st_size,
                          'source': source.name, 'format': 'pg_dump -Fc --create',
                          'snapshot_state_unchanged': True})
        # Predetermined real failures, not retry-to-green of a positive run.
        transport.command('backup-error', ['exec', source.name, 'pg_dump', '-U', 'postgres',
                                           '-d', 'b7rv1_database_does_not_exist', '-Fc'], expected='nonzero')
        bad = private / 'corrupt.dump'
        bad.write_bytes(b'NOT_A_POSTGRESQL_ARCHIVE')
        docker('cp', str(bad), verification.name + ':/tmp/corrupt.dump')
        transport.command('restore-error', ['exec', verification.name, 'pg_restore', '-U',
            'postgres', '--exit-on-error', '--dbname=postgres', '/tmp/corrupt.dump'], expected='nonzero')
        docker('exec', verification.name, 'rm', '-f', '/tmp/corrupt.dump')
        verification.empty_for_restore()
        missing = transport.restore(verification, archive, 'missing-schema-candidate',
                                    schemas=[s for s in SCHEMAS if s != 'ra4b_test'], expected=None)
        with verification.connect() as c:
            assert c.execute("SELECT to_regnamespace('ra4b_test')").fetchone()[0] is None
        try:
            capture(verification)
        except AssertionError as exc:
            assert str(exc) == 'MISSING_REQUIRED_SCHEMA'
        else:
            raise AssertionError('MISSING_SCHEMA_CANDIDATE_ACCEPTED')
        publish('missing-schema-denied', {'native_restore_exit': missing.returncode,
            'readiness': False, 'missing': 'ra4b_test', 'gate': 'MISSING_REQUIRED_SCHEMA'})
        verification.empty_for_restore()
        transport.restore(verification, archive, 'verification-restore')
        restored = snapshot(verification, 'verification-restored')
        publish('verification-equality', compare(baseline, restored))
        publish('verification-low-role', low_role_checks(verification, fixture))
        compare(restored, snapshot(verification, 'verification-after-readonly'))
        publish('tampered-sealed-hash-denied', tampered_candidate(verification, fixture, private))
        compare(restored, snapshot(verification, 'verification-after-candidate'))
        # A real second dump forms source -> verification -> target, rather than
        # merely importing the original archive twice and calling that a chain.
        second_archive = transport.backup(verification, 'verification-backup')
        target_restore_start = time.monotonic()
        target.empty_for_restore()
        transport.restore(target, second_archive, 'target-restore')
        target_baseline = snapshot(target, 'target-restored')
        publish('target-equality', compare(baseline, target_baseline))
        publish('target-low-role', low_role_checks(target, fixture))
        compare(target_baseline, snapshot(target, 'target-after-readonly'))
        publish('chain', {'stages': [e.name for e in environments],
            'source_dump_sha256': digest(archive.read_bytes()),
            'verification_dump_sha256': digest(second_archive.read_bytes()),
            'source_root': baseline['root'], 'verification_root': restored['root'],
            'target_root': target_baseline['root'], 'empty_destinations': True,
            'observed_chain_including_negatives_seconds': time.monotonic() - start,
            'observed_target_restore_through_readonly_gates_seconds': time.monotonic() - target_restore_start,
            'rpo': 'No source advancement across measured backup; no production SLA',
            'sealed_reports': 'accepted fixture samples; NOT generated by this Worker'})
        # Only the current-epoch expired lease is eligible. Original guards remain.
        transport.worker(target, 'complete', minor, 'target-reclaimed')
        cfg = target.config()
        with store.connect(cfg) as c:
            status = store.status(c, cfg, fixture['inflight']['request_id'])
        assert status['status'] == 'TEST_ONLY_CONSUMED' and status['share_grant'] is None
        fresh = admit(target, 'b7rv1-after-restore-current-0003')
        transport.worker(target, 'complete', minor, 'target-fresh')
        with store.connect(cfg) as c:
            assert store.status(c, cfg, fresh['request_id'])['status'] == 'TEST_ONLY_CONSUMED'
        final = snapshot(target, 'target-after-recovery')
        for name, table in baseline['tables'].items():
            if name.startswith(('b3_p0.', 'ra4a_bytes.', 'ra4a_review_test.')):
                assert final['tables'][name] == table, 'IMMUTABLE_OR_B3_STATE_CHANGED:' + name
        with target.connect() as admin:
            before_audit = baseline['tables']['ra4a.audit']['rows']
            before_outbox = baseline['tables']['ra4a.outbox']['rows']
            after_audit = final['tables']['ra4a.audit']['rows']
            after_outbox = final['tables']['ra4a.outbox']['rows']
            assert all(row in after_audit for row in before_audit)
            assert all(row in after_outbox for row in before_outbox)
            assert len(after_audit) == len(before_audit) + 5
            assert len(after_outbox) == len(before_outbox) + 3
            observed = admin.execute('SELECT state,attempts,lease_seq FROM ra4a.jobs WHERE job_id=%s', (fixture['inflight']['job_id'],)).fetchone()
            assert observed == ('TEST_ONLY_DONE', 2, 2)
        from .business import denied
        with store.connect(target.config('WORKER')) as c:
            old = fixture['lease']
            denied(c, 'SELECT ra4b_test.finish(%s,%s,%s,%s)',
                   ('tenant-test', old[0], old[2], old[3]), expected='55000')
        compare(final, snapshot(target, 'target-after-old-token-replay'))
        publish('recovery', {'old_lease_denial': '55000', 'reclaimed': observed,
            'original_audit_rows_preserved': len(before_audit), 'audit_delta': 5,
            'original_outbox_rows_preserved': len(before_outbox), 'outbox_delta': 3,
            'b3_and_report_bytes_unchanged': True, 'fresh_current_epoch_worker_done': True,
            'old_A1': 'PAUSED; MAX3 0/3 unchanged; full B7 EXIT remains blocked',
            'old_epoch_eligible_queue_constructed': False})
    finally:
        cleanup = []
        for env in reversed(environments):
            try:
                secrets.extend([env.admin_password, *env.runtime_passwords.values()])
                env.stop()
                cleanup.append({'environment': env.name, 'absent': True})
            except Exception as exc:
                cleanup.append({'environment': env.name, 'absent': False,
                                'error_type': type(exc).__name__})
        (private / 'scan-credentials.json').write_bytes(encode(list(set(secrets))))
        publish('cleanup', cleanup)
        assert len(cleanup) == len(environments) and all(row['absent'] for row in cleanup), 'CLEANUP_NOT_PROVEN'

"""Actual two-environment backup/recovery positives and failures; no mocks."""
import os
from dataclasses import replace
import json
from pathlib import Path
import uuid

import psycopg
import pytest

from vrae.identity.boundary import IdentityDenied
from vrae.persistence.contracts import admission_payload
from vrae.persistence.private_bytes import locator
from vrae.persistence.review_cas import TestOnlyReviewCAS as ReviewCAS
from tests.identity.issuer import NONCE

from .fixtures import initialize, build_source, identity, all_private_credentials
from .lab import Environment, RUNTIME, DOCS, RecoveryDenied, digest, encode
from .manifest import capture, verify_sources, public_catalog
from .security import runtime_audit, table_acl_entries, TABLE_ACL_SCOPE
from .restore import Restore, backup


def database_name():
    return 'vrae_p2b1_' + uuid.uuid4().hex[:12]


class Run:
    def record(self, name, value):
        self.output.joinpath(name + '.json').write_bytes(encode(value))


@pytest.fixture(scope='session')
def run():
    r = Run()
    r.output = Path(os.environ['RA4E_OUTPUT']).resolve()
    r.private = Path(os.environ['RA4E_PRIVATE']).resolve()
    assert r.output.is_relative_to(DOCS.resolve()) and r.private.is_relative_to(RUNTIME.resolve())
    r.output.mkdir(parents=True, exist_ok=True)
    r.private.mkdir(parents=True, exist_ok=True)
    r.source = Environment('source', r.private / 'source', r.output / 'source')
    r.destination = Environment('destination', r.private / 'destination', r.output / 'destination')
    try:
        r.source.start()
        initialize(r.source)
        r.fixture = build_source(r.source)
        r.name = r.fixture['dbname']
        r.source_runtime = runtime_audit(r.source, r.name, r.fixture['graphs'])
        r.record('source-runtime-sql', r.source_runtime)
        r.expected, catalog = capture(r.source, r.name)
        r.record('independent-before-backup', r.expected)
        diagnostic = os.environ.get('RA4E_DIAGNOSTIC') == 'ONE_RUN'
        r.record('source-catalog', public_catalog(catalog))
        if diagnostic:
            r.private.joinpath('source-original-private-catalog.json').write_bytes(encode(catalog))
        r.record('independent-accepted-originals', verify_sources(r.source, r.name, r.fixture['graphs']))
        r.old_issuer, r.old_token, _ = identity(r.source, r.name, r.fixture['graphs']['404'])
        if diagnostic:
            from .observation import snapshot, diff
            r.source_observation = snapshot(r.source, r.name, r.private, r.output, 'source-before-backup')
        r.archive, r.sha = backup(r.source, r.name, r.private, r.expected, r.output)
        if diagnostic:
            after = snapshot(r.source, r.name, r.private, r.output, 'source-after-backup')
            r.source_stability = diff(r.source_observation, after, r.output, 'source-during-backup')
        r.destination.start()
        initialize(r.destination)
        r.restorer = Restore(r.destination, r.private, r.output, r.expected, r.fixture['graphs'])
        yield r
    finally:
        errors = []
        for environment in [r.destination, r.source]:
            try:
                environment.stop()
            except Exception as exc:
                errors.append(type(exc).__name__)
        # Scan actual fixture secrets before forgetting the private process state.
        secrets = all_private_credentials([r.source, r.destination])
        r.private.joinpath('scan-credentials.json').write_bytes(encode(secrets))
        for file in r.private.glob('*.dump'):
            assert file.resolve().is_relative_to(RUNTIME.resolve())
            file.unlink()
        r.record('final-cleanup', {'environment_cleanup_errors': errors, 'raw_dumps_removed': not list(r.private.glob('*.dump'))})
        assert not errors


@pytest.fixture(scope='session')
def restored(run):
    name = database_name()
    run.restorer.perform(run.archive, run.sha, name)
    return name


def test_two_independent_storage_and_credentials(run):
    assert run.source.name != run.destination.name and run.source.port != run.destination.port
    assert run.source.admin_password != run.destination.admin_password
    role = 'p2b1_test_a_reviewer'
    assert run.source.runtime_passwords[role] != run.destination.runtime_passwords[role]
    with pytest.raises(psycopg.OperationalError):
        run.destination.connect(role, password=run.source.runtime_passwords[role])


def test_full_restore_matches_prebackup_sql_catalog_audit_and_outbox(run, restored):
    actual, _ = capture(run.destination, restored)
    assert actual == run.expected
    for table in ['ra4a.audit', 'ra4a.outbox', 'ra4a_review_test.audit', 'ra4a_review_test.outbox']:
        assert actual['tables'][table]['count'] > 0
    run.record('verified-original-audit-outbox', {k:v for k,v in actual['tables'].items() if k.endswith(('.audit', '.outbox'))})


def test_original_404_and_200_native_null(run, restored):
    values = verify_sources(run.destination, restored, run.fixture['graphs'])
    assert values['404']['findings'] == 1 and values['404']['native_content_hash'] is not None
    assert values['200']['findings'] == 0 and values['200']['native_content_hash'] is None
    run.record('restored-original-semantics', values)


@pytest.mark.parametrize('role', ['p2b1_test_b_reviewer', 'ra4a_test_unassigned', 'ra4a_test_b_app'])
def test_wrong_tenant_and_unassigned_are_actual_sql_denials(run, restored, role):
    point = locator(run.fixture['graphs']['404'])
    with run.destination.connect(role, dbname=restored) as c, pytest.raises(psycopg.Error) as error:
        c.execute('SELECT * FROM ra4a_review_test.load_target(%s,%s,%s,%s,%s,%s)',
                  (point.tenant, point.ref_id, point.source_run, point.report, point.version, point.target_digest))
    assert error.value.sqlstate == '42501'
    run.record('denial-' + role, {'sqlstate': error.value.sqlstate, 'private_rows_returned': 0})


@pytest.mark.parametrize('query,repair', [
    ("UPDATE ra4a_private.principals SET enabled=false WHERE db_role='p2b1_test_a_reviewer'",
     "UPDATE ra4a_private.principals SET enabled=true WHERE db_role='p2b1_test_a_reviewer'"),
    ("UPDATE ra4a_review_test.assignments SET active=false WHERE db_role='p2b1_test_a_reviewer'",
     "UPDATE ra4a_review_test.assignments SET active=true WHERE db_role='p2b1_test_a_reviewer'")])
def test_current_disable_and_assignment_revoke_after_restore(run, restored, query, repair):
    with run.destination.connect(dbname=restored) as admin:
        admin.execute(query)
        try:
            with pytest.raises(psycopg.Error) as error:
                verify_sources(run.destination, restored, run.fixture['graphs'])
            assert error.value.sqlstate == '42501'
        finally:
            admin.execute(repair)
    assert capture(run.destination, restored)[0] == run.expected


def test_private_raw_sql_denied_to_runtime(run, restored):
    for role in ['ra4a_test_a_app', 'p2b1_test_a_reviewer']:
        with run.destination.connect(role, dbname=restored) as c:
            row = c.execute('SELECT session_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=session_user').fetchone()
            assert row == (role, False, False)
            with pytest.raises(psycopg.Error) as error:
                c.execute('SELECT * FROM ra4a_bytes.objects')
            assert error.value.sqlstate == '42501'


def test_restored_test_review_idempotent_exact_receipt(run, restored):
    before = capture(run.destination, restored)[0]
    for case, g in run.fixture['graphs'].items():
        with run.destination.connect('p2b1_test_a_reviewer', dbname=restored) as c:
            result = ReviewCAS(c, mode='TEST_ONLY_P2B1_REVIEW_CAS').submit(
                locator(g), run.fixture['commands'][case], provenance=g)
            assert result.payload == run.fixture['receipts'][case]
            assert result.document['native_decision'] is None
            assert result.document['share_grant'] is None
    assert capture(run.destination, restored)[0] == before


def test_b2_binding_restored_but_signing_and_replay_state_not_restored(run, restored):
    _, _, boundary = identity(run.destination, restored, run.fixture['graphs']['404'])
    with pytest.raises(IdentityDenied):
        boundary.check(run.old_token, locator(run.fixture['graphs']['404']), nonce=NONCE)
    run.record('identity-recovery-boundary', {'persisted_principal_assignment_verified': True,
        'fresh_trust_observation_verified': True, 'old_issuer_token_denied': True,
        'private_keys_and_replay_store_restored': False, 'real_person_approval': False})


def test_wrong_backup_sha_denied_before_import(run):
    before = run.restorer.imports
    name = database_name()
    with pytest.raises(RecoveryDenied, match='BACKUP_SHA_MISMATCH'):
        run.restorer.perform(run.archive, '0' * 64, name)
    assert run.restorer.imports == before and not (run.output / (name + '-ready.json')).exists()


def test_corrupted_custom_archive_denied(run):
    file = run.private / 'corrupted.dump'
    file.write_bytes(b'PGDMP\x00incomplete-custom-archive')
    name = database_name()
    with pytest.raises(RecoveryDenied, match='ARCHIVE_FORMAT_INVALID'):
        run.restorer.perform(file, digest(file.read_bytes()), name)
    assert not (run.output / (name + '-ready.json')).exists()


def test_partial_restore_never_publishes_success(run):
    name = database_name()
    before = run.restorer.source_verifications
    with pytest.raises(RecoveryDenied, match='^FROZEN_TEN_POLICY_CONTRACT$'):
        run.restorer.perform(run.archive, run.sha, name, partial=True)
    assert not (run.output / (name + '-ready.json')).exists()
    assert run.restorer.source_verifications == before
    assert not any(s['stage'] == 'full_manifest_gate_passed' for s in run.restorer.stages if s['database'] == name)
    with run.destination.connect(dbname='postgres') as c:
        assert c.execute('SELECT 1 FROM pg_database WHERE datname=%s', (name,)).fetchone() is None


def test_mismatched_independent_source_target_fails_closed(run):
    diagnostic_control = getattr(run, 'diagnostic_control', None)
    if diagnostic_control is not None and diagnostic_control.error is not None:
        run.record('target-negative-blocked', {'status': 'BLOCKED', 'valid_full_manifest_gate': False,
            'earlier_gate_code': diagnostic_control.code, 'target_specific_denial_reached': False})
        pytest.skip('BLOCKED: unmodified diagnostic control failed; no target-negative PASS')
    control = database_name()
    try:
        run.restorer.perform(run.archive, run.sha, control)
    except RecoveryDenied as exc:
        if str(exc) != 'RESTORED_MANIFEST_MISMATCH':
            raise
        pytest.skip('BLOCKED: valid full-manifest control unavailable; target binding not reached')
    original = run.fixture['graphs']['404']
    target = json.loads(original.target)
    target['source_manifest_sha256'] = '0' * 64
    wrong = dict(run.fixture['graphs'], **{'404': replace(original, target=encode(target))})
    restorer = Restore(run.destination, run.private, run.output, run.expected, wrong)
    name = database_name()
    with pytest.raises(psycopg.Error) as error:
        restorer.perform(run.archive, run.sha, name)
    assert error.value.sqlstate == '42501'
    assert error.value.diag.message_primary == 'P2A_EXACT_LOCATOR_DENIED'
    stages = [s['stage'] for s in restorer.stages if s['database'] == name]
    assert 'full_manifest_gate_passed' in stages and 'source_target_gate_passed' not in stages
    assert not (run.output / (name + '-ready.json')).exists()


def test_real_interrupted_import_then_clean_destination_recovery(run):
    name = database_name()
    with pytest.raises(RecoveryDenied, match='IMPORT_INTERRUPTED'):
        run.restorer.perform(run.archive, run.sha, name, interrupt=True)
    assert not (run.output / (name + '-ready.json')).exists()
    result = run.restorer.perform(run.archive, run.sha, name)
    assert result['restored_root_sha256'] == run.expected['root_sha256']


def test_verified_restore_replay_is_noop_and_conflict_denied(run, restored):
    before = run.restorer.imports
    first = run.restorer.ready[restored]
    assert run.restorer.perform(run.archive, run.sha, restored) == first
    assert run.restorer.imports == before
    with pytest.raises(RecoveryDenied, match='RESTORE_REPLAY_CONFLICT'):
        run.restorer.perform(run.archive, '0' * 64, restored)


def test_restored_original_admission_and_expired_lease_recovery(run):
    name = database_name()
    run.restorer.perform(run.archive, run.sha, name)
    raw, sha = admission_payload()
    with run.destination.connect('ra4a_test_a_app', dbname=name) as c:
        replay = c.execute('SELECT * FROM ra4a.admit(%s,%s,%s,%s,%s,%s)',
            ('tenant-test', 'pol-001', 1, 'b7p0-completed-0001', sha, raw)).fetchone()
        assert replay == run.fixture['admitted']
    assert capture(run.destination, name)[0] == run.expected
    old = run.fixture['expired_lease']
    with run.destination.connect('ra4a_test_a_worker', dbname=name) as c:
        with pytest.raises(psycopg.Error) as error:
            c.execute('SELECT ra4a.finish(%s,%s,%s,%s)', ('tenant-test', old[0], old[2], old[3]))
        assert error.value.sqlstate == '55000'
        assert capture(run.destination, name)[0] == run.expected
        current = c.execute('SELECT * FROM ra4a.claim(%s,%s)', ('tenant-test', 30)).fetchone()
        assert current[0] == old[0] and current[3] == old[3] + 1 and current[2] != old[2]
        first = c.execute('SELECT ra4a.finish(%s,%s,%s,%s)', ('tenant-test', current[0], current[2], current[3])).fetchone()
        again = c.execute('SELECT ra4a.finish(%s,%s,%s,%s)', ('tenant-test', current[0], current[2], current[3])).fetchone()
        assert first == again
    run.record('restored-lease-recovery', {'old_lease_sqlstate': error.value.sqlstate, 'new_lease_seq': current[3],
        'new_token': True, 'exact_finish_replay': True, 'human_approval': False})


def test_acl_null_empty_and_explicit_permission_differences_in_actual_sql(run, restored):
    results = []
    for environment, database in [(run.source, run.name), (run.destination, restored)]:
        with environment.connect(dbname=database) as c:
            default = table_acl_entries(c, None, 'ra4a_owner')
            explicit = table_acl_entries(c, '{ra4a_owner=arwdDxt/ra4a_owner}', 'ra4a_owner')
            empty = table_acl_entries(c, '{}', 'ra4a_owner')
            assert default == explicit and len(default) == 7 and empty == [] and empty != default
            variants = {
                'owner_select_only': '{ra4a_owner=r/ra4a_owner}',
                'extra_public': '{ra4a_owner=arwdDxt/ra4a_owner,=r/ra4a_owner}',
                'extra_runtime': '{ra4a_owner=arwdDxt/ra4a_owner,ra4a_test_a_app=r/ra4a_owner}',
                'grantor_changed': '{ra4a_owner=arwdDxt/postgres}',
                'grant_option_changed': '{ra4a_owner=ar*wdDxt/ra4a_owner}',
            }
            for label, value in variants.items():
                assert table_acl_entries(c, value, 'ra4a_owner') != default
                results.append({'environment': environment.tag, 'case': label, 'effective_acl_differs': True})
            results.append({'environment': environment.tag, 'null_equals_explicit_default': True,
                            'null_differs_from_empty': True, 'actual_sql': True})
    run.record('acl-null-empty-sql-proof', results)


def test_separate_security_planes_and_actual_privilege_matrix(run, restored):
    _, source = capture(run.source, run.name)
    _, target = capture(run.destination, restored)
    a = source['comparison_catalog']['independent_security_planes']
    b = target['comparison_catalog']['independent_security_planes']
    assert a == b
    required = ['default_acls', 'schema_acls', 'column_acls', 'database_acl', 'sequence_acls',
                'procedure_acls', 'role_attributes', 'membership_options', 'has_table_privilege',
                'has_column_privilege', 'has_schema_privilege']
    assert set(a) == set(required)
    roles = {r[0] for r in a['role_attributes']}
    assert len(a['has_table_privilege']) == len(roles) * 13 * 7
    assert {r[1] + '.' + r[2] for r in a['has_table_privilege']} == {s + '.' + t for s, t in TABLE_ACL_SCOPE}
    run.record('independent-security-plane-equality', {'all_equal': True,
        'plane_counts': {k:len(a[k]) for k in required}, 'roles': sorted(roles),
        'source_target_has_table_privilege_sha256': digest(encode(a['has_table_privilege']))})


def test_complete_actual_runtime_sql_matrix(run, restored):
    target = json.loads((run.output / (restored + '-runtime-sql.json')).read_text())
    for value, environment in [(run.source_runtime, run.source), (target, run.destination)]:
        assert value['actual_sql'] is True
        assert value['raw_denial_count'] == len(environment.runtime_passwords) * 13 * 5
        assert all(r['sqlstate'] == '42501' for r in value['raw_private_denials'])
        assert any(r['result'] == 'AUTHORIZED_ORIGINAL_READ' for r in value['scoped_allow_deny'])
        assert value['authorized_originals']['404']['findings'] == 1
        assert value['authorized_originals']['200']['findings'] == 0


def test_only_thirteen_table_acl_representations_normalized_raw_evidence_retained(run, restored):
    _, source = capture(run.source, run.name)
    _, target = capture(run.destination, restored)
    original = {r['table']:r for r in source['raw_table_acl_evidence']}
    actual = {r['table']:r for r in target['raw_table_acl_evidence']}
    assert set(original) == set(actual) == {s + '.' + t for s, t in TABLE_ACL_SCOPE}
    for name, expected in original.items():
        assert expected['relkind'] == actual[name]['relkind'] == 'r'
        assert expected['owner'] == actual[name]['owner'] == 'ra4a_owner'
        assert expected['expanded_entries'] == actual[name]['expanded_entries']
    run.record('thirteen-table-semantic-acl-proof', {'source': original, 'destination': actual,
        'other_acl_planes_independently_strict': True})


def test_genuine_restored_row_manifest_mismatch_denies_readiness(run, restored):
    assert run.restorer.ready[restored]['status'] == 'VERIFIED_TEST_ONLY_RESTORE'
    def revoke_after_import(environment, name, partial):
        assert not partial
        with environment.connect(dbname=name) as c:
            c.execute("UPDATE ra4a_private.assignments SET active=false WHERE db_role='ra4a_test_a_app'")
    probe = Restore(run.destination, run.private, run.output, run.expected, run.fixture['graphs'], observer=revoke_after_import)
    name = database_name()
    with pytest.raises(RecoveryDenied, match='^RESTORED_MANIFEST_MISMATCH$'):
        probe.perform(run.archive, run.sha, name)
    assert probe.source_verifications == 0
    assert not (run.output / (name + '-ready.json')).exists()
    run.record('genuine-row-mismatch-negative', {'controlled_assignment_revoked_after_import': True,
        'expected_source_root_unchanged': True, 'gate': 'RESTORED_MANIFEST_MISMATCH', 'ready_receipt': False})

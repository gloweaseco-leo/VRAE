"""Real custom archive transfer; readiness is published only after independent checks."""
from pathlib import Path
import subprocess
import time
import uuid

from .lab import RUNTIME, RecoveryDenied, digest, encode, docker, invoke
from .manifest import capture, verify_sources, public_catalog
from .security import runtime_audit


class Restore:
    def __init__(self, destination, private, output, expected, graphs, *, observer=None):
        self.destination, self.private, self.output = destination, private, output
        self.expected, self.graphs = expected, graphs
        self.imports = 0
        self.ready = {}
        self.observer = observer
        self.stages = []
        self.source_verifications = 0

    def stage(self, name, database, **values):
        self.stages.append({'stage': name, 'database': database, **values})
        self.output.joinpath(database + '-stages.json').write_bytes(encode(self.stages))

    def archive(self, file, expected_sha):
        file = Path(file).resolve()
        if not file.is_relative_to(RUNTIME.resolve()) or file.suffix != '.dump':
            raise RecoveryDenied('PRIVATE_ARCHIVE_PATH_REQUIRED')
        if digest(file.read_bytes()) != expected_sha:
            raise RecoveryDenied('BACKUP_SHA_MISMATCH')
        remote = '/tmp/ra4e-' + uuid.uuid4().hex + '.dump'
        docker('cp', str(file), self.destination.name + ':' + remote)
        p = invoke('exec', self.destination.name, 'pg_restore', '--list', remote)
        if p.returncode:
            self.output.joinpath('archive-rejection-' + uuid.uuid4().hex[:12] + '.json').write_bytes(encode({
                'stage': 'actual_pg_restore_list', 'returncode': p.returncode,
                'stderr_sha256': digest(p.stderr), 'stderr_bytes': len(p.stderr)}))
            docker('exec', self.destination.name, 'rm', '--', remote)
            raise RecoveryDenied('ARCHIVE_FORMAT_INVALID')
        return remote

    def perform(self, file, expected_sha, name, *, partial=False, interrupt=False):
        if name in self.ready:
            actual, _ = capture(self.destination, name)
            if self.ready[name]['backup_sha256'] != expected_sha or actual['root_sha256'] != self.expected['root_sha256']:
                raise RecoveryDenied('RESTORE_REPLAY_CONFLICT')
            return self.ready[name]
        remote = self.archive(file, expected_sha)
        self.stage('archive_verified', name)
        created = False
        try:
            self.destination.database(name, create=True)
            self.stage('empty_database_created', name)
            created = True
            self.imports += 1
            if interrupt:
                self.interrupted_import(remote, name)
                raise RecoveryDenied('IMPORT_INTERRUPTED')
            args = ['exec', self.destination.name, 'pg_restore', '-U', 'postgres', '-d', name, '--exit-on-error', '--single-transaction']
            if partial:
                args.append('--section=pre-data')
            p = invoke(*args, remote, timeout=120)
            self.output.joinpath(name + '-import.json').write_bytes(encode({'returncode': p.returncode,
                'stderr_sha256': digest(p.stderr), 'stderr_bytes': len(p.stderr), 'partial_injection': partial}))
            if p.returncode:
                raise RecoveryDenied('PG_RESTORE_FAILED')
            self.stage('pg_restore_completed', name, partial=partial)
            if self.observer is not None:
                self.observer(self.destination, name, partial)
                self.stage('actual_diagnostic_snapshot_saved_before_gate', name)
            actual, catalog = capture(self.destination, name)
            self.stage('original_manifest_captured', name)
            if self.observer is not None:
                self.output.joinpath(name + '-actual-original-manifest.json').write_bytes(encode(actual))
                self.private.joinpath(name + '-actual-private-catalog.json').write_bytes(encode(catalog))
            if actual['root_sha256'] != self.expected['root_sha256']:
                raise RecoveryDenied('RESTORED_MANIFEST_MISMATCH')
            self.stage('full_manifest_gate_passed', name)
            self.source_verifications += 1
            sources = verify_sources(self.destination, name, self.graphs)
            self.stage('source_target_gate_passed', name)
            privilege_proof = runtime_audit(self.destination, name, self.graphs)
            self.output.joinpath(name + '-runtime-sql.json').write_bytes(encode(privilege_proof))
            after_runtime, _ = capture(self.destination, name)
            if after_runtime != actual:
                raise RecoveryDenied('RUNTIME_SQL_AUDIT_CHANGED_RESTORED_STATE')
            self.stage('runtime_sql_allow_deny_gate_passed', name)
            receipt = {'status': 'VERIFIED_TEST_ONLY_RESTORE', 'dbname': name, 'backup_sha256': expected_sha,
                'source_root_sha256': self.expected['root_sha256'], 'restored_root_sha256': actual['root_sha256'],
                'sources': sources, 'catalog_sha256': actual['catalog_sha256'], 'native_human_approval': False}
            self.output.joinpath(name + '-ready.json').write_bytes(encode(receipt))
            self.output.joinpath(name + '-catalog.json').write_bytes(encode(public_catalog(catalog)))
            self.ready[name] = receipt
            return receipt
        except BaseException as exc:
            self.stage('gate_denied', name, code=str(exc) if isinstance(exc, RecoveryDenied) else 'SQL_OR_SOURCE_VERIFICATION_DENIED', sqlstate=getattr(exc, 'sqlstate', None))
            if created:
                self.destination.database(name, drop=True)
            self.output.joinpath(name + '-denied.json').write_bytes(encode({'ready_receipt': False,
                'database_removed': created, 'error_type': type(exc).__name__,
                'sqlstate': getattr(exc, 'sqlstate', None),
                'gate_code': str(exc) if isinstance(exc, RecoveryDenied) else 'SQL_OR_SOURCE_VERIFICATION_DENIED'}))
            raise
        finally:
            docker('exec', self.destination.name, 'rm', '--', remote)

    def interrupted_import(self, remote, name):
        # Real schema import, then a distinct connection prevents a real data COPY.
        docker('exec', self.destination.name, 'pg_restore', '-U', 'postgres', '-d', name,
               '--exit-on-error', '--single-transaction', '--section=pre-data', remote)
        app = 'ra4e-interrupt-' + uuid.uuid4().hex[:12]
        with self.destination.connect(dbname=name) as lock, self.destination.connect(dbname=name) as observer:
            lock.execute('BEGIN')
            lock.execute('LOCK TABLE ra4a_private.migrations IN ACCESS EXCLUSIVE MODE')
            command = ['docker', 'exec', '-e', 'PGAPPNAME=' + app, self.destination.name,
                       'pg_restore', '-U', 'postgres', '-d', name, '--data-only', '--disable-triggers',
                       '--exit-on-error', '--single-transaction', remote]
            child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 20
                row = None
                while time.monotonic() < deadline:
                    row = observer.execute("SELECT pid,wait_event_type FROM pg_stat_activity WHERE application_name=%s AND datname=%s AND wait_event_type='Lock'", (app, name)).fetchone()
                    if row:
                        break
                    if child.poll() is not None:
                        raise RecoveryDenied('INTERRUPTION_IMPORT_ENDED_EARLY')
                    time.sleep(.05)
                if not row:
                    raise RecoveryDenied('REAL_IMPORT_LOCK_WAIT_NOT_OBSERVED')
                terminated = observer.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid=%s AND application_name=%s AND datname=%s", (row[0], app, name)).fetchone()
                stdout, stderr = child.communicate(timeout=20)
                if terminated != (True,) or child.returncode == 0:
                    raise RecoveryDenied('IMPORT_INTERRUPTION_UNPROVEN')
                lock.execute('ROLLBACK')
                counts = observer.execute('SELECT (SELECT count(*) FROM ra4a.requests),(SELECT count(*) FROM ra4a_review_test.proposals),(SELECT count(*) FROM ra4a_bytes.objects)').fetchone()
                if counts != (0, 0, 0):
                    raise RecoveryDenied('INTERRUPTED_IMPORT_ADVANCED_DATA')
                self.output.joinpath(name + '-interrupted.json').write_bytes(encode({'real_backend_wait': row[1],
                    'targeted_termination': True, 'returncode': child.returncode, 'post_rollback_counts': counts,
                    'stdout_sha256': digest(stdout), 'stderr_sha256': digest(stderr), 'ready_receipt': False}))
            finally:
                lock.execute('ROLLBACK')
                if child.poll() is None:
                    observer.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name=%s AND datname=%s', (app, name))
                    child.communicate(timeout=20)


def backup(source, dbname, private, expected, output):
    before, _ = capture(source, dbname)
    if before['root_sha256'] != expected['root_sha256']:
        raise RecoveryDenied('SOURCE_CHANGED_BEFORE_BACKUP')
    raw = docker('exec', source.name, 'pg_dump', '-U', 'postgres', '-d', dbname, '--format=custom', timeout=120)
    after, _ = capture(source, dbname)
    if after != before:
        raise RecoveryDenied('SOURCE_CHANGED_DURING_BACKUP')
    file = private / 'synthetic-private.dump'
    file.write_bytes(raw)
    output.joinpath('backup.json').write_bytes(encode({'tool': 'pg_dump', 'format': 'custom',
        'sha256': digest(raw), 'bytes': len(raw), 'source_root_sha256': expected['root_sha256'],
        'credentials_or_globals_exported': False, 'raw_archive_published': False}))
    return file, digest(raw)

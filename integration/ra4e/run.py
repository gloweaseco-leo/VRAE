"""Standalone genuine restore runner; produces only bounded sanitized public evidence."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

from .lab import DOCS, RUNTIME, ROOT, LABEL, docker, digest, encode, RecoveryDenied


def no_owned_resources():
    observed = {}
    for kind, args in [('container', ['ps', '-aq']), ('network', ['network', 'ls', '-q']), ('volume', ['volume', 'ls', '-q'])]:
        value = docker(*args, '--filter', 'label=' + LABEL).decode().strip()
        observed[kind] = len(value.splitlines()) if value else 0
    if any(observed.values()):
        raise RecoveryDenied('EXISTING_B7_OWNED_RESOURCE_STOP')
    return observed


def source_manifest():
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT).decode().strip()
    rows = git('ls-tree', '-r', 'HEAD', '--', 'vrae', 'apps', 'worker', 'db', 'infra', 'integration/ra4a', 'tests', '.github/workflows').splitlines()
    return {'head': git('rev-parse', 'HEAD'), 'head_record': git('log', '-1', '--format=%H %P'),
        'github_sha': os.environ.get('GITHUB_SHA'), 'github_run_id': os.environ.get('GITHUB_RUN_ID'),
        'python': sys.version, 'protected_blob_mode_sha256': digest('\n'.join(rows).encode()),
        'restore_source_sha256': {p.relative_to(ROOT).as_posix(): digest(p.read_bytes().replace(b'\r\n', b'\n'))
                                  for p in sorted((ROOT / 'integration/ra4e').glob('*.py'))},
        'migration_sha256': {p.name: digest(p.read_bytes().replace(b'\r\n', b'\n')) for p in sorted((ROOT / 'db/migrations').glob('*.sql'))}}


def publication(output, private):
    secrets = []
    for file in private.rglob('scan-credentials.json'):
        secrets.extend(json.loads(file.read_text()))
    token = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
    files, matches = {}, []
    for file in output.rglob('*'):
        if not file.is_file():
            continue
        raw = file.read_bytes()
        relative = file.relative_to(output).as_posix()
        files[relative] = digest(raw)
        if (file.suffix in ['.dump', '.bin', '.env'] or file.name == 'state.json'
                or token.search(raw) or any(s.encode() in raw for s in secrets)):
            matches.append(relative)
    output.joinpath('publication.json').write_bytes(encode({'files_scanned': len(files),
        'actual_fixture_credentials_compared': len(set(secrets)), 'matches': matches,
        'publication_allowed': not matches, 'artifact_file_sha256': files}))
    if matches:
        raise RecoveryDenied('PUBLICATION_SECRET_OR_RAW_ARCHIVE_DENIED')


def public_junit(raw_xml):
    """Rebuild names/status only; never copy traceback, properties or streams."""
    original = ET.fromstring(raw_xml)
    cases = original.findall('.//testcase')
    suite = ET.Element('testsuite', name='B7-P0 real PG16 recovery', tests=str(len(cases)),
        failures=str(sum(c.find('failure') is not None for c in cases)),
        errors=str(sum(c.find('error') is not None for c in cases)),
        skipped=str(sum(c.find('skipped') is not None for c in cases)))
    for case in cases:
        # Parameter IDs in this suite are fixed synthetic role/query constants.
        safe = ET.SubElement(suite, 'testcase', name=case.attrib['name'],
            classname='integration.ra4e.cases')
        for kind in ['failure', 'error', 'skipped']:
            if case.find(kind) is not None:
                ET.SubElement(safe, kind, message='See private original; digest in receipt')
    return ET.tostring(suite, encoding='utf-8', xml_declaration=True)


def artifact(output, private):
    """Classify generated records by producer, then scan the bounded export."""
    # Full catalogs and diagnostic snapshots remain local even when synthetic.
    fixed = {'before-owned-absence.json', 'after-owned-absence.json', 'backup.json',
        'independent-before-backup.json', 'independent-accepted-originals.json',
        'verified-original-audit-outbox.json', 'restored-original-semantics.json',
        'identity-recovery-boundary.json', 'restored-lease-recovery.json',
        'acl-null-empty-sql-proof.json', 'independent-security-plane-equality.json',
        'thirteen-table-semantic-acl-proof.json', 'genuine-row-mismatch-negative.json',
        'final-cleanup.json', 'ownership.json', 'transport.json', 'cleanup.json'}
    generated = re.compile(r'(?:vrae_p2b1_[0-9a-f]{12}-(?:stages|import|ready|denied|interrupted)|'
        r'archive-rejection-[0-9a-f]{12}|denial-(?:p2b1_test_b_reviewer|ra4a_test_unassigned|ra4a_test_b_app))\.json')
    destination = output / 'public-artifact'
    destination.mkdir(exist_ok=False)
    inventory = []
    for file in sorted(output.rglob('*')):
        if not file.is_file() or destination in file.parents:
            continue
        relative = file.relative_to(output)
        name = file.name
        if len(relative.parts) == 1 and name in {'source.json', 'receipt.json'}:
            category = 'source identity and actual aggregate status'
        elif name == 'tests.xml':
            category = 'rebuilt names and statuses; original digest in receipt'
        elif name in fixed or generated.fullmatch(name):
            category = 'synthetic catalog counters, ACL tuples, SQLSTATEs or ordered stages'
        elif name == 'source-runtime-sql.json' or re.fullmatch(r'vrae_p2b1_[0-9a-f]{12}-runtime-sql\.json', name):
            category = 'actual SQL counts, role identity and scoped allow/deny'
        else:
            continue
        raw = file.read_bytes()
        if category == 'actual SQL counts, role identity and scoped allow/deny':
            value = json.loads(raw)
            raw = encode({k: value[k] for k in ['actual_sql', 'raw_denial_count', 'matrix_sha256',
                'scoped_allow_deny', 'authorized_originals']})
        elif name == 'tests.xml':
            raw = public_junit(raw)
        else:
            json.loads(raw)  # Fail closed on malformed producer output.
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        inventory.append({'path': relative.as_posix(), 'bytes': len(raw), 'sha256': digest(raw),
            'classification': category, 'provenance': 'B7 TEST_ONLY generated record; never raw DB rows'})
    if not list(private.rglob('scan-credentials.json')):
        raise RecoveryDenied('ARTIFACT_CREDENTIAL_INVENTORY_MISSING')
    destination.joinpath('classification.json').write_bytes(encode({'files': inventory,
        'excluded': ['full catalogs', 'raw JUnit/logs', 'diagnostic snapshots', 'runtime state', 'archives'],
        'classification_manifest_self_hash': 'external artifact digest'}))
    publication(destination, private)
    return destination


def run(output, repeats):
    output = Path(output).resolve()
    if not output.is_relative_to(DOCS.resolve()) or repeats not in [1, 2]:
        raise RecoveryDenied('BOUNDED_RESTORE_OUTPUT_REQUIRED')
    output.mkdir(parents=True, exist_ok=False)
    private = RUNTIME / ('run-' + uuid.uuid4().hex[:12])
    private.mkdir(parents=True, exist_ok=False)
    source = source_manifest()
    output.joinpath('source.json').write_bytes(encode(source))
    runs = []
    failed = False
    completed = False
    try:
        for number in range(1, repeats + 1):
            folder = output / ('standalone-' + str(number))
            folder.mkdir()
            folder.joinpath('before-owned-absence.json').write_bytes(encode(no_owned_resources()))
            env = dict(os.environ, PYTHONUTF8='1', RA4E_OUTPUT=str(folder), RA4E_PRIVATE=str(private / str(number)))
            raw_junit = private / ('original-junit-' + str(number) + '.xml')
            argv = [sys.executable, '-B', '-m', 'pytest', '-q', '--tb=short', '--import-mode=importlib',
                '--confcutdir=integration/ra4e', 'integration/ra4e/cases.py',
                '--basetemp=' + str(private / ('pytest-' + str(number))), '--junitxml=' + str(raw_junit)]
            result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True)
            for name, raw in [('stdout.log', result.stdout), ('stderr.log', result.stderr)]:
                private.joinpath(str(number) + '-' + name).write_bytes(raw)
            folder.joinpath('after-owned-absence.json').write_bytes(encode(no_owned_resources()))
            raw_xml = raw_junit.read_bytes()
            xml = ET.fromstring(raw_xml)
            folder.joinpath('tests.xml').write_bytes(public_junit(raw_xml))
            cases = xml.findall('.//testcase')
            row = {'standalone': number, 'returncode': result.returncode, 'tests': len(cases),
                   'failures': sum(any(c.find(k) is not None for k in ['failure', 'error']) for c in cases),
                   'skips': sum(c.find('skipped') is not None for c in cases),
                   'stdout_sha256': digest(result.stdout), 'stderr_sha256': digest(result.stderr),
                   'original_junit_sha256': digest(raw_xml), 'public_junit_sha256': digest(folder.joinpath('tests.xml').read_bytes()),
                   'public_copy_names_status_only': True}
            runs.append(row)
            print(json.dumps(row), flush=True)
            if result.returncode or row['tests'] != 23 or row['skips'] or row['failures']:
                failed = True
                break
        if source_manifest() != source:
            raise RecoveryDenied('SOURCE_CHANGED_DURING_RECOVERY')
        completed = not failed and len(runs) == repeats
    finally:
        output.joinpath('receipt.json').write_bytes(encode({'source': source['head'], 'standalone_runs': runs,
            'required_standalone_runs': repeats, 'synthetic_only': True, 'native_human_approval': False,
            'status': 'TEST_ONLY_RECOVERY_GATES_PASSED' if completed else 'RED_OR_INCOMPLETE'}))
        artifact(output, private)
    if failed or len(runs) != repeats:
        raise RecoveryDenied('ACTUAL_RESTORE_SUITE_RED_STOP')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output')
    parser.add_argument('--repeats', type=int, default=2)
    options = parser.parse_args()
    run(options.output, options.repeats)

"""Native runner. Exports only hashed/sanitized evidence after credential scan."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from integration.ra4e.lab import ROOT, digest, encode
from integration.ra4e.run import publication, public_junit

PACKAGE = Path(__file__).resolve().parent
DOCS = ROOT / 'docs/03-engineering/beta-closure/codex3/b7_restore_v1'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    options = parser.parse_args()
    assert re.fullmatch(r'[a-z0-9-]{3,64}', options.run_id)
    minor = str(sys.version_info.major) + str(sys.version_info.minor)
    assert minor in ('311', '313'), 'NATIVE_PYTHON_311_OR_313_REQUIRED'
    private = PACKAGE / '.private' / options.run_id
    public = DOCS / options.run_id
    private.mkdir(parents=True, exist_ok=False)
    public.mkdir(parents=True, exist_ok=False)
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT).decode().strip()
    source = {'head': git('rev-parse', 'HEAD'), 'parents': git('show', '-s', '--format=%P', 'HEAD'),
              'branch': git('branch', '--show-current'), 'python': sys.version,
              'github_sha': os.environ.get('GITHUB_SHA'), 'github_run_id': os.environ.get('GITHUB_RUN_ID'),
              'code_sha256': {p.relative_to(ROOT).as_posix(): digest(p.read_bytes().replace(b'\r\n', b'\n'))
                             for p in sorted(PACKAGE.glob('*.py'))},
              'protected_git_tree_sha256': digest(git('ls-tree', '-r', 'HEAD', '--',
                  'db', 'worker', 'vrae', 'apps', 'integration/ra4a', 'integration/ra4b',
                  'integration/b3_p0', 'integration/ra4e').encode()),
              'test_only': True, 'full_beta_exit': False, 'old_A1_new_experiments': 0}
    (public / 'source.json').write_bytes(encode(source))
    environment = os.environ.copy()
    environment.update(B7RV1_PRIVATE=str(private), B7RV1_PUBLIC=str(public), B7RV1_MINOR=minor,
                       PYTHONDONTWRITEBYTECODE='1', PYTHONFAULTHANDLER='1')
    started = time.monotonic()
    with (private / 'native.log').open('wb') as stream:
        process = subprocess.run([sys.executable, '-B', '-m', 'pytest', '-q',
            str(PACKAGE / 'test_recovery.py'), '--junitxml=' + str(private / 'tests.xml'),
            '-p', 'no:cacheprovider'], cwd=ROOT, env=environment,
            stdout=stream, stderr=subprocess.STDOUT, timeout=1200)
    if (private / 'tests.xml').exists():
        suite = ET.fromstring(public_junit((private / 'tests.xml').read_bytes()))
        suite.set('name', 'B7-P1 native six-schema three-environment PG16 recovery')
        for case in suite.findall('testcase'):
            case.set('classname', 'integration.beta_review.codex3.b7_restore_v1.test_recovery')
        (public / 'tests.xml').write_bytes(ET.tostring(suite, encoding='utf-8', xml_declaration=True))
    receipt = {'native_pytest_exit': process.returncode,
               'elapsed_seconds': time.monotonic() - started,
               'native_log_sha256': digest((private / 'native.log').read_bytes()),
               'native_junit_sha256': digest((private / 'tests.xml').read_bytes()) if (private / 'tests.xml').exists() else None,
               'candidate': process.returncode == 0,
               'full_B7_EXIT': False, 'old_A1': 'PAUSED/MAX3 0/3 unchanged',
               'private_dump_retention': 'never published; destroy after verified evidence inventory',
               'source_head': source['head']}
    (public / 'receipt.json').write_bytes(encode(receipt))
    if not (private / 'scan-credentials.json').exists():
        print('STOP: credential inventory absent; no export permitted', flush=True)
        return 2
    publication(public, private)
    print(json.dumps({'run_id': options.run_id, 'native_pytest_exit': process.returncode,
                      'publication_allowed': True, 'candidate': receipt['candidate']}), flush=True)
    return process.returncode


if __name__ == '__main__':
    raise SystemExit(main())

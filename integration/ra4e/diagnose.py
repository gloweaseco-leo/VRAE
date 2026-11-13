"""Owner 6854094838: exactly one 3.11 fresh-pair diagnostic, then STOP."""
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

from .lab import RUNTIME, DOCS, ROOT, encode, digest
from .run import source_manifest, publication, no_owned_resources


def main():
    assert sys.version_info[:2] == (3, 11), 'OWNER_ONE_RUN_PY311_ONLY'
    output = DOCS / 'evidence/diagnostic-go-6854094838-311'
    private = RUNTIME / 'diagnostic-go-6854094838'
    RUNTIME.mkdir(exist_ok=True, parents=True)
    # Exclusive sentinel prevents an accidental second invocation of this GO.
    with (RUNTIME / 'diagnostic-go-6854094838.started').open('x') as stream:
        stream.write('ONE_AUTHORIZED_PY311_DIAGNOSTIC_ONLY\n')
    output.mkdir(parents=True, exist_ok=False)
    private.mkdir(parents=True, exist_ok=False)
    source = source_manifest()
    output.joinpath('source.json').write_bytes(encode(source))
    output.joinpath('before-owned-absence.json').write_bytes(encode(no_owned_resources()))
    env = dict(os.environ, PYTHONUTF8='1', RA4E_OUTPUT=str(output),
               RA4E_PRIVATE=str(private / 'pair'), RA4E_DIAGNOSTIC='ONE_RUN')
    command = [sys.executable, '-B', '-m', 'pytest', '-q', '--tb=short', '--import-mode=importlib',
               '--confcutdir=integration/ra4e', 'integration/ra4e/diagnostic_cases.py',
               '--basetemp=' + str(private / 'pytest'), '--junitxml=' + str(output / 'tests.xml')]
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True)
    output.joinpath('stdout.log').write_bytes(result.stdout)
    output.joinpath('stderr.log').write_bytes(result.stderr)
    output.joinpath('after-owned-absence.json').write_bytes(encode(no_owned_resources()))
    cases = ET.parse(output / 'tests.xml').getroot().findall('.//testcase')
    receipt = {'status': 'DIAGNOSTIC_COMPLETE_STOP_OWNER_SECOND_DECISION_REQUIRED',
        'owner_go': 6854094838, 'fresh_pairs': 1, 'python': sys.version,
        'pytest_returncode': result.returncode, 'collected': len(cases),
        'passed': sum(not any(c.find(k) is not None for k in ['failure', 'error', 'skipped']) for c in cases),
        'failures': sum(c.find('failure') is not None for c in cases),
        'errors': sum(c.find('error') is not None for c in cases),
        'blocked_or_skipped': [{'name': c.get('name'), 'reason': c.find('skipped').get('message')} for c in cases if c.find('skipped') is not None],
        'original_red_overwritten': False, 'oracle_normalized': False,
        'source_unchanged_during_run': source_manifest() == source,
        'commit_push_pr_ci_deploy': False}
    output.joinpath('receipt.json').write_bytes(encode(receipt))
    diffs = []
    for file in output.glob('full-*-diff.json'):
        value = json.loads(file.read_text())
        diffs.extend(value['differences'])
    classes = {}
    for row in diffs:
        classes[row['classification']] = classes.get(row['classification'], 0) + 1
    matrix = {'classification_counts': classes, 'capped_differences': diffs[:30], 'cap': 30,
        'full_diff_files': {p.name: digest(p.read_bytes()) for p in output.glob('*-diff.json')},
        'semantic_normalization_applied': False}
    output.joinpath('capped-diff-matrix.json').write_bytes(encode(matrix))
    publication(output, private)
    print(json.dumps(receipt, indent=2))
    print(json.dumps({'classification_counts': classes, 'diff_files': matrix['full_diff_files']}, indent=2))
    for row in diffs[:12]:
        print(json.dumps({'capped_sanitized_diff': row}, separators=(',', ':')))
    print('OWNER_DIAGNOSTIC_BOUND_REACHED_STOP_NO_FURTHER_RUNS')


if __name__ == '__main__':
    main()

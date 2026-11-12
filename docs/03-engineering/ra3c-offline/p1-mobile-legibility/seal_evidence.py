"""Seal P1 real results without overwriting original 1.0.1 evidence."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import zipfile

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
OLD = '6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2'
MAIN = '60dbe1e1acfc84ad0849e84f3abe3712ad8ebccd'
FUNCTIONAL = '2be7a177d5c5e33492eb63ff4847bb3a67790996'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def raw(ref, path):
    return git('show', ref + ':' + path)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, indent=2) + '\n').encode('utf-8'))


def status(case):
    return ('failed' if case.find('failure') is not None else 'error'
            if case.find('error') is not None else 'skipped'
            if case.find('skipped') is not None else 'passed')


def trees(ref):
    return {line.split('\t')[1]: line.split('\t')[0]
            for line in git('ls-tree', '-r', ref).decode().splitlines()}


results = []
for label in ('python311', 'python313'):
    folder = ROOT / 'docs/03-engineering/ra3c-offline/.checks' / ('p1-' + label)
    summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    assert len(summary['results']) == 25 and all(r['matches'] for r in summary['results'])
    cases = ET.parse(folder / 'full.xml').findall('.//testcase')
    counts = {s: sum(status(c) == s for c in cases) for s in ('passed', 'failed', 'error', 'skipped')}
    assert counts == {'passed': 1943, 'failed': 0, 'error': 0, 'skipped': 25}, counts
    groups = {}
    for name, classname, count in (
        ('reporting', 'tests.reporting.test_draft', 71),
        ('frozen_qa44', 'tests.interpretation.test_ra3b_independent_adversarial', 224),
        ('prior_qa', 'tests.findings.test_ra2c3_independent_adversarial', 139)):
        selected = [c for c in cases if c.get('classname') == classname]
        assert len(selected) == count and all(status(c) == 'passed' for c in selected)
        groups[name] = count
    skipped = [{'classname': c.get('classname'), 'name': c.get('name'),
                'reason': c.find('skipped').get('message')} for c in cases if status(c) == 'skipped']
    assert all(c['classname'] in ('tests.collection.test_isolated',
                                 'tests.browser.test_isolated_browser') for c in skipped)
    prior = json.loads((OUT / ('previous-engine-' + label + '.json')).read_text(encoding='utf-8'))
    assert prior['status'] == 'PRIOR_RENDERER_OWN_ENGINE_REPLAY_PASS' and len(prior['cases']) == 8
    assert prior['module_sha256'] == sha(raw(OLD, 'vrae/reporting/renderer.py'))
    old_pins = json.loads((OUT / 'previous-caller-pins.json').read_text(encoding='utf-8'))
    for row in prior['cases']:
        assert row['draft_ref'] == old_pins[row['case']]['expected_draft_ref']
        assert row['html_sha256'] == old_pins[row['case']]['expected_html_sha256']
    summary.update({'functional_commit': FUNCTIONAL, 'accepted_main': MAIN, 'full_counts': counts,
                    'groups_passed': groups, 'skips': skipped, 'prior_renderer_own_engine_replays': 8,
                    'child_utf8_mode': True})
    dest = OUT / 'local' / label
    dest.mkdir(parents=True, exist_ok=True)
    write(dest / 'summary.json', summary)
    (dest / 'full.xml').write_bytes((folder / 'full.xml').read_bytes())
    results.append({'runtime': label, 'python': summary['python'], 'counts': counts,
                    'groups': groups, 'commands_matched': 25, 'prior_engine_replays': 8})

browser = json.loads((OUT / 'ui/browser-acceptance.json').read_text(encoding='utf-8'))
assert len(browser['results']) == 18 and not browser['external_requests'] and not browser['runtime_exceptions']
assert sum(r['evidence_anchors_clicked'] for r in browser['results']) == 108
for row in browser['results']:
    m = row['metrics']
    assert m['banner']['minFontPx'] >= 12 and m['banner']['visible']
    assert m['banner']['top'] >= 0 and m['banner']['bottom'] <= row['viewport']['height']
    assert m['scrollWidth'] <= row['viewport']['width'] + 1
    assert sha((OUT / 'preview' / ('contact-' + row['case'] + '.html')).read_bytes()) == row['html_sha256']
    if row['printProof']:
        assert row['printProof']['pages'] == 1
        assert sha((OUT / 'ui' / ('contact-' + row['case'] + '-A4.pdf')).read_bytes()) == row['printProof']['pdf_sha256']
red = json.loads((OUT / 'prior-renderer-red/banner-red-404-375.json').read_text(encoding='utf-8'))
assert red['metrics']['banner']['minFontPx'] == 11
assert red['html_sha256'] == sha(raw(OLD, 'docs/03-engineering/ra3c-offline/preview/contact-404.html'))

before, accepted, current = trees(OLD), trees(MAIN), trees('HEAD')
assert len(accepted) == 1416 and all(current[p] == v for p, v in accepted.items())
historic = [p for p in before if p.startswith('docs/03-engineering/ra3c-offline/')
            and p != 'docs/03-engineering/ra3c-offline/README.md']
assert all(current[p] == before[p] for p in historic)
assert not git('diff', FUNCTIONAL, '--', 'vrae/reporting', 'tests/reporting', 'scripts/verify_ra3c.py')
old_renderer = raw(OLD, 'vrae/reporting/renderer.py').decode('utf-8')
new_renderer = (ROOT / 'vrae/reporting/renderer.py').read_text(encoding='utf-8')
needle = '.private-bar{padding:10px 16px;gap:3px 10px;font-size:12px}'
assert new_renderer.count(needle) == 1
assert new_renderer.replace("RENDERER_VERSION = 'ra3c-html-1.0.2'", "RENDERER_VERSION = 'ra3c-html-1.0.1'").replace(
    needle, needle.replace('font-size:12px', 'font-size:11px')) == old_renderer
old_tests = ast.parse(raw(OLD, 'tests/reporting/test_draft.py'))
new_tests = ast.parse((ROOT / 'tests/reporting/test_draft.py').read_text(encoding='utf-8'))
new_defs = {n.name: ast.dump(n, include_attributes=False) for n in new_tests.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
for node in old_tests.body:
    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
        assert new_defs[node.name] == ast.dump(node, include_attributes=False)
current_pins = json.loads((ROOT / 'tests/reporting/fixtures/caller-pins.json').read_text(encoding='utf-8'))
for name, held in old_pins.items():
    assert current_pins[name]['expected_issue_count'] == held['expected_issue_count']
    assert {k: v for k, v in current_pins[name]['pins'].items() if k != 'expected_renderer_version'} == {
        k: v for k, v in held['pins'].items() if k != 'expected_renderer_version'}
source_sha = sha((ROOT / 'tests/reporting/fixtures/sources.json').read_bytes())
assert source_sha == '3189a276ffabfa307f9e0c478208941b3868bd27895f0281928c0d96000bb26b'
snapshot = json.loads((OUT / 'previous-engine-source.json').read_text(encoding='utf-8'))
assert snapshot['prior_commit'] == OLD
assert sha(git('-c', 'core.autocrlf=false', '-c', 'core.eol=lf', 'archive', '--format=zip', OLD)) == snapshot['snapshot_zip_sha256']
tree = Path(snapshot['source_path']).resolve()
assert tree.is_relative_to((ROOT / 'docs/03-engineering/ra3c-offline/.checks').resolve())
for entry in snapshot['entries']:
    assert sha((tree / entry['path']).read_bytes()) == entry['sha256']
proof = {'accepted_main': MAIN, 'accepted_files_preserved': len(accepted), 'accepted_git_entries': accepted,
         'prior_sha': OLD, 'prior_historical_report_artifacts_preserved': len(historic),
         'prior_artifact_git_entries': {p: before[p] for p in historic},
         'functional_commit': FUNCTIONAL, 'current_head_before_evidence_commit': git('rev-parse', 'HEAD').decode().strip(),
         'production_delta': 'ONLY_RENDERER_VERSION_AND_MOBILE_PRIVATE_BAR_11_TO_12',
         'original_reporting_test_definitions_ast_unchanged': True,
         'prior_engine_source_files_reverified': len(snapshot['entries']),
         'source_guard_raw_container_sha256': source_sha, 'guard_policy_semantics_unchanged': True,
         'runtime_results': results, 'screen_views': 18, 'anchor_clicks': 108,
         'prior_font_red': 11, 'new_screen_font_min': 12}
write(OUT / 'source-and-results-proof.json', proof)

archives = []
def archive(name, paths, base=OUT):
    entries = []
    with zipfile.ZipFile(OUT / name, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(paths):
            assert p.resolve().is_relative_to(base.resolve())
            data = p.read_bytes()
            key = p.relative_to(base).as_posix()
            z.writestr(key, data)
            entries.append({'path': key, 'bytes': len(data), 'sha256': sha(data)})
    with zipfile.ZipFile(OUT / name) as z:
        assert z.testzip() is None
        assert all(sha(z.read(e['path'])) == e['sha256'] for e in entries)
    archives.append({'archive': name, 'sha256': sha((OUT / name).read_bytes()), 'entries': entries})

paths = [p for name in ('preview', 'ui', 'local', 'prior-renderer-red', 'prior-export-crlf') for p in (OUT / name).rglob('*') if p.is_file()]
paths += list(OUT.glob('previous-engine-*.json')) + [OUT / 'previous-caller-pins.json', OUT / 'previous-pr-body.md']
archive('p1-current-and-prior-proof-raw.zip', paths)
for label in ('python311', 'python313'):
    folder = ROOT / 'docs/03-engineering/ra3c-offline/.checks' / ('p1-' + label)
    archive(label + '-full-raw.zip', [p for p in folder.iterdir() if p.is_file()], ROOT)
archive('source-fixtures-raw.zip', list((ROOT / 'tests/reporting/fixtures').glob('*.json')), ROOT)
ci = ROOT / 'docs/03-engineering/ra3c-offline/.checks/ci-43165855835'
if (ci / 'security-proof.json').exists():
    archive('p1-functional-ci-raw.zip', [p for p in ci.iterdir() if p.is_file()], ROOT)
    dest = OUT / 'ci-functional'
    dest.mkdir(exist_ok=True)
    for name in ('proof.json', 'security-proof.json'):
        (dest / name).write_bytes((ci / name).read_bytes())
write(OUT / 'archive-index.json', archives)
print(json.dumps({'results': results, 'accepted_main_files': len(accepted),
                  'prior_artifacts_preserved': len(historic), 'archives': len(archives)}))

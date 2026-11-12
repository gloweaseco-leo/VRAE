"""One explicit pre-release layout revision; never regenerates source/guard truth."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.verify_ra3c import load_case, FIXTURES  # noqa: E402
from vrae.reporting import build_draft  # noqa: E402
from vrae.reporting.renderer import RENDERER_VERSION  # noqa: E402

OUT = Path(__file__).resolve().parent
held_path = FIXTURES / 'caller-pins.json'
source_path = FIXTURES / 'sources.json'
before = hashlib.sha256(source_path.read_bytes()).hexdigest()
old = json.loads(held_path.read_text(encoding='utf-8'))
assert all(c['pins']['expected_renderer_version'] == 'ra3c-html-1.0.0' for c in old.values())
assert RENDERER_VERSION == 'ra3c-html-1.0.1'
archive = OUT / 'initial-render-baseline.json'
assert not archive.exists()
archive.write_text(json.dumps({'sources_sha256': before, 'caller_pins': old}, sort_keys=True, indent=2) + '\n', encoding='utf-8')
for folder in ('preview', 'ui'):
    source = OUT / folder
    destination = OUT / (folder + '-initial')
    assert source.resolve().is_relative_to(OUT.resolve()) and not destination.exists()
    if source.exists():
        shutil.copytree(source, destination)
new = {}
for name, held in old.items():
    p, f, g, m, pins, _ = load_case(name)
    updated = {**pins, 'expected_renderer_version': RENDERER_VERSION}
    d = build_draft(p, f, g, m, **updated)
    assert len(d.document['issues']) == held['expected_issue_count']
    assert {k: v for k, v in updated.items() if k != 'expected_renderer_version'} == {
        k: v for k, v in pins.items() if k != 'expected_renderer_version'}
    new[name] = {**held, 'pins': updated, 'expected_draft_ref': d.ref,
                 'expected_html_sha256': d.document['html_sha256']}
assert hashlib.sha256(source_path.read_bytes()).hexdigest() == before
held_path.write_text(json.dumps(new, sort_keys=True, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': 'EXPLICIT_LAYOUT_BASELINE_REVISION', 'source_and_guard_bytes_unchanged': before,
                  'from': 'ra3c-html-1.0.0', 'to': RENDERER_VERSION,
                  'issue_counts_unchanged': {k: v['expected_issue_count'] for k, v in new.items()}}))

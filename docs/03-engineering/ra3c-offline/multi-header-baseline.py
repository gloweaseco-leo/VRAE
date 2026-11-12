"""Preserve the genuine two-page print failure; refresh only new render hashes."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.verify_ra3c import load_case, FIXTURES  # noqa: E402
from vrae.reporting import build_draft  # noqa: E402

OUT = Path(__file__).resolve().parent
source_path = FIXTURES / 'sources.json'
before = hashlib.sha256(source_path.read_bytes()).hexdigest()
pin_path = FIXTURES / 'caller-pins.json'
old = json.loads(pin_path.read_text(encoding='utf-8'))
archive = OUT / 'print-red-multi-header-baseline.json'
assert not archive.exists()
archive.write_text(json.dumps({'failure': 'ONE_PAGE_PRINT_REQUIRED_404_ACTUAL_2',
    'cause': 'Three-issue print total 1101.828px; card body now fits, header/footer spacing remains excessive.',
    'fix': 'Compact three-issue print header/footer only; same facts and one-page assertion.',
    'source_guard_sha256': before, 'caller_pins': old}, indent=2, sort_keys=True) + '\n', encoding='utf-8')
destination = OUT / 'preview-print-red-multi-header'
assert not destination.exists() and destination.resolve().is_relative_to(OUT.resolve())
shutil.copytree(OUT / 'preview', destination)
new = {}
for name, held in old.items():
    p, f, g, m, pins, _ = load_case(name)
    d = build_draft(p, f, g, m, **pins)
    assert len(d.document['issues']) == held['expected_issue_count']
    new[name] = {**held, 'expected_draft_ref': d.ref, 'expected_html_sha256': d.document['html_sha256']}
assert hashlib.sha256(source_path.read_bytes()).hexdigest() == before
pin_path.write_text(json.dumps(new, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print(json.dumps({'source_guard_bytes_unchanged': before, 'facts_and_issue_counts_unchanged': True,
                  'one_page_expectation_unchanged': True}))

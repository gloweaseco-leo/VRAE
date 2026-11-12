"""P1-only output baseline update; raw source, guards and issue counts are immutable."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from scripts.verify_ra3c import FIXTURES, load_case  # noqa: E402
from vrae.reporting import build_draft  # noqa: E402
from vrae.reporting.renderer import RENDERER_VERSION  # noqa: E402

OUT = Path(__file__).resolve().parent
old = json.loads((OUT / 'previous-caller-pins.json').read_text(encoding='utf-8'))
path = FIXTURES / 'caller-pins.json'
assert json.loads(path.read_text(encoding='utf-8')) == old
source_sha = hashlib.sha256((FIXTURES / 'sources.json').read_bytes()).hexdigest()
assert source_sha == '3189a276ffabfa307f9e0c478208941b3868bd27895f0281928c0d96000bb26b'
assert RENDERER_VERSION == 'ra3c-html-1.0.2'
new = {}
for name, held in old.items():
    p, f, g, m, pins, _ = load_case(name)
    assert pins['expected_renderer_version'] == 'ra3c-html-1.0.1'
    current = {**pins, 'expected_renderer_version': RENDERER_VERSION}
    d = build_draft(p, f, g, m, **current)
    assert len(d.document['issues']) == held['expected_issue_count']
    new[name] = {**held, 'pins': current, 'expected_draft_ref': d.ref,
                 'expected_html_sha256': d.document['html_sha256']}
assert hashlib.sha256((FIXTURES / 'sources.json').read_bytes()).hexdigest() == source_sha
path.write_bytes((json.dumps(new, sort_keys=True, indent=2) + '\n').encode('utf-8'))
(OUT / 'pin-update.json').write_bytes((json.dumps({
    'authority': 'https://github.com/gloweaseco-leo/VRAE/pull/47#issuecomment-6815824618',
    'from': 'ra3c-html-1.0.1', 'to': RENDERER_VERSION,
    'raw_source_guard_container_sha256_unchanged': source_sha,
    'facts_guard_pins_metadata_and_issue_counts_unchanged': True,
    'prior_pins': 'previous-caller-pins.json', 'current': new}, indent=2) + '\n').encode('utf-8'))
print('P1_RENDER_ONLY_PINS_UPDATED_SOURCE_GUARD_FACTS_UNCHANGED')

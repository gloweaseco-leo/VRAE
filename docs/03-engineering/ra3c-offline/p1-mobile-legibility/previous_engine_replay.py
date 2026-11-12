"""Replay the retained 1.0.1 reports using their exact original engine, never the new loader."""
import hashlib
import json
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TREE = ROOT / 'docs/03-engineering/ra3c-offline/.checks/p1-previous-engine/tree'
assert TREE.is_dir(), 'PREVIOUS_ENGINE_SNAPSHOT_NOT_PREPARED'
sys.path.insert(0, str(TREE))
from vrae.reporting.renderer import RENDERER_VERSION  # noqa: E402
import vrae.reporting.renderer as renderer  # noqa: E402

assert RENDERER_VERSION == 'ra3c-html-1.0.1'
assert Path(renderer.__file__).resolve().is_relative_to(TREE.resolve())
script = TREE / 'scripts/verify_ra3c.py'
label = 'python' + str(sys.version_info.major) + str(sys.version_info.minor)
output = TREE / 'docs/03-engineering/ra3c-offline' / ('replay-' + label)
sys.argv = [str(script), '--output', str(output)]
runpy.run_path(str(script), run_name='__main__')
summary = json.loads((output / 'replay-summary.json').read_text(encoding='utf-8'))
assert len(summary['cases']) == 8
assert all(c['issues'] == (1 if c['case'] in ('404', '410') else 0) for c in summary['cases'])
result = {'status': 'PRIOR_RENDERER_OWN_ENGINE_REPLAY_PASS',
    'prior_commit': '6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2', 'renderer': RENDERER_VERSION,
    'python': sys.version, 'module_path': renderer.__file__,
    'module_sha256': hashlib.sha256(Path(renderer.__file__).read_bytes()).hexdigest(),
    'cases': summary['cases'], 'current_engine_compatibility': '1.0.2_REJECTS_1.0.1_PINS_BY_DESIGN'}
(HERE / ('previous-engine-' + label + '.json')).write_bytes((json.dumps(result, indent=2) + '\n').encode('utf-8'))
print(json.dumps(result, sort_keys=True))

"""Record real pytest outcomes; never convert unsupported/failed tests to success."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
TEST = 'tests/findings/test_ra2c3_independent_adversarial.py'
parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, default=ROOT)
parser.add_argument('--label', required=True)
parser.add_argument('--target-sha', required=True)
parser.add_argument('--contract-only', action='store_true')
parser.add_argument('--archive-manifest', type=Path)
args = parser.parse_args()
out = ROOT / 'docs/03-engineering/ra2c3-independent-qa/runs' / args.label
out.mkdir(parents=True, exist_ok=False)
command = [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', TEST,
           '--tb=short', '--junitxml=' + str(out / 'junit.xml')]
if args.contract_only:
    command += ['-k', 'contract']
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
started = datetime.now(timezone.utc).isoformat()
import_probe = subprocess.run([sys.executable, '-c',
    'import vrae.findings.builder; print(vrae.findings.builder.__file__)'],
    cwd=args.root, env=env, capture_output=True, text=True)
assert import_probe.returncode == 0 and str(args.root.resolve()) in import_probe.stdout
result = subprocess.run(command, cwd=args.root, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
(out / 'stdout.txt').write_text(result.stdout, encoding='utf-8')
(out / 'stderr.txt').write_text(result.stderr, encoding='utf-8')
counts = {}
if (out / 'junit.xml').exists():
    tree = ET.parse(out / 'junit.xml')
    counts = {key: sum(int(e.get(key, '0')) for e in tree.findall('.//testsuite'))
              for key in ('tests', 'failures', 'errors', 'skipped')}
files = [TEST, 'tests/findings/fixtures/ra2c3_codex2_inputs.json',
         'tests/findings/fixtures/ra2c3_codex2_legacy_pins.json']
metadata = dict(started_utc=started, finished_utc=datetime.now(timezone.utc).isoformat(),
    target_sha=args.target_sha, qa_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    python=sys.version, command=command, cwd=str(args.root.resolve()), exit_code=result.returncode,
    counts=counts, import_probe=import_probe.stdout.strip(),
    source_sha256={p: hashlib.sha256((args.root / p).read_bytes()).hexdigest() for p in files})
if args.archive_manifest:
    manifest = json.loads(args.archive_manifest.read_text(encoding='utf-8'))
    assert manifest['target_sha'] == args.target_sha
    changed = [p for p, digest in manifest['original_files_sha256'].items()
               if not (args.root / p).is_file() or hashlib.sha256((args.root / p).read_bytes()).hexdigest() != digest]
    metadata['candidate_original_files_changed'] = changed
    assert not changed, 'Candidate production/archive changed during tests'
(out / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
print(json.dumps(metadata, indent=2))
print(result.stdout[-2500:])
sys.exit(result.returncode)

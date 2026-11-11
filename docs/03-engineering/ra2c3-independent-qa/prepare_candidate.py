"""Archive an exact commit; overlay only independent QA, never another branch."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[3]
BASE = '4b5ebe689f048ba20d38354ae7c03d4bbaf37c6a'
OWNED = ('tests/findings/test_ra2c3_independent_adversarial.py',
         'tests/findings/fixtures/ra2c3_codex2_inputs.json',
         'tests/findings/fixtures/ra2c3_codex2_legacy_pins.json')
parser = argparse.ArgumentParser()
parser.add_argument('sha')
args = parser.parse_args()
sha = subprocess.check_output(['git', 'rev-parse', args.sha + '^{commit}'], cwd=ROOT, text=True).strip()
assert sha == args.sha and len(sha) == 40, 'Supply a full exact candidate commit SHA'
changes = subprocess.check_output(['git', 'diff', '--name-status', BASE, sha], cwd=ROOT, text=True)
archive = subprocess.check_output(['git', 'archive', '--format=tar', sha], cwd=ROOT)
target = Path(tempfile.mkdtemp(prefix='vrae-codex2-c3-'))
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
    for member in tar.getmembers():
        assert member.isfile() or member.isdir(), 'No symlinks or special files in QA archive'
        assert target.resolve() in (target / member.name).resolve().parents
    tar.extractall(target, filter='data')
original = {str(p.relative_to(target)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in target.rglob('*') if p.is_file()}
for path in OWNED:
    assert not (target / path).exists(), 'Candidate collides with exclusive QA file: ' + path
    destination = target / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes((ROOT / path).read_bytes())
metadata = dict(target_sha=sha, target_tree=subprocess.check_output(['git', 'rev-parse', sha + '^{tree}'],
    cwd=ROOT, text=True).strip(), archive_sha256=hashlib.sha256(archive).hexdigest(),
    root=str(target), changes=changes, original_files_sha256=original,
    overlays_sha256={p: hashlib.sha256((target / p).read_bytes()).hexdigest() for p in OWNED})
out = ROOT / 'docs/03-engineering/ra2c3-independent-qa/runs' / ('candidate-' + sha)
out.mkdir(parents=True, exist_ok=False)
(out / 'archive-manifest.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in metadata.items() if k != 'original_files_sha256'}, indent=2))

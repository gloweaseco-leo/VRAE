"""Isolated fresh-process comparison; baseline differs only in pack.py."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = '6b2a2dfff8d6de2cf16c2509e9cdcf30a2267d83'
MATCH = ('capture_sha256', 'input_product_body_sha256', 'output_sha256',
         'diagnosis_ref', 'diagnosis_bytes_sha256', 'assessment_results')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    baseline = subprocess.check_output(['git', 'show', BASE + ':vrae/evidence/pack.py'], cwd=ROOT)
    files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    files += [str(p.relative_to(ROOT)).replace('\\', '/')
              for p in (ROOT / 'integration/evidence_perf').glob('*.py')]
    selected = sorted({p for p in files if p and (p.startswith(('vrae/', 'tests/', 'contracts/',
        'industry-packs/', 'integration/')) or p == 'docs/03-engineering/l2-industrial-v1/example/source.json')})
    for variant in ('baseline', 'candidate'):
        tree = out / variant
        if tree.exists():
            raise SystemExit('FRESH_OUTPUT_DIRECTORY_REQUIRED')
        for name in selected:
            target = tree / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        if variant == 'baseline':
            (tree / 'vrae/evidence/pack.py').write_bytes(baseline)
    receipts = []
    # ABBA ordering, independent process and pack each time; no warm cache reuse.
    for n, variant in enumerate(('baseline', 'candidate', 'candidate', 'baseline')):
        tree = out / variant
        receipt = out / f'{n}-{variant}.json'
        with (out / f'{n}-{variant}.log').open('wb') as log:
            subprocess.run([sys.executable, '-m', 'integration.evidence_perf.benchmark_one',
                '--variant', variant, '--out', str(receipt)], cwd=tree,
                env={**os.environ, 'PYTHONPATH': str(tree)}, stdout=log,
                stderr=subprocess.STDOUT, check=True)
        receipts.append(json.loads(receipt.read_bytes()))
        print(f'{n} {variant} completed', flush=True)
    for receipt in receipts[1:]:
        for key in MATCH:
            if receipt[key] != receipts[0][key]:
                raise AssertionError('BASELINE_CANDIDATE_MISMATCH:' + key)
    summary = {'base': BASE, 'matched_fields': MATCH, 'identical_outputs': True,
               'baseline_pack_sha256': hashlib.sha256(baseline).hexdigest(),
               'candidate_pack_sha256': hashlib.sha256((ROOT / 'vrae/evidence/pack.py').read_bytes()).hexdigest(),
               'receipts': receipts}
    (out / 'comparison.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print('IDENTICAL_INPUTS_OUTPUTS_AND_GUARD_SEMANTICS', flush=True)


if __name__ == '__main__':
    main()

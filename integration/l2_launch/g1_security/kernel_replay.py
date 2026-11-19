"""Execute accepted R1-A probe unchanged; copy evidence, never a G1 HTTP claim."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from integration.l2_launch.security import lab

OWN = Path(__file__).resolve().parent
ROOT = OWN.parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--base', required=True)
    args = parser.parse_args()
    if not re.fullmatch('[a-z0-9-]{3,32}', args.label):
        raise ValueError('OWNED_LABEL_REQUIRED')
    label = 'g1s1-'+args.label
    out = OWN/'.runtime'/label
    out.mkdir(parents=True, exist_ok=False)
    original = lab.OWN/'.runtime'/label
    try:
        run = subprocess.run([sys.executable, '-B', '-m', 'integration.l2_launch.security.lab',
            '--label', label, '--base', args.base], cwd=ROOT, capture_output=True, check=False, timeout=1500)
        (out/'launcher.log').write_bytes(run.stdout+run.stderr)
        run.check_returncode()
    finally:
        # The accepted lab owns cleanup. No extra docker rm/prune/service action.
        for name in ('receipt.json', 'isolated.xml', 'kernel-and-tests.log', 'build.log'):
            if (original/name).is_file():
                shutil.copyfile(original/name, out/name)
    receipt = json.loads((out/'receipt.json').read_text())
    assert receipt['pass'] and receipt['owned_container_removed'] and receipt['kernel_api_metadata_denials'] == 4
    result = {'scope': 'ACCEPTED_R1A_KERNEL_PROBE_RERUN_NOT_G1_HTTP', 'actual_g1_http_pass': False,
              'source_sha': receipt['source_sha'], 'owner': receipt['owner'], 'kernel_denials': 4,
              'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}}
    (out/'inherited-probe.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()

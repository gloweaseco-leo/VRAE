"""Independent Python verification of frozen source and the bounded public receipt."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PINS = {
    'docs/03-engineering/ra4c3-pg-read/browser-test.mjs':
        ('3cf73d4ec0397acdca3d988ac4332ef7dfcf258b', 20000),
    'integration/b5b/browser.mjs':
        ('3f37f2268585f4a481c5882cfdb8e6e2d65f3578', 30000),
}


def verify(receipt):
    assert receipt['acceptedBase'] == 'cb86cdb1b57962aa89fa2ef4465131219c8c45e9'
    assert re.fullmatch('[a-f0-9]{64}', receipt['binary']['sha256'])
    assert receipt['binary']['executedExecutable'] == receipt['binary']['requestedExecutable']
    assert len(receipt['results']) == 2
    for row in receipt['results']:
        blob, deadline = PINS[row['file']]
        assert row['blob'] == blob and row['deadlineMs'] == deadline
        assert row['spawnOptions'] == {'windowsHide': True, 'stdio': ['ignore', 'pipe', 'pipe']}
        assert row['classification'] == 'ENDPOINT_AVAILABLE'
        assert 0 <= row['spawnAtMs'] <= row['endpointAtMs'] <= deadline
        assert row['connected'] is True and row['cleanup']['closeObserved'] is True
        assert row['closeAtMs'] >= row['exitAtMs'] >= row['decisionAtMs']
        assert re.fullmatch('[a-f0-9]{64}', row['stderrSha256'])
        assert row['stderrBytes'] >= 0
        assert row['launchArgs'][-2:] == ['--user-data-dir=<owned-temp>', 'about:blank']
        assert row['browserVersion'] is None or re.fullmatch(r'\d+\.\d+\.\d+\.\d+', row['browserVersion'])
        assert not {'stderr', 'stdout', 'environment', 'cookies', 'http', 'endpoint'} & row.keys()


def main():
    for file, (pin, deadline) in PINS.items():
        # Read canonical Git bytes and independently compute the object fingerprint.
        raw = subprocess.check_output(['git', 'show', f'HEAD:{file}'], cwd=ROOT)
        assert hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest() == pin
        disk = subprocess.check_output(['git', 'hash-object', '--path', file, file], cwd=ROOT).decode().strip()
        assert disk == pin
        assert f',{deadline});chrome.on(\'error\''.encode() in raw
    if len(sys.argv) > 1:
        receipt = json.loads(Path(sys.argv[1]).read_text())
        verify(receipt)
        # Prove that a falsely promoted timeout receipt cannot pass this verifier.
        receipt['results'][0]['classification'] = 'NO_ENDPOINT_WITH_ALIVE_PROCESS'
        try:
            verify(receipt)
        except AssertionError:
            pass
        else:
            raise AssertionError('FALSE_PROMOTION_ACCEPTED')
    print(f'Python {sys.version.split()[0]}: frozen source / receipt checks PASS')


if __name__ == '__main__':
    main()

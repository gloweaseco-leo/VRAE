"""Read-only official artifact audit; publish fingerprints, never raw private payloads."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

REPO = 'repos/gloweaseco-leo/VRAE'
ARTIFACTS = [
    (14346573399, 44124070028, 134182924667, 'browser-2026-11-17T16-23-32-900Z'),
    (14383001827, 44202972104, 134461535003, 'browser-2026-11-17T23-57-06-656Z'),
    (14383155835, 44202972396, 134461535216, None),
]


def api(endpoint):
    return subprocess.check_output(['gh', 'api', f'{REPO}/{endpoint}'])


def main():
    results = []
    for artifact, run, job, directory in ARTIFACTS:
        metadata = json.loads(api(f'actions/artifacts/{artifact}'))
        raw = api(f'actions/artifacts/{artifact}/zip')
        digest = hashlib.sha256(raw).hexdigest()
        if metadata['digest'] != 'sha256:' + digest:
            raise RuntimeError('OFFICIAL_DIGEST_MISMATCH')
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if archive.testzip() is not None:
                raise RuntimeError('ZIP_CRC_FAILURE')
            # First list only known receipt/failure member names, never dump bodies.
            candidates = [n for n in archive.namelist() if
                          n.endswith(('receipt.json', 'failure.txt', 'failure.json'))]
            selected = [n for n in archive.namelist() if not n.endswith('/') and
                        (directory is None or directory + '/' in n)]
            members = [{'name': n, 'bytes': len(archive.read(n)),
                        'sha256': hashlib.sha256(archive.read(n)).hexdigest()}
                       for n in selected]
            results.append({'artifact': artifact, 'run': run, 'job': job,
                            'head': metadata['workflow_run']['head_sha'],
                            'zipBytes': len(raw), 'zipSha256': digest,
                            'officialDigestMatched': True, 'crcVerified': True,
                            'selectedDirectory': directory, 'members': members,
                            'receiptCandidates': candidates if directory is None else [],
                            'classification': 'UNKNOWN',
                            'reason': 'Historical archives lack complete child lifecycle evidence'})
    out = Path(__file__).parent / 'output'
    out.mkdir(exist_ok=True)
    (out / 'historical-artifacts.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()

"""Read actual hosted run metadata and raw log ZIP; no workflow or GitHub mutations."""
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

OUT = Path(__file__).resolve().parent / '.checks' / ('ci-' + sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
REPO = 'gloweaseco-leo/VRAE'


def gh(*args):
    return subprocess.check_output(['gh', *args])


run = json.loads(gh('run', 'view', sys.argv[1], '--repo', REPO, '--json',
                   'databaseId,headSha,event,status,conclusion,url,jobs'))
pr = json.loads(gh('pr', 'view', '47', '--repo', REPO, '--json',
                  'headRefOid,baseRefOid,isDraft,mergeCommit,state,url'))
assert pr['isDraft'] and pr['state'] == 'OPEN'
assert run['headSha'] == pr['headRefOid'] and run['event'] == 'pull_request'
assert run['status'] == 'completed' and run['conclusion'] == 'success'
assert len(run['jobs']) == 4 and all(j['conclusion'] == 'success' for j in run['jobs'])
raw = gh('api', f'repos/{REPO}/actions/runs/{sys.argv[1]}/logs')
(OUT / 'raw-logs.zip').write_bytes(raw)
jobs = []
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    assert z.testzip() is None
    files = {n: z.read(n) for n in z.namelist() if not n.endswith('/')}
    for job in run['jobs']:
        # GitHub supplies one root-level full job log plus individual step logs.
        candidates = [n for n in files if '/' not in n and job['name'] in n]
        assert len(candidates) == 1, (job['name'], candidates)
        name = candidates[0]
        log = files[name].decode('utf-8')
        shas = re.findall(r"git log -1 --format='%H'\s*\n[^\n]*?([a-f0-9]{40})", log)
        if not shas:
            lines = log.splitlines()
            shas = [m.group(1) for i, line in enumerate(lines[:-1])
                    if 'git log -1 --format' in line
                    and (m := re.search(r'\b([a-f0-9]{40})\b', lines[i+1]))]
        assert len(set(shas)) == 1, (job['name'], shas)
        jobs.append({'name': job['name'], 'id': job['databaseId'], 'url': job['url'],
                     'conclusion': job['conclusion'], 'checkout': shas[0], 'raw_log': name,
                     'pytest_summaries': re.findall(r'\b\d+ passed[^\n]*', log),
                     'log_sha256': hashlib.sha256(files[name]).hexdigest()})
    assert len({j['checkout'] for j in jobs}) == 1
    entries = [{'path': n, 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}
               for n, b in sorted(files.items())]
merge = json.loads(gh('api', f'repos/{REPO}/git/commits/{jobs[0]["checkout"]}'))
assert [p['sha'] for p in merge['parents']] == [pr['baseRefOid'], pr['headRefOid']]
head = json.loads(gh('api', f'repos/{REPO}/git/commits/{pr["headRefOid"]}'))
assert merge['tree']['sha'] == head['tree']['sha']
artifacts = json.loads(gh('api', f'repos/{REPO}/actions/runs/{sys.argv[1]}/artifacts'))
browser_artifacts = []
for artifact in artifacts['artifacts']:
    assert not artifact['expired']
    zipped = gh('api', f'repos/{REPO}/actions/artifacts/{artifact["id"]}/zip')
    (OUT / ('artifact-' + str(artifact['id']) + '.zip')).write_bytes(zipped)
    with zipfile.ZipFile(io.BytesIO(zipped)) as z:
        assert z.testzip() is None
        artifact_entries = [{'path': n, 'bytes': len(z.read(n)),
                             'sha256': hashlib.sha256(z.read(n)).hexdigest()}
                            for n in z.namelist() if not n.endswith('/')]
    browser_artifacts.append({'metadata': artifact,
        'downloaded_zip_sha256': hashlib.sha256(zipped).hexdigest(), 'entries': artifact_entries})
proof = {'run': run, 'pr': pr, 'jobs': jobs, 'test_merge': merge,
         'head_tree': head['tree'], 'raw_zip_sha256': hashlib.sha256(raw).hexdigest(),
         'entries': entries, 'browser_artifacts': browser_artifacts,
         'checkout_parents_and_tree_verified': True}
(OUT / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'run': run['url'], 'head': pr['headRefOid'], 'base': pr['baseRefOid'],
                  'checkout': jobs[0]['checkout'], 'jobs': jobs,
                  'raw_zip_sha256': proof['raw_zip_sha256']}, indent=2))

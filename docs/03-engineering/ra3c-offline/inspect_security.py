"""Inspect original browser CI archive without changing security expectations."""
import json
from pathlib import Path
import sys
import zipfile

folder = Path(__file__).resolve().parent / '.checks' / ('ci-' + sys.argv[1])
proof = json.loads((folder / 'proof.json').read_text(encoding='utf-8'))
for artifact in proof['browser_artifacts']:
    with zipfile.ZipFile(folder / ('artifact-' + str(artifact['metadata']['id']) + '.zip')) as z:
        summary = json.loads(z.read('summary.json'))
        lifecycle = json.loads(z.read('lifecycle.json'))
        for entry in summary:
            expected = (137 if entry['name'] == 'worker_kill-worker' else 1
                        if entry['name'].endswith(('-process-absence', '-cleanup-proof',
                                                   '-volume-cleanup-proof')) else 0)
            assert entry['exit_code'] == expected, entry
        workers = [e for e in lifecycle if e['event'] == 'worker_exited']
        assert len(workers) == 16
        assert all(e['exit_code'] == (137 if e['case'] == 'worker_kill' else 0) for e in workers)
        assert len([e for e in lifecycle if e['event'] == 'automatic_exit_observed']) == 16
        result = {'commands': len(summary), 'all_expected_exits_match': True,
                  'worker_exits': workers, 'negative_probes': [
                      {'name': e['name'], 'exit_code': e['exit_code']}
                      for e in summary if e['exit_code'] == 1],
                  'server_digest': artifact['metadata']['digest'],
                  'downloaded_zip_sha256': artifact['downloaded_zip_sha256']}
        (folder / 'security-proof.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'commands': len(summary), 'workers': len(workers),
                          'worker_kill_exit': 137, 'negative_probes_exit_1': len(result['negative_probes']),
                          'all_expected_exits_match': True}))

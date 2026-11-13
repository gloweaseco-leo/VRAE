"""Audit actual GitHub raw logs, checkout objects and downloaded security ZIP."""
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

HERE = Path(__file__).resolve().parent


def main():
    directory, expected_head, expected_main, count = Path(sys.argv[1]), sys.argv[2], sys.argv[3], int(sys.argv[4])
    def read(name):
        return json.loads((directory / name).read_text(encoding='utf-8-sig'))
    run, jobs, pr, merge = read('run.json'), read('jobs.json')['jobs'], read('pr.json'), read('merge.json')
    assert run['head_sha'] == expected_head and run['event'] == 'pull_request'
    assert run['status'] == 'completed' and run['conclusion'] == 'success'
    assert pr['head']['sha'] == expected_head and pr['base']['sha'] == expected_main
    assert pr['draft'] is True and pr['merged'] is False and pr['auto_merge'] is None
    assert [p['sha'] for p in merge['parents']] == [expected_main, expected_head]
    assert pr['merge_commit_sha'] == merge['sha']
    assert len(jobs) == 4 and all(j['status'] == 'completed' and j['conclusion'] == 'success' for j in jobs)
    expected_sources = {r['path']: r['git_bytes_sha256'] for r in
                        json.loads((HERE.parent / 'ra3d-d1d2-offline/SOURCE_FREEZE.json').read_text())['frozen_source_and_inputs']}
    proofs = []
    for job in jobs:
        raw = (directory / (str(job['id']) + '.log')).read_bytes()
        log = raw.decode('utf-8-sig')
        assert all(value in log for value in (merge['sha'], expected_head, expected_main))
        row = {'job': job['name'], 'id': job['id'], 'url': job['html_url'],
               'status': job['conclusion'], 'checkout': merge['sha'],
               'decoded_log_sha256': hashlib.sha256(raw).hexdigest()}
        if job['name'] != 'isolated-browser':
            lines = [line for line in log.splitlines() if 'RA3D_D1D2_ACTUAL_RECEIPT=' in line]
            assert len(lines) == 1
            receipt = json.loads(lines[0].split('RA3D_D1D2_ACTUAL_RECEIPT=', 1)[1])
            assert receipt['collected'] == receipt['called'] == receipt['passed'] == count
            assert receipt['session_exit'] == 0
            assert len(receipt['calls']) == count and all(c['outcome'] == 'passed' for c in receipt['calls'])
            assert {r['path']: r['lf_bytes_sha256'] for r in receipt['source_hashes']} == expected_sources
            assert receipt['native_approvals'] == receipt['share_grants'] == receipt['real_human_decisions'] == 0
            summaries = [(int(p), int(s)) for p, s in re.findall(r'(\d+) passed, (\d+) skipped', log)]
            expected = (2348, 1) if job['name'] == 'isolated-http' else (2324, 25)
            assert expected in summaries, (job['name'], summaries)
            row['pytest_pass_skip'] = expected
            row['actual_offline_call_receipt'] = receipt
        proofs.append(row)
    artifact_meta = read('artifact-metadata.json')['artifacts']
    assert len(artifact_meta) == 1 and not artifact_meta[0]['expired']
    zip_raw = (directory / 'security.zip').read_bytes()
    assert artifact_meta[0]['digest'] == 'sha256:' + hashlib.sha256(zip_raw).hexdigest()
    with zipfile.ZipFile(directory / 'security.zip') as archive:
        assert archive.testzip() is None
        def content(name):
            return archive.read(name).decode('utf-8')
        commands = json.loads(content('summary.json'))
        events = json.loads(content('lifecycle.json'))
        assert len(commands) == 245 and len(events) == 540
        by_name = {c['name']: c for c in commands}
        cases = [c['name'][:-7] for c in commands if c['name'].endswith('-worker')]
        assert len(cases) == 16
        positive = next(json.loads(x) for x in content('kernel-control.log').splitlines() if x.startswith('{'))
        negative = next(json.loads(x) for x in content('kernel-deny.log').splitlines() if x.startswith('{'))
        assert positive['positive_control'] is True and len(positive['results']) == 4
        assert all(r['created'] is True for r in positive['results'])
        assert negative['positive_control'] is False and len(negative['results']) == 4
        assert all(r['errno'] == 1 for r in negative['results'])
        assert 'ROOT_WRITE_DENIED errno=30' in content('kernel-deny.log')
        assert 'SANDBOX_PREFLIGHT_PASS' in content('sandbox.log')
        security_cases = []
        for case in cases:
            assert by_name[case + '-worker']['exit_code'] == (137 if case == 'worker_kill' else 0)
            assert by_name[case + '-automatic-exit']['exit_code'] == 0
            assert all(by_name[case + s]['exit_code'] != 0 for s in
                       ('-process-absence', '-cleanup-proof', '-volume-cleanup-proof'))
            observed = next(e['monotonic_ns'] for e in events if e.get('case') == case
                            and e['event'] == 'automatic_exit_observed')
            cleanup = next(e['monotonic_ns'] for e in events if e.get('case') == case
                           and e['event'] == 'supervisor_cleanup_started')
            assert observed < cleanup
            worker = content(case + '-worker.log')
            network = [json.loads(x.split('NETWORK_EVIDENCE ', 1)[1]) for x in worker.splitlines()
                       if 'NETWORK_EVIDENCE ' in x]
            for r in network:
                assert r['bait_connections'] == 0 and r['external_routes'] is False and r['uid'] == 65532
            for line in worker.splitlines():
                if line.startswith('{') and 'unauthorized_connections' in line:
                    r = json.loads(line)
                    assert r['unauthorized_connections'] == 0 and r['writes'] == 0
            security_cases.append({'case': case, 'worker_exit': by_name[case + '-worker']['exit_code'],
                                   'automatic_exit_before_cleanup': True, 'network_records': network})
        security = {'artifact_id': artifact_meta[0]['id'], 'sha256': hashlib.sha256(zip_raw).hexdigest(),
                    'members': len(archive.namelist()), 'commands': len(commands), 'events': len(events),
                    'positive_control': positive, 'negative_control': negative, 'cases': security_cases}
    result = {'run': run['id'], 'final_head': expected_head, 'accepted_main': expected_main,
              'actual_merge': merge['sha'], 'ordered_parents': [expected_main, expected_head],
              'jobs': proofs, 'security': security, 'draft': True, 'merged': False}
    (directory / 'FINAL_CI_RECEIPT.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('run', 'final_head', 'accepted_main', 'actual_merge')}))
    print('VERIFIED_FOUR_NEW_REAL_CI_SUCCESS_WITH_EXACT_SOURCE_CALLS_AND_SECURITY_ARTIFACT')


if __name__ == '__main__':
    main()

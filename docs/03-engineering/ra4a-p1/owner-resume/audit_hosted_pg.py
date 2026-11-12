"""Audit downloaded exact-head real PG artifacts; no SQL or oracle mutation."""
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def main():
    folder = Path(sys.argv[1])
    head, base, merge = sys.argv[2:5]
    jobs = json.loads((folder / 'pg-jobs.json').read_text())['jobs']
    metadata = json.loads((folder / 'pg-artifacts.json').read_text())['artifacts']
    assert len(jobs) == len(metadata) == 2
    scope = json.loads((HERE / 'MAIN_INTEGRATION_SCOPE.json').read_text())
    source_map = {r['path']: r['git_sha256'] for r in scope['frozen_sources']}
    expected_calls = json.loads((HERE / 'source-3eceea9/py311/pg-catalog-and-calls.json').read_text())['calls']
    expected_calls = {r['id'] for r in expected_calls}
    proof = []
    for runtime in ('3.11', '3.13'):
        job = next(j for j in jobs if j['name'] == 'postgres-16 (' + runtime + ')')
        assert job['status'] == 'completed' and job['conclusion'] == 'success'
        assert all(s['conclusion'] == 'success' for s in job['steps'])
        raw = (folder / (str(job['id']) + '.log')).read_bytes()
        log = raw.decode('utf-8-sig')
        assert all(s in log for s in (head, base, merge))
        assert 'RA4A_START_FAILURE_CLEANUP_PROOF=' in log
        meta = next(a for a in metadata if a['name'] == 'ra4a-pg16-' + runtime)
        archive = folder / ('pg-' + runtime + '.zip')
        sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        assert not meta['expired'] and meta['digest'] == 'sha256:' + sha
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            prefix = 'ci-' + runtime + '/'
            def read(name):
                return json.loads(z.read(name))
            def target(name):
                return read(prefix + name)
            assert not any('lab-state' in p or '/.venv/' in p for p in z.namelist())
            for name, expected in (('postgres.xml', 54), ('pure.xml', 11)):
                suite = ET.fromstring(z.read(prefix + name)).find('testsuite')
                assert int(suite.attrib['tests']) == expected
                assert all(int(suite.attrib[k]) == 0 for k in ('errors', 'failures', 'skipped'))
                assert len(suite.findall('testcase')) == expected
            commands = target('commands.json')
            assert commands['github_checkout'] == merge
            assert len(commands['commands']) == 6 and all(c['exit'] == 0 for c in commands['commands'])
            catalog = target('pg-catalog-and-calls.json')
            assert catalog['github_checkout'] == merge and catalog['session_exit'] == 0
            assert len(catalog['calls']) == 54 and all(c['outcome'] == 'passed' for c in catalog['calls'])
            assert {c['id'] for c in catalog['calls']} == expected_calls
            assert catalog['actual_human_approvals'] == catalog['share_grants'] == 0
            assert catalog['synthetic_authority_only'] is True
            assert 'PostgreSQL 16.15' in catalog['server_version']
            assert catalog['migrations'] == [[1, '0557738e22e83a6f1c991e8c2a796749ce43845ad80fec44d8dc4c891fd9b5e2']]
            assert len(catalog['roles']) == 8
            assert all(all(r[i] is False for i in (1, 2, 4, 5)) for r in catalog['roles'])
            tenant_tables = [r for r in catalog['tables'] if r[0] == 'ra4a']
            assert len(tenant_tables) == 8 and all(r[2:] == ['ra4a_owner', True, True] for r in tenant_tables)
            assert len(catalog['policies']) == 10
            assert all(p[3] and p[4] for p in catalog['policies'])
            assert all(g[3] == 'SELECT' for g in catalog['grants'])
            assert all(f[1] == 'ra4a_owner' for f in catalog['functions'])
            manifest = target('source-manifest.json')
            assert manifest['actual_git_head'] == merge
            assert all(source_map[r['path']] == r['lf_sha256'] for r in manifest['files'])
            expected_paths = {p for p in source_map if p.startswith(('vrae/', 'tests/', 'integration/', 'db/', 'infra/'))}
            assert {r['path'] for r in manifest['files']} == expected_paths
            backup = target('backup-restore.json')
            assert backup['source_data_sha256'] == backup['restored_data_sha256']
            assert hashlib.sha256(z.read(prefix + 'synthetic-metadata.dump')).hexdigest() == backup['dump_sha256']
            assert len(z.read(prefix + 'synthetic-metadata.dump')) == backup['dump_bytes']
            assert backup['data_equal_before_and_after_idempotent_replay']
            assert backup['nonprivileged_function_owners'] and backup['restored_tenant_isolation_and_write_denial']
            restart = target('real-restart.json')
            assert restart['committed_ids_preserved'] and all(v == 'on' for v in restart['settings'].values())
            def cleanup(name):
                r = read(name)
                assert re.fullmatch(r'vrae-ra4a-p1-[0-9a-f]{12}', r['container'])
                assert r['network'] == r['container'] + '-local' and r['data_volume'] == r['container'] + '-data'
                assert all(r[k] is True for k in ('owned_container_removed', 'owned_network_removed', 'owned_volume_removed'))
                assert len(r['actual_results']) == 3
                assert all(x['absent_after'] and 'error' not in x for x in r['actual_results'])
                assert all(x.get('remove_returncode', 0) == 0 for x in r['actual_results'])
                return r
            teardown = cleanup(prefix + 'teardown/teardown.json')
            assert all(r['present_before'] for r in teardown['actual_results'])
            failure_prefix = 'ci-' + runtime + '-failure/'
            failure = read(failure_prefix + 'failure-probe.json')
            assert failure['startup_exit'] != 0 and failure['state_never_published']
            assert failure['actual_cleanup_passes'] == 3 and failure['business_tests_executed'] == 0
            first = failure_prefix + 'startup/failure-cleanup/teardown.json'
            assert hashlib.sha256(z.read(first)).hexdigest() == failure['first_cleanup_sha256']
            cleanup(first)
            for repeat in (1, 2):
                repeated = cleanup(failure_prefix + 'repeat-cleanup-' + str(repeat) + '/teardown.json')
                assert all(r['present_before'] is False for r in repeated['actual_results'])
            startup = [json.loads(line) for line in z.read('ci-' + runtime + '-startup/startup.jsonl').decode().splitlines()]
            ready = [r for r in startup if r['event'] == 'target_sql_ready']
            assert len(ready) == 1 and ready[0]['dbname'] == 'vrae_ra4a_p1' and ready[0]['server_version_num'] == '160015'
            assert ready[0]['loopback_publication_only'] and ready[0]['kernel_egress_denial'] is False
            proof.append({'job': job['name'], 'url': job['html_url'], 'artifact_id': meta['id'],
                          'sha256': sha, 'members': len(z.namelist()), 'checkout': merge,
                          'pg_actual_pass': 54, 'pure_actual_pass': 11, 'roles': catalog['roles'],
                          'tables': catalog['tables'], 'migrations': catalog['migrations'],
                          'backup': backup, 'restart': restart, 'teardown': teardown,
                          'pre_state_failure_cleanup': failure,
                          'decoded_log_sha256': hashlib.sha256(raw).hexdigest()})
    (folder / 'PG_ACTUAL_HOSTED_RECEIPT.json').write_text(json.dumps(proof, indent=2)+'\n', encoding='utf-8')
    print('VERIFIED_TWO_REAL_HOSTED_PG16_DUAL_54_PLUS_11_WITH_CATALOG_RECOVERY_AND_FAILURE_CLEANUP')


if __name__ == '__main__':
    main()

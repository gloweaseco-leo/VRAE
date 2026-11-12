"""Read-only original QA V2 and HTTP network evidence audit, no oracle edits."""
import json
from pathlib import Path
import sys

directory = Path(sys.argv[1])
jobs = json.loads((directory / 'jobs.json').read_text(encoding='utf-8-sig'))['jobs']
proof = []
for job in jobs:
    if job['name'] == 'isolated-browser':
        continue
    log = (directory / (str(job['id']) + '.log')).read_text(encoding='utf-8-sig')
    def one(marker):
        lines = [line for line in log.splitlines() if marker in line]
        assert len(lines) == 1, (job['name'], marker, len(lines))
        return json.loads(lines[0].split(marker, 1)[1])
    collection = one('OWNER_RA3C_V2_ACTUAL_COLLECTION ')
    reports = one('OWNER_RA3C_V2_ACTUAL_CALL_REPORTS ')
    assert collection['primary_collected'] == reports['primary_count'] == 64
    assert collection['denials_collected'] == reports['denial_count'] == 54
    assert len(reports['actual_call_reports']) == 118
    assert all(outcome == 'passed' for outcome in reports['actual_call_reports'].values())
    assert reports['setup_or_call_problems'] == []
    assert collection['source_sha256'] == reports['source_sha256'] == '9e60d3e307d3a4726adca62b79319b6a85f11a65453390b68a5003bd6a643e62'
    assert collection['profile_sha256'] == 'f6d9f5432314e567016b3e09a84d753cc54fa6d6bd4543492fc1ee692b781294'
    assert collection['verified_evidence_members'] == 24
    assert collection['historical_v1_omitted_from_default'] == 64
    assert collection['frozen_oracles_modified'] is False
    row = {'job': job['name'], 'collection': collection, 'reports': reports}
    if job['name'] == 'isolated-http':
        network = [json.loads(line.split('NETWORK_EVIDENCE ', 1)[1]) for line in log.splitlines()
                   if 'NETWORK_EVIDENCE ' in line]
        assert len(network) == 24
        assert all(r['bait_connections'] == 0 and r['external_routes'] is False and r['uid'] == 65532
                   for r in network)
        row['http_network_records'] = network
    proof.append(row)
assert len(proof) == 3
out = directory / 'RA3C_V2_AND_HTTP_ACTUAL_PROOF.json'
assert not out.exists(), 'Do not overwrite historical proof'
out.write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
print('VERIFIED_118_ACTUAL_RA3C_V2_CALLS_IN_ALL_THREE_FULL_JOBS_AND_24_HTTP_NETWORK_NEGATIVES')

"""Post-run read-only artifact audit. Never reads or exports business row bytes."""
import argparse
import copy
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))


def main():
    from integration.ra4e.lab import digest, encode
    from integration.ra4e.run import publication
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id')
    options = parser.parse_args()
    assert re.fullmatch(r'[a-z0-9-]{3,64}', options.run_id)
    docs = Path(__file__).resolve().parent
    public = docs / options.run_id
    private = ROOT / 'integration/beta_review/codex3/b7_restore_v1/.private' / options.run_id
    gate = json.loads((public / 'publication.json').read_bytes())
    assert gate['publication_allowed'] and gate['actual_fixture_credentials_compared'] > 0
    assert {p.relative_to(public).as_posix() for p in public.rglob('*') if p.is_file()} == set(gate['artifact_file_sha256']) | {'publication.json'}
    assert all(digest((public / name).read_bytes()) == expected for name, expected in gate['artifact_file_sha256'].items())
    def read(name):
        return json.loads((private / (name + '.json')).read_bytes())
    source, verification, target = [read(name) for name in ('source-baseline', 'verification-restored', 'target-restored')]
    final = read('target-after-old-token-replay')
    assert source['root'] == verification['root'] == target['root']
    assert source['catalog_root'] == final['catalog_root']
    differences = {}
    for stage, candidate in [('verification', verification), ('target', target)]:
        rows = []
        for name, raw in source['raw_acls'].items():
            after = candidate['raw_acls'].get(name)
            if raw != after:
                # Compare exactly the corresponding expanded effective tuples.
                assert not name.startswith(('SCHEMA:', 'FUNCTION:')) and name != 'DATABASE'
                before_relation = next(r for r in source['catalog']['relations'] if r[0] + '.' + r[1] == name)
                after_relation = next(r for r in candidate['catalog']['relations'] if r[0] + '.' + r[1] == name)
                assert before_relation == after_relation
                rows.append({'relation': name, 'before': raw, 'after': after,
                             'owner': before_relation[3], 'expanded_acl': before_relation[4],
                             'rls': before_relation[5], 'force_rls': before_relation[6],
                             'effective_equal': True})
        differences[stage] = rows
    catalog = copy.deepcopy(source['catalog'])
    for function in catalog['functions']:
        function[2] = {'definition_sha256': digest(function[2].encode()), 'raw_body': 'accepted source, not exported'}
    out = docs / (options.run_id + '-audit')
    out.mkdir(exist_ok=False)
    (out / 'catalog-and-effective-privileges.json').write_bytes(encode(catalog))
    (out / 'raw-acl-representation-differences.json').write_bytes(encode(differences))
    receipt = json.loads((public / 'receipt.json').read_bytes())
    assert receipt['candidate'] and receipt['native_pytest_exit'] == 0
    (out / 'audit.json').write_bytes(encode({
        'native_source_head': receipt['source_head'], 'native_junit_sha256': receipt['native_junit_sha256'],
        'native_publication_sha256': digest((public / 'publication.json').read_bytes()),
        'three_restored_roots_equal': True, 'post_worker_catalog_unchanged': True,
        'source_root': source['root'], 'source_catalog_root': source['catalog_root'],
        'raw_acl_diff_counts': {name: len(rows) for name, rows in differences.items()},
        'role_count': len(catalog['roles']), 'policy_count': len(catalog['policies']),
        'table_count': len(source['tables']), 'business_rows_exported': False,
        'privilege_repairs_executed': False, 'full_B7_EXIT': False}))
    publication(out, private)
    print(json.dumps({'run_id': options.run_id, 'audited': True,
                      'raw_acl_diff_counts': {name: len(rows) for name, rows in differences.items()}}))


if __name__ == '__main__':
    main()

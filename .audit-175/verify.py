"""Consistency and redaction checks for generated Phase A reports only."""
import hashlib
import json
from pathlib import Path
import re

root=Path(__file__).resolve().parent
data=json.loads((root/'AUDIT_SNAPSHOT.json').read_text(encoding='utf-8'))
manifest=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
assert len(data['entries'])==data['directory_count']==97
assert sum(data['classes'].values())==97
assert data['actual_bytes_freed']==0 and data['no_private_contents_read'] and data['no_runtime_mutation'] and data['no_git_fetch_pull']
assert len({e['path'].lower() for e in data['entries']})==97
assert len({e['common_dir'] for e in data['entries'] if e.get('common_dir')})==1
active=[e for e in data['entries'] if e.get('active_exclusion')]
assert len(active)==1 and active[0]['classification']=='A'
assert active[0]['git_state']=='UNKNOWN_PROTECT_ACTIVE_TREE_NOT_ENTERED'
assert not active[0]['size']['complete'] and active[0]['size']['logical_bytes_observed']==0
eligible=[e for e in data['entries'] if e['classification']=='D']
assert len(eligible)==3
for e in eligible:
    assert not e['runtime_reference_observed'] and not e['open_prs'] and e['head_ancestor_of_live_main']
    assert e['tracked_change_entries']==e['untracked_entries']==e['ignored_entries']==0 and e['size']['complete']
assert sum(e['size']['logical_bytes_observed'] for e in eligible)==data['candidate_D_logical_bytes']
assert sum(x['count'] for x in data['local_code_risks']['dirty_paths'].values())==37
assert len(data['local_code_risks']['commit_risks']['P046']['not_reachable_from_locally_available_live_refs'])==2
for name, sha in manifest.items():
    raw=(root/name).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==sha
    text=raw.decode('utf-8')
    assert not re.search(r'-----BEGIN [A-Z ]*PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{16,}',text)
for container in data['runtime']['docker']['containers']:
    assert 'Env' not in container and 'Cmd' not in container
    for mount in container['mounts']:
        assert 'Source' not in mount and 'password' not in mount['destination'].lower()
print(json.dumps({'reports_validated':list(manifest),'directories':97,'classes':data['classes'],
                  'candidate_logical_bytes':data['candidate_D_logical_bytes'],
                  'actual_bytes_freed':0,'runtime_metadata_errors':data['runtime']['docker']['errors']+data['runtime']['windows']['errors'],
                  'audit_snapshot_sha256':manifest['AUDIT_SNAPSHOT.json']}))

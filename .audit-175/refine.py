"""Read-only end-of-audit reconciliation; output remains metadata only."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess

OUT = Path(__file__).resolve().parent
ENV = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
def run(args, data=None):
    p = subprocess.run(args, input=data, capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV, timeout=45)
    return p.returncode, p.stdout
def git(path, *args, data=None):
    return run(['git','--no-optional-locks','-c','core.fsmonitor=false','-C',path,*args],data)
def api(endpoint):
    c, out = run(['gh','api',endpoint])
    if c:
        raise RuntimeError('GITHUB_NETWORK_READ_FAILED')
    return json.loads(out)
def save(name, data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

inventory=json.loads((OUT/'inventory-snapshot.json').read_text(encoding='utf-8'))
if not inventory.get('complete'):
    raise SystemExit('COLLECTION_NOT_COMPLETE')
github=json.loads((OUT/'github-snapshot.json').read_text(encoding='utf-8'))
runtime=json.loads((OUT/'runtime-snapshot.json').read_text(encoding='utf-8'))
result={'observed_at':datetime.now(timezone.utc).isoformat(),'dirty_paths':{},'local_commit_risks':{},'errors':[]}
end_main=api('repos/gloweaseco-leo/VRAE/commits/main')
result['main_sha']=end_main['sha'] if end_main else None
result['prs']={}
for number in (172,174):
    p=api(f'repos/gloweaseco-leo/VRAE/pulls/{number}')
    result['prs'][str(number)]={'sha':p['head']['sha'],'state':p['state'],'draft':p['draft']} if p else {'unknown':True}

c,out=git('D:/Projects/VRAE','worktree','list','--porcelain')
result['end_worktree_metadata']={}
current=None
for line in out.splitlines():
    if line.startswith('worktree '):
        current=line[9:]
    elif line.startswith('HEAD ') and current:
        result['end_worktree_metadata'][current]=line[5:]

tags=api('repos/gloweaseco-leo/VRAE/git/matching-refs/tags/')
live_refs=set(github['live_heads'].values())
if tags is not None:
    live_refs.update(t['object']['sha'] for t in tags)
c,out=git('D:/Projects/VRAE','cat-file','--batch-check=%(objectname) %(objecttype)',data='\n'.join(live_refs)+'\n')
present=[line.split()[0] for line in out.splitlines() if line.endswith(' commit') or line.endswith(' tag')]
result['live_ref_object_coverage']={'heads_snapshot_plus_tags':len(live_refs),'locally_present_objects':len(present),'tags_query_ok':tags is not None}
for item in inventory['entries']:
    if item.get('active_exclusion'):
        continue
    if item.get('tracked_change_entries',0):
        c, names=git(item['path'],'diff','--name-only','HEAD','-z')
        paths=[]
        for name in names.split('\0'):
            if not name:
                continue
            paths.append('[SENSITIVE_PATH_REDACTED]' if re.search(r'private|secret|credential|(^|/)\.env|\.(pem|key|pfx|p12)$',name,re.I) else name)
        result['dirty_paths'][item['id']]={'count':len(paths),'paths':paths,'patch_contents_read':False}
    if int(item.get('cached_remote_unreachable_commits') or 0)>0:
        args=('rev-list','HEAD','--not',*present)
        c, commits=git(item['path'],*args)
        result['local_commit_risks'][item['id']]={'not_reachable_from_locally_available_live_refs':commits.splitlines() if c==0 else None,
            'coverage_complete':len(present)==len(live_refs) and tags is not None,
            'interpretation':'Protect; refs/pull and server reflogs are not queried; do not assert never uploaded'}

# Refine mount metadata without reading its contents or any environment/command.
volumes=[v['name'] for v in runtime['docker']['volumes']]
for container in runtime['docker']['containers']:
    template='{"mounts":{{json .Mounts}},"running":{{json .State.Running}},"image":{{json .Image}}}'
    c,out=run(['docker','inspect','--format',template,container['name']])
    if c:
        result['errors'].append('END_CONTAINER_METADATA_UNAVAILABLE')
        continue
    d=json.loads(out)
    for public, raw in zip(container['mounts'],d['mounts']):
        if public['type']=='bind':
            matches=[n for n in volumes if '/'+n+'/' in raw.get('Source','').replace('\\','/')]
            public['backing_named_volume_if_observed']=matches[0] if len(matches)==1 else 'UNKNOWN_PROTECT'
        if re.search(r'password|secret|token|key',public.get('destination',''),re.I):
            public['destination']='[PRIVATE_INPUT_DESTINATION_REDACTED]'
    container['end_running']=d['running']
    container['end_image_matches_start']=d['image']==container['image_id']
runtime['end_observed_at']=datetime.now(timezone.utc).isoformat()
save('runtime-snapshot.json',runtime)
save('end-reconciliation.json',result)
print(json.dumps({'end_metadata_checked':True,'dirty_roots':list(result['dirty_paths']),
 'local_commit_risks':result['local_commit_risks'],'ref_coverage':result['live_ref_object_coverage'],
 'docker_errors':result['errors']}))

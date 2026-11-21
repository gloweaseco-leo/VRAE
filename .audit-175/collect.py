"""Issue175 Phase A: metadata-only collection. Writes ONLY audit deliverables.

No fetch/pull, index refresh, worktree mutation, private file contents, container
execution, volume contents, deployment or model calls. Runtime JSON is filtered
in memory before storage. Run sequentially at low I/O pressure.
"""
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlsplit

OUT = Path(__file__).resolve().parent
BASE = Path('D:/Projects')
MAIN = BASE / 'VRAE'
ACTIVE = BASE / 'VRAE-codex3-API-20261119'
ENV = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')


def now():
    return datetime.now(timezone.utc).isoformat()


def cmd(args, timeout=35):
    try:
        p = subprocess.run(args, capture_output=True, env=ENV, timeout=timeout)
        return p.returncode, p.stdout.decode('utf-8', 'replace'), p.stderr.decode('utf-8', 'replace')
    except subprocess.TimeoutExpired:
        return 124, '', 'TIMEOUT'
    except OSError:
        return 125, '', 'UNAVAILABLE'


def git(root, *args, timeout=35):
    return cmd(['git', '--no-optional-locks', '-c', 'core.fsmonitor=false', '-c', 'core.untrackedCache=false',
                '-C', str(root), *args], timeout)


def api(endpoint):
    code, stdout, _ = cmd(['gh', 'api', endpoint], timeout=40)
    if code:
        raise RuntimeError('GITHUB_METADATA_UNAVAILABLE')
    return json.loads(stdout)


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def norm(path):
    value = str(path).replace('\\', '/').rstrip('/')
    if value.lower().startswith('/run/desktop/mnt/host/d/'):
        value = 'D:/' + value[len('/run/desktop/mnt/host/d/'):]
    elif value.lower().startswith('/host_mnt/d/'):
        value = 'D:/' + value[len('/host_mnt/d/'):]
    return value


def under(path, parent):
    a, b = norm(path).lower(), norm(parent).lower()
    return a == b or a.startswith(b + '/')


def safe_url(raw):
    raw = raw.strip()
    if re.fullmatch(r'(?:https://|git@)github\.com[:/]gloweaseco-leo/VRAE(?:\.git)?', raw, re.I):
        return 'https://github.com/gloweaseco-leo/VRAE.git'
    return 'OTHER_REMOTE_REDACTED' if raw else None


def parse_worktrees(raw):
    entries = []
    for block in raw.strip().split('\n\n'):
        row = {}
        for line in block.splitlines():
            key, _, value = line.partition(' ')
            if key in ('worktree', 'HEAD', 'branch'):
                row[key] = value
            elif key in ('detached', 'bare', 'locked', 'prunable'):
                row[key] = True
        if row.get('worktree'):
            entries.append(row)
    return entries


def metadata_size(root, excluded):
    start = time.monotonic()
    result = {'logical_bytes_observed': 0, 'files_observed': 0, 'directories_observed': 0,
              'complete': True, 'skipped_protected_subtrees': 0, 'reparse_points_skipped': 0,
              'access_errors': 0, 'top_buckets': {}}
    stack = [(root, None)]
    buckets = Counter()
    newest = 0
    while stack:
        if time.monotonic() - start > 25:
            result['complete'] = False
            result['time_budget_exhausted'] = True
            break
        path, bucket = stack.pop()
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if entry.name == '.audit-175':
                        continue
                    key = bucket or entry.name
                    stat = entry.stat(follow_symlinks=False)
                    if stat.st_file_attributes & 0x400:
                        result['reparse_points_skipped'] += 1
                        result['complete'] = False
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if norm(entry.path).lower() in excluded:
                            continue  # accounted for as a separate inventory unit
                        if entry.name.lower() in ('.private', '.aws', '.codex', '.agents'):
                            result['skipped_protected_subtrees'] += 1
                            result['complete'] = False
                            continue
                        stack.append((entry.path, key))
                        result['directories_observed'] += 1
                    else:
                        result['files_observed'] += 1
                        result['logical_bytes_observed'] += stat.st_size
                        buckets[key] += stat.st_size
                        newest = max(newest, stat.st_mtime)
        except (OSError, PermissionError):
            result['access_errors'] += 1
            result['complete'] = False
        if result['files_observed'] and result['files_observed'] % 2000 == 0:
            time.sleep(0.01)
    result['seconds'] = round(time.monotonic() - start, 2)
    # Expose only infrastructure categories, never sensitive file/target names.
    totals = Counter()
    for name, size in buckets.items():
        kind = 'virtualenv' if name.startswith('.venv') or name in ('venv', 'node_modules') else (
            'git_metadata' if name == '.git' else 'evidence_or_artifacts' if name in ('artifacts', 'output', 'docs') else
            'cache' if name in ('.pytest_cache', '.ruff_cache', '.mypy_cache', '__pycache__') else 'source_or_other')
        totals[kind] += size
    result['top_buckets'] = dict(totals)
    result['newest_file_mtime_observed_utc'] = datetime.fromtimestamp(newest, timezone.utc).isoformat() if newest else None
    return result


def path_kind(path):
    p = path.lower().replace('\\', '/')
    if any(x in p.split('/') for x in ('.private', '.aws', '.codex', '.agents')) or re.search(r'(^|/)(\.env[^/]*|.*\.(pem|key|pfx|p12))$', p):
        return 'PRIVATE_OR_CONFIGURATION_UNKNOWN_PROTECT'
    if any(x in p for x in ('evidence', 'artifact', '.log', 'output/', 'receipt', '.xml', '.png')):
        return 'EVIDENCE_OR_GENERATED_UNKNOWN_PROTECT'
    if any(x in p for x in ('.venv', 'node_modules', '/venv')):
        return 'ENVIRONMENT_UNKNOWN_PROTECT'
    if any(x in p for x in ('__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache')):
        return 'REGENERABLE_CACHE_METADATA'
    return 'OTHER_LOCAL_DATA_UNKNOWN_PROTECT'


started = now()
top = [p for p in BASE.iterdir() if 'vrae' in p.name.lower() and p.is_dir()]
code, raw, _ = git(MAIN, 'worktree', 'list', '--porcelain')
registered = parse_worktrees(raw)
roots = {norm(p).lower(): p for p in top}
for row in registered:
    p = Path(row['worktree'])
    if under(p, BASE):
        roots[norm(p).lower()] = p
for parent in list(roots.values()):
    if parent == ACTIVE:
        continue
    hidden = parent / '.worktrees'
    if hidden.is_dir():
        for child in hidden.iterdir():
            if child.is_dir():
                roots.setdefault(norm(child).lower(), child)
roots = dict(sorted(roots.items()))
save('scope.json', {'roots': [str(p) for p in roots.values()], 'audit_pids': [os.getpid(), os.getppid()]})

live_main = api('repos/gloweaseco-leo/VRAE/commits/main')['sha']
prs = api('repos/gloweaseco-leo/VRAE/pulls?state=open&per_page=100')
issues = api('repos/gloweaseco-leo/VRAE/issues?state=open&per_page=100')
refs = api('repos/gloweaseco-leo/VRAE/git/matching-refs/heads/')
remote_heads = {r['ref'].removeprefix('refs/heads/'): r['object']['sha'] for r in refs}
vf = api('repos/gloweaseco-leo/VEYFRONT/pulls/37')
github = {'observed_at': now(), 'main_sha': live_main, 'live_heads': remote_heads,
          'open_prs': [{'number': p['number'], 'branch': p['head']['ref'], 'head': p['head']['sha'], 'draft': p['draft']} for p in prs],
          'open_issues': [{'number': i['number'], 'title': i['title']} for i in issues if 'pull_request' not in i],
          'vf_pr37': {'head': vf['head']['sha'], 'branch': vf['head']['ref']}}
save('github-snapshot.json', github)

code, psraw, _ = cmd(['powershell', '-NoProfile', '-File', str(OUT / 'runtime_metadata.ps1'), '-RootsFile', str(OUT / 'scope.json')], timeout=60)
windows = json.loads(psraw) if code == 0 else {'errors': ['WINDOWS_METADATA_UNAVAILABLE']}
docker = {'containers': [], 'volumes': [], 'images': [], 'errors': []}
code, ids, _ = cmd(['docker', 'ps', '-a', '--filter', 'name=vrae', '--format', '{{.ID}}'])
if code:
    docker['errors'].append('DOCKER_CONTAINER_METADATA_UNAVAILABLE')
else:
    for cid in ids.split():
        template = ('{"Name":{{json .Name}},"Image":{{json .Image}},"Mounts":{{json .Mounts}},'
                    '"State":{"Status":{{json .State.Status}},"Running":{{json .State.Running}}},'
                    '"HostConfig":{"RestartPolicy":{"Name":{{json .HostConfig.RestartPolicy.Name}}}}}')
        code, inspect, _ = cmd(['docker', 'inspect', '--format', template, cid])
        if code:
            docker['errors'].append('CONTAINER_INSPECT_UNAVAILABLE')
            continue
        d = json.loads(inspect)
        mounts = []
        for m in d.get('Mounts', []):
            source = norm(m.get('Source', ''))
            candidates = [str(p) for p in roots.values() if under(source, p)]
            mounts.append({'type': m['Type'], 'volume': m.get('Name') if m['Type'] == 'volume' else None,
                           'project_roots': candidates, 'destination': m['Destination'], 'read_write': m.get('RW'),
                           'source_redacted': '[NAMED_VOLUME_CONTENTS_NOT_READ]' if m['Type'] == 'volume' else
                           ('[VRAE_PROJECT_BIND]' if candidates else '[OTHER_BIND_NOT_SCANNED]')})
        # Never persist Config.Env, Cmd, entrypoint, labels or inspect raw JSON.
        docker['containers'].append({'name': d['Name'].lstrip('/'), 'image_id': d['Image'],
             'status': d['State']['Status'], 'running': d['State']['Running'], 'mounts': mounts,
             'restart_policy': d['HostConfig']['RestartPolicy']['Name']})
    image_ids = sorted({c['image_id'] for c in docker['containers']})
    for iid in image_ids:
        template = ('{"Size":{{json .Size}},"revision":{{json (index .Config.Labels "org.opencontainers.image.revision")}}}')
        code, inspect, _ = cmd(['docker', 'image', 'inspect', '--format', template, iid])
        if code:
            continue
        d = json.loads(inspect)
        sha_labels = {'org.opencontainers.image.revision': d['revision']} if re.fullmatch(r'[0-9a-f]{40}', d.get('revision') or '') else {}
        docker['images'].append({'id': iid, 'source_sha_labels': sha_labels, 'size_bytes_shared_not_reclaimable': d.get('Size')})
    code, volumes, _ = cmd(['docker', 'volume', 'ls', '--format', '{{.Name}}'])
    if code:
        docker['errors'].append('VOLUME_METADATA_UNAVAILABLE')
    else:
        docker['volumes'] = [{'name': n, 'contents_read': False, 'classification': 'UNKNOWN_PROTECT'} for n in volumes.splitlines() if n.lower().startswith('vrae')]
runtime = {'observed_at': now(), 'windows': windows, 'docker': docker,
           'limitations': ['No container exec or volume file reads', 'No Tailscale configuration read',
                           'No raw commands, environment variables or sensitive configuration published']}
save('runtime-snapshot.json', runtime)

runtime_roots = set()
for group in ('processes', 'tasks', 'services', 'startup', 'registry_run'):
    for item in windows.get(group, []):
        runtime_roots.update(norm(p).lower() for p in item.get('roots', []))
for c in docker['containers']:
    for m in c['mounts']:
        runtime_roots.update(norm(p).lower() for p in m['project_roots'])
runtime_roots.add(norm(ACTIVE).lower())
runtime_roots.add(norm(MAIN).lower())  # canonical shared object store / linked admin roots
registered_by_path = {norm(r['worktree']).lower(): r for r in registered}
entries = []
common_cache = {}
for idx, (key, root) in enumerate(roots.items(), 1):
    entry = {'id': f'P{idx:03}', 'path': str(root), 'exists': root.exists(), 'active_exclusion': root == ACTIVE,
             'directory_mtime_utc': datetime.fromtimestamp(root.stat().st_mtime, timezone.utc).isoformat() if root.exists() else None,
             'registered_worktree': key in registered_by_path, 'runtime_reference_observed': key in runtime_roots}
    row = registered_by_path.get(key)
    if row:
        entry.update(head=row.get('HEAD'), branch=row.get('branch', '').removeprefix('refs/heads/') or None,
                     detached=bool(row.get('detached')), git_kind='LINKED_WORKTREE_METADATA')
    if not root.exists() or root == ACTIVE:
        entry.update(git_state='UNKNOWN_PROTECT_ACTIVE_TREE_NOT_ENTERED', size={'complete': False, 'logical_bytes_observed': 0, 'reason': 'ACTIVE_TREE_NOT_ENTERED'})
        entries.append(entry)
        print(json.dumps({'id': entry['id'], 'step': idx, 'total': len(roots), 'active_skipped': True}), flush=True)
        continue
    marker = root / '.git'
    entry['git_marker'] = 'directory' if marker.is_dir() else 'file' if marker.is_file() else 'absent'
    code, prefix, _ = git(root, 'rev-parse', '--show-toplevel')
    is_root = code == 0 and norm(prefix.strip()).lower() == key
    entry['is_git_root'] = is_root
    if not is_root:
        entry.update(git_kind='NON_REPOSITORY_DIRECTORY', git_state='NOT_A_GIT_ROOT',
                     local_data='UNKNOWN_PROTECT_NO_CONTENT_READ')
    else:
        entry['git_kind'] = 'PRIMARY_REPOSITORY' if marker.is_dir() else 'LINKED_WORKTREE'
        def val(*args):
            c, out, _ = git(root, *args)
            return out.strip() if c == 0 else None
        entry['head'] = val('rev-parse', 'HEAD')
        entry['branch'] = val('symbolic-ref', '--quiet', '--short', 'HEAD')
        entry['detached'] = entry['branch'] is None
        entry['common_dir'] = val('rev-parse', '--path-format=absolute', '--git-common-dir')
        entry['remote'] = safe_url(val('remote', 'get-url', 'origin') or '')
        entry['upstream'] = val('rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}')
        entry['cached_upstream_ahead_behind'] = val('rev-list', '--left-right', '--count', 'HEAD...@{upstream}') if entry['upstream'] else None
        entry['live_main_ahead_behind'] = val('rev-list', '--left-right', '--count', f'HEAD...{live_main}')
        entry['head_ancestor_of_live_main'] = git(root, 'merge-base', '--is-ancestor', 'HEAD', live_main)[0] == 0
        entry['cached_remote_unreachable_commits'] = val('rev-list', '--count', 'HEAD', '--not', '--remotes')
        entry['head_matches_live_remote_branches'] = [b for b, sha in remote_heads.items() if sha == entry['head']]
        entry['open_prs'] = [p['number'] for p in github['open_prs'] if p['branch'] == entry['branch'] or p['head'] == entry['head']]
        if entry['common_dir'] not in common_cache:
            c, branch_raw, _ = git(root, 'branch', '-vv', '--no-color')
            common_cache[entry['common_dir']] = {'branch_vv_ok': c == 0, 'branch_count': len(branch_raw.splitlines())}
        entry['branch_vv_summary'] = common_cache[entry['common_dir']]
        code, status, _ = git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=normal', '--ignored=matching', timeout=25)
        if code:
            entry['git_state'] = 'UNKNOWN_PROTECT_STATUS_UNAVAILABLE'
        else:
            tracked = untracked = ignored = 0
            categories = {'untracked': Counter(), 'ignored': Counter()}
            records = iter(status.split('\0'))
            for record in records:
                if not record:
                    continue
                state, path = record[:2], record[3:]
                if state == '??':
                    untracked += 1
                    categories['untracked'][path_kind(path)] += 1
                elif state == '!!':
                    ignored += 1
                    categories['ignored'][path_kind(path)] += 1
                else:
                    tracked += 1
                    if 'R' in state or 'C' in state:
                        next(records, None)
            entry.update(git_state='DIRTY_TRACKED' if tracked else 'TRACKED_CLEAN', tracked_change_entries=tracked,
                         untracked_entries=untracked, ignored_entries=ignored,
                         local_data_categories={k: dict(v) for k, v in categories.items()},
                         unstored_patch_exists=tracked > 0)
    entry['size'] = metadata_size(root, set(roots) - {key})
    entries.append(entry)
    save('inventory-snapshot.json', {'started_at': started, 'last_updated': now(), 'complete': False, 'entries': entries})
    print(json.dumps({'id': entry['id'], 'step': idx, 'total': len(roots), 'git': entry.get('git_kind'),
                      'state': entry.get('git_state'), 'bytes': entry['size']['logical_bytes_observed'],
                      'size_complete': entry['size']['complete']}), flush=True)

snapshot = {'started_at': started, 'finished_at': now(), 'complete': True, 'entries': entries,
            'registered_worktrees': registered, 'common_stores': common_cache,
            'safety': {'git_optional_locks': False, 'fetch_pull_executed': False, 'active_tree_not_entered': str(ACTIVE),
                       'private_contents_read': False, 'runtime_mutations': False},
            'size_semantics': 'Logical file lengths, not allocated/deduplicated/reclaimable disk bytes; linked worktree children counted separately; private subtrees/reparse points skipped'}
save('inventory-snapshot.json', snapshot)
print(json.dumps({'complete': True, 'directories': len(entries), 'common_stores': len(common_cache), 'finished_at': now()}), flush=True)

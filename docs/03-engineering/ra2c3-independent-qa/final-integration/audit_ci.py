"""Read actual hosted job logs and verify each checkout of the held merge SHA."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--run', required=True)
parser.add_argument('--head', required=True)
parser.add_argument('--base', required=True)
parser.add_argument('--merge', required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = 'gloweaseco-leo/VRAE'
args.out.mkdir(parents=True, exist_ok=False)
def gh(*command):
    return subprocess.check_output(['gh', *command, '--repo', repo], encoding='utf-8', errors='strict')

run = json.loads(gh('run', 'view', args.run, '--json', 'headSha,event,url,conclusion,jobs'))
(args.out / 'run.json').write_text(json.dumps(run, indent=2) + '\n', encoding='utf-8')
assert run['headSha'] == args.head and run['event'] == 'pull_request'
assert run['conclusion'] == 'success'
expected = {'contracts-domain (3.11)', 'contracts-domain (3.13)', 'isolated-http', 'isolated-browser'}
assert {j['name'] for j in run['jobs']} == expected and len(run['jobs']) == 4
parents = subprocess.check_output(['git', 'show', '-s', '--format=%P', args.merge], text=True).strip().split()
assert parents == [args.base, args.head], parents
jobs = []
for job in run['jobs']:
    assert job['conclusion'] == 'success'
    log = gh('run', 'view', args.run, '--job', str(job['databaseId']), '--log')
    assert re.search(r'git log -1 --format=%H[^\n]*\n[^\n]*\b' + re.escape(args.merge) + r'\b', log), job['name']
    path = args.out / (str(job['databaseId']) + '.log')
    path.write_text(log, encoding='utf-8')
    jobs.append(dict(name=job['name'], url=job['url'], checkout_sha=args.merge,
                     log_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
summary = dict(read_utc=datetime.now(timezone.utc).isoformat(), head=args.head, base=args.base,
    merge=args.merge, merge_parents=parents, jobs=jobs)
(args.out / 'audit.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summary, indent=2))

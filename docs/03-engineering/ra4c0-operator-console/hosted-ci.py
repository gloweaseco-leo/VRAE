"""Retain genuine GitHub logs/checkout receipts; never infer skipped QA success."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
REPO='gloweaseco-leo/VRAE'


def api(path):
    return subprocess.check_output(['gh','api',f'repos/{REPO}/{path}'],cwd=ROOT)


run_id=int(sys.argv[1])
out=HERE/'evidence'/('hosted-'+str(run_id)+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'))
out.mkdir(parents=True)
run_raw=api(f'actions/runs/{run_id}')
jobs_raw=api(f'actions/runs/{run_id}/jobs?per_page=100')
pr_raw=api('pulls/61')
for name,raw in [('run.json',run_raw),('jobs.json',jobs_raw),('pr.json',pr_raw)]:
    (out/name).write_bytes(raw)
run=json.loads(run_raw)
pr=json.loads(pr_raw)
merge_raw=api('git/commits/'+pr['merge_commit_sha'])
(out/'merge-commit.json').write_bytes(merge_raw)
merge=json.loads(merge_raw)
head_raw=api('git/commits/'+json.loads(run_raw)['head_sha'])
(out/'head-commit.json').write_bytes(head_raw)
artifacts_raw=api(f'actions/runs/{run_id}/artifacts')
(out/'artifacts.json').write_bytes(artifacts_raw)
artifacts=[]
for artifact in json.loads(artifacts_raw)['artifacts']:
    if artifact['name']=='ra1b-synthetic-security-evidence' and not artifact['expired']:
        raw=api(f'actions/artifacts/{artifact["id"]}/zip')
        (out/'original-browser-security.zip').write_bytes(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            summaries=[n for n in archive.namelist() if n.endswith('/summary.json') or n=='summary.json']
            for index,name in enumerate(summaries):
                (out/f'browser-summary-{index}.json').write_bytes(archive.read(name))
        artifacts.append({'id':artifact['id'],'name':artifact['name'],'url':artifact['archive_download_url'],
                          'file':'original-browser-security.zip','sha256':hashlib.sha256(raw).hexdigest(),
                          'summary_members':summaries})
rows=[]
for job in json.loads(jobs_raw)['jobs']:
    row={'name':job['name'],'job_id':job['id'],'conclusion':job['conclusion'],'url':job['html_url']}
    if job['status']=='completed':
        raw=api(f'actions/jobs/{job["id"]}/logs')
        name=str(job['id'])+'.log'
        (out/name).write_bytes(raw)
        content=raw.decode('utf-8',errors='replace')
        match=re.search(r'git log -1 --format=%H\r?\n[^\n]*?([0-9a-f]{40})',content)
        row.update(log=name,log_sha256=hashlib.sha256(raw).hexdigest(),checkout=match.group(1) if match else None)
        for label in ('OWNER_RA3C_V2_ACTUAL_COLLECTION','OWNER_RA3C_V2_ACTUAL_CALL_REPORTS'):
            lines=[line.split(label+' ',1)[1].strip() for line in content.splitlines() if label+' ' in line]
            row[label]=[json.loads(line) for line in lines]
        row['missing_apps']=bool(re.search(r"ModuleNotFoundError: No module named 'apps'",content))
        row['pytest_summaries']=re.findall(r'\d+ passed[^\n]*',content)
    rows.append(row)
receipt={'run_id':run_id,'run_head':run['head_sha'],'run_status':run['status'],
         'pr_head':pr['head']['sha'],'accepted_main':pr['base']['sha'],'draft':pr['draft'],
         'merge_commit':merge['sha'],'merge_parents':[p['sha'] for p in merge['parents']],
         'merge_tree':merge['tree']['sha'],'head_tree':json.loads(head_raw)['tree']['sha'],
         'jobs':rows,'artifacts':artifacts}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'out':str(out),'head':receipt['run_head'],
    'jobs':[{k:r.get(k) for k in ('name','conclusion','checkout','missing_apps')} for r in rows]},indent=2))

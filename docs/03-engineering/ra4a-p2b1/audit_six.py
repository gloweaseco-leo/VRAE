"""Run all exact-HEAD audits, preserving raw audit stdout/stderr and six receipts."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
folder=Path(sys.argv[1]).resolve()
head,main=sys.argv[2:4]
def load(name):
    return json.loads((folder/name).read_text(encoding="utf-8-sig"))
pr,merge=load("pr.json"),load("merge.json")
assert pr["head"]["sha"]==head and pr["base"]["sha"]==main
assert pr["draft"] is True and pr["merged"] is False and pr["auto_merge"] is None
assert [p["sha"] for p in merge["parents"]]==[main,head]
assert pr["merge_commit_sha"]==merge["sha"]
for name in ("run.json","pg-run.json"):
    run=load(name)
    assert run["head_sha"]==head and run["event"]=="pull_request"
    assert run["status"]=="completed" and run["conclusion"]=="success"
jobs=load("jobs.json")["jobs"]+load("pg-jobs.json")["jobs"]
assert len(jobs)==6 and all(j["status"]=="completed" and j["conclusion"]=="success" for j in jobs)
assert {j["name"] for j in jobs}=={"contracts-domain (3.11)","contracts-domain (3.13)","isolated-http","isolated-browser","postgres-16 (3.11)","postgres-16 (3.13)"}
for job in jobs:
    lines=(folder/(str(job["id"])+".log")).read_text(encoding="utf-8-sig").splitlines()
    positions=[i for i,line in enumerate(lines) if "[command]/usr/bin/git log -1 --format=%H" in line]
    assert len(positions)==1
    assert lines[positions[0]+1].split()[-1]==merge["sha"], job["name"]
stages=[("legacy",["audit_hosted_legacy.py",str(folder),head,main,"127"]),
        ("v2",["audit_hosted_v2.py",str(folder)]),
        ("postgres",["audit_hosted_pg.py",str(folder),head,main,merge["sha"]])]
records=[]
for label,argv in stages:
    argv=[str(HERE/argv[0]),*argv[1:]]
    r=subprocess.run([sys.executable,*argv],cwd=ROOT,capture_output=True,check=False)
    for tag,raw in (("stdout",r.stdout),("stderr",r.stderr)):
        (folder/("audit-"+label+"."+tag+".log")).write_bytes(raw)
    records.append({"stage":label,"exit":r.returncode,"stdout_sha256":hashlib.sha256(r.stdout).hexdigest(),"stderr_sha256":hashlib.sha256(r.stderr).hexdigest()})
    (folder/"audit-commands.json").write_text(json.dumps(records,indent=2)+"\n",encoding="utf-8")
    print(label,r.returncode,flush=True)
    if r.returncode:
        print(r.stdout.decode(errors="replace")[-2000:])
        print(r.stderr.decode(errors="replace")[-3000:])
        raise SystemExit(r.returncode)
receipts=[]
for j in jobs:
    raw=(folder/(str(j["id"])+".log")).read_bytes()
    log=raw.decode("utf-8-sig")
    assert all(s in log for s in (head,main,merge["sha"]))
    receipts.append({"job":j["name"],"url":j["html_url"],"conclusion":j["conclusion"],
                     "actual_checkout":merge["sha"],"decoded_log_sha256":hashlib.sha256(raw).hexdigest()})
out={"final_head":head,"accepted_main":main,"actual_merge_ref":merge["sha"],"ordered_parents":[main,head],
     "jobs":receipts,"legacy_receipt":"FINAL_CI_RECEIPT.json","ra3c_v2_receipt":"RA3C_V2_AND_HTTP_ACTUAL_PROOF.json",
     "real_pg_receipt":"PG_P2B1_ACTUAL_RECEIPT.json","draft":True,"merged":False,"auto_merge":None,
     "authority":"TEST_ONLY_SYNTHETIC_DECISIONS_NOT_HUMAN_APPROVAL"}
(folder/"SIX_CI_ACTUAL_RECEIPT.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
print("VERIFIED_SIX_REAL_CI_EXACT_HEAD_MAIN_MERGE_REF_RAW_LOGS_ARTIFACTS_AND_SECURITY")

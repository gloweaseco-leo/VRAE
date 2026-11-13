"""Seal actual local phases, whole-tree scope, frozen sources and raw archive."""
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
ENTRY="e9ec1bd7f36a0446af14f04b66b71e4d45ebfb97"
MAIN="cf11278ba4c9b62b3645cdbd6fd2cd8bb2f1838b"
EXCEPT={"infra/ra4a/lab.py",".github/workflows/ra4a-pg.yml"}


def git(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT)


def tree(ref):
    return {s.split("\t")[1]:s.split("\t")[0] for s in git("ls-tree","-r",ref).decode().splitlines()}


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def junit(path, expected):
    suite=ET.parse(path).getroot().find("testsuite")
    assert int(suite.attrib["tests"])==expected
    assert all(int(suite.attrib[k])==0 for k in ("failures","errors","skipped"))
    cases=suite.findall("testcase")
    assert len(cases)==expected
    return cases


def main():
    head=git("rev-parse","HEAD").decode().strip()
    before,after=tree(MAIN),tree(head)
    assert all(after.get(p)==v for p,v in before.items() if p not in EXCEPT)
    assert {p for p in before if after.get(p)!=before[p]}==EXCEPT
    allowed=("vrae/persistence/","integration/ra4a/","tests/persistence/","infra/ra4a/","docs/03-engineering/ra4a-p2a/")
    added=sorted(after.keys()-before.keys())
    assert all(p.startswith(allowed) or p=="db/migrations/0002_ra4a_private_bytes.sql" for p in added)
    assert not git("diff","--name-only","HEAD").strip()
    frozen=[]
    for p in sorted((set(added)|EXCEPT)-{p for p in added if p.startswith("docs/")}):
        raw=git("show",head+":"+p)
        frozen.append({"path":p,"mode_blob":after[p],"sha256":hashlib.sha256(raw).hexdigest()})
    sql1=hashlib.sha256(git("show",head+":db/migrations/0001_ra4a_test_only.sql")).hexdigest()
    sql2=hashlib.sha256(git("show",head+":db/migrations/0002_ra4a_private_bytes.sql")).hexdigest()
    results=[]
    ids=None
    for label in ("dev-full-04","local311-fresh"):
        folder=HERE/label
        record=load(folder/"commands.json")
        assert all(c["exit"]==0 for c in record["commands"])
        for source in load(folder/"source-manifest.json"):
            assert hashlib.sha256(git("show",head+":"+source["path"])).hexdigest()==source["sha256"],source["path"]
        p1=load(folder/"p1-v1/pg-catalog-and-calls.json")
        compat=load(folder/"p1-v2/pg-catalog-and-calls.json")
        assert p1["migrations"]==[[1,sql1]]
        assert compat["migrations"]==[[1,sql1],[2,sql2]]
        for data in (p1,compat):
            assert len(data["calls"])==54 and all(c["outcome"]=="passed" for c in data["calls"])
        junit(folder/"p1-v1/postgres.xml",54)
        junit(folder/"p1-v2/tests.xml",54)
        pure=junit(folder/"p1-v1/pure.xml",25)
        assert sum(c.attrib["classname"].endswith("test_contracts") for c in pure)==11
        assert sum(c.attrib["classname"].endswith("test_p2a_contracts") for c in pure)==14
        junit(folder/"p2a/tests.xml",86)
        actual=load(folder/"p2a/p2a-catalog-and-calls.json")
        calls=actual["actual_calls"]
        assert len(calls)==86 and all(c["outcome"]=="passed" for c in calls)
        current={c["id"] for c in calls}
        assert len(current)==86 and (ids is None or ids==current)
        ids=current
        assert actual["migrations"]==[[1,sql1],[2,sql2]]
        recovery=load(folder/"p2a/p2a-recovery.json")
        raw=(folder/"p2a/private-bytes.dump").read_bytes()
        assert hashlib.sha256(raw).hexdigest()==recovery["dump_sha256"] and len(raw)==recovery["dump_bytes"]
        assert all(recovery[k] for k in ("actual_volume_restart","restored_original_bytes_exact","cross_tenant_and_stale_denied_after_both_recoveries"))
        for case in ("404-v1","200-v1","404-v2"):
            held=folder/"p2a/independently-held"/case
            for a in load(held/"manifest.json"):
                raw=(held/(a["kind"]+"-"+a["key"]+".bin")).read_bytes()
                assert len(raw)==a["length"] and hashlib.sha256(raw).hexdigest()==a["sha256"]
        results.append({"label":label,"python":record["python"],"recorded_start_head":record["actual_source_head"],
                        "all_runtime_source_hashes_match_committed_head":True,"p1_v1":54,"p1_v2":54,"original_pure":11,
                        "new_pure":14,"p2a_pg":86,"schema_sha256":actual["schema_sha256"],"recovery":recovery})
    for label in ("local313-and-reused311-cleanup","local311-fresh-cleanup"):
        cleanup=load(HERE/label/"scan-and-cleanup.json")
        assert cleanup["actual_credential_scan"]=="NO_MATCHES" and cleanup["cleanup_exit"]==0
        proof=load(HERE/label/"teardown/teardown.json")
        assert all(proof[k] for k in ("owned_container_removed","owned_network_removed","owned_volume_removed"))
    assert not (ROOT/"infra/ra4a/.venv/lab-state.json").exists()
    source_set=hashlib.sha256(json.dumps(frozen,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    scope={"entry_main":ENTRY,"accepted_main":MAIN,"functional_head":head,"accepted_main_blobs":len(before),
           "preserved_main_blob_modes":len(before)-2,"authorized_minimal_existing_exceptions":sorted(EXCEPT),
           "frozen_sources":frozen,"source_set_sha256":source_set,"migration_1_sha256":sql1,"migration_2_sha256":sql2,
           "p2a_actual_ids":sorted(ids),"actual_dual_results":results,
           "source_3_13_note":"Start HEAD was entry main with uncommitted P2A sources; every runtime source SHA independently matches the later committed functional HEAD. Both hosted final jobs still required.",
           "codex2_branch_modified":False,"original_p1_sql_business_tests_unchanged":True}
    (HERE/"SOURCE_SCOPE.json").write_text(json.dumps(scope,indent=2)+"\n",encoding="utf-8")
    files=sorted(p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts and "post-ci" not in p.parts
                 and p.name not in ("raw-local-evidence.zip","RAW_LOCAL_MANIFEST.json"))
    members=[]
    archive=HERE/"raw-local-evidence.zip"
    with zipfile.ZipFile(archive,"x",zipfile.ZIP_DEFLATED) as z:
        for path in files:
            raw=path.read_bytes()
            name=path.relative_to(HERE).as_posix()
            z.writestr(name,raw)
            members.append({"member":name,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()})
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(r["member"])).hexdigest()==r["sha256"] for r in members)
    manifest={"sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),"bytes":archive.stat().st_size,
              "source_set_sha256":source_set,"members":members}
    (HERE/"RAW_LOCAL_MANIFEST.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in manifest.items() if k!="members"}))
    print("LATEST_MAIN_BLOBS_PRESERVED="+str(len(before)-2)+" PLUS_TWO_AUTHORIZED_HARNESS_WORKFLOW_EXCEPTIONS")


if __name__=="__main__":
    main()

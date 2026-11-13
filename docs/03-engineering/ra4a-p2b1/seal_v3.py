"""Outside-tree and actual-result audit; never infer a test PASS from a file."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
ENTRY="558d183624a0a36d1f4eaf9d3d75af73b9c88547"
EXCEPT={"infra/ra4a/lab.py","infra/ra4a/p2a_run.py",".github/workflows/ra4a-pg.yml"}
PREFIXES=("vrae/persistence/","integration/ra4a/","tests/persistence/","infra/ra4a/","docs/03-engineering/ra4a-p2b1/")


def git(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT)


def tree(ref):
    return {s.split("\t")[1]:s.split("\t")[0] for s in git("ls-tree","-r",ref).decode().splitlines()}


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def scope(main):
    before,after=tree(main),tree("HEAD")
    assert all(after.get(p)==v for p,v in before.items() if p not in EXCEPT)
    assert {p for p in before if after.get(p)!=before[p]}==EXCEPT
    added=sorted(after.keys()-before.keys())
    assert all(p.startswith(PREFIXES) or p=="db/migrations/0003_ra4a_test_review_cas.sql" for p in added)
    frozen=[]
    for p in sorted((set(added)|EXCEPT)-{p for p in added if p.startswith("docs/")}):
        frozen.append({"path":p,"mode_blob":after[p],"sha256":digest(git("show","HEAD:"+p))})
    assert not git("diff","HEAD","--name-only","--","vrae","tests","integration","infra","db",".github").strip()
    return before,frozen


def junit(path,n):
    suite=ET.parse(path).getroot().find("testsuite")
    assert int(suite.attrib["tests"])==n
    assert all(int(suite.attrib[k])==0 for k in ("failures","errors","skipped"))
    cases=suite.findall("testcase")
    assert len(cases)==n
    return cases


def freeze():
    out=HERE/"SOURCE_SCOPE_V3.json"
    assert not out.exists()
    main=sys.argv[2] if len(sys.argv)>2 else ENTRY
    before,frozen=scope(main)
    matrix=load(HERE/"FROZEN_MATRIX_V3.json")
    for r in matrix["sources_and_accepted_fixtures"]:
        assert digest(git("show","HEAD:"+r["path"]))==r["lf_sha256"]
    runtime=[{"path":p,"sha256":digest(git("show","HEAD:"+p))} for p in sorted(tree("HEAD"))
             if p.startswith(("vrae/persistence/","integration/ra4a/","tests/persistence/","infra/ra4a/","db/migrations/"))]
    state=load(ROOT/"infra/ra4a/.venv/lab-state.json")
    data={"entry_main":ENTRY,"accepted_main":main,"functional_head":git("rev-parse","HEAD").decode().strip(),
          "accepted_main_blobs":len(before),"preserved_main_blob_modes":len(before)-len(EXCEPT),
          "authorized_existing_exceptions":sorted(EXCEPT),"frozen_sources":frozen,"runtime_sources":runtime,
          "source_set_sha256":digest(json.dumps(frozen,sort_keys=True,separators=(",",":")).encode()),
          "p2b1_count":matrix["p2b1_count"],"p2b1_actual_ids":matrix["actual_collected_ids"],
          "p2b1_schema_sha256":state["p2b1_schema_sha256"],
          "migration_3_sha256":digest(git("show","HEAD:db/migrations/0003_ra4a_test_review_cas.sql")),
          "authority":"TEST_ONLY_SYNTHETIC_DECISIONS_NOT_HUMAN_APPROVAL"}
    out.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:data[k] for k in ("functional_head","preserved_main_blob_modes","p2b1_count","source_set_sha256")}))


def results():
    held=load(HERE/"SOURCE_SCOPE_V3.json")
    integrated=load(HERE/"INTEGRATION_SCOPE_V3.json") if (HERE/"INTEGRATION_SCOPE_V3.json").exists() else held
    _,current=scope(integrated["accepted_main"])
    assert current==held["frozen_sources"]
    all_results=[]
    for label in ("local313-v3-fresh","local311-v3-fresh"):
        folder=HERE/label
        cmd=load(folder/"commands.json")
        assert cmd["phase"]=="full" and len(cmd["commands"])==3 and all(c["exit"]==0 for c in cmd["commands"])
        assert {r["path"]:r["sha256"] for r in load(folder/"source-manifest.json")}=={r["path"]:r["sha256"] for r in held["runtime_sources"]}
        pre=folder/"accepted-prelude"
        pcmd=load(pre/"commands.json")
        assert len(pcmd["commands"])==4 and all(c["exit"]==0 for c in pcmd["commands"])
        assert {r["path"]:r["sha256"] for r in load(pre/"source-manifest.json")}=={r["path"]:r["sha256"] for r in held["runtime_sources"]}
        for phase,xml in (("p1-v1","postgres.xml"),("p1-v2","tests.xml")):
            junit(pre/phase/xml,54)
            p=load(pre/phase/"pg-catalog-and-calls.json")
            assert len(p["calls"])==54 and all(c["outcome"]=="passed" for c in p["calls"])
            b=load(pre/phase/"backup-restore.json")
            assert b["source_data_sha256"]==b["restored_data_sha256"]
            assert digest((pre/phase/"synthetic-metadata.dump").read_bytes())==b["dump_sha256"]
        pure=junit(pre/"p1-v1/pure.xml",35)
        for module,n in (("test_contracts",11),("test_p2a_contracts",14),("test_p2b1_contracts",10)):
            assert sum(c.attrib["classname"].endswith(module) for c in pure)==n
        junit(pre/"p2a/tests.xml",86)
        p2a=load(pre/"p2a/p2a-catalog-and-calls.json")
        assert len(p2a["actual_calls"])==86 and all(c["outcome"]=="passed" for c in p2a["actual_calls"])
        p2ar=load(pre/"p2a/p2a-recovery.json")
        assert digest((pre/"p2a/private-bytes.dump").read_bytes())==p2ar["dump_sha256"]
        junit(folder/"p2b1/tests.xml",held["p2b1_count"])
        b=load(folder/"p2b1/p2b1-catalog-and-calls.json")
        assert b["session_exit"]==0 and len(b["calls"])==held["p2b1_count"]
        assert all(c["outcome"]=="passed" for c in b["calls"])
        assert {c["id"] for c in b["calls"]}==set(held["p2b1_actual_ids"])
        assert b["schema_sha256"]==held["p2b1_schema_sha256"]
        recovery=load(folder/"p2b1/p2b1-recovery.json")
        assert digest((folder/"p2b1/test-review-ledger.dump").read_bytes())==recovery["dump_sha256"]
        assert all(recovery[k] for k in ("actual_container_volume_restart","restore_exact","old_version_and_foreign_tenant_denied"))
        cleanup=load(HERE/(label+"-cleanup")/"scan-and-cleanup.json")
        assert cleanup["actual_credential_scan"]=="NO_MATCHES" and cleanup["cleanup_exit"]==0
        all_results.append({"label":label,"python":cmd["python"],"recorded_head":cmd["source_head"],
                            "runtime_source_hashes_match_frozen_git":True,"p1_v1":54,"p1_v2_compat":54,
                            "p2a_pg":86,"original_pure":25,"new_pure":10,"p2b1_pg":held["p2b1_count"],
                            "new_pg_skip_xfail":0,"recovery":recovery})
    assert not (ROOT/"infra/ra4a/.venv/lab-state.json").exists()
    result=HERE/"LOCAL_DUAL_ACTUAL_RESULTS_V3.json"
    assert not result.exists()
    result.write_text(json.dumps(all_results,indent=2)+"\n",encoding="utf-8")
    paths=[p for p in sorted(HERE.rglob("*")) if p.is_file() and "__pycache__" not in p.parts and p.name!="P2B1_LOCAL_RAW_EVIDENCE_V3.zip"]
    manifest=[{"path":p.relative_to(HERE).as_posix(),"bytes":p.stat().st_size,"sha256":digest(p.read_bytes())} for p in paths]
    (HERE/"RAW_MANIFEST_V3.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    archive=HERE/"P2B1_LOCAL_RAW_EVIDENCE_V3.zip"
    with zipfile.ZipFile(archive,"x",compression=zipfile.ZIP_DEFLATED) as z:
        for p in paths: z.write(p,p.relative_to(HERE).as_posix())
        z.write(HERE/"RAW_MANIFEST_V3.json","RAW_MANIFEST_V3.json")
    (HERE/"ARCHIVE_RECEIPT_V3.json").write_text(json.dumps({"archive":archive.name,"sha256":digest(archive.read_bytes()),"bytes":archive.stat().st_size,
        "members":len(paths)+1,"manifest_sha256":digest((HERE/"RAW_MANIFEST_V3.json").read_bytes()),"source_set_sha256":held["source_set_sha256"]},indent=2)+"\n",encoding="utf-8")
    print("VERIFIED_DUAL_FRESH_FULL_RESULTS RAW_ZIP_SHA256="+digest(archive.read_bytes()))


def verify_head():
    held=load(HERE/"SOURCE_SCOPE_V3.json")
    integrated=load(HERE/"INTEGRATION_SCOPE_V3.json") if (HERE/"INTEGRATION_SCOPE_V3.json").exists() else held
    before,current=scope(integrated["accepted_main"])
    assert current==held["frozen_sources"]
    head=git("rev-parse","HEAD").decode().strip()
    out=Path(sys.argv[2])
    out.mkdir(parents=True,exist_ok=True)
    (out/"FINAL_SOURCE_CHAIN.json").write_text(json.dumps({"final_head":head,"functional_head":held["functional_head"],
       "accepted_main":integrated["accepted_main"],"main_blob_modes_preserved":len(before)-len(EXCEPT),
       "existing_exceptions":sorted(EXCEPT),"all_frozen_runtime_and_test_blobs_unchanged":True,
       "source_set_sha256":held["source_set_sha256"]},indent=2)+"\n",encoding="utf-8")
    print("VERIFIED_FINAL_HEAD_PROTECTED_MAIN_AND_FROZEN_RUNTIME_GIT_BLOBS "+head)


def integrate_audit():
    held=load(HERE/"SOURCE_SCOPE_V3.json")
    main=sys.argv[2]
    assert main=="51e2ff3f592c206fddf8193ad7346efbd2a70136"
    before,current=scope(main)
    assert current==held["frozen_sources"]
    head=git("rev-parse","HEAD").decode().strip()
    parents=git("show","-s","--format=%P",head).decode().strip().split()
    assert parents==[held["functional_head"],main]
    out=HERE/"INTEGRATION_SCOPE_V3.json"
    assert not out.exists()
    data={"integration_head":head,"ordered_merge_parents":parents,"accepted_main":main,
          "accepted_main_blobs":len(before),"preserved_main_blob_modes":len(before)-len(EXCEPT),
          "existing_exceptions":sorted(EXCEPT),"functional_head":held["functional_head"],
          "all_frozen_p2b1_runtime_and_test_blob_modes_unchanged":True,"source_set_sha256":held["source_set_sha256"],
          "ra4c2_main_app_and_tests_preserved":True,"final_ci_must_cover_additional_96_console_cases":True}
    out.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(data))


def hosted_results():
    """Full actual hosted gate, with local ERROR kept as ERROR, never PASS."""
    held=load(HERE/"SOURCE_SCOPE_V3.json")
    integrated=load(HERE/"INTEGRATION_SCOPE_V3.json")
    _,current=scope(integrated["accepted_main"])
    assert current==held["frozen_sources"]
    hosted=HERE/"source-v3-ci-8e99cb5"
    six=load(hosted/"SIX_CI_ACTUAL_RECEIPT.json")
    assert six["final_head"]==held["functional_head"] and six["accepted_main"]==integrated["accepted_main"]
    assert len(six["jobs"])==6 and all(j["conclusion"]=="success" for j in six["jobs"])
    pg=load(hosted/"PG_P2B1_ACTUAL_RECEIPT.json")
    assert len(pg)==2 and all(p["p2b1_pg"]==131 for p in pg)
    assert {p["job"] for p in pg}=={"postgres-16 (3.11)","postgres-16 (3.13)"}
    local=[]
    for label in ("local313-v3-fresh","local311-v3-fresh"):
        folder=HERE/label
        cmd=load(folder/"commands.json")
        assert cmd["phase"]=="full" and cmd["commands"][-1]["exit"]!=0
        assert all(c["exit"]==0 for c in cmd["commands"][:-1])
        assert {r["path"]:r["sha256"] for r in load(folder/"source-manifest.json")}=={r["path"]:r["sha256"] for r in held["runtime_sources"]}
        pre=folder/"accepted-prelude"
        for phase,xml in (("p1-v1","postgres.xml"),("p1-v2","tests.xml")):
            junit(pre/phase/xml,54)
        junit(pre/"p2a/tests.xml",86)
        junit(pre/"p1-v1/pure.xml",35)
        calls=load(folder/"p2b1/p2b1-catalog-and-calls.json")
        assert calls["session_exit"]!=0 and all(c["outcome"]=="passed" for c in calls["calls"])
        suite=ET.parse(folder/"p2b1/tests.xml").getroot().find("testsuite")
        assert int(suite.attrib["errors"])==1 and int(suite.attrib["failures"])==int(suite.attrib["skipped"])==0
        assert "connection timeout expired" in (folder/"p2b1.stdout.log").read_text()
        cleanup=load(HERE/(label+"-cleanup")/"scan-and-cleanup.json")
        assert cleanup["actual_credential_scan"]=="NO_MATCHES" and cleanup["cleanup_exit"]==0
        local.append({"label":label,"python":cmd["python"],"source_head":cmd["source_head"],
          "p1_v1":54,"p1_v2_compat":54,"p2a":86,"pure":35,"actual_p2b1_call_passes":len(calls["calls"]),
          "errors":1,"remaining_not_executed":131-len(calls["calls"]),"full_local_pass":False,
          "error":"ConnectionTimeout at setup/teardown; root cause unconfirmed; diagnostics subsequently reconnected",
          "junit_attributes":suite.attrib})
    result=HERE/"V3_ACTUAL_RESULTS.json"
    assert not result.exists()
    result.write_text(json.dumps({"functional_head":held["functional_head"],"integration":integrated,
       "primary_full_dual_python_gate":"ACTUAL_HOSTED_FRESH_PG_BOTH_131_PASS",
       "hosted_dual_pg":pg,"hosted_six":six,"local_runs":local,
       "local_errors_not_converted_to_pass":True,"real_identity_native_approval_share_deploy":False},indent=2)+"\n",encoding="utf-8")
    assert not (ROOT/"infra/ra4a/.venv/lab-state.json").exists()
    archive=HERE/"P2B1_V3_ENGINEERING_EVIDENCE.zip"
    assert not archive.exists()
    paths=[p for p in sorted(HERE.rglob("*")) if p.is_file() and "__pycache__" not in p.parts and p!=archive]
    manifest=[{"path":p.relative_to(HERE).as_posix(),"bytes":p.stat().st_size,"sha256":digest(p.read_bytes())} for p in paths]
    (HERE/"RAW_MANIFEST_V3.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    with zipfile.ZipFile(archive,"x",compression=zipfile.ZIP_DEFLATED) as z:
        for p in paths: z.write(p,p.relative_to(HERE).as_posix())
        z.write(HERE/"RAW_MANIFEST_V3.json","RAW_MANIFEST_V3.json")
    with zipfile.ZipFile(archive) as z: assert z.testzip() is None
    receipt={"archive":archive.name,"sha256":digest(archive.read_bytes()),"bytes":archive.stat().st_size,
        "members":len(paths)+1,"manifest_sha256":digest((HERE/"RAW_MANIFEST_V3.json").read_bytes()),
        "source_set_sha256":held["source_set_sha256"],"primary_full_gate":"HOSTED_BOTH_PYTHON_131_PASS",
        "local_error_evidence_preserved":True,"private_unredacted_failure_bytes_not_published":True}
    (HERE/"ARCHIVE_RECEIPT_V3.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(receipt))


if __name__=="__main__":
    {"freeze":freeze,"results":results,"verify":verify_head,"integrate":integrate_audit,"hosted":hosted_results}[sys.argv[1]]()

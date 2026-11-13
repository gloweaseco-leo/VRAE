"""Audit original downloaded hosted P1/P2A PG ZIPs against outside held bytes."""
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from integration.ra4a.p2a_support import graph
from vrae.persistence.private_bytes import descriptors

HERE=Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    folder=Path(sys.argv[1])
    head,main,merge=sys.argv[2:5]
    scope=load(HERE.parent/"ra4a-p2a/SOURCE_SCOPE.json")
    generation="SOURCE_SCOPE.json" if head in ("19caca8d3ebfcafda6e088a29fd6611f96214c24","292b030593c60e64c6f4e5f0a1473b113836e554") else "SOURCE_SCOPE_V3.json"
    new_scope=load(HERE/generation)
    expected_ids=set(scope["p2a_actual_ids"])
    expected_sources={r["path"]:r["sha256"] for r in new_scope["runtime_sources"]}
    jobs=load(folder/"pg-jobs.json")["jobs"]
    arts=load(folder/"pg-artifacts.json")["artifacts"]
    assert len(jobs)==len(arts)==2
    proofs=[]
    for version in ("3.11","3.13"):
        job=next(j for j in jobs if j["name"]=="postgres-16 ("+version+")")
        assert job["status"]=="completed" and job["conclusion"]=="success"
        log=(folder/(str(job["id"])+".log")).read_text(encoding="utf-8-sig")
        assert all(v in log for v in (head,main,merge))
        meta=next(a for a in arts if a["name"]=="ra4a-pg16-"+version)
        archive=folder/("pg-"+version+".zip")
        sha=hashlib.sha256(archive.read_bytes()).hexdigest()
        assert not meta["expired"] and meta["digest"]=="sha256:"+sha
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            assert not any("lab-state.json" in p or "/.venv/" in p for p in z.namelist())
            def suffix(name):
                names=[n for n in z.namelist() if n.endswith(name)]
                assert len(names)==1,(name,names)
                return names[0]
            def read(name):
                return json.loads(z.read(name))
            prefix=suffix("/p1-v1/pg-catalog-and-calls.json").removesuffix("p1-v1/pg-catalog-and-calls.json")
            def data(name):
                return read(prefix+name)
            def junit(name,n):
                suite=ET.fromstring(z.read(prefix+name)).find("testsuite")
                assert int(suite.attrib["tests"])==n and len(suite.findall("testcase"))==n
                assert all(int(suite.attrib[k])==0 for k in ("failures","errors","skipped"))
                return suite.findall("testcase")
            cmd=data("commands.json")
            assert cmd["actual_source_head"]==cmd["checkout"]==merge
            assert len(cmd["commands"])==4 and all(c["exit"]==0 for c in cmd["commands"])
            assert {r["path"]:r["sha256"] for r in data("source-manifest.json")}==expected_sources
            for name,expected_migrations,xml in (
                ("p1-v1",[[1,scope["migration_1_sha256"]]],"postgres.xml"),
                ("p1-v2",[[1,scope["migration_1_sha256"]],[2,scope["migration_2_sha256"]]],"tests.xml"),
            ):
                c=data(name+"/pg-catalog-and-calls.json")
                assert c["github_checkout"]==merge and c["session_exit"]==0
                assert c["migrations"]==expected_migrations
                assert len(c["calls"])==54 and all(x["outcome"]=="passed" for x in c["calls"])
                junit(name+"/"+xml,54)
                backup=data(name+"/backup-restore.json")
                assert backup["source_data_sha256"]==backup["restored_data_sha256"]
                assert hashlib.sha256(z.read(prefix+name+"/synthetic-metadata.dump")).hexdigest()==backup["dump_sha256"]
                restart=data(name+"/real-restart.json")
                assert restart["committed_ids_preserved"] and all(v=="on" for v in restart["settings"].values())
            pure=junit("p1-v1/pure.xml",35)
            assert sum(c.attrib["classname"].endswith("test_contracts") for c in pure)==11
            assert sum(c.attrib["classname"].endswith("test_p2a_contracts") for c in pure)==14
            assert sum(c.attrib["classname"].endswith("test_p2b1_contracts") for c in pure)==10
            junit("p2a/tests.xml",86)
            pg=data("p2a/p2a-catalog-and-calls.json")
            assert pg["session_exit"]==0 and pg["checkout"]==merge and "PostgreSQL 16.15" in pg["server"]
            assert len(pg["actual_calls"])==86 and {r["id"] for r in pg["actual_calls"]}==expected_ids
            assert all(r["outcome"]=="passed" for r in pg["actual_calls"])
            assert len(pg["roles"])==4 and all(not any(r[i] for i in (1,2,4,5)) for r in pg["roles"])
            assert len(pg["tables"])==3 and all(t[1:]==[True,True,"ra4a_owner"] for t in pg["tables"])
            assert len(pg["policies"])==3 and all(p[1] and p[2] for p in pg["policies"])
            assert all(g[0]=="ra4a_owner" for g in pg["grants"])
            assert any(t[1]=="complete_bytes" and t[2:] == [True,True] for t in pg["triggers"])
            assert sum(t[1]=="immutable_bytes" for t in pg["triggers"])==3
            assert sum(t[1]=="immutable_truncate" for t in pg["triggers"])==3
            assert any(t[1]=="no_append_after_seal" for t in pg["triggers"])
            assert all(f[2]=="ra4a_owner" for f in pg["functions"])
            assert pg["schema_sha256"]==scope["actual_dual_results"][0]["schema_sha256"]
            assert pg["native_approvals"]==pg["share_grants"]==0 and pg["production_authority"] is False
            recovery=data("p2a/p2a-recovery.json")
            dump=z.read(prefix+"p2a/private-bytes.dump")
            assert hashlib.sha256(dump).hexdigest()==recovery["dump_sha256"] and len(dump)==recovery["dump_bytes"]
            assert all(recovery[k] for k in ("actual_volume_restart","restored_original_bytes_exact","cross_tenant_and_stale_denied_after_both_recoveries"))
            for case,ver in (("404",1),("200",1),("404",2)):
                held=prefix+"p2a/independently-held/"+case+"-v"+str(ver)+"/"
                expected=graph(case,ver)
                assert z.read(held+"held.json")==expected.trust.held
                assert z.read(held+"policy.json")==expected.trust.policy
                assert z.read(held+"manifest.json")==expected.manifest
                for a in expected.artifacts:
                    assert z.read(held+a.kind+"-"+a.key+".bin")==a.raw
            assert recovery["held_expected_artifacts"]==descriptors(graph("404",2).artifacts)+descriptors(graph("200").artifacts)
            # P2B1 runs only after the complete unchanged accepted prelude.
            bprefix=suffix("/p2b1/p2b1-catalog-and-calls.json").removesuffix("p2b1/p2b1-catalog-and-calls.json")
            def bdata(name):
                return read(bprefix+name)
            bcmd=bdata("commands.json")
            assert bcmd["source_head"]==bcmd["checkout"]==merge and bcmd["phase"]=="full"
            assert len(bcmd["commands"])==3 and all(c["exit"]==0 for c in bcmd["commands"])
            assert {r["path"]:r["sha256"] for r in bdata("source-manifest.json")}==expected_sources
            b=bdata("p2b1/p2b1-catalog-and-calls.json")
            assert b["checkout"]==merge and b["session_exit"]==0
            assert len(b["calls"])==new_scope["p2b1_count"]
            assert {r["id"] for r in b["calls"]}==set(new_scope["p2b1_actual_ids"])
            assert all(c["outcome"]=="passed" for c in b["calls"])
            bsuite=ET.fromstring(z.read(bprefix+"p2b1/tests.xml")).find("testsuite")
            assert int(bsuite.attrib["tests"])==new_scope["p2b1_count"]
            assert all(int(bsuite.attrib[k])==0 for k in ("failures","errors","skipped"))
            assert b["migrations"]==[[1,scope["migration_1_sha256"]],[2,scope["migration_2_sha256"]],[3,new_scope["migration_3_sha256"]]]
            assert len(b["roles"])==5 and all(not any(r[i] for i in (1,2,4,5)) for r in b["roles"])
            assert len(b["tables"])==7 and all(t[1:]==[True,True,"ra4a_owner"] for t in b["tables"])
            assert len(b["policies"])==7 and all(p[1] and p[2] for p in b["policies"])
            assert all(g[0]=="ra4a_owner" for g in b["grants"])
            assert all(f[2]=="ra4a_owner" for f in b["functions"])
            assert b["schema_sha256"]==new_scope["p2b1_schema_sha256"]
            assert any(t[1]=="complete_proposal" and t[2:]==[True,True] for t in b["triggers"])
            assert sum(t[1]=="immutable_review" for t in b["triggers"])==5
            assert sum(t[1]=="review_no_truncate" for t in b["triggers"])==6
            assert b["authority"]=="TEST_ONLY_SYNTHETIC_DECISIONS_NOT_HUMAN_APPROVAL"
            assert b["native_human_approvals"]==b["share_grants"]==0
            br=bdata("p2b1/p2b1-recovery.json")
            bdump=z.read(bprefix+"p2b1/test-review-ledger.dump")
            assert hashlib.sha256(bdump).hexdigest()==br["dump_sha256"] and len(bdump)==br["dump_bytes"]
            assert all(br[k] for k in ("actual_container_volume_restart","restore_exact","old_version_and_foreign_tenant_denied"))
            def cleanup(name):
                c=read(suffix(name))
                assert all(c[k] is True for k in ("owned_container_removed","owned_network_removed","owned_volume_removed"))
                assert len(c["actual_results"])==3 and all(r["absent_after"] and "error" not in r for r in c["actual_results"])
                return c
            normal=cleanup("/ci-"+version+"/teardown/teardown.json")
            assert all(r["present_before"] for r in normal["actual_results"])
            failure=read(suffix("/ci-"+version+"-failure/failure-probe.json"))
            assert failure["startup_exit"]!=0 and failure["business_tests_executed"]==0
            assert failure["state_never_published"] and failure["actual_cleanup_passes"]==3
            first="/ci-"+version+"-failure/startup/failure-cleanup/teardown.json"
            cleanup(first)
            assert hashlib.sha256(z.read(suffix(first))).hexdigest()==failure["first_cleanup_sha256"]
            for i in (1,2):
                c=cleanup("/ci-"+version+"-failure/repeat-cleanup-"+str(i)+"/teardown.json")
                assert all(r["present_before"] is False for r in c["actual_results"])
            proofs.append({"job":job["name"],"url":job["html_url"],"artifact_id":meta["id"],"sha256":sha,
                           "p1_v1":54,"p1_v2_compat":54,"p1_pure":11,"p2a_pure":14,"p2a_pg":86,
                           "schema_sha256":pg["schema_sha256"],"roles":pg["roles"],"tables":pg["tables"],
                           "recovery":recovery,"normal_cleanup":normal,"before_state_cleanup":failure,
                           "complete_held_graphs_match_independent_main_fixtures":True,"checkout":merge,
                           "p2b1_pg":new_scope["p2b1_count"],"p2b1_schema_sha256":b["schema_sha256"],"p2b1_recovery":br})
    (folder/"PG_P2B1_ACTUAL_RECEIPT.json").write_text(json.dumps(proofs,indent=2)+"\n",encoding="utf-8")
    print("VERIFIED_BOTH_REAL_HOSTED_ACCEPTED_P1_P2A_AND_P2B1_TRANSACTION_CONCURRENCY_RECOVERY_CLEANUP")


if __name__=="__main__":
    main()

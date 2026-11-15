"""Issue96 S1 orchestration of accepted interfaces; never fabricates a business bridge."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import time
import traceback
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
OWN = Path(__file__).resolve().parent
PRIVATE = OWN/".private"
DOC = ROOT/"docs/03-engineering/beta-closure/codex3"
if os.environ.get("BETA_CODEX3_PRIVATE_EVIDENCE") == "1":
    DOC = DOC/".private"
OWNER_LABEL = "vrae.beta.codex3"

def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2,default=str)+"\n",encoding="utf-8")

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def cmd(args, **kw):
    p = subprocess.run(args,cwd=ROOT,capture_output=True,timeout=kw.pop("timeout",120),**kw)
    if p.returncode:
        failure=PRIVATE/("command-failure-"+uuid.uuid4().hex)
        failure.with_suffix(".stderr.log").write_bytes(p.stderr)
        failure.with_suffix(".stdout.log").write_bytes(p.stdout)
        raise RuntimeError("COMMAND_FAILED_"+Path(args[0]).name+"_"+failure.name)
    return p.stdout

def wait(predicate, seconds=60):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if predicate():
            return
        time.sleep(.1)
    raise TimeoutError("BETA_COMPONENT_START_DEADLINE")

def snapshot(path):
    names=set(cmd(["git","ls-files","-z"]).decode().split("\0"))-{""}
    names.update(p.relative_to(ROOT).as_posix() for p in OWN.iterdir() if p.suffix in (".py",".mjs"))
    names.add("scripts/beta_internal.py")
    manifest=[]
    with tarfile.open(path,"w:gz",compresslevel=1) as archive:
        for name in sorted(names):
            if name.startswith(("docs/",".git")) or "__pycache__" in name:
                continue
            p=ROOT/name
            if not p.is_file():
                continue
            raw=p.read_bytes()
            item=tarfile.TarInfo(name)
            item.size,item.mode=len(raw),0o644
            archive.addfile(item,io.BytesIO(raw))
            manifest.append({"path":name,"sha256":sha(raw)})
    return manifest

class Run:
    def __init__(self,label,minor,*,b5=False):
        from integration.ra4c_b5a import lab as lab_module
        from integration.ra4c_b5a.support import Runtime
        assert re.fullmatch(r"[a-z0-9-]{3,48}",label)
        self.label=label
        self.folder=PRIVATE/label
        self.folder.mkdir(parents=True,exist_ok=False)
        self.public=DOC/label
        self.public.mkdir(parents=True,exist_ok=False)
        self.b5=b5
        if b5:
            from integration.ra4c_b5p0 import lab as lab_module
            from integration.ra4c_b5p0.support import Runtime
        lab_module.RUNTIME=self.folder/"pg"
        self.r=Runtime("beta-"+uuid.uuid4().hex[:12])
        self.minor=minor
        self.client=None
        self.ssr=None
        self.logs=[]
        self.cases=[]
        self.source_volume="vrae-beta-c3-"+uuid.uuid4().hex[:12]
        self.client_name=self.source_volume+"-runtime"
        self.created_volume=False
        self.started_pg=False
        self.result={"status":"RUNNING","source_sha":cmd(["git","rev-parse","HEAD"]).decode().strip(),
            "parents":cmd(["git","show","-s","--format=%P","HEAD"]).decode().strip().split(),
            "branch":cmd(["git","branch","--show-current"]).decode().strip(),
            "host_python":sys.version.split()[0],"native_python_minor":minor,
            "scope":"TEST_ONLY_NOT_APPROVED_NOT_BETA_READY","human_gold":"0/26"}
        manifest=snapshot(self.folder/"source.tar.gz")
        write(self.public/"source-manifest.json",manifest)
        self.result["executable_source_root"]=sha(json.dumps(manifest,sort_keys=True,separators=(",",":")).encode())

    def case(self,name,fn):
        begin=time.monotonic()
        print(json.dumps({"stage":name,"state":"START"}),flush=True)
        try:
            result=fn()
            self.cases.append({"name":name,"seconds":time.monotonic()-begin,"result":"PASS"})
            return result
        except BaseException as exc:
            self.cases.append({"name":name,"seconds":time.monotonic()-begin,
                "result":"FAIL","error_type":type(exc).__name__})
            (self.folder/("failure-"+name+".log")).write_text(traceback.format_exc(),encoding="utf-8")
            raise
        finally:
            suite=ET.Element("testsuite",name="beta_current_main_component_integration",
                tests=str(len(self.cases)),failures=str(sum(c["result"]!="PASS" for c in self.cases)))
            for c in self.cases:
                item=ET.SubElement(suite,"testcase",classname="codex3.beta.components",
                    name=c["name"],time=str(round(c["seconds"],3)))
                if c["result"]!="PASS":
                    ET.SubElement(item,"failure",message=c["error_type"])
            ET.ElementTree(suite).write(self.public/"component-stages.xml",encoding="utf-8",xml_declaration=True)

    def pipeline(self):
        from .pipeline import run
        self.result["pipeline"]=run(self.folder/"pipeline")

    def start_pg(self):
        from integration.ra4c_b5a import lab as lab_module
        self.r.bootstrap()
        self.started_pg=True
        from integration.ra4b import support as b4
        with lab_module.wire(self.r.lab.state_path):
            b4.migrate()
            b4.seed()
        self.r.lab.state=json.loads(self.r.lab.state_path.read_text())
        self.r.lab.state["port"]=self.r.lab.port
        self.r.lab.save()
        info=json.loads(cmd(["docker","network","inspect",self.r.lab.name+"-net"]))[0]
        assert info["Driver"] == "bridge"
        self.result["pg"]={"server":"PostgreSQL16","internal_network":bool(info["Internal"]), "egress_kernel_denial":False,
            "loopback_only":True,"migration_0001_0004":"UNCHANGED_ACCEPTED",
            "private_port":self.r.lab.port}
        write(self.folder/"ownership.json",{"client":self.client_name,"volume":self.source_volume,
            "pg":self.r.lab.name,"label":OWNER_LABEL,"value":self.label})
        self.profile=self.folder/"reviewer-profile.json"
        write(self.profile,self.r.profile())
        if self.b5:
            self.bridge=self.folder/"b5-bridge.private.json"
            write(self.bridge,self.r.bridge_profile())
            from .native_observation import ObservedIssuer
            self.r.issuer=ObservedIssuer(self.r.issuer,self.folder)

    def start_native(self):
        image="vrae-ra4b-p1:"+self.minor.replace(".","")
        image_id=cmd(["docker","image","inspect","--format","{{.Id}}",image]).decode().strip()
        self.result["runtime_image_id"]=image_id
        cmd(["docker","volume","create","--label",OWNER_LABEL+"="+self.label,self.source_volume])
        self.created_volume=True
        cmd(["docker","run","--rm","-i","--network","none","--read-only","--cap-drop","ALL",
            "--mount","type=volume,src="+self.source_volume+",dst=/source",image_id,
            "python","-c","import sys,tarfile;tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz').extractall('/source',filter='data')"],
            input=(self.folder/"source.tar.gz").read_bytes())
        out=self.folder/"native"
        out.mkdir()
        log=(self.folder/"native-supervisor.log").open("wb")
        self.logs.append(log)
        args=["docker","run","--rm","-i","--name",self.client_name,
            "--label",OWNER_LABEL+"="+self.label,
            "--network","container:"+self.r.lab.name,
            "--read-only","--cap-drop","ALL","--cap-add","SETUID","--cap-add","SETGID","--cap-add","CHOWN",
            "--security-opt","no-new-privileges","--memory","768m","--pids-limit","128",
            "--tmpfs","/tmp:rw,nosuid,nodev,size=256m",
            "--mount","type=volume,src="+self.source_volume+",dst=/work,readonly",
            "--mount","type=bind,src="+str(out.resolve())+",dst=/evidence",
            image_id,"python","-m","integration.beta_review.codex3.native"]
        self.client=subprocess.Popen(args,cwd=ROOT,stdin=subprocess.PIPE,stdout=log,stderr=log)
        self.client.stdin.write(json.dumps(self.r.lab.state).encode())
        self.client.stdin.close()
        def ready():
            if self.client.poll() is not None:
                raise RuntimeError("NATIVE_API_WORKER_RED")
            return (out/"ready.json").exists()
        wait(ready,90)
        value=json.loads((out/"native-result.json").read_text())
        assert value["native_python"].startswith(self.minor+".")
        self.result["native_python"]=value["native_python"]
        write(self.folder/"native-linkage.private.json",value)
        self.result["api_worker"]={"records":[{"case":r["case"],"request_sha256":sha(r["receipt"]["request_id"].encode()),
            "run_sha256":sha(r["receipt"]["run_id"].encode()),"job_sha256":sha(r["receipt"]["job_id"].encode()),
            "origin_epoch":r["origin_epoch"],"job_state":r["job_state"],
            "commit_observed_before_worker":r["commit_observed_before_worker"],
            "worker_uid":r["worker_uid"],"app_uid":r["app_uid"],
            "generated_report_by_worker":False,"consumed_audit":r["consumed_audit"],
            "consumed_outbox":r["consumed_outbox"]} for r in value["records"]],
            "unauthorized_http":value["unauthorized_http"],
            "cross_tenant_denied":value["cross_tenant_denied"],
            "worker_raw_select_denied":value["worker_raw_select_denied"]}

    def start_ssr(self):
        self.ready=self.folder/"ssr-ready.json"
        self.ready.unlink(missing_ok=True)
        log=(self.folder/"ssr.log").open("ab")
        self.logs.append(log)
        deps=self.folder/"b5-deps.ready.json"
        deps.unlink(missing_ok=True)
        extra=(["--bridge",str(self.bridge),"--audit",str(self.folder/"b5-audit.private.jsonl"),"--deps-ready",str(deps)] if self.b5 else [])
        self.ssr=subprocess.Popen([sys.executable,"-B","-m","integration.beta_review.codex3.ssr",
            "--profile",str(self.profile),"--ready",str(self.ready),*extra],
            cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,
            env={**{k:v for k,v in os.environ.items() if k.upper() in
                {"PATH","SYSTEMROOT","WINDIR","TEMP","TMP","COMSPEC"}},
                "PYTHONUTF8":"1","PYTHONDONTWRITEBYTECODE":"1"})
        if self.b5:
            from .native_observation import launched
            launched(self)
        def ready():
            if self.ssr.poll() is not None:
                raise RuntimeError("SSR_START_FAILED")
            return self.ready.exists()
        if self.b5:
            def dependencies_ready():
                if self.ssr.poll() is not None:
                    raise RuntimeError("B5_DEPENDENCY_BOOT_FAILED")
                return deps.exists()
            wait(dependencies_ready,60)
            assert json.loads(deps.read_text())=={"driver_ready":True}
        wait(ready,30)
        self.r.origin=json.loads(self.ready.read_text())["origin"]
        self.result["ssr_origin"]=self.r.origin
        write(self.folder/"control.json",{"origin":self.r.origin,"pid":os.getpid(),
            "profile":str(self.profile),"mode":"TEST_ONLY_NOT_APPROVED"})
        write(self.folder/"signer.private.json",{k:base64_key(v) for k,v in self.r.issuer.keys.items()})

    def restart_ssr(self):
        from .native_observation import stopped
        assert stopped(self,"documented_restart") is None,"SSR_ALREADY_EXITED_NO_RESTART"
        self.start_ssr()

    def signed_reads(self):
        from integration.ra4c_b5a.support import Client
        from integration.ra4c_b5a.cases import snapshot as db_snapshot
        before=db_snapshot(self.r)
        records=[]
        self.browser_sessions=[]
        for case in ("404","200"):
            client=Client(self.r.origin)
            response,token,_=client.login(self.r.issuer,"task-"+case)
            assert response[0]==303
            for endpoint in ("review","target","proposal","evidence/0","evidence/capture"):
                path=self.r.review_path(case,endpoint)
                code,raw,_=client.request("GET",path)
                assert code==200 and "Reviewer".encode() in raw
                assert b"NOT_APPROVED" in raw or b"NOT APPROVED" in raw
                assert token.encode() not in raw
                (self.folder/(case+"-"+endpoint.replace("/","-")+".html")).write_bytes(raw)
            version_path=self.r.review_path(case).replace("version=1","version=999")
            old_status=client.request("GET",version_path)[0]
            assert old_status == 409
            other="200" if case=="404" else "404"
            assert client.request("GET",self.r.review_path(other))[0] == 403
            # There is no accepted B6 route: record actual refusal, not B6 EXIT.
            denied=client.request("POST","/b5a/share",b"{}",{"Content-Type":"application/json"})[0]
            assert denied == 501
            records.append({"case":case,"signed_reviewer_pg_reads":5,
                "old_version":old_status,"cross_task":403,"share_route_response":denied,
                "persisted_review_intent":"BLOCKED_PR89_NOT_IN_ACCEPTED_MAIN",
                "task_id":"task-"+case,"source":"ACCEPTED_SEALED_REVIEW_GRAPH_NOT_NEW_WORKER_RESULT"})
            self.browser_sessions.append({"case":case,"origin":self.r.origin,
                "cookies":client.cookies,"path":self.r.review_path(case)})
        assert db_snapshot(self.r)==before
        self.result["reviewer"]=records
        write(self.folder/"browser-sessions.private.json",self.browser_sessions)
        self.result["reviewer_business_tables_unchanged"]=True

    def browser(self):
        # Existing session lifetime is deliberately unchanged. Each browser run
        # gets a fresh genuine signed login after the preceding slow read replay.
        from integration.ra4c_b5a.support import Client
        fresh=[]
        for case in ("404","200"):
            client=Client(self.r.origin)
            response,_,_=client.login(self.r.issuer,"task-"+case)
            assert response[0]==303
            fresh.append({"case":case,"origin":self.r.origin,"cookies":client.cookies,
                "path":self.r.review_path(case)})
        write(self.folder/"browser-sessions.private.json",fresh)
        result=cmd(["node",str(OWN/"browser.mjs"),str(self.folder/"browser-sessions.private.json"),
            str(self.folder/"browser")],timeout=120)
        value=json.loads(result)
        assert value["status"]=="PASS" and value["widths"]==[1280,375,320]
        self.result["browser"]=value

    def cleanup(self):
        evidence=[]
        errors=[]
        def attempt(name,fn):
            try:
                fn()
                evidence.append({"resource":name,"absent_or_port_closed":True})
            except BaseException as exc:
                errors.append(type(exc).__name__+"_"+name)
        def native_stop():
            if not self.client:
                return
            write(self.folder/"native/stop.json",{"stop":True})
            try:
                self.client.wait(timeout=15)
            except subprocess.TimeoutExpired:
                owned=cmd(["docker","inspect","--format",'{{index .Config.Labels "vrae.beta.codex3"}}',
                    self.client_name]).decode().strip()
                assert owned==self.label
                cmd(["docker","rm","-f",self.client_name])
                self.client.wait(timeout=10)
            assert subprocess.run(["docker","inspect",self.client_name],
                capture_output=True,timeout=20).returncode!=0
        def ssr_stop():
            if not self.ssr:
                return
            if self.b5:
                from .native_observation import stopped
                stopped(self,"owned_cleanup")
            else:
                self.ssr.terminate()
                self.ssr.wait(timeout=15)
            import socket
            from urllib.parse import urlsplit
            def closed():
                with socket.socket() as sock:
                    sock.settimeout(1)
                    return sock.connect_ex(("127.0.0.1",urlsplit(self.r.origin).port))!=0
            wait(closed,5)
        def volume_stop():
            if not self.created_volume:
                return
            owned=cmd(["docker","volume","inspect","--format",'{{index .Labels "vrae.beta.codex3"}}',
                self.source_volume]).decode().strip()
            assert owned==self.label
            cmd(["docker","volume","rm",self.source_volume])
            assert subprocess.run(["docker","volume","inspect",self.source_volume],capture_output=True).returncode!=0
        attempt("native_client",native_stop)
        attempt("original_ssr",ssr_stop)
        attempt("pg_container_network_volume",self.r.lab.stop)
        attempt("source_volume",volume_stop)
        for stream in self.logs:
            stream.close()
        self.result["cleanup"]=evidence
        self.result["cleanup_errors"]=errors
        assert not errors,"OWNED_CLEANUP_FAILED"
        
    def publish(self):
        native_error=None
        if self.b5 and self.ssr:
            from .native_observation import assert_no_native_crash
            try:
                assert_no_native_crash(self)
            except Exception as exc:
                native_error=exc
                self.result["status"]="NATIVE_RED_PRESERVED"
                self.result["native_observation_error"]=type(exc).__name__
        self.result["dependencies"]=[
            {"stage":"S1/S2","interface":"B4 Worker -> live Collector/RuleExecution/report persistence",
             "owner":"Codex1/Owner","state":"BLOCKED_NO_ACCEPTED_INTERFACE",
             "minimal_change":"Versioned low-role processing/status bridge; no admin runtime or raw table grants."},
            {"stage":"S1/S2","interface":"DISC-01/02 finding -> guarded fact -> report",
             "owner":"Codex1 Issue94","state":"ACCEPTED_DISC_ADAPTER_LIVE_OFFLINE_CONNECTED"},
            {"stage":"S2","interface":"B4 request/run/job -> assigned Reviewer task",
             "owner":"Codex1 B4-P2","state":"BLOCKED_NOT_MERGED"},
            {"stage":"S2","interface":"Signed SSR -> B3 durable per-claim TEST_ONLY intent",
             "owner":"Codex2 PR89","state":"ACCEPTED_B5P0_SEALED_LANE_AVAILABLE_B4_RESULT_BINDING_BLOCKED"},
            {"stage":"S3","interface":"Private exact-version B6 read/revoke/refusal",
             "owner":"Codex2 PR92","state":"ACCEPTED_B6_P0_PRIVATE_DENY_ONLY"},
            {"stage":"S4","interface":"B7 old-first deterministic provenance / protected permissions",
             "owner":"Owner","state":"DEFERRED_BY_OWNER6895932668_MAX3_HISTORY_PRESERVED"},
            {"stage":"S5","interface":"Single accepted-SHA full B1-B7 EXIT",
             "owner":"Owner","state":"NOT_READY_2_OF_7"}]
        self.result["component_stages_sha256"]=sha((self.public/"component-stages.xml").read_bytes())
        write(self.public/"result.json",self.result)
        secrets=[self.r.lab.state["admin_password"],*self.r.lab.state["runtime_passwords"].values()]
        for p in self.public.rglob("*"):
            if p.is_file():
                assert not any(s.encode() in p.read_bytes() for s in secrets if len(s)>12)
        write(self.public/"publication.json",{"actual_credential_matches":0,
            "private_raw_outputs_excluded":True,"source_sha":self.result["source_sha"]})
        print(json.dumps({"run":self.label,"status":self.result["status"],
            "component_assertion_stages":len(self.cases),"component_stages_sha256":self.result["component_stages_sha256"]}),flush=True)
        if native_error is not None:
            raise native_error

def base64_key(key):
    import base64
    return base64.b64encode(key.private_bytes_raw()).decode()

def restore_issuer(path):
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from tests.identity.issuer import Issuer
    issuer=Issuer()
    issuer.keys={k:Ed25519PrivateKey.from_private_bytes(base64.b64decode(v))
        for k,v in json.loads(path.read_text()).items()}
    return issuer

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=("verify","start","stop","status","session","open","trace","restart-api"))
    parser.add_argument("--run",required=True)
    parser.add_argument("--minor",choices=("3.11","3.13"),default="3.11")
    parser.add_argument("--task",choices=("404","200"),default="404")
    parser.add_argument("--phase",choices=("s1","s2"),default="s1")
    parser.add_argument("--request")
    args=parser.parse_args()
    assert re.fullmatch(r"[a-z0-9-]{3,48}",args.run)
    folder=PRIVATE/args.run
    if args.action in ("trace","restart-api"):
        from .s2_runtime import trace_case,trace_request,restart_api
        if args.action=="restart-api":
            print(json.dumps(restart_api(folder),sort_keys=True))
        else:
            value=trace_request(folder,args.request) if args.request else trace_case(folder,args.task)
            print(json.dumps(value.get("summary",value),sort_keys=True))
        return
    if args.action in ("stop","status","session","open"):
        control=json.loads((folder/"control.json").read_text())
        if args.action=="stop":
            write(folder/"stop.json",{"stop":True})
            print("STOP_REQUESTED_OWN_RUN_ONLY")
        elif args.action=="status":
            print(json.dumps({"origin":control["origin"],"url":control["origin"]+"/b5a/login","run":args.run,"mode":control["mode"]}))
        else:
            from integration.ra4c_b5a.support import Client
            client=Client(control["origin"])
            response,_,_=client.login(restore_issuer(folder/"signer.private.json"),"task-"+args.task)
            assert response[0]==303
            from urllib.parse import urlencode
            profile=json.loads((folder/"reviewer-profile.json").read_text())
            draft=profile["tasks"][args.task]["report_pins"]["expected_draft_ref"]
            path="/b5a/tasks/task-"+args.task+"/review?"+urlencode({"version":1,"draft":draft})
            session_path=folder/"operator-session.private.json"
            write(session_path,[{"case":args.task,"origin":control["origin"],"cookies":client.cookies,"path":path}])
            if args.action=="open":
                subprocess.run(["node",str(OWN/"browser.mjs"),str(session_path),str(folder/"operator-browser"),
                    "--interactive"],cwd=ROOT,check=True)

            print("SIGNED_TEST_SESSION_WRITTEN_PRIVATE_NO_HUMAN_APPROVAL")
        return
    if args.action=="verify":
        raw_folder=PRIVATE/("pytest-"+args.run)
        raw_folder.mkdir(parents=True,exist_ok=False)
        env={**os.environ,"BETA_CODEX3_RUN":args.run,"BETA_CODEX3_MINOR":args.minor,
             "PYTHONDONTWRITEBYTECODE":"1","PYTHONUTF8":"1"}
        with (raw_folder/"pytest.log").open("wb") as stream:
            result=subprocess.run([sys.executable,"-B","-m","pytest","-x","-q","-p","no:cacheprovider",
                "--confcutdir=integration/beta_review/codex3","--import-mode=importlib",
                *(["integration/beta_review/codex3/test_s2_consumer.py","integration/beta_review/codex3/test_accepted_chain.py"] if args.phase=="s2" else ["integration/beta_review/codex3/test_current_main.py"]),
                "--basetemp="+str(raw_folder/"temp"),"--junitxml="+str(raw_folder/"raw-junit.xml")],
                cwd=ROOT,env=env,stdout=stream,stderr=stream)
        raw=(raw_folder/"raw-junit.xml").read_bytes()
        original=ET.fromstring(raw)
        safe=ET.Element("testsuites")
        for suite in original.findall("testsuite"):
            target=ET.SubElement(safe,"testsuite",{k:v for k,v in suite.attrib.items() if k in ("name","tests","failures","errors","skipped","time")})
            for case in suite.findall("testcase"):
                item=ET.SubElement(target,"testcase",{k:v for k,v in case.attrib.items() if k in ("name","classname","time")})
                for kind in ("failure","error","skipped"):
                    if case.find(kind) is not None:
                        ET.SubElement(item,kind,message="NATIVE_RESULT_PRESERVED_PRIVATELY")
        (DOC/args.run).mkdir(parents=True,exist_ok=True)
        ET.ElementTree(safe).write(DOC/args.run/"junit.xml",encoding="utf-8",xml_declaration=True)
        import zlib
        receipt={"returncode":result.returncode,"python":sys.version.split()[0],
            "native_junit_sha256":sha(raw),"native_junit_crc32":format(zlib.crc32(raw),"08x"),
            "native_tests":len(original.findall(".//testcase")),
            "failures":len(original.findall(".//failure")),"errors":len(original.findall(".//error")),
            "skipped":len(original.findall(".//skipped")),
            "public_junit_sha256":sha((DOC/args.run/"junit.xml").read_bytes()),
            "source_sha":cmd(["git","rev-parse","HEAD"]).decode().strip(),
            "chain":"BLOCKED_NOT_FULL_BETA_PASS"}
        write(DOC/args.run/"native-pytest-receipt.json",receipt)
        print(json.dumps(receipt),flush=True)
        raise SystemExit(result.returncode)
    launch=PRIVATE/"local-launches"/args.run
    stop=launch/"stop.json"
    if args.action=="start" and stop.is_file():
        write(launch/"cancelled-before-start.json",{"cancelled_before_run":True,"resources_started":False})
        return
    run=Run(args.run,args.minor,b5=args.phase=="s2")
    class StartupCancelled(Exception):
        pass
    def start_case(name,operation):
        if args.action=="start" and (stop.is_file() or (folder/"stop.json").is_file()):
            raise StartupCancelled()
        return run.case(name,operation)
    try:
        start_case("live_offline_source_policy_six_rules_guard_report",run.pipeline)
        start_case("owned_pg16_accepted_migrations_loopback_network",run.start_pg)
        start_case("real_http202_commit_low_uid_worker_done_security",run.start_native)
        start_case("original_reviewer_ssr_start",run.start_ssr)
        if args.phase=="s1":
            start_case("signed_original_reads_version_tenant_share_denial",run.signed_reads)
            start_case("chromium_desktop_mobile_readonly",run.browser)
        else:
            from .s2_runtime import trace_case
            run.result["s2_task_traces"]=[trace_case(run.folder,c)["summary"] for c in ("404","200")]
            assert all(t["generated_report"] is None for t in run.result["s2_task_traces"])

        run.result["status"]="COMPONENTS_VERIFIED_CHAIN_BLOCKED"
        write(folder/"started.json",{"origin":run.r.origin,"source_sha":run.result["source_sha"]})
        if args.action=="start":
            print(json.dumps({"run":args.run,"origin":run.r.origin,"url":run.r.origin+"/b5a/login","mode":"TEST_ONLY_NOT_APPROVED",
                "chain":"BLOCKED","auto_stop_seconds":1800}),flush=True)
            deadline=time.monotonic()+1800
            while time.monotonic()<deadline and not (folder/"stop.json").exists() and not stop.exists():
                if run.client.poll() is not None or run.ssr.poll() is not None:
                    raise RuntimeError("COMPONENT_EXITED")
                time.sleep(.25)
    except StartupCancelled:
        run.result["status"]="CANCELLED_DURING_STARTUP"
    except BaseException:
        run.result["status"]="STOP_NATIVE_RED_PRESERVED"
        raise
    finally:
        try:
            run.case("owned_cleanup",run.cleanup)
        finally:
            run.publish()

if __name__=="__main__":
    main()

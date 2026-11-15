"""Actual original-API reads under UID10001, bound to one owned running fixture."""
import json
import subprocess
import time
from uuid import UUID
from .task_trace import TaskObservation,TraceDenied
from .runner import ROOT,OWNER_LABEL,write

def owned_client(folder):
    own=json.loads((folder/"ownership.json").read_text(encoding="utf-8"))
    label=folder.name
    name=own["client"]
    if not name.startswith("vrae-beta-c3-") or not name.endswith("-runtime"):
        raise TraceDenied("OWNED_CLIENT_REQUIRED")
    result=subprocess.run(["docker","inspect","--format",'{{index .Config.Labels "vrae.beta.codex3"}}',name],
        capture_output=True,timeout=20)
    if result.returncode or result.stdout.decode().strip()!=label or own["label"]!=OWNER_LABEL:
        raise TraceDenied("OWNED_CLIENT_REQUIRED")
    return name

def trace_request(folder,request_id):
    request_id=str(UUID(request_id))
    client=owned_client(folder)
    result=subprocess.run(["docker","exec","--user","10001:10001","--env","VRAE_RA4B_TEST_ONLY=1",
        client,"python","-m","integration.beta_review.codex3.task_trace","--request",request_id],
        cwd=ROOT,capture_output=True,timeout=15)
    if result.returncode not in (0,2) or len(result.stdout)>32768:
        (folder/"trace-error.private.log").write_bytes(result.stderr)
        raise TraceDenied("ORIGINAL_API_TRACE_FAILED")
    value=json.loads(result.stdout)
    if result.returncode==2 and value.get("decision")!="DENIED":
        raise TraceDenied("INVALID_TRACE_DENIAL")
    if result.returncode==0:
        observation=TaskObservation(**value["observation"])
        if observation.request_id!=request_id or observation.summary()!=value["summary"]:
            raise TraceDenied("TRACE_TRANSPORT_CORRELATION")
    write(folder/("trace-"+request_id+".private.json"),value)
    return value

def trace_case(folder,case):
    state=json.loads((folder/"native/native-result.json").read_text())
    record=next(r for r in state["records"] if r["case"]==case)
    return trace_request(folder,record["receipt"]["request_id"])

def restart_api(folder):
    owned_client(folder)
    out=folder/"native"
    request=out/"api-restart.request.json"
    receipt=out/"api-restart.receipt.json"
    if request.exists() or receipt.exists():
        raise TraceDenied("RESTART_ALREADY_REQUESTED")
    pending=request.with_suffix(".tmp")
    write(pending,{"action":"RESTART_OWN_ORIGINAL_API_ONCE"})
    pending.replace(request)
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        if receipt.exists():
            value=json.loads(receipt.read_text())
            if value!={"original_api_restarted":True,"app_uid":10001,"new_admissions":0}:
                raise TraceDenied("RESTART_RECEIPT_INVALID")
            return value
        time.sleep(.1)
    raise TraceDenied("RESTART_RECEIPT_DEADLINE")

"""Consume accepted B5P0 in the existing SSR; no Worker/report association."""
from html import unescape
from uuid import UUID
import json
import os
import re
import subprocess
import time
from .runner import ROOT,write,sha

LANE="ACCEPTED_SEALED_B5P0_TEST_ONLY_NOT_WORKER_OUTPUT"

def receipt_digest(body):
    found=re.search(rb'data-key="receipt-sha">([0-9a-f]{64})<',body)
    assert found and b"TEST_ONLY_REVIEW_INTENT" in body and b"NOT APPROVED" in body
    assert b"idempotency_key" not in body and b"witness" not in body.lower()
    return found[1].decode()

def receipt_metadata(body):
    match=re.search(r"<pre>(.*?)</pre>",body.decode("utf-8"),re.S)
    assert match
    document=json.loads(unescape(match[1]))
    assert document["report_version"]==1 and document["durable"] is True
    assert document["effective_approval"] is False and document["external_visibility"] is False
    assert document["native_decision"] is None and document["person_id"] is None and document["share_grant"] is None
    for field in ("intent_id","event_id","report_id","ref_id","source_run_id"):
        assert str(UUID(document[field]))==document[field]
    return document

def browser_save(run):
    out=run.folder/"b5-browser"
    out.mkdir(exist_ok=False)
    env={**os.environ,"B5P0_CHROMIUM":"C:/Program Files/Google/Chrome/Application/chrome.exe"}
    with (run.folder/"b5-browser.stderr.private.log").open("wb") as errors:
        node=subprocess.Popen(["node","integration/ra4c_b5p0/browser.mjs"],cwd=ROOT,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=errors,text=True,encoding="utf-8",env=env)
        try:
            node.stdin.write(json.dumps({"type":"init","base":run.r.origin+"/b5a/",
                "output":str(out),"private":str(run.folder)})+"\n")
            node.stdin.flush()
            done=None
            for line in node.stdout:
                message=json.loads(line)
                if message.get("kind")=="done":
                    done=message
                    break
                assert message["kind"]=="sign"
                now=int(time.time())
                token=run.r.issuer.token({"iat":now,"nbf":now,"exp":now+90,"nonce":message["nonce"]})
                run.r.secrets.append(token)
                node.stdin.write(json.dumps({"id":message["id"],"result":token})+"\n")
                node.stdin.flush()
            assert node.wait(timeout=30)==0 and done and done["pass"],"ACCEPTED_B5_BROWSER_RED"
        finally:
            if node.poll() is None:
                node.terminate()
                node.wait(timeout=15)
    cleanup=json.loads((out/"browser-process-cleanup.json").read_text(encoding="utf-8"))
    assert cleanup["exit_observed"]
    report=json.loads((out/"browser.json").read_text(encoding="utf-8"))
    assert report["status"]=="ACTUAL_B5P0_SIGNED_PG_INTENT_SSR_PASS"
    assert len(report["shots"])==12 and all(r["pass"] for r in report["records"])
    summary={"lane":LANE,"assertions":done["assertions"],"screenshots":[
        {"file":s["file"],"sha256":s["sha256"]} for s in report["shots"]],
        "widths":[1280,375,320],"chromium_exit_observed":True}
    write(run.public/"b5-browser.json",summary)
    run.result["b5_browser"]=summary
    return summary

def read_receipt(run,case):
    from integration.ra4c_b5a.support import Client
    client=Client(run.r.origin)
    assert client.login(run.r.issuer,"task-"+case)[0][0]==303
    path="/b5a/tasks/task-"+case+"/rehearsal"
    code,body,_=client.request("GET",path+"/receipt")
    assert code==200
    digest=receipt_digest(body)
    (run.folder/("b5-receipt-"+case+".private.html")).write_bytes(body)
    return client,path,digest,sha(body)

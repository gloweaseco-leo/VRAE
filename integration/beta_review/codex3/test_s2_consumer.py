"""Real PG/API consumption and refusal of invented result provenance on accepted main."""
import json
import os
from dataclasses import asdict
from uuid import UUID
import pytest
from .runner import Run
from .s2_runtime import trace_case,trace_request,restart_api
from .task_trace import TaskObservation,TraceDenied,RESULT_BLOCK,require_generated_result

@pytest.fixture(scope="module")
def beta(request):
    r=Run(os.environ["BETA_CODEX3_RUN"],os.environ["BETA_CODEX3_MINOR"],b5=True)
    try:
        r.case("s2_owned_pg16_original_interfaces",r.start_pg)
        r.case("s2_real_app_commit_worker",r.start_native)
        r.case("s2_independent_live_diagnostic_candidate",r.pipeline)
        r.case("s2_accepted_b5p0_same_ssr",r.start_ssr)
        yield r
    finally:
        if request.session.testsfailed and r.started_pg:
            # Out-of-band own fixture diagnostics only; never result authority.
            from .runner import write,sha
            try:
                with r.r.lab.connect() as observer:
                    rows=observer.execute("SELECT pid,state,wait_event_type,wait_event,usename,query FROM pg_stat_activity WHERE datname=%s",(r.r.lab.dbname,)).fetchall()
                write(r.folder/"failed-own-backends.private.json",[{"pid":v[0],"state":v[1],"wait_type":v[2],"wait":v[3],"role":v[4],"query_sha256":sha(v[5].encode())} for v in rows])
            except Exception as diagnostic_error:
                write(r.folder/"diagnostic-error.private.json",{"type":type(diagnostic_error).__name__})
        try:
            r.case("s2_owned_cleanup",r.cleanup)
        finally:
            clean=(len(r.cases)==5 and all(c["result"]=="PASS" for c in r.cases))
            r.result["status"]=("S2_NATIVE_RED_PRESERVED" if request.session.testsfailed or not clean else "S2_READ_CONSUMER_READY_PROCESSING_RESULT_BLOCKED")
            r.publish()

@pytest.mark.parametrize("case",["404","200"])
def test_actual_low_role_trace_preserves_committed_ids_and_blocks_result(beta,case):
    value=trace_case(beta.folder,case)
    state=json.loads((beta.folder/"native/native-result.json").read_text())
    original=next(r for r in state["records"] if r["case"]==case)
    obs=TaskObservation(**value["observation"])
    assert (obs.request_id,obs.run_id,obs.job_id)==tuple(original["receipt"][k] for k in ("request_id","run_id","job_id"))
    assert obs.job_state=="TEST_ONLY_DONE" and obs.source_ref=="accepted-"+case
    assert value["summary"]["processing_result"]==RESULT_BLOCK
    assert value["summary"]["generated_report"] is None
    assert value["summary"]["origin_epoch"] is None
    beta.result.setdefault("s2_actual_trace",[]).append(value["summary"])

@pytest.mark.parametrize("case",["404","200"])
def test_presealed_metadata_does_not_prove_generated_job_result(beta,case):
    value=trace_case(beta.folder,case)
    obs=TaskObservation(**value["observation"])
    candidate={"source_ref":obs.source_ref,"report_version":obs.report_version_metadata,
        "job_id":obs.job_id,"status":"TEST_ONLY_DONE","generated_report_by_worker":True}
    with pytest.raises(TraceDenied,match=RESULT_BLOCK):
        require_generated_result(obs,candidate)

@pytest.mark.parametrize("case",["404","200"])
def test_real_separate_pipeline_output_is_not_associated_by_copied_job_id(beta,case):
    obs=TaskObservation(**trace_case(beta.folder,case)["observation"])
    actual=next(r for r in beta.result["pipeline"] if r["case"]==case)
    assert actual["run_id"]!=obs.run_id
    assert actual["pack_ref"] and actual["execution_ref"] and actual["package_ref"] and actual["draft_ref"]
    candidate={**actual,"job_id":obs.job_id,"claimed_tenant":"tenant-test","source_ref":obs.source_ref}
    with pytest.raises(TraceDenied,match=RESULT_BLOCK):
        require_generated_result(obs,candidate)

def test_unknown_request_http_denial_has_no_status_or_report(beta):
    value=trace_request(beta.folder,"00000000-0000-4000-8000-000000000001")
    assert value=={"schema":"C3_S2_READ_TRACE_1","decision":"DENIED","http_status":404,"generated_report":None}

def test_caller_response_correlation_tamper_rejected(beta):
    obs=TaskObservation(**trace_case(beta.folder,"404")["observation"])
    value=asdict(obs)
    # This is a consumer-envelope negative, not a mutation of PG rows or policy.
    with pytest.raises(TraceDenied,match="STATUS_REQUEST_CORRELATION"):
        TaskObservation.from_status({"request_id":str(UUID(int=1)),**{"run_id":value["run_id"]}},
            obs.request_id,{"sources":{}})

def test_original_api_restart_reloads_exact_durable_status_without_new_admission(beta):
    before={case:trace_case(beta.folder,case) for case in ("404","200")}
    receipt=restart_api(beta.folder)
    after={case:trace_case(beta.folder,case) for case in ("404","200")}
    assert receipt["original_api_restarted"] and receipt["new_admissions"]==0
    assert before==after
    beta.result["s2_original_api_restart"]={"receipt":receipt,"exact_durable_status":True,
        "generated_result":"BLOCKED","new_admissions":0}

def test_accepted_b5p0_browser_saves_real_signed_intents(beta):
    from .b5_consumer import browser_save
    before=beta.r.roots()
    assert all(v==0 for v in beta.r.data().values())
    browser_save(beta)
    counts=beta.r.data()
    assert counts['intents']==counts['audit']==counts['outbox']==2
    assert counts['claims']==9 and beta.r.roots()==before
    beta.result['b5_counts']=counts
    beta.b5_roots=before
    beta.b5_receipts={}

@pytest.mark.parametrize('case',['404','200'])
def test_b5p0_actual_originals_and_version_bound_receipt(beta,case):
    from .b5_consumer import read_receipt,receipt_metadata,LANE
    from .runner import sha
    client,path,digest,body_sha=read_receipt(beta,case)
    other='200' if case=='404' else '404'
    assert client.request('GET','/b5a/tasks/task-'+other+'/rehearsal/receipt')[0]==403
    from urllib.parse import urlencode
    profile=json.loads(beta.profile.read_text(encoding='utf-8'))
    draft=profile['tasks'][case]['report_pins']['expected_draft_ref']
    assert client.request('GET','/b5a/tasks/task-'+case+'/review?'+urlencode({'version':999,'draft':draft}))[0]==409
    document=receipt_metadata((beta.folder/("b5-receipt-"+case+".private.html")).read_bytes())
    location=beta.r.bindings["task-"+case].location
    assert document["report_id"]==location.report and document["source_run_id"]==location.source_run
    assert document["ref_id"]==location.ref_id
    originals=beta.r.original_facts(case)
    beta.b5_receipts[case]={'lane':LANE,'receipt_sha256':digest,'page_sha256':body_sha,
        'originals':originals,'identity_sha256':{k:sha(document[k].encode()) for k in ('intent_id','event_id','report_id','ref_id','source_run_id')},'report_version':1,'worker_result_binding':'BLOCKED','approval':'NOT_APPROVED'}
    beta.result['b5_receipts']=beta.b5_receipts
    assert beta.r.data()==beta.result['b5_counts']

def test_b5p0_real_ssr_process_restart_reauthenticates_and_rereads_same_receipts(beta):
    from integration.ra4c_b5a.support import Client
    from .b5_consumer import read_receipt
    stale,path,_,_=read_receipt(beta,'404')
    beta.restart_ssr()
    old=Client(beta.r.origin)
    old.cookies=dict(stale.cookies)
    assert old.request('GET',path+'/receipt')[0]==403
    for case in ('404','200'):
        _,_,digest,body_sha=read_receipt(beta,case)
        assert digest==beta.b5_receipts[case]['receipt_sha256']
        assert body_sha==beta.b5_receipts[case]['page_sha256']
    assert beta.r.data()==beta.result['b5_counts']
    assert beta.r.roots()==beta.b5_roots
    beta.result['b5_process_restart']={'old_cookie_denied':403,'fresh_signed_receipts_identical':True,
        'original_journal_and_b3_pg_retained':True,'new_intents':0,'worker_binding':'BLOCKED'}

def test_b5p0_current_provisioning_revocation_denies_saved_receipt(beta):
    from .b5_consumer import read_receipt
    client,path,_,_=read_receipt(beta,'404')
    # Accepted loader's real private-provisioning invalidation, no DB/ACL edits.
    beta.bridge.write_bytes(beta.bridge.read_bytes()+b'\n')
    status,body,_=client.request('GET',path+'/receipt')
    assert status==403 and b'data-key="receipt-sha"' not in body
    assert beta.r.data()==beta.result['b5_counts']
    assert beta.r.roots()==beta.b5_roots
    beta.result['b5_current_revocation']={'http_status':403,'receipt_leaked':False,'new_intents':0}

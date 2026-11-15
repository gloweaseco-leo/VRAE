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
    r=Run(os.environ["BETA_CODEX3_RUN"],os.environ["BETA_CODEX3_MINOR"])
    try:
        r.case("s2_owned_pg16_original_interfaces",r.start_pg)
        r.case("s2_real_app_commit_worker",r.start_native)
        r.case("s2_independent_live_diagnostic_candidate",r.pipeline)
        yield r
    finally:
        try:
            r.case("s2_owned_cleanup",r.cleanup)
        finally:
            clean=(len(r.cases)==4 and all(c["result"]=="PASS" for c in r.cases))
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

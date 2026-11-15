"""Read-only consumer of accepted B4 status; never treats a source JOIN as output."""
import argparse
from dataclasses import dataclass
import hashlib
import http.client
import json
from uuid import UUID
from vrae.application.ra4b import store

VERSION = "C3_S2_READ_TRACE_1"
RESULT_BLOCK = "BLOCKED_NO_ACCEPTED_LEASE_BOUND_RESULT_PORT"

class TraceDenied(ValueError):
    pass

def canonical_id(value):
    try:
        if type(value) is not str or str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise TraceDenied("REQUEST_ID_INVALID") from None
    return value

@dataclass(frozen=True)
class TaskObservation:
    request_id: str
    run_id: str
    job_id: str
    source_ref: str
    configured_reference_sha256: str
    request_state: str
    job_state: str
    report_version_metadata: int
    provenance: str = "ACCEPTED_STATUS_AND_CONFIGURATION_INPUT_REFERENCE_ONLY"

    @classmethod
    def from_status(cls, status, request_id, config):
        canonical_id(request_id)
        if not isinstance(status, dict) or status.get("request_id") != request_id:
            raise TraceDenied("STATUS_REQUEST_CORRELATION")
        if status.get("authority") != store.AUTHORITY or status.get("native_approval") is not None or status.get("share_grant") is not None:
            raise TraceDenied("STATUS_AUTHORITY")
        run_id,job_id = canonical_id(status.get("run_id")),canonical_id(status.get("job_id"))
        ref=status.get("source_ref")
        if not isinstance(ref,str) or ref not in config["sources"]:
            raise TraceDenied("SOURCE_NOT_CONFIGURED")
        binding=config["sources"][ref]
        version=status.get("report_version")
        if type(version) is not int or version<1:
            raise TraceDenied("SOURCE_VERSION_METADATA_INVALID")
        if not all(type(status.get(k)) is str and status[k] for k in ("status","job_state")):
            raise TraceDenied("STATUS_STATE_INVALID")
        return cls(request_id,run_id,job_id,ref,binding["sha256"],status["status"],status["job_state"],version)

    def summary(self):
        def h(v):
            return hashlib.sha256(v.encode()).hexdigest()
        return {"schema":VERSION,"request_sha256":h(self.request_id),"run_sha256":h(self.run_id),
            "job_sha256":h(self.job_id),"source_ref":self.source_ref,
            "configured_reference_sha256":self.configured_reference_sha256,
            "source_reference_scope":self.provenance,"request_state":self.request_state,
            "job_state":self.job_state,"report_version_metadata":self.report_version_metadata,
            "source_bytes_sha256":None,"origin_epoch":None,"lease_token":None,"processing_result":RESULT_BLOCK,"generated_report":None,
            "reviewer_job_result_binding":"BLOCKED","approval_status":"NOT_APPROVED"}

def require_generated_result(observation, candidate):
    """No accepted result read/persist port exists on the current accepted B4 seam.
    Even genuine rendered bytes or matching input metadata are not job provenance.
    No caller-provided UUID, flag, locator or claimed lease can confer authority.
    """
    if type(observation) is not TaskObservation:
        raise TraceDenied("TASK_OBSERVATION_REQUIRED")
    if not isinstance(candidate,dict):
        raise TraceDenied("RESULT_CANDIDATE_INVALID")
    raise TraceDenied(RESULT_BLOCK)

def read_status(config,request_id):
    request_id=canonical_id(request_id)
    headers={"Host":"127.0.0.1:8765","Origin":"http://127.0.0.1:8765",
        "Authorization":"Bearer "+config["bearer"]}
    c=http.client.HTTPConnection("127.0.0.1",8765,timeout=5)
    try:
        c.request("GET","/v1/audit-requests/"+request_id,headers=headers)
        r=c.getresponse()
        raw=r.read(32769)
        if len(raw)>32768:
            raise TraceDenied("STATUS_RESPONSE_BOUND")
        if r.status!=200:
            return {"schema":VERSION,"decision":"DENIED","http_status":r.status,"generated_report":None}
        observation=TaskObservation.from_status(json.loads(raw),request_id,config)
        return {"schema":VERSION,"decision":"READ_ONLY_STATUS","http_status":200,
            "observation":observation.__dict__,"summary":observation.summary()}
    finally:
        c.close()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--request",required=True)
    p.add_argument("--config",default="/tmp/b4-app/config.json")
    args=p.parse_args()
    try:
        cfg=store.load_config(args.config,"APP")
        result=read_status(cfg,args.request)
        print(json.dumps(result,sort_keys=True))
        if result["decision"]=="DENIED":
            raise SystemExit(2)
    except TraceDenied as exc:
        print(json.dumps({"schema":VERSION,"decision":"DENIED","code":str(exc),"generated_report":None}))
        raise SystemExit(2)

if __name__=="__main__":
    main()

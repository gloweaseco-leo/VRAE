"""Actual accepted C1 runtime composition, separate from report/review authority."""
from dataclasses import asdict, dataclass, field

from vrae.industry.l2_v1 import diagnose, load, verify
from vrae.reporting.common import encode
from vrae.reviewing.canonical import parse, sha

from .sources import OperationsDenied
from .tasks import WorkerEvidence


@dataclass(frozen=True)
class NativeDiagnosis:
    evidence: WorkerEvidence = field(repr=False)
    industry_ref: str
    result_ref: str
    payload: bytes = field(repr=False)
    activities: tuple = field(repr=False)

    @property
    def document(self):
        return parse(self.payload, limit=4_000_000)

    def verify(self):
        d = self.document
        task = self.evidence.task
        if (d["tenant_id"], d["run_id"]) != (task.tenant_id, task.run_id):
            raise OperationsDenied("L2_NATIVE_TASK_SCOPE")
        verify(d, self.evidence.pack, expected_result_ref=self.result_ref,
               expected_pack_ref=self.evidence.pack.ref, expected_industry_ref=self.industry_ref)

    def metadata(self):
        d = self.document
        return {"state": "NATIVE_L2_VERIFIED_REPORT_NOT_PRODUCED", "task": asdict(self.evidence.task),
                "worker_pack_ref": self.evidence.pack.ref, "industry_ref": self.industry_ref,
                "diagnosis_ref": self.result_ref, "diagnosis_sha256": sha(self.payload),
                "source_bundle_sha256": self.evidence.source_bundle_sha256,
                "source_fact_count": len(d["source_facts"]), "assessment_count": len(d["assessments"]),
                "models": sorted({a["model"] for a in d["assessments"]}),
                "procurement_chain_count": len(d["procurement_chains"]),
                "activities": list(self.activities), "cost_status": "UNKNOWN", "report_complete": False,
                "review_authority": False, "semantic_approval": False}


def analyze(evidence):
    from .accounting import ActivityTimer

    if type(evidence) is not WorkerEvidence:
        raise OperationsDenied("L2_ACTUAL_WORKER_EVIDENCE_REQUIRED")
    task, pack = evidence.task, evidence.pack
    if (pack.document["tenant_id"], pack.document["run_id"]) != (task.tenant_id, task.run_id):
        raise OperationsDenied("L2_NATIVE_TASK_SCOPE")
    # Both pins come from this trusted task's pack and server IndustryPack config.
    # No browser-provided industry, diagnosis or tenant participates.
    config = load(tenant_id=task.tenant_id)
    timer = ActivityTimer(task.job_id + "-native-l2", "DIAGNOSIS_RUNTIME", "SYSTEM")
    data = diagnose(pack, expected_pack_ref=pack.ref, expected_industry_ref=config["industry_ref"])
    result = NativeDiagnosis(evidence, config["industry_ref"], data["diagnosis_ref"], encode(data), ())
    result.verify()  # full original source/Guard/industry replay, not schema/hash only
    activity = timer.finish().priced()
    return NativeDiagnosis(evidence, result.industry_ref, result.result_ref, result.payload, (activity,))

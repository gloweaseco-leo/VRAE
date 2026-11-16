"""Actual offline Worker producer + C1 native replay, not APP/PG/browser proof."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json

import pytest

from integration.l2_ops.source_profiles import selected
from tests.collection.test_security import fixture
from vrae.application.ra4b_p2.m1.consumer import AppEndpoint, TaskClient, TaskHandle
from vrae.application.ra4b_p2.m1.reader import GeneratedReport
from vrae.application.ra4b_p2.m1.runtime import build
from vrae.collection.manifest import document_hash
from vrae.evidence import EvidenceError
from vrae.l2_ops.native_diagnosis import analyze
from vrae.l2_ops.sources import OperationsDenied
from vrae.l2_ops.tasks import L2Tasks, RegisteredSource
from vrae.reporting.common import encode


@pytest.fixture(scope="module")
def native_result():
    ref, _, native = selected("industrial-p40-v3")
    now = datetime.now(UTC)
    ids = [f"00000000-0000-4000-8000-{i:012d}" for i in range(11, 16)]
    task = TaskHandle("tenant-test", ref, *ids[:4])
    policy = fixture("SourcePolicy")
    policy.update(tenant_id=task.tenant_id, permitted_hosts=["example.org"], scope_paths=["/"],
                  expires_at=(now + timedelta(hours=1)).isoformat(), revoked_at=None)
    audit = fixture("AuditRequest")
    audit.update(tenant_id=task.tenant_id, source_policy_ref=policy["policy_id"], source_policy_version=policy["policy_version"])
    from integration.l2_ops.catalog import admission
    _, raw = admission(native, source_ref=ref)
    row = {"raw_source": raw, "policy_document": policy, "audit_document": audit, "tenant_id": task.tenant_id,
           "request_id": task.request_id, "run_id": task.run_id, "job_id": task.job_id,
           "worker_role": "ra4b_test_a_worker", "lease_until": now + timedelta(seconds=30), "origin_epoch": 1,
           "source_ref": ref, "reference_sha256": "a" * 64, "loaded_at": now}
    output = build(row, (task.job_id, None, ids[4], 1))
    result = GeneratedReport({k: getattr(task, k) for k in ("tenant_id", "request_id", "run_id", "job_id")},
                             output.source, output.report, output.html)
    client = TaskClient(AppEndpoint("x" * 40, task.tenant_id, frozenset({ref})))
    adapter = L2Tasks(client, [RegisteredSource(ref, native)])
    # Detached contract fixture only. Runtime read paths call original signed
    # reader/session before this internal parser; no test grant is published.
    evidence = adapter._from_authorized_result(task, native_source := adapter.sources[ref], result)
    assert native_source.native.pack.ref != evidence.pack.ref
    return analyze(evidence)


def test_actual_c1_native_diagnosis_uses_new_worker_scope_and_all_19_assessments(native_result):
    value = native_result
    value.verify()
    meta = value.metadata()
    assert meta["models"] == ["P40", "V25"] and meta["assessment_count"] == 19
    assert meta["source_fact_count"] == 81 and meta["procurement_chain_count"] == 2
    assert all(len(chain["stages"]) == 5 for chain in value.document["procurement_chains"])
    assert meta["state"] == "NATIVE_L2_VERIFIED_REPORT_ADAPTER_PENDING"
    assert meta["report_complete"] is False and meta["review_authority"] is False
    assert meta["cost_status"] == "UNKNOWN" and meta["activities"][0]["actor_kind"] == "SYSTEM"
    assert meta["activities"][0]["human_labor_claim"] is False
    d = value.document
    assert d["tenant_id"] == "tenant-test" and d["run_id"] == value.evidence.task.run_id
    assert d["expected_pack_ref"] == value.evidence.pack.ref
    assert d["semantic_approval"] is False and d["approval_status"] == "NOT_APPROVED"


@pytest.mark.parametrize("change", ["industry", "result_pin", "fact_rehashed", "assessment_rehashed", "task_run"])
def test_native_full_replay_rejects_spliced_and_rehashed_results(native_result, change):
    value = native_result
    if change == "industry":
        changed = replace(value, industry_ref="ip-" + "a" * 64)
    elif change == "result_pin":
        changed = replace(value, result_ref="l2-" + "a" * 64)
    elif change == "task_run":
        changed = replace(value, evidence=replace(value.evidence, task=replace(value.evidence.task, run_id="other-run")))
    else:
        doc = json.loads(value.payload)
        if change == "fact_rehashed":
            doc["source_facts"][0]["statement"] = "forged source statement"
        else:
            doc["assessments"][0]["reason"] = "forged professional conclusion"
        doc.pop("diagnosis_ref")
        doc["diagnosis_ref"] = "l2-" + document_hash(doc)
        changed = replace(value, payload=encode(doc), result_ref=doc["diagnosis_ref"])
    with pytest.raises((EvidenceError, OperationsDenied)):
        changed.verify()


def test_original_worker_rejects_preserved_allow_robots_archive_without_rewriting():
    from pathlib import Path
    from vrae.l2_ops.ingest import load_source
    from vrae.l2_ops.native_input import load_native
    from vrae.application.ra4b_p2.m1.runtime import RecordedTransport
    from vrae.application.ra4b_p2.producer import CandidateDenied
    manifest = Path(__file__).resolve().parents[1] / "fixtures/native-p40.json"
    bundle = load_source(manifest)
    value = load_native(bundle, "industrial-p40-native",
        expected_pack_ref="ep-c716086614744c7f5a70e3220d7f42b4136360aebcf9345076962dee172bf992",
        expected_capture_run_id="l2-p40-original-capture-v2")
    with pytest.raises(CandidateDenied, match="M1_RECORDED_ROBOTS_REQUIRED"):
        RecordedTransport(json.loads(bundle.inputs[0].raw))
    assert value.pack.document["tenant_id"] == "tenant-test"

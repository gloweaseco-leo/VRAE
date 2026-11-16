from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import pytest
from vrae.l2_ops.briefs import CurrentL2
from vrae.l2_ops.sources import EvidenceInput, OperationsDenied, SourceBundle
from vrae.reviewing.canonical import canonical, sha
from integration.l2_ops.source_profiles import selected
from tests.collection.test_security import fixture
from vrae.application.ra4b_p2.m1.consumer import AppEndpoint, TaskClient, TaskHandle
from vrae.application.ra4b_p2.m1.reader import GeneratedReport
from vrae.application.ra4b_p2.m1.runtime import build
from vrae.l2_ops.native_diagnosis import analyze
from vrae.l2_ops.tasks import L2Tasks, RegisteredSource




@pytest.fixture
def bundle():
    return SourceBundle("tenant-test", "controlled-manufacturer-v1", "OFFLINE_SYNTHETIC", (
        EvidenceInput("catalog", "text/plain", "合成工业零件目录：材料牌号未知。".encode(),
                      "synthetic-fixture:catalog", "internal-synthetic-analysis", True),))


class TestOnlyReader:
    __test__ = False

    def __init__(self, value):
        self.value, self.allowed, self.locked, self.reads = value, True, False, 0

    @contextmanager
    def current(self):
        self.reads += 1
        if not self.allowed:
            raise OperationsDenied("TEST_REVOKED")
        self.locked = True
        try:
            yield self.value
        finally:
            self.locked = False


@pytest.fixture
def reader(bundle):
    payload = {"diagnostic_depth": "L2", "tenant_id": bundle.tenant_id,
               "run_id": "test-run", "expected_pack_ref": "ep-" + "d" * 64,
               "diagnosis_ref": "l2-" + "e" * 64, "test_fixture_only": True,
               "findings": [{"id": "f-1", "observation": "目录缺少材料牌号。",
                             "evidence_refs": ["catalog"], "hypothesis": "待客户验证"}]}
    pins = {"tenant_id": bundle.tenant_id, "request_id": "test-request",
            "run_id": "test-run", "job_id": "test-job", "event_id": "test-event", "source_ref": "test-source", "report_ref": "test-report",
            "report_version": "test-version-1", "native_pack_ref": payload["expected_pack_ref"],
            "diagnosis_ref": payload["diagnosis_ref"], "report_sha256": "a" * 64,
            "source_bundle_sha256": bundle.document()["content_sha256"],
            "industry_pack_sha256": "b" * 64, "payload_sha256": sha(canonical(payload))}
    review = {"receipt_ref": "test-review", "receipt_sha256": "c" * 64,
              "report_version": pins["report_version"], "report_sha256": pins["report_sha256"],
              "decision": "APPROVE_INTERNAL"}
    blueprint = {"report_version": pins["report_version"], "report_sha256": pins["report_sha256"],
                 "items": [{"finding_ref": "f-1", "proposal": "客户确认后补充材料与公差。"}]}
    return TestOnlyReader(CurrentL2(pins, payload, review, blueprint, datetime.now(UTC) + timedelta(seconds=90)))






@pytest.fixture(scope="session")
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
    # Catalog preparation precedes claim in the real runtime; start the
    # detached fixture lease only once that preparation has completed.
    loaded = datetime.now(UTC)
    row = {"raw_source": raw, "policy_document": policy, "audit_document": audit, "tenant_id": task.tenant_id,
           "request_id": task.request_id, "run_id": task.run_id, "job_id": task.job_id,
           "worker_role": "ra4b_test_a_worker", "lease_until": loaded + timedelta(seconds=30), "origin_epoch": 1,
           "source_ref": ref, "reference_sha256": "a" * 64, "loaded_at": loaded}
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

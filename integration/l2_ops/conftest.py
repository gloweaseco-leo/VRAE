"""One immutable detached native fixture; never cache a task/review authority."""
from datetime import UTC, datetime, timedelta
import pytest
from integration.l2_ops.source_profiles import selected
from tests.collection.test_security import fixture
from vrae.application.ra4b_p2.m1.consumer import AppEndpoint, TaskClient, TaskHandle
from vrae.application.ra4b_p2.m1.reader import GeneratedReport
from vrae.application.ra4b_p2.m1.runtime import build
from vrae.l2_ops.native_diagnosis import analyze
from vrae.l2_ops.tasks import L2Tasks, RegisteredSource
from integration.l2_ops import native_report as assembly


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


@pytest.fixture(scope="session")
def native_source(native_result):
    _, bundle, _ = selected("industrial-p40-v3")
    source = assembly.produce(native_result, bundle, created_at="2026-11-16T12:00:00+00:00")
    return source, bundle

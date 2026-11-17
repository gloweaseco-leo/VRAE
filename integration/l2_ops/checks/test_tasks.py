"""Contract tests with the real offline Collector/producer, not PG/APP E2E."""
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

from tests.collection.test_security import fixture
from vrae.application.ra4b_p2.m1.consumer import AppEndpoint, ConsumerDenied, TaskClient, TaskHandle
from vrae.application.ra4b_p2.m1.reader import GeneratedReport, SignedGeneratedReader
from vrae.application.ra4b_p2.m1.runtime import build
from vrae.l2_ops.ingest import load_source
from vrae.l2_ops.native_input import load_native
from vrae.l2_ops.sources import OperationsDenied
from vrae.l2_ops.tasks import L2Tasks, RegisteredSource

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def generated():
    bundle = load_source(FIXTURES / "native-offline_synthetic.json")
    native = load_native(bundle, "industrial-native",
        expected_pack_ref="ep-735db2c276030e018f21ba7124fb61db6d46f3e922eca1b99df254512064582e",
        expected_capture_run_id="l2-industrial-capture-v1")
    now = datetime.now(UTC)
    ids = [f"00000000-0000-4000-8000-{i:012d}" for i in range(1, 6)]
    task = TaskHandle("tenant-test", "l2-industrial-native-v1", *ids[:4])
    policy = fixture("SourcePolicy")
    policy.update(tenant_id=task.tenant_id, permitted_hosts=["example.org"], scope_paths=["/"],
                  expires_at=(now + timedelta(hours=1)).isoformat(), revoked_at=None)
    audit = fixture("AuditRequest")
    audit.update(tenant_id=task.tenant_id, source_policy_ref=policy["policy_id"],
                 source_policy_version=policy["policy_version"])
    row = {"raw_source": bundle.inputs[0].raw, "policy_document": policy, "audit_document": audit,
           "tenant_id": task.tenant_id, "request_id": task.request_id, "run_id": task.run_id,
           "job_id": task.job_id, "worker_role": "ra4b_test_a_worker",
           "lease_until": now + timedelta(seconds=30), "origin_epoch": 1,
           "source_ref": task.source_ref, "reference_sha256": "a" * 64, "loaded_at": now}
    output = build(row, (task.job_id, None, ids[4], 1))
    locator = {k: getattr(task, k) for k in ("tenant_id", "request_id", "run_id", "job_id")}
    return native, task, GeneratedReport(locator, output.source, output.report, output.html)


def ports(monkeypatch, generated, *, state="TEST_ONLY_DONE", changed_task=None, changed_result=None):
    native, task, result = generated
    client = TaskClient(AppEndpoint("x" * 40, "tenant-test", frozenset({task.source_ref})))
    calls = []

    def request(method, path, body=None, key=None):
        calls.append((method, path, body, key))
        value = changed_task or task
        return {"authority": "TEST_ONLY_PRIVATE_RUNTIME_NOT_HUMAN_APPROVAL",
                **{k: getattr(value, k) for k in ("request_id", "run_id", "job_id", "event_id", "source_ref")},
                "job_state": state, "native_approval": None, "share_grant": None}

    monkeypatch.setattr(client, "_request", request)
    reader = object.__new__(SignedGeneratedReader)
    read = Mock(return_value=changed_result or result)
    monkeypatch.setattr(reader, "read", read)
    adapter = L2Tasks(client, [RegisteredSource(task.source_ref, native)])
    return adapter, reader, calls, read


def test_actual_offline_worker_producer_keeps_all_eight_pages_and_fresh_scope(monkeypatch, generated):
    native, task, _ = generated
    adapter, reader, calls, read = ports(monkeypatch, generated)
    created = adapter.create(task.source_ref, idempotency_key="l2-contract-only-0001")
    assert created == task and calls[0][0] == "POST"
    evidence = adapter.read_worker(created, reader, "Bearer contract-test", nonce="server-held-test-nonce")
    assert len(evidence.pack.document["snapshots"]) == 8
    assert evidence.pack.document["run_id"] == task.run_id != native.pack.document["run_id"]
    assert evidence.pack.ref != native.pack.ref
    read.assert_called_once_with("Bearer contract-test", task.tenant_id, task.job_id, nonce="server-held-test-nonce")
    metadata = evidence.metadata()
    assert metadata["state"] == "WORKER_EVIDENCE_VERIFIED_DEEP_ANALYSIS_PENDING"
    assert metadata["l2_complete"] is False and metadata["review_authority"] is False
    assert "objects_base64" not in json.dumps(metadata)


def test_done_alone_cannot_bypass_signed_read(monkeypatch, generated):
    adapter, reader, _, read = ports(monkeypatch, generated, state="PENDING")
    with pytest.raises(ConsumerDenied):
        adapter.read_worker(generated[1], reader, "Bearer test", nonce="test")
    read.assert_not_called()


@pytest.mark.parametrize("field", ["tenant_id", "request_id", "run_id", "job_id"])
def test_signed_locator_cannot_be_spliced_between_tasks(monkeypatch, generated, field):
    _, task, result = generated
    forged = replace(result, locator={**result.locator, field: "other"})
    adapter, reader, _, _ = ports(monkeypatch, generated, changed_result=forged)
    with pytest.raises(ConsumerDenied):
        adapter.read_worker(task, reader, "Bearer test", nonce="test")


def test_another_valid_source_cannot_be_attached(monkeypatch, generated):
    from tests.reviewing.synthetic import inputs
    from vrae.l2_ops.sources import EvidenceInput, SourceBundle
    raw = json.loads(inputs("200").source)
    archive = json.dumps({k: raw[k] for k in ("pack", "objects_base64")}).encode()
    bundle = SourceBundle("tenant-test", "other-registered-capture", "OFFLINE_SYNTHETIC", (
        EvidenceInput("capture", "application/json", archive, "synthetic-other", "internal-test", True),))
    pin = json.loads(inputs("200").document)["pins"]["expected_pack_ref"]
    other = load_native(bundle, "capture", expected_pack_ref=pin, expected_capture_run_id=raw["pack"]["run_id"])
    adapter, reader, _, _ = ports(monkeypatch, generated)
    adapter.sources[generated[1].source_ref] = RegisteredSource(generated[1].source_ref, other)
    with pytest.raises(OperationsDenied, match="WORKER_SOURCE_MISMATCH"):
        adapter.read_worker(generated[1], reader, "Bearer test", nonce="test")


def test_unregistered_and_unsigned_paths_refuse(monkeypatch, generated):
    adapter, reader, calls, _ = ports(monkeypatch, generated)
    with pytest.raises(OperationsDenied, match="UNREGISTERED"):
        adapter.create("unregistered", idempotency_key="test-key-0001")
    with pytest.raises(OperationsDenied, match="SIGNED_READER"):
        adapter.read_worker(generated[1], object(), "Bearer test", nonce="test")
    assert not calls


def test_admission_preview_replays_same_input_without_a_deep_report(generated):
    from integration.l2_ops.catalog import admission
    native = generated[0]
    reference, source = admission(native)
    data = json.loads(source)
    assert data["pack"] == native.pack.document
    assert reference["metadata"]["evidence_pack_ref"] == native.pack.ref
    assert reference["metadata"]["source_record_sha256"] == __import__("hashlib").sha256(source).hexdigest()
    assert reference["kind"] == "COVERAGE_ONLY" and reference["issue_count"] == 0
    assert reference["native_id"] is None and reference["native_h0"] is None


@pytest.mark.parametrize("bad", ["hash", "policy", "tenant", "role", "kind", "old_sources", "version"])
def test_private_app_source_provisioning_fails_closed(bad):
    from integration.l2_ops.provisioning import extend_app_sources
    config = {"kind": "APP", "tenant": "tenant-test", "role": "ra4b_test_a_app",
              "sources": {"accepted-404": {"unchanged": 1}, "accepted-200": {"unchanged": 2}}}
    binding = {"sha256": "a" * 64, "policy_id": "pol-001", "policy_version": 1}
    if bad == "hash":
        binding["sha256"] = "not-a-hash"
    elif bad == "policy":
        binding["policy_id"] = "other"
    elif bad == "version":
        binding["policy_version"] = True
    elif bad == "old_sources":
        config["sources"] = {}
    else:
        config[{"tenant": "tenant", "role": "role", "kind": "kind"}[bad]] = "other"
    with pytest.raises(ValueError, match="PROVISIONING_DENIED"):
        extend_app_sources(config, binding)


def test_private_app_binding_preserves_existing_sources_and_credentials():
    from copy import deepcopy
    from integration.l2_ops.provisioning import extend_app_sources
    config = {"kind": "APP", "tenant": "tenant-test", "role": "ra4b_test_a_app", "password": "test-only",
              "sources": {"accepted-404": {"unchanged": 1}, "accepted-200": {"unchanged": 2}}}
    old = deepcopy(config)
    binding = {"sha256": "a" * 64, "policy_id": "pol-001", "policy_version": 1}
    extend_app_sources(config, binding)
    assert config["sources"].pop("l2-industrial-native-v1") == binding
    assert config == old

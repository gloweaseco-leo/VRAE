from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest

from vrae.l2_ops.briefs import CurrentL2
from vrae.l2_ops.sources import EvidenceInput, OperationsDenied, SourceBundle
from vrae.reviewing.canonical import canonical, sha


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

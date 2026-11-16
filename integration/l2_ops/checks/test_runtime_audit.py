"""Private probe routing must fail closed before touching live authority.

These routing checks are NOT claimed as real Worker/dual-authority evidence.
The actual probes run only against the same Chrome-created live task.
"""
import json
from types import SimpleNamespace

import pytest

from integration.l2_ops.runtime_audit import consume
from vrae.l2_ops.sources import OperationsDenied


def test_absent_private_probe_has_no_effect(tmp_path):
    assert consume(SimpleNamespace(root=tmp_path), None, None, None, ()) is None


@pytest.mark.parametrize("command", [
    {"case": "arbitrary-python", "job_id": "owned-job"},
    {"case": "idempotent", "job_id": "other-job"},
    {"case": "idempotent", "job_id": "owned-job", "sql": "untrusted"},
])
def test_private_probe_cannot_select_code_sql_or_another_job(tmp_path, command):
    (tmp_path/"s0-audit-request.json").write_text(json.dumps(command))
    reader = SimpleNamespace(task=SimpleNamespace(job_id="owned-job"))
    with pytest.raises(OperationsDenied, match="S0_PRIVATE_AUDIT_SCOPE_DENIED"):
        consume(SimpleNamespace(root=tmp_path), reader, None, None, ())
    assert not list(tmp_path.glob("s0-audit-*.running.json"))


def test_previous_probe_receipt_cannot_be_overwritten_or_randomly_retried(tmp_path):
    command = {"case": "idempotent", "job_id": "owned-job"}
    (tmp_path/"s0-audit-request.json").write_text(json.dumps(command))
    result = tmp_path/"s0-audit-idempotent.json"
    result.write_bytes(b"retained RED or GREEN")
    reader = SimpleNamespace(task=SimpleNamespace(job_id="owned-job"))
    with pytest.raises(OperationsDenied, match="S0_PRIVATE_AUDIT_ALREADY_EXECUTED"):
        consume(SimpleNamespace(root=tmp_path), reader, None, None, ())
    assert result.read_bytes() == b"retained RED or GREEN"

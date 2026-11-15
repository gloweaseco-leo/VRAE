"""Explicit M1 CI gate, separate from frozen default test-ID inventory."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from tests.collection.test_security import fixture
from vrae.application.ra4b_p2.m1.runtime import build
from vrae.application.ra4b_p2.m1.producer import replay, select_facts
from vrae.application.ra4b_p2.producer import encode


def row_and_lease(case):
    source = json.loads(
        (Path(__file__).parents[1] / "reviewing/fixtures" / f"{case}.json").read_bytes()
    )["source"]
    now = datetime.now(timezone.utc)
    audit, policy = fixture("AuditRequest"), fixture("SourcePolicy")
    audit.update(tenant_id="tenant-test", source_policy_ref="policy-m1", source_policy_version=1)
    policy.update(
        tenant_id="tenant-test",
        policy_id="policy-m1",
        policy_version=1,
        expires_at=(now + timedelta(days=1)).isoformat(),
        revoked_at=None,
        permitted_hosts=["example.org"],
        scope_paths=["/"],
    )
    ids = [uuid4() for _ in range(4)]
    lease = (ids[0], ids[1], ids[2], 1, now + timedelta(seconds=30))
    row = dict(
        tenant_id="tenant-test",
        request_id=ids[3],
        run_id=ids[1],
        job_id=ids[0],
        worker_role="ra4b_test_a_worker",
        lease_until=lease[4],
        origin_epoch=1,
        source_ref="accepted-" + case,
        reference_sha256="1" * 64,
        raw_source=encode(source),
        policy_document=policy,
        audit_document=audit,
        loaded_at=now,
    )
    return row, lease


@pytest.mark.parametrize("case", ["404", "200"])
def test_collector_to_bounded_report_retains_complete_fact_catalog(case):
    row, lease = row_and_lease(case)
    output = build(row, lease)
    d = replay(output)
    s = json.loads(output.source)
    selection = s["editorial_selection"]
    full_catalog = json.loads(selection["full_catalog_json"])
    assert hashlib.sha256(encode(full_catalog)).hexdigest() == selection["full_catalog_sha256"]
    assert d["metadata"]["report_id"] == "job-" + str(lease[0])
    assert len(d["issues"]) == (1 if case == "404" else 0)
    assert len(s["guard_inputs"]) <= 16
    assert selection["full_evidence_retained"]
    assert (
        len(full_catalog) == len(selection["selected_facts"]) + selection["omitted_positive_facts"]
    )
    assert len(selection["selected_facts"]) == len(select_facts(full_catalog))
    if case == "200":
        assert len(full_catalog) == 17
        assert len(selection["selected_facts"]) == 3
        assert selection["omitted_positive_facts"] == 14
    assert len(s["package"]["rule_execution"]["executions"]) == 16
    assert d["approval_status"] == "NOT_APPROVED" and not d["shareable"]


def test_changed_html_and_selection_cannot_replay():
    row, lease = row_and_lease("200")
    output = build(row, lease)
    with pytest.raises(Exception):
        replay(replace(output, html=output.html + b"forged"))
    source = json.loads(output.source)
    source["editorial_selection"]["full_catalog_json"] = "[]"
    with pytest.raises(Exception, match="M1_EDITORIAL_SELECTION"):
        replay(replace(output, source=encode(source)))

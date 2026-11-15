"""Actual HTTP-only APP consumer to existing signed generated-result port."""

from dataclasses import fields, replace
import hashlib
from uuid import uuid4

import pytest

from integration.ra4b_p2.m1.native_cases import m1, runtime, reader  # noqa: F401
from vrae.application.ra4b_p2.m1.consumer import AppEndpoint, TaskClient, ConsumerDenied
from vrae.identity.boundary import IdentityDenied


@pytest.mark.parametrize("case", ["404", "200"])
def test_http_only_consumer_current_task_to_signed_result(m1, case):  # noqa: F811
    # Trusted operator exports only the service bearer, not the APP config.
    endpoint = AppEndpoint(
        m1["runtime"]["held"]["APP"]["bearer"], "tenant-test", frozenset({"accepted-404", "accepted-200"})
    )
    assert {f.name for f in fields(endpoint)} == {"bearer", "tenant_id", "source_refs"}
    assert endpoint.bearer not in repr(endpoint)
    client = TaskClient(endpoint)
    key = "consumer-" + case
    task = client.create("accepted-" + case, idempotency_key=key)
    assert client.create("accepted-" + case, idempotency_key=key) == task
    assert client.status(task)["job_state"] == "PENDING"
    port, token, nonce = reader(m1, task.__dict__)
    with pytest.raises(ConsumerDenied):
        client.read(task, port, token, nonce=nonce)
    worker_receipt = m1["spawn"]()
    assert client.status(task)["job_state"] == "TEST_ONLY_DONE"
    report = client.read(task, port, token, nonce=nonce)
    assert report.locator == worker_receipt
    assert report.locator["report_sha256"] == hashlib.sha256(report.report).hexdigest()
    assert report.locator["report_version"] == 1
    assert report.locator["authority"] == "TEST_ONLY_GENERATED_NOT_APPROVED"
    with pytest.raises(ConsumerDenied):
        client.status(replace(task, job_id=str(uuid4())))
    with pytest.raises(ConsumerDenied):
        client.status(replace(task, source_ref="accepted-200" if case == "404" else "accepted-404"))
    with pytest.raises(IdentityDenied):
        client.read(task, port, token, nonce=nonce)
    peer, token2, nonce2 = reader(m1, task.__dict__, role="p2b1_test_a_peer")
    with pytest.raises(IdentityDenied):
        client.read(task, peer, token2, nonce=nonce2)

"""Focused PR105/M3 adapter checks, not another M1 foundation acceptance run."""

import json

import pytest

from vrae.application.ra4b_p2.m1.consumer import ConsumerDenied

from .m3_cases import app, admin  # noqa: F401
from .m3_results import api, materialize, read_owned_job, restart_pg, submit, task_status


def test_00_private_consumer_identity_has_no_database_configuration(app):  # noqa: F811
    result = api(app["label"], "configuration")
    assert result["uid"] == 10003
    assert result["body"] == {
        "profile_fields": ["bearer", "tenant_id", "source_refs"],
        "database_configs_unreadable": True,
        "directory_mode": "0700",
        "file_mode": "0600",
    }
    with admin(app) as c:
        assert c.execute("SELECT count(*) FROM ra4b_p2.m1_results").fetchone() == (0,)


@pytest.mark.parametrize("source", ["404", "200"])
def test_10_canonical_taskclient_pending_to_real_worker_result(app, source):  # noqa: F811
    key = "m3-taskclient-" + source + "-0001"
    created = api(app["label"], "submit", source=source, key=key)
    handle = created["body"]
    assert created["http_status"] == 202
    pending = api(app["label"], "status", handle=json.dumps(handle))
    assert pending["body"]["job_state"] == "PENDING"
    for forged in (
        {**handle, "job_id": handle["request_id"]},
        {**handle, "source_ref": "accepted-200" if source == "404" else "accepted-404"},
    ):
        with pytest.raises(ConsumerDenied):
            api(app["label"], "status", handle=json.dumps(forged))
    with pytest.raises(ConsumerDenied):
        api(app["label"], "submit", source="200" if source == "404" else "404", key=key)
    task = submit(app["label"], source, key)
    assert task["task_handle"] == handle
    proof = materialize(app["label"], task["job_id"], 90)
    assert task_status(app["label"], task["job_id"])["api_status"]["job_state"] == "TEST_ONLY_DONE"
    assert proof["locator"]["job_id"] == handle["job_id"]
    assert proof["locator"]["run_id"] == handle["run_id"]
    assert proof["locator"]["report_version"] == 1
    report = read_owned_job(app["label"], task["job_id"])
    app["tasks"][source] = task
    app["reports"][source] = (report.source, report.report, report.html)
    worker_log = (app["folder"] / "native/boot-0/m1-worker.log").read_text(encoding="utf-8")
    records = [json.loads(line) for line in worker_log.splitlines() if line.startswith("{")]
    assert any(
        r.get("state") == "M3_CANONICAL_WORKER_STARTED"
        and r["uid"] == 10002
        and r["module"] == "vrae.application.ra4b_p2.m1.runtime"
        for r in records
    )
    assert any(r.get("job_id") == handle["job_id"] for r in records)


def test_20_restart_reprovisions_http_identity_and_reads_same_handles(app):  # noqa: F811
    assert restart_pg(app["label"])["actual_pg_restart"]
    assert api(app["label"], "configuration")["body"]["database_configs_unreadable"]
    for source, task in app["tasks"].items():
        assert (
            task_status(app["label"], task["job_id"])["api_status"]["job_state"] == "TEST_ONLY_DONE"
        )
        report = read_owned_job(app["label"], task["job_id"])
        assert (report.source, report.report, report.html) == app["reports"][source]
    with admin(app) as c:
        assert c.execute("SELECT count(*) FROM ra4b_p2.m1_results").fetchone() == (2,)

"""Real M3 integration of accepted M1; M2 binding is intentionally not fabricated."""

import hashlib
import json
import os
import subprocess
import time

import psycopg
import pytest

from vrae.identity.boundary import IdentityDenied

from .local_app import folder_for, request_stop, start, status
from .m3_results import materialize, read_owned_job, restart_pg, submit
from .runner import ROOT


@pytest.fixture(scope="module")
def app():
    label = os.environ["M3_RUN"]
    minor = os.environ.get("M3_MINOR", "3.11")
    _result, code = start(label, minor, False)
    assert code == 0
    folder = folder_for(label)
    try:
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            current = status(label)
            if current["state"] == "M1_READY_M2_UI_PENDING":
                break
            assert current["state"] in ("STARTING", "ABSENT"), current
            time.sleep(0.25)
        else:
            raise AssertionError("M3_APPLICATION_NOT_READY")
        yield {"label": label, "folder": folder, "tasks": {}, "reports": {}}
    finally:
        request_stop(label)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline and status(label)["state"] != "CLOSED":
            time.sleep(0.25)
        assert status(label)["state"] == "CLOSED"
        assert status(label)["component_result"] == "M1_READY_M2_UI_PENDING"
        end = folder.parent / "local-launches" / label / "supervisor-end.json"
        deadline = time.monotonic() + 5
        while not end.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        assert json.loads(end.read_bytes()) == {"exitcode": 0}


def admin(app):
    paths = list((app["folder"] / "pg").glob("*/state.json"))
    assert len(paths) == 1
    s = json.loads(paths[0].read_bytes())
    return psycopg.connect(
        host="127.0.0.1",
        port=s["port"],
        dbname="vrae_ra4a_p1",
        user="postgres",
        password=s["admin_password"],
        autocommit=True,
        connect_timeout=5,
    )


def test_00_clean_start_real_workers_and_one_ssr(app):
    current = status(app["label"])
    assert current["review_ui"] == "PENDING_OWNER_MERGED_M2"
    assert current["ssr_is_generated_job_reviewer"] is False
    runtime = json.loads((app["folder"] / "native/boot-0/native-result.json").read_bytes())
    assert (
        runtime["mode"] == "M1_REAL_GENERATION"
        and runtime["worker_uid"] == 10002
        and runtime["app_uid"] == 10001
    )
    assert runtime["generated_rows_seeded"] == 0
    with admin(app) as c:
        assert c.execute("SELECT count(*) FROM ra4b_p2.m1_results").fetchone() == (0,)
        assert c.execute("SELECT count(*) FROM ra4a.jobs").fetchone() == (0,)


@pytest.mark.parametrize("source", ["404", "200"])
def test_10_real_app202_worker_report_source_and_version(app, source):
    task = submit(app["label"], source, "m3-functional-" + source + "-0001")
    assert task["http_status"] == 202
    proof = materialize(app["label"], task["job_id"], 90)
    assert all(proof["locator"][k] == task[k] for k in ("request_id", "run_id", "job_id"))
    assert proof["locator"]["authority"] == "TEST_ONLY_GENERATED_NOT_APPROVED"
    report = read_owned_job(app["label"], task["job_id"])
    data = json.loads(report.report)
    assert data["scope"]["run_id"] == task["run_id"]
    assert (
        data["metadata"]["report_id"] == "job-" + task["job_id"]
        and data["metadata"]["version"] == 1
    )
    assert len(data["issues"]) == (1 if source == "404" else 0)
    if source == "200":
        assert report.editorial_selection["full_fact_count"] == 17
        assert report.editorial_selection["omitted_positive_facts"] == 14
    app["tasks"][source] = task
    app["reports"][source] = (report.source, report.report, report.html)
    with admin(app) as c:
        assert c.execute(
            "SELECT count(*) FROM ra4a.audit WHERE run_id=%s AND action='TEST_ONLY_CONSUMED'",
            (task["run_id"],),
        ).fetchone() == (1,)
        assert c.execute(
            "SELECT count(*) FROM ra4a.outbox WHERE run_id=%s AND kind='TEST_ONLY_CONSUMED'",
            (task["run_id"],),
        ).fetchone() == (1,)


def test_20_idempotency_is_actual_same_job_and_only_two_results(app):
    again = submit(app["label"], "404", "m3-functional-404-0001")
    assert again == app["tasks"]["404"]
    with admin(app) as c:
        assert c.execute("SELECT count(*) FROM ra4b_p2.m1_results").fetchone() == (2,)


def test_30_current_assignment_revocation_denies_cached_file_read(app):
    job = app["tasks"]["404"]["job_id"]
    with admin(app) as c:
        c.execute("UPDATE ra4b_p2.m1_assignments SET active=false WHERE job_id=%s", (job,))
    try:
        with pytest.raises(IdentityDenied):
            materialize(app["label"], job)
    finally:
        with admin(app) as c:
            c.execute("UPDATE ra4b_p2.m1_assignments SET active=true WHERE job_id=%s", (job,))


def test_40_real_pg_restart_no_bootstrap_and_exact_result_readback(app):
    result = restart_pg(app["label"])
    assert (
        result["actual_pg_restart"]
        and not result["migrations_rerun"]
        and not result["results_reseeded"]
    )
    for source, task in app["tasks"].items():
        report = read_owned_job(app["label"], task["job_id"])
        assert (report.source, report.report, report.html) == app["reports"][source]
    with admin(app) as c:
        assert c.execute("SELECT count(*) FROM ra4b_p2.m1_results").fetchone() == (2,)


def test_50_browser_views_both_actual_generated_html_hashes(app):
    for source, task in app["tasks"].items():
        proof = materialize(app["label"], task["job_id"])
        output = app["folder"] / "generated" / task["job_id"] / "browser"
        process = subprocess.run(
            [
                "node",
                str(ROOT / "integration/beta_review/codex3/m3_preview.mjs"),
                proof["private_html"],
                proof["locator"]["html_sha256"],
                str(output),
            ],
            cwd=ROOT,
            capture_output=True,
            timeout=90,
            check=False,
        )
        (app["folder"] / ("browser-" + source + ".stderr.private.log")).write_bytes(process.stderr)
        assert process.returncode == 0
        result = json.loads(process.stdout)
        assert result["pass"] and result["html_sha256"] == proof["locator"]["html_sha256"]
        assert (
            result["screenshot_sha256"]
            == hashlib.sha256((output / "generated-report.png").read_bytes()).hexdigest()
        )
        assert json.loads((output / "cleanup.json").read_bytes())["exit_observed"]

"""Actual launcher/browser M3 closure. No original M1/M2 acceptance reruns."""

import hashlib
import json
import os
import re
import subprocess
import sys
import time

import psycopg
import pytest

from .local_app import folder_for, launch_for, status
from .runner import ROOT


def cli(*arguments, timeout=30):
    return subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/beta_internal.py"), "app", *arguments],
        cwd=ROOT,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


@pytest.fixture(scope="module")
def business():
    label, minor = os.environ["M3_RUN"], os.environ.get("M3_MINOR", "3.11")
    folder = folder_for(label)
    started = cli("start", "--run", label, "--minor", minor)
    assert started.returncode == 0
    try:
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            current = status(label)
            if current["state"] == "M3_READY":
                break
            assert current["state"] in ("STARTING", "ABSENT"), current
            time.sleep(0.25)
        else:
            raise AssertionError("M3_STARTUP_RED")
        yield {"label": label, "folder": folder, "sha": current["source_sha"]}
    finally:
        stopped = cli("stop", "--run", label)
        assert stopped.returncode == 0
        deadline = time.monotonic() + 90
        while (
            time.monotonic() < deadline and not (launch_for(label) / "supervisor-end.json").exists()
        ):
            time.sleep(0.25)
        assert json.loads((launch_for(label) / "supervisor-end.json").read_bytes()) == {
            "exitcode": 0
        }
        assert status(label)["state"] == "CLOSED"
        assert status(label)["component_result"] == "M3_READY"


def connection(business):
    paths = list((business["folder"] / "pg").glob("*/state.json"))
    assert len(paths) == 1
    state = json.loads(paths[0].read_bytes())
    return psycopg.connect(
        host="127.0.0.1",
        port=state["port"],
        dbname="vrae_ra4a_p1",
        user="postgres",
        password=state["admin_password"],
        autocommit=True,
        connect_timeout=5,
    )


def test_00_real_cli_bootstrap_and_unique_low_role_ssr(business):
    current = status(business["label"])
    assert current["ssr_is_generated_job_reviewer"] and current["url"].endswith("/b5a/m2/")
    native = json.loads((business["folder"] / "native/boot-0/native-result.json").read_bytes())
    assert native["worker_uid"] == 10002 and native["app_uid"] == 10001
    ownership = json.loads((business["folder"] / "ownership.json").read_bytes())
    ssr = ownership["volume"] + "-ssr"
    uid = subprocess.check_output(["docker", "exec", ssr, "id", "-u"]).decode().strip()
    assert uid == "10003"
    with connection(business) as c:
        assert c.execute("SHOW server_version_num").fetchone()[0].startswith("16")
        assert c.execute("SELECT count(*) FROM ra4b_p2.m1_results").fetchone() == (2,)
        assert c.execute("SELECT count(*) FROM b5b_m2.receipts").fetchone() == (0,)
        assert c.execute(
            "SELECT has_table_privilege('p2b1_test_a_reviewer','b5b_m2.receipts','SELECT,INSERT,UPDATE,DELETE')"
        ).fetchone() == (False,)


def test_10_real_browser_new_tasks_review_pdf_restart_and_denials(business):
    result = cli("verify", "--run", business["label"], timeout=900)
    (business["folder"] / "browser-cli.stdout.private.log").write_bytes(result.stdout)
    (business["folder"] / "browser-cli.stderr.private.log").write_bytes(result.stderr)
    assert result.returncode == 0, "M3_BROWSER_RED_SEE_PRIVATE_EVIDENCE"
    proof = json.loads(result.stdout)
    assert proof["pass"] and proof["source_sha"] == business["sha"]
    browser = json.loads((business["folder"] / "browser-acceptance/browser.json").read_bytes())
    assert browser["status"] == "M3_FULL_BROWSER_TASK_WORKER_REVIEW_A4_RESTART_PASS"
    assert all(r["pass"] for r in browser["records"])
    assert len(browser["shots"]) == 18
    assert any(r["name"] == "unsigned-browser-report-denied" for r in browser["records"])
    assert any(r["name"] == "cross-job-receipt-denied" for r in browser["records"])
    assert json.loads(
        (business["folder"] / "browser-acceptance/browser-process-cleanup.json").read_bytes()
    )["exit_observed"]


def test_20_all_browser_jobs_and_receipts_are_real_same_version(business):
    with connection(business) as c:
        rows = c.execute(
            "SELECT job_id,request_id,run_id,source_ref,report_version,source_sha256,report_sha256,html_sha256,report,source_record,html FROM ra4b_p2.m1_results ORDER BY job_id"
        ).fetchall()
        receipts = c.execute(
            "SELECT job_id,command_id,receipt FROM b5b_m2.receipts ORDER BY command_id"
        ).fetchall()
        assert len(rows) == 8 and len(receipts) == 6
        assert c.execute(
            "SELECT count(*) FROM ra4a.jobs WHERE state<>'TEST_ONLY_DONE'"
        ).fetchone() == (0,)
    assert {r[2]["decision"] for r in receipts} == {
        "APPROVE_INTERNAL",
        "REJECT_INTERNAL",
        "REVISE_INTERNAL",
    }
    known = {str(r[0]): r for r in rows}
    archive = business["folder"] / "actual-generated.private"
    archive.mkdir()
    for row in rows:
        saved = archive / str(row[0])
        saved.mkdir()
        for name, index, hash_index in (
            ("source.json", 9, 5),
            ("report.json", 8, 6),
            ("report.html", 10, 7),
        ):
            raw = bytes(row[index])
            assert hashlib.sha256(raw).hexdigest() == row[hash_index]
            (saved / name).write_bytes(raw)
        doc = json.loads(bytes(row[8]))
        assert row[4] == 1 and hashlib.sha256(bytes(row[8])).hexdigest() == row[6]
        assert doc["metadata"]["version"] == 1 and doc["scope"]["run_id"] == str(row[2])
        assert doc["approval_status"] == "NOT_APPROVED" and doc["shareable"] is False
        assert len(doc["issues"]) == (1 if row[3] == "accepted-404" else 0)
    proof = []
    for job, command, receipt in receipts:
        row = known[str(job)]
        assert receipt["report"]["report_sha256"] == row[6]
        assert receipt["report"]["report_version"] == 1
        assert receipt["report_approval_status"] == "NOT_APPROVED"
        assert receipt["human_approval"] is False and receipt["external_delivery"] is False
        proof.append({"job_id": str(job), "command_id": str(command), "receipt": receipt})
    (business["folder"] / "real-durable-receipts.private.json").write_text(
        json.dumps(proof, indent=2), encoding="utf-8"
    )
    snapshots = list(business["folder"].glob("restart-*.json"))
    assert len(snapshots) == 2
    for path in snapshots:
        data = json.loads(path.read_bytes())
        assert (
            data["actual_pg_restart"]
            and not data["migrations_rerun"]
            and not data["results_reseeded"]
        )


def test_30_actual_chinese_single_page_a4_and_screenshot_hashes(business):
    folder = business["folder"] / "browser-acceptance"
    browser = json.loads((folder / "browser.json").read_bytes())
    for item in browser["shots"]:
        assert hashlib.sha256((folder / item["file"]).read_bytes()).hexdigest() == item["sha256"]
    for case in ("404", "200"):
        raw = (folder / ("a4-" + case + ".pdf")).read_bytes()
        assert raw.startswith(b"%PDF-") and len(re.findall(rb"/Type\s*/Page\b", raw)) == 1
        assert b"/ToUnicode" in raw
        box = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", raw)
        assert box and 594 <= float(box[1]) <= 596 and 841 <= float(box[2]) <= 843

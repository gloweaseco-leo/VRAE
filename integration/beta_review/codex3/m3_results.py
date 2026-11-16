"""Trusted local operator adapters for actual M1 tasks; no web authorization shortcut."""

import json
import secrets
import subprocess
import time
from uuid import UUID

import psycopg

from tests.identity.issuer import AUDIENCE, ISSUER, Issuer
from vrae.application.ra4b_p2.m1.consumer import ConsumerDenied
from vrae.application.ra4b_p2.m1.reader import JobAssignment, SignedGeneratedReader
from vrae.identity.boundary import TrustAnchor

from .local_app import control_write, folder_for
from .runner import ROOT, write
from .s2_runtime import owned_client


def context(label):
    folder = folder_for(label)
    state = json.loads((folder / "m3-runtime.json").read_bytes())
    assert state["mode"] in ("M1_GENERATED_REPORTS_M2_UI_PENDING", "M3_SYNTHETIC_BROWSER_WORKBENCH")
    current = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    assert current == state["source_sha"], "M3_SOURCE_CHANGED_RESTART_FULL_RUN_REQUIRED"
    return folder, state


def api(label, action, **args):
    folder, _state = context(label)
    client = owned_client(folder)
    command = [
        "docker",
        "exec",
        "--user",
        "10003:10003",
        "--env",
        "VRAE_RA4B_TEST_ONLY=1",
        client,
        "python",
        "-B",
        "-m",
        "integration.beta_review.codex3.m3_client",
        action,
    ]
    for name, value in args.items():
        command.extend(["--" + name, str(value)])
    p = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=15, check=False)
    if p.returncode == 2 and len(p.stdout) < 65536:
        denial = json.loads(p.stdout)
        assert denial == {"decision": "DENIED", "reason": "M1_CONSUMER_DENIED", "uid": 10003}
        raise ConsumerDenied()
    assert p.returncode == 0 and len(p.stdout) < 65536, "M3_ORIGINAL_API_REQUEST_FAILED"
    result = json.loads(p.stdout)
    assert result["uid"] == 10003
    assert result["adapter"] == "vrae.application.ra4b_p2.m1.consumer.TaskClient"
    return result


def submit(label, source, key=None):
    assert source in ("404", "200")
    folder, state = context(label)
    key = key or "m3-" + secrets.token_hex(16)
    result = api(label, "submit", source=source, key=key)
    assert result["http_status"] == 202
    body = result["body"]
    for name in ("request_id", "run_id", "job_id", "event_id"):
        assert str(UUID(body[name])) == body[name]
    task = {
        **{k: body[k] for k in ("request_id", "run_id", "job_id", "event_id")},
        "task_handle": body,
        "source": source,
        "source_ref": "accepted-" + source,
        "http_status": 202,
        "generated_report": None,
        "acceptance": "ACTUAL_APP202_AFTER_COMMIT",
    }
    file = folder / "m3-tasks" / (task["job_id"] + ".json")
    if file.exists():
        assert json.loads(file.read_bytes()) == task
    else:
        write(file, task)
    output = (folder / state["native_out"]).resolve()
    assert output.is_relative_to(folder.resolve())
    wake = output / (task["job_id"] + ".wake.json")
    if not wake.exists():
        temporary = wake.with_suffix(".tmp")
        write(temporary, {"process_one": True})
        temporary.replace(wake)
    return task


def owned_task(label, job):
    assert str(UUID(job)) == job
    folder, _ = context(label)
    task = json.loads((folder / "m3-tasks" / (job + ".json")).read_bytes())
    assert task["job_id"] == job
    return folder, task


def task_status(label, job):
    _, task = owned_task(label, job)
    result = api(label, "status", handle=json.dumps(task["task_handle"], separators=(",", ":")))
    body = result["body"]
    assert result["http_status"] == 200 and all(
        body[k] == task[k] for k in ("request_id", "run_id", "job_id")
    )
    assert body["source_ref"] == task["source_ref"]
    return {"task": task, "api_status": body, "generated_report": "REQUIRES_SIGNED_GENERATED_READ"}


def read_owned_job(label, job, wait_seconds=0):
    folder, task = owned_task(label, job)
    deadline = time.monotonic() + wait_seconds
    while True:
        status = task_status(label, job)
        if status["api_status"]["job_state"] == "TEST_ONLY_DONE":
            break
        if time.monotonic() >= deadline:
            raise RuntimeError("M3_GENERATION_PENDING")
        time.sleep(0.25)
    # This signer is the TEST_ONLY local operator fixture, not an HTTP identity
    # adapter or a human approval. Future M2 must use its own accepted auth flow.
    cfg = json.loads((folder / "m3-reviewer.private.json").read_bytes())

    def connect(role):
        assert role == cfg["role"] == "p2b1_test_a_reviewer"
        return psycopg.connect(
            host=cfg["host"],
            port=cfg["port"],
            dbname=cfg["dbname"],
            user=role,
            password=cfg["password"],
            autocommit=True,
            connect_timeout=5,
            options="-c statement_timeout=2000 -c lock_timeout=1500",
        )

    issuer = Issuer()
    now = int(time.time())
    nonce = secrets.token_urlsafe(24)
    reader = SignedGeneratedReader(
        anchor=TrustAnchor(ISSUER, AUDIENCE, issuer.jwks(), now + 180),
        assignments=[
            JobAssignment(
                ISSUER, "synthetic-reviewer-1", cfg["role"], "tenant-test", job, now + 180
            )
        ],
        connect=connect,
    )
    token = issuer.token({"iat": now, "nbf": now, "exp": now + 120, "nonce": nonce})
    result = reader.read(token, "tenant-test", job, nonce=nonce)
    assert all(result.locator[k] == task[k] for k in ("request_id", "run_id", "job_id"))
    source, report = json.loads(result.source), json.loads(result.report)
    assert source["pack"]["run_id"] == task["run_id"] == report["scope"]["run_id"]
    assert result.locator["report_id"] == report["metadata"]["report_id"] == "job-" + job
    assert result.locator["report_version"] == report["metadata"]["version"]
    assert len(report["issues"]) == (1 if task["source"] == "404" else 0)
    assert report["approval_status"] == "NOT_APPROVED" and report["shareable"] is False
    return result


def materialize(label, job, wait_seconds=90):
    result = read_owned_job(label, job, wait_seconds)
    folder, _ = owned_task(label, job)
    output = folder / "generated" / job
    output.mkdir(parents=True, exist_ok=True)
    for name, raw in (
        ("source.json", result.source),
        ("report.json", result.report),
        ("report.html", result.html),
    ):
        path = output / name
        if path.exists():
            assert path.read_bytes() == raw
        else:
            path.write_bytes(raw)
    proof = {
        "locator": result.locator,
        "editorial_selection": result.editorial_selection,
        "review_ui": "M2_CONNECTED"
        if context(label)[1]["mode"] == "M3_SYNTHETIC_BROWSER_WORKBENCH"
        else "PENDING_OWNER_MERGED_M2",
        "scope": "AUTHORIZED_LOCAL_DIAGNOSTIC_NOT_EXTERNAL_DELIVERY",
        "private_html": str(output / "report.html"),
    }
    write(output / "locator.json", proof)
    return proof


def restart_pg(label):
    folder, _ = context(label)
    request = folder / "m3-control" / (secrets.token_hex(12) + ".request.json")
    control_write(request, {"operation": "restart-pg"})
    response = request.with_name(request.name.replace(".request.json", ".response.json"))
    deadline = time.monotonic() + 150
    while not response.exists():
        ended = folder.parent / "local-launches" / label / "supervisor-end.json"
        if ended.exists():
            raise RuntimeError("M3_CONTROL_SUPERVISOR_EXIT_SEE_PRIVATE_FAILURE")
        assert time.monotonic() < deadline, "M3_RESTART_CONTROL_DEADLINE"
        time.sleep(0.25)
    return json.loads(response.read_bytes())

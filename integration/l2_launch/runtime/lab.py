"""Bounded Linux drill; reuses frozen PG/API/lease/Worker/C1/C2 components."""

from dataclasses import asdict
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from integration.ra4a import support as old
from integration.ra4b import runtime_check as native
from integration.l2_launch.runtime.adapter import LocalPolicy, PrivateAdapter, Denied
from vrae.application.ra4b_p2.m1.consumer import AppEndpoint, TaskClient

OUT = Path("/evidence")
ENV = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "PYTHONPATH": "/work",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONUNBUFFERED": "1",
    "PYTHONUTF8": "1",
    "VRAE_RA4B_TEST_ONLY": "1",
    "HOME": "/tmp",
}
CHECKS = []


def check(name, value):
    assert value, name
    CHECKS.append(name)


def low(module, uid, *args, pipe=False):
    stream = (OUT / (module.rsplit(".", 1)[-1] + "-" + str(len(native.CHILDREN)) + ".log")).open(
        "ab"
    )
    child = subprocess.Popen(
        [sys.executable, "-B", "-m", module, *args],
        cwd="/work",
        env=ENV,
        stdin=subprocess.PIPE if pipe else subprocess.DEVNULL,
        stdout=subprocess.PIPE if pipe else stream,
        stderr=stream,
        user=uid,
        group=uid,
        extra_groups=[],
    )
    stream.close()
    child.b4_uid = uid
    native.CHILDREN.append(child)
    return child


def network():
    check(
        "only_loopback_interface",
        sorted(p.name for p in Path("/sys/class/net").iterdir()) == ["lo"],
    )
    check("no_ipv4_route", len(Path("/proc/net/route").read_text().splitlines()) == 1)
    check("no_docker_socket", not Path("/var/run/docker.sock").exists())
    # Documentation and metadata IPs: no interface/route, connect cannot emit packets.
    code = """import errno,socket
for ip in ('203.0.113.1','169.254.169.254'):
 s=socket.socket();s.settimeout(1)
 try:s.connect((ip,443));raise AssertionError('EGRESS_OPEN')
 except OSError as e:assert e.errno==errno.ENETUNREACH,(ip,e.errno)
 finally:s.close()
print('NO_ROUTE_DENIED')
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=ENV,
        user=10002,
        group=10002,
        extra_groups=[],
        capture_output=True,
        timeout=5,
        check=True,
    )
    check("worker_kernel_egress_denied", result.stdout.strip() == b"NO_ROUTE_DENIED")


def draft(state, cfg, task, binding, phase):
    from tests.identity.issuer import Issuer, ISSUER, AUDIENCE
    from integration.l2.support import Issuer as ReviewIssuer

    issuer, review = Issuer(), ReviewIssuer()
    now = int(time.time())
    data = {
        "task": asdict(task),
        "app_bearer": cfg["bearer"],
        "reviewer_password": state["runtime_passwords"]["p2b1_test_a_reviewer"],
        "anchor": {
            "issuer": ISSUER,
            "audience": AUDIENCE,
            "jwks": json.loads(issuer.jwks()),
            "expires": now + 600,
        },
        "review_anchor": {
            "issuer": review.issuer,
            "audience": review.audience,
            "jwks": review.jwks,
            "expires": now + 600,
        },
        "policy_expires_at": binding["policy_expires_at"],
        "phase": phase,
    }
    child = low("integration.l2_launch.runtime.consumer", 10003, pipe=True)
    child.stdin.write(json.dumps(data).encode() + b"\n")
    child.stdin.flush()
    result = None
    for line in child.stdout:
        message = json.loads(line)
        if message["kind"] == "m1-sign":
            token = issuer.token(
                {"iat": now, "nbf": now, "exp": now + 300, "nonce": message["nonce"]}
            )
        elif message["kind"] == "c2-sign":
            token = review.token("launch-synthetic-reviewer", message["nonce"])
        elif message["kind"] == "result":
            result = message["value"]
            break
        else:
            raise AssertionError("UNKNOWN_SIGNING_REQUEST")
        child.stdin.write(json.dumps({"bearer": token}).encode() + b"\n")
        child.stdin.flush()
    check("original_signed_c1_c2_" + phase, child.wait(timeout=10) == 0 and result is not None)
    check(
        "controlled_only_" + phase,
        result["controlled_formal_human"] is False and result["external_delivery"] is False,
    )
    return result


def main():
    assert os.geteuid() == 0
    start = time.monotonic()
    state = json.load(sys.stdin)
    phase = state.pop("phase")
    OUT.mkdir(exist_ok=True)
    OUT.chmod(0o711)
    private = Path("/tmp/launch-supervisor")
    private.mkdir(mode=0o700)
    old.STATE = private / "state.json"
    old.STATE.write_text(json.dumps(state))
    old.STATE.chmod(0o600)
    native.OUT = OUT
    network()
    from importlib.metadata import version
    from packaging.requirements import Requirement

    installed = {}

    def audit_lock(path):
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("-r "):
                audit_lock(path.parent / line[3:])
                continue
            requirement = Requirement(line)
            if requirement.marker is not None and not requirement.marker.evaluate():
                continue
            actual = version(requirement.name)
            check("locked_dependency_" + requirement.name, actual in requirement.specifier)
            installed[requirement.name] = actual

    audit_lock(Path("/work/requirements-ra4b-p1.lock"))
    from integration.ra4b.support import migrate, seed
    from integration.beta_review.codex3.m3_bootstrap import install
    from integration.l2_ops.catalog import install as install_source
    from integration.l2_ops.source_profiles import selected
    from integration.l2_ops.provisioning import extend_app_sources

    source_ref, _, source = selected("industrial-p40-v3")
    if phase == "first":
        migrate()
        seed()
        install(old)
        binding = install_source(old, source, source_ref=source_ref)
        state = json.loads(old.STATE.read_bytes())
        state["launch_binding"] = binding
        consumer = OUT / "consumer"
        consumer.mkdir(mode=0o700)
        os.chown(consumer, 10003, 10003)
    else:
        binding = state["launch_binding"]
    app_path, cfg = native.provision("APP", 10001)
    extend_app_sources(
        cfg,
        {"sha256": binding["reference_sha256"], "policy_id": "pol-001", "policy_version": 1},
        source_ref=source_ref,
    )
    subprocess.run(
        [sys.executable, "-B", "-m", "integration.l2_ops.provisioning", str(app_path)],
        input=json.dumps(cfg).encode(),
        capture_output=True,
        check=True,
        env=ENV,
        user=10001,
        group=10001,
        extra_groups=[],
        timeout=10,
    )
    worker_path, _ = native.provision("WORKER", 10002)
    try:
        api, log = native.spawn("APP", app_path)
        native.wait_for(lambda: b"READY" in log.read_bytes())
        check("api_alive_" + phase, api.poll() is None)
        status, _ = native.request(
            cfg, method="GET", path="/health", overrides={"Authorization": ""}
        )
        check("missing_bearer_" + phase, status == 401)
        client = TaskClient(AppEndpoint(cfg["bearer"], "tenant-test", frozenset(cfg["sources"])))
        adapter = PrivateAdapter(client, LocalPolicy("tenant-test", time.time() + 600))
        if phase == "first":
            # Lose the FIRST response after sending a complete original request.
            body = json.dumps({"source_ref": source_ref}).encode()
            head = (
                "POST /v1/audit-requests HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nOrigin: http://127.0.0.1:8765\r\nAuthorization: Bearer "
                + cfg["bearer"]
                + "\r\nContent-Type: application/json\r\nIdempotency-Key: launch-recovery-0001\r\nContent-Length: "
                + str(len(body))
                + "\r\nConnection: close\r\n\r\n"
            ).encode()
            with socket.create_connection(("127.0.0.1", 8765), timeout=5) as sock:
                sock.sendall(head + body)
                sock.shutdown(socket.SHUT_RDWR)

            def original_admission_committed():
                with old.connect() as c:
                    return c.execute("SELECT count(*) FROM ra4a.jobs").fetchone() == (1,)

            check(
                "first_response_lost_after_original_commit",
                native.wait_for(original_admission_committed),
            )
            code, accepted, task = adapter.submit(
                "tenant-test", {"source_ref": source_ref}, "launch-recovery-0001"
            )
            check("submit_202_created_not_report", code == 202 and accepted["status"] == "CREATED")
            check(
                "idempotent_same_task",
                task
                == adapter.submit(
                    "tenant-test", {"source_ref": source_ref}, "launch-recovery-0001"
                )[2],
            )
            check(
                "idempotency_conflict",
                native.request(
                    cfg, payload={"source_ref": "accepted-404"}, key="launch-recovery-0001"
                )[0]
                == 409,
            )
            for name, action in [
                ("wrong_tenant", lambda: adapter.status("tenant-beta", task)),
                (
                    "approved_report_unavailable",
                    lambda: adapter.approved_report("tenant-test", task),
                ),
                ("cancel_not_implemented", lambda: adapter.cancel("tenant-test", task)),
            ]:
                try:
                    action()
                    raise AssertionError(name)
                except Denied as e:
                    check(name, e.status == (501 if name.startswith("cancel") else 403))
            check(
                "http_wrong_tenant",
                native.request(
                    cfg,
                    method="GET",
                    path="/v1/audit-requests/" + task.request_id,
                    overrides={"X-Tenant-ID": "tenant-beta"},
                )[0]
                in (400, 403),
            )
            from integration.l2_launch.runtime.resume import ResumeProposal

            resume = ResumeProposal(adapter)
            invitation = resume.issue_controlled("tenant-test", task)
            set_cookie, headers = resume.exchange("tenant-test", invitation)
            cookie = set_cookie.split(";", 1)[0]
            check(
                "return_cookie_private_transport_proposal",
                "HttpOnly" in set_cookie
                and "Secure" in set_cookie
                and "SameSite=Strict" in set_cookie
                and headers["Cache-Control"] == "no-store",
            )
            check(
                "return_current_original_pg_status",
                resume.status("tenant-test", cookie)[0]["request_id"] == task.request_id,
            )
            for name, action in [
                ("return_invite_replay_denied", lambda: resume.exchange("tenant-test", invitation)),
                ("return_wrong_tenant_denied", lambda: resume.status("tenant-beta", cookie)),
                (
                    "return_url_query_denied",
                    lambda: resume.status(
                        "tenant-test", cookie, query="audit_id=" + task.request_id
                    ),
                ),
                (
                    "return_id_is_not_bearer",
                    lambda: resume.status("tenant-test", "__Host-vrae-return=" + task.request_id),
                ),
                (
                    "return_restart_ends_old_cookie",
                    lambda: ResumeProposal(adapter).status("tenant-test", cookie),
                ),
            ]:
                try:
                    action()
                    raise AssertionError(name)
                except Denied as error:
                    check(name, error.code == "RETURN_ACCESS_ENDED")
            resume.revoke_all()
            try:
                resume.status("tenant-test", cookie)
                raise AssertionError("REVOKED_RETURN_ACCEPTED")
            except Denied:
                check("return_revocation_denied", True)
            pending = adapter.status("tenant-test", task)
            check(
                "queue_stall_no_false_progress",
                pending["native_job_state"] == "PENDING"
                and pending["report_available"] is False
                and pending["progress_percent"] is None,
            )
            # Drop response at the socket, then retry the SAME key; query original PG.
            sock = socket.create_connection(("127.0.0.1", 8765), timeout=5)
            body = json.dumps({"source_ref": source_ref}).encode()
            head = (
                "POST /v1/audit-requests HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nOrigin: http://127.0.0.1:8765\r\nAuthorization: Bearer "
                + cfg["bearer"]
                + "\r\nContent-Type: application/json\r\nIdempotency-Key: launch-recovery-0001\r\nContent-Length: "
                + str(len(body))
                + "\r\nConnection: close\r\n\r\n"
            ).encode()
            sock.sendall(head + body)
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
            check(
                "lost_response_retry_same_task",
                task == client.create(source_ref, idempotency_key="launch-recovery-0001"),
            )
            with old.connect() as c:
                check(
                    "one_original_job_after_retries",
                    c.execute("SELECT count(*) FROM ra4a.jobs").fetchone() == (1,),
                )
            from integration.ra4b.support import config as original_config
            from vrae.application.ra4b import store

            other = original_config("APP", "b")
            with store.connect(other) as c:
                check(
                    "pg_wrong_tenant_status_hidden", store.status(c, other, task.request_id) is None
                )
            with old.connect() as c:
                expiry = c.execute(
                    "SELECT expires_at FROM ra4a.policies WHERE tenant_id='tenant-test'"
                ).fetchone()[0]
                c.execute(
                    "UPDATE ra4a.policies SET expires_at=clock_timestamp()-interval '1 second' WHERE tenant_id='tenant-test'"
                )
                try:
                    check(
                        "expired_pg_policy_denies_submit",
                        native.request(
                            cfg, payload={"source_ref": source_ref}, key="launch-expired-0001"
                        )[0]
                        == 403,
                    )
                finally:
                    c.execute(
                        "UPDATE ra4a.policies SET expires_at=%s WHERE tenant_id='tenant-test'",
                        (expiry,),
                    )
            try:
                PrivateAdapter(client, LocalPolicy("tenant-test", time.time() - 1))
                raise AssertionError("EXPIRED_ADAPTER_ACCEPTED")
            except Denied:
                check("expired_adapter_denied", True)
            # Fixture lock prevents load; claim is the ORIGINAL committed 30s lease.
            with old.connect() as blocker, blocker.transaction():
                blocker.execute("LOCK TABLE ra4b_p2.m1_inputs IN ACCESS EXCLUSIVE MODE")
                killed = low(
                    "vrae.application.ra4b_p2.m1.runtime", 10002, "--config", str(worker_path)
                )

                def leased():
                    with old.connect() as c:
                        return c.execute(
                            "SELECT lease_until,extract(epoch FROM lease_until-clock_timestamp()) FROM ra4a.jobs WHERE state='LEASED'"
                        ).fetchone()

                lease = native.wait_for(leased, seconds=5)
                native.signal_child(killed, signal.SIGKILL)
                check("actual_worker_sigkill", killed.wait(timeout=5) == -signal.SIGKILL)
                check("original_30_second_lease", 25 < float(lease[1]) <= 30)
                with old.connect() as c:
                    check(
                        "no_result_before_commit",
                        c.execute("SELECT count(*) FROM ra4b_p2.m1_results").fetchone() == (0,),
                    )
            while time.time() <= lease[0].timestamp() + 0.15:
                time.sleep(0.1)
            worker = low("vrae.application.ra4b_p2.m1.runtime", 10002, "--config", str(worker_path))
            check("restarted_original_worker_success", worker.wait(timeout=180) == 0)
            with old.connect() as c:
                check(
                    "one_commit_attempt_two",
                    c.execute("SELECT state,lease_seq,attempts FROM ra4a.jobs").fetchone()
                    == ("TEST_ONLY_DONE", 2, 2)
                    and c.execute("SELECT count(*) FROM ra4b_p2.m1_results").fetchone() == (1,),
                )
            # Missing file is tested in an actual separate original Worker process.
            missing = low(
                "vrae.application.ra4b_p2.m1.runtime",
                10002,
                "--config",
                "/tmp/missing-launch-key.json",
            )
            check("missing_worker_secret_denied", missing.wait(timeout=10) != 0)
            state["launch_task"] = asdict(task)
        else:
            from vrae.application.ra4b_p2.m1.consumer import TaskHandle

            task = TaskHandle(**state["launch_task"])
            check(
                "old_bearer_rejected_after_restart",
                native.request(
                    cfg,
                    method="GET",
                    path="/v1/audit-requests/" + task.request_id,
                    overrides={"Authorization": "Bearer " + state["old_bearer"]},
                )[0]
                == 401,
            )
            if phase != "revoked":
                check(
                    "restored_pg_committed_task",
                    client.status(task)["job_state"] == "TEST_ONLY_DONE",
                )
        if phase == "revoked":
            check(
                "durable_pg_revocation_denies_admission",
                native.request(cfg, payload={"source_ref": source_ref}, key="launch-revoked-0001")[
                    0
                ]
                == 403,
            )
            try:
                client.status(task)
                raise AssertionError("REVOKED_STATUS_ACCEPTED")
            except ValueError:
                check("durable_pg_revocation_denies_status", True)
            result = {"revoked": True}
        else:
            result = draft(state, cfg, task, binding, phase)
            state["old_bearer"] = cfg["bearer"]
            if phase == "restore":
                # A TEST_ONLY admin fixture revokes original PG policy; no lease or report bytes rewritten.
                with old.connect() as c:
                    c.execute(
                        "UPDATE ra4a.policies SET status='REVOKED' WHERE tenant_id='tenant-test'"
                    )
        (OUT / "private-state.json").write_text(json.dumps(state))
        (OUT / "private-state.json").chmod(0o600)
        with old.connect() as c:
            db_bytes = c.execute("SELECT pg_database_size(current_database())").fetchone()[0]
        native.publish(
            phase + "-result.json",
            {
                "phase": phase,
                "native_python": sys.version,
                "locked_dependencies_measured": installed,
                "checks": CHECKS,
                "result": result,
                "elapsed_seconds": time.monotonic() - start,
                "database_bytes_measured": db_bytes,
                "candidate": "R1B_PRIVATE_RUNTIME_CANDIDATE_DEPLOYMENT_GO_PENDING",
                "release_status": "R1_ENGINEERING_CANDIDATE_NO_LIVE_SOURCE_NO_EXTERNAL_RELEASE",
                "model_calls_measured": 0,
                "cloud_resources_created": 0,
                "money_status": "UNKNOWN",
                "pg_roles_restore": "SAME_ISOLATED_CLUSTER_NOT_FULL_DISASTER_RECOVERY",
                "identity_restart": "FRESH_SYNTHETIC_KEYS_NOT_DURABLE_OIDC",
            },
        )
    finally:
        for child in reversed(native.CHILDREN):
            native.signal_child(child, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                native.signal_child(child, signal.SIGKILL)
                child.wait(timeout=5)


if __name__ == "__main__":
    main()

"""Real accepted-port evidence. PASS here is a permission audit, not S2 PASS."""

import http.client
from contextlib import closing
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time

import psycopg
import pytest

from integration.ra4a import support
from integration.ra4b import support as bootstrap
from integration.ra4b.runtime_check import signal_child
from vrae.application.ra4b import store

OUT = Path("/evidence")


@pytest.fixture(scope="module")
def runtime():
    assert os.getuid() == 0 and sorted(p.name for p in Path("/sys/class/net").iterdir()) == ["lo"]
    assert not Path("/var/run/docker.sock").exists()
    private = Path("/tmp/s2-supervisor")
    private.mkdir(mode=0o700)
    support.STATE = private / "state.json"
    state = json.loads(sys.stdin.read())
    support.STATE.write_text(json.dumps(state))
    support.STATE.chmod(0o600)
    # Accepted fixture module imports this path by value; set it before import.
    from integration.ra4a import p2a_support, p2b1_support

    p2a_support.STATE = p2b1_support.STATE = support.STATE
    bootstrap.migrate()
    bootstrap.seed()
    children = []
    held = {}

    def spawn(kind, *args):
        uid = 10001 if kind == "APP" else 10002
        cfg = bootstrap.config("WORKER" if kind == "S2_WORKER" else kind)
        if kind == "APP":
            cfg["bearer"] = secrets.token_urlsafe(40)
        directory = Path("/tmp/s2-" + kind.lower() + "-" + str(len(children)))
        directory.mkdir(mode=0o700)
        path = directory / "config.json"
        path.write_text(json.dumps(cfg))
        path.chmod(0o600)
        os.chown(path, uid, uid)
        os.chown(directory, uid, uid)
        log = (OUT / (kind.lower() + "-" + str(len(children)) + ".log")).open("wb")
        module = (
            "vrae.application.ra4b_p2.worker"
            if kind == "S2_WORKER"
            else "apps.api.ra4b"
            if kind == "APP"
            else "worker.ra4b.main"
        )
        if kind == "S2_WORKER":
            receipt = directory / "private-worker.json"
            args = (*args, "--private-receipt", str(receipt))
            held["S2_WORKER_RECEIPT_PATH"] = str(receipt)
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "PYTHONPATH": "/work",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
            "PYTHONUTF8": "1",
            "VRAE_RA4B_TEST_ONLY": "1",
            "HOME": "/tmp",
        }
        p = subprocess.Popen(
            [sys.executable, "-m", module, "--config", str(path), *args],
            user=uid,
            group=uid,
            extra_groups=[],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
        )
        children.append((p, log))
        p.b4_uid = uid
        held[kind] = cfg
        return p

    app = spawn("APP")
    deadline = time.monotonic() + 8
    while True:
        try:
            with closing(http.client.HTTPConnection("127.0.0.1", 8765, timeout=1)) as c:
                c.connect()
            break
        except OSError:
            assert app.poll() is None and time.monotonic() < deadline
            time.sleep(0.05)
    value = {"held": held, "spawn": spawn, "denials": []}
    try:
        yield value
    finally:
        for p, log in children:
            if p.poll() is None:
                signal_child(p, signal.SIGTERM)
            p.wait(timeout=15)
            log.close()
        (OUT / "port-audit.json").write_text(
            json.dumps(
                {
                    k: v
                    for k, v in value.items()
                    if k not in ("held", "spawn", "lease", "candidate")
                },
                default=str,
                indent=2,
            )
        )
        state = json.loads(support.STATE.read_bytes())
        (OUT / "private-credential-scan-values.json").write_text(
            json.dumps(
                [
                    state["admin_password"],
                    *state["runtime_passwords"].values(),
                    held["APP"]["bearer"],
                    *held.get("extra_secret_values", []),
                ]
            )
        )


def test_committed_app_202_precedes_original_uid_worker_done(runtime):
    cfg = runtime["held"]["APP"]
    headers = {
        "Host": "127.0.0.1:8765",
        "Origin": "http://127.0.0.1:8765",
        "Authorization": "Bearer " + cfg["bearer"],
        "Content-Type": "application/json",
        "Idempotency-Key": "s2-port-audit-real-0001",
    }
    with closing(http.client.HTTPConnection("127.0.0.1", 8765, timeout=5)) as c:
        c.request("POST", "/v1/audit-requests", json.dumps({"source_ref": "accepted-404"}), headers)
        response = c.getresponse()
        result = json.loads(response.read())
    assert response.status == 202
    with store.connect(cfg) as c:
        before = store.status(c, cfg, result["request_id"])
    assert before["job_state"] == "PENDING"
    worker = runtime["spawn"]("WORKER", "--once", "--lease-seconds", "30")
    worker.wait(timeout=30)
    assert worker.returncode == 0
    with store.connect(cfg) as c:
        after = store.status(c, cfg, result["request_id"])
    assert after["job_state"] == "TEST_ONLY_DONE" and after["lease_seq"] == 1
    assert all(before[k] == after[k] == result[k] for k in ("request_id", "run_id", "job_id"))
    runtime["committed_app_and_worker"] = {
        "http": 202,
        "before": before,
        "after": after,
        "worker_uid": 10002,
        "generated_result": "NOT_PRODUCED_BY_ORIGINAL_ENTRYPOINT",
    }


def test_claim_and_finish_are_the_only_current_worker_ports(runtime):
    cfg = bootstrap.config("WORKER")
    with store.connect(cfg) as c:
        ports = c.execute(
            "SELECT p.proname,pg_get_function_result(p.oid) FROM pg_proc p WHERE p.pronamespace='ra4b_test'::regnamespace AND has_function_privilege(session_user,p.oid,'EXECUTE') ORDER BY 1"
        ).fetchall()
        identity = c.execute("SELECT session_user,current_user").fetchone()
    assert [p[0] for p in ports] == ["claim", "finish"]
    assert identity == ("ra4b_test_a_worker", "ra4b_test_a_worker")
    assert (
        "lease_token uuid" in ports[0][1]
        and "source_ref" not in ports[0][1]
        and "epoch" not in ports[0][1]
    )
    runtime["worker_ports"] = ports


@pytest.mark.parametrize("uid", [10001, 10002])
def test_low_uid_cannot_read_supervisor_bootstrap_credentials(runtime, uid):
    assert support.STATE.parent.stat().st_mode & 0o777 == 0o700
    # Accepted migration helpers rewrite the state file without exposing its
    # enclosing root-only directory. Neither actual runtime UID can traverse it.
    code = "from pathlib import Path; import sys\ntry: Path(sys.argv[1]).read_bytes()\nexcept PermissionError: sys.exit(0)\nelse: sys.exit(1)"
    p = subprocess.run(
        [sys.executable, "-c", code, str(support.STATE)],
        user=uid,
        group=uid,
        extra_groups=[],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert p.returncode == 0 and p.stdout == p.stderr == b""


@pytest.mark.parametrize(
    "query",
    [
        "SELECT source_ref FROM ra4a.requests LIMIT 1",
        "SELECT epoch FROM ra4b_test.origin_epochs LIMIT 1",
        "SELECT * FROM ra4a_bytes.read_graph('tenant-test','accepted-404','not-authority','not-authority',1,repeat('0',64))",
        "SELECT ra4a_bytes.register('tenant-test','accepted-404',NULL,NULL,NULL,NULL,NULL)",
    ],
)
def test_original_worker_source_epoch_and_result_write_are_42501(runtime, query):
    with store.connect(bootstrap.config("WORKER")) as c:
        with pytest.raises(psycopg.Error) as error:
            c.execute(query)
    assert error.value.sqlstate == "42501"
    runtime["denials"].append(
        {"kind": "WORKER_MISSING_PORT", "sqlstate": error.value.sqlstate, "query": query}
    )


def test_current_reviewer_cannot_read_b4_status_or_origin(runtime):
    role = "p2b1_test_a_reviewer"
    for query in (
        "SELECT * FROM ra4b_test.status('tenant-test',gen_random_uuid())",
        "SELECT epoch FROM ra4b_test.origin_epochs LIMIT 1",
    ):
        with support.connect(role) as c:
            assert c.execute("SELECT session_user,current_user").fetchone() == (role, role)
            with pytest.raises(psycopg.Error) as error:
                c.execute(query)
        assert error.value.sqlstate == "42501"
        runtime["denials"].append(
            {"kind": "REVIEWER_MISSING_B4_PORT", "sqlstate": "42501", "query": query}
        )


def test_no_existing_authoritative_generated_result_namespace(runtime):
    with store.connect(bootstrap.config("WORKER")) as c:
        assert c.execute("SELECT to_regnamespace('ra4b_p2')").fetchone() == (None,)
    runtime["missing_ports"] = [
        "ra4b_p2.load_leased_source",
        "ra4b_p2.commit_generated_result",
        "ra4b_p2.read_assigned_generated_result",
    ]

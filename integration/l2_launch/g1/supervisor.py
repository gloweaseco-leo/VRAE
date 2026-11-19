"""T0 owned network-none supervisor. Real HTTP/PG/Worker, no G1 PASS claim."""

import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
from threading import Thread
import time
from datetime import datetime, UTC, timedelta

ROOT = Path("/evidence/.private-root")
OUT = Path("/evidence")
CHILDREN = []
ENV = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "PYTHONPATH": "/work",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONUNBUFFERED": "1",
    "PYTHONUTF8": "1",
    "VRAE_RA4B_TEST_ONLY": "1",
    "HOME": "/tmp",
}


def write(path, value):
    path.write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf8")
    path.chmod(0o600)


def wait(predicate, seconds=30):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("G1_BOUNDED_WAIT_FAILED")


def provision(name, uid, cfg, cert=None):
    directory = Path("/tmp/g1-" + name)
    directory.mkdir(mode=0o700)
    if cert:
        for source, key in ((cert["certificate"], "certificate"), (cert["key"], "certificate_key")):
            path = directory / Path(source).name
            shutil.copyfile(source, path)
            path.chmod(0o600)
            os.chown(path, uid, uid)
            cfg[key] = str(path)
    path = directory / "config.json"
    write(path, cfg)
    os.chown(path, uid, uid)
    os.chown(directory, uid, uid)
    return path


def spawn(name, uid, config, module):
    log = ROOT / (name + "-" + str(len(CHILDREN)) + ".log")
    with log.open("wb") as stream:
        child = subprocess.Popen(
            [sys.executable, "-m", module, "--config", str(config)],
            env=ENV,
            cwd="/work",
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=stream,
            user=uid,
            group=uid,
            extra_groups=[],
        )
    child.uid = uid
    CHILDREN.append(child)
    return child, log


def stop(child, number=signal.SIGTERM):
    if child.poll() is None:
        subprocess.run(
            [
                sys.executable,
                "-c",
                "import os,sys;os.kill(int(sys.argv[1]),int(sys.argv[2]))",
                str(child.pid),
                str(int(number)),
            ],
            env=ENV,
            user=child.uid,
            group=child.uid,
            extra_groups=[],
            capture_output=True,
            check=True,
        )
        child.wait(timeout=5)


def main():
    assert os.geteuid() == 0
    ROOT.mkdir(mode=0o700)
    OUT.mkdir(exist_ok=True)
    OUT.chmod(0o711)
    from integration.ra4a import support as old

    old.STATE = ROOT / "state.json"
    state = json.load(sys.stdin)
    write(old.STATE, state)
    # All support modules with import-by-value STATE are loaded only after bind.
    from integration.l2_launch.g1.bootstrap import install, hydrate

    state = install(old)
    from integration.l2_launch.g1.network import install as fence

    network = fence()
    from integration.ra4b.support import config

    app = config("APP")
    app["bearer"] = secrets.token_urlsafe(40)
    app["sources"].update({v["source_ref"]: v["binding"] for v in state["g1_plans"].values()})
    app_path = provision("app", 10001, app)
    worker_path = provision("worker", 10002, config("WORKER"))
    api, api_log = spawn("app", 10001, app_path, "apps.api.ra4b")
    wait(lambda: b"RA4B_LOOPBACK_TEST_ONLY_READY" in api_log.read_bytes())
    from tests.identity.issuer import Issuer, ISSUER, AUDIENCE
    from integration.l2.support import Issuer as ReviewIssuer
    from integration.l2_launch.g1.fixture_keys import FixtureAuthority
    from integration.l2_launch.g1.broker import NonceBroker
    from vrae.application.ra4b_p2.m1.consumer import TaskClient, AppEndpoint

    issuer, review, authority = Issuer(), ReviewIssuer(), FixtureAuthority()
    client = TaskClient(AppEndpoint(app["bearer"], "tenant-test", frozenset(app["sources"])))
    broker_dir = Path("/tmp/g1-broker")
    broker_dir.mkdir(mode=0o711)

    def read_task(task):
        with old.connect() as c:
            row = c.execute(
                "SELECT j.state FROM ra4a.jobs j JOIN ra4a.runs r USING(tenant_id,run_id) JOIN ra4a.requests q USING(tenant_id,request_id) WHERE j.tenant_id=%s AND j.job_id=%s AND j.run_id=%s AND r.request_id=%s AND q.source_ref=%s",
                (task.tenant_id, task.job_id, task.run_id, task.request_id, task.source_ref),
            ).fetchone()
            if row != ("TEST_ONLY_DONE",):
                raise ValueError("G1_ORIGINAL_CURRENT_TASK_REQUIRED")

    broker = NonceBroker(str(broker_dir / "nonce.sock"), client, issuer, review, read_task)
    Thread(target=broker.serve, daemon=True).start()
    from integration.l2_launch.g1.tls import create

    tls = create(ROOT / "tls")
    # Only public CA is shared; leaf private keys move to their own UID dirs.
    ca = Path("/tmp/g1-ca.pem")
    shutil.copyfile(tls["ca"], ca)
    ca.chmod(0o644)
    token = secrets.token_urlsafe(40)
    owner = secrets.token_urlsafe(40)
    routing = secrets.token_urlsafe(40)
    now = int(time.time())
    realm = {
        "epoch": 1,
        "service_hash": hashlib.sha256(token.encode()).hexdigest(),
        "controller_expires": now + 1800,
        "keys": authority.public(),
    }
    from psycopg.types.json import Jsonb

    with old.connect() as c:
        c.execute("INSERT INTO g1_http.settings VALUES(%s,%s)", ("realm", Jsonb(realm)))
    report = Path("/tmp/g1-reports")
    report.mkdir(mode=0o700)
    os.chown(report, 10003, 10003)
    cfg = {
        "mode": "OFFLINE_SYNTHETIC",
        "bind": "127.0.0.1",
        "live": False,
        "tenant": "tenant-test",
        "meta_role": "g1_http_a",
        "meta_password": state["runtime_passwords"]["g1_http_a"],
        "app_bearer": app["bearer"],
        "source_refs": list(app["sources"]),
        "service_token": token,
        "source_sha": state["g1_source_sha"]
        if not state["g1_source_dirty"]
        else "UNCOMMITTED_WORKING_SOURCE",
        "owned_run_id": state["g1_owned_run_id"],
        "owner_token": owner,
        "epoch": 1,
        "routing_key": routing,
        "broker": str(broker_dir / "nonce.sock"),
        "report_root": str(report),
        "origins": ["https://127.0.0.1:8766", "https://127.0.0.1:8767"],
        "reviewer_password": state["runtime_passwords"]["p2b1_test_a_reviewer"],
        "m1_anchor": {
            "issuer": ISSUER,
            "audience": AUDIENCE,
            "jwks": json.loads(issuer.jwks()),
            "expires": now + 1800,
        },
        "review_anchor": {
            "issuer": review.issuer,
            "audience": review.audience,
            "jwks": review.jwks,
            "expires": now + 1800,
        },
    }
    facade_path = provision("facade", 10003, cfg, tls["facade"])
    facade, facade_log = spawn("facade", 10003, facade_path, "integration.l2_launch.g1.http_server")
    wait(lambda: b"G1_REAL_LOOPBACK_TLS_READY" in facade_log.read_bytes())
    vf_cfg = {
        "ca": str(ca),
        "facade_pin": tls["facade"]["der_sha256"],
        "service_token": token,
        "source_sha": cfg["source_sha"],
    }
    vf_path = provision("vf", 10004, vf_cfg, tls["vf"])
    vf, vf_log = spawn("vf", 10004, vf_path, "integration.l2_launch.g1.vf_stub")
    wait(lambda: b"G1_VF_SYNTHETIC_SERVER_READY" in vf_log.read_bytes())
    from integration.l2_launch.g1.client import Client
    from integration.l2_launch.g1.fixtures import submission, return_grant
    from contracts.l2_launch.contract import digest, validate

    vf_client = Client(8767, str(ca), tls["vf"]["der_sha256"])
    owner_client = Client(8766, str(ca), tls["facade"]["der_sha256"], owner_token=owner)
    checks = []
    tasks = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
        print(json.dumps({"check": name, "status": "PASS"}), flush=True)

    def call(method, path, body=None, **kwargs):
        result = vf_client.request(method, path, body, **kwargs)
        write(OUT / "http.json", vf_client.trace + owner_client.trace)
        return result

    # Real kernel denial: worker UID cannot reach APP or metadata/facade.
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import socket; s=socket.socket();s.settimeout(1);s.connect(('127.0.0.1',8765))",
        ],
        user=10002,
        group=10002,
        extra_groups=[],
        env=ENV,
        capture_output=True,
    )
    check("WORKER_KERNEL_APP_BYPASS_DENIED", probe.returncode != 0)
    for kind in (
        ("manufacturer",)
        if "--quick" in sys.argv
        else ("manufacturer", "distributor", "forbidden", "robots", "unknown")
    ):
        with old.connect() as c:
            plan = hydrate(
                c.execute(
                    "SELECT document FROM g1_http.sourceplans WHERE source_ref=%s",
                    ("g1-recorded-" + kind,),
                ).fetchone()[0]
            )
        body, invitation = submission(plan, authority)
        with old.connect() as c:
            c.execute(
                "INSERT INTO g1_http.invitations VALUES(%s,%s,%s)",
                (body["invitation_ref"], "tenant-test", Jsonb(invitation)),
            )
        if kind == "manufacturer":
            from copy import deepcopy

            missing = deepcopy(body)
            missing["invitation_ref"] = "missing-invitation-g1"
            check("NO_INVITATION_HTTP403", call("POST", "/v1/audit-requests", missing)[0] == 403)
            wrong = deepcopy(body)
            wrong["command"]["request"]["tenant_id"] = "tenant-beta"
            check("WRONG_TENANT_HTTP403", call("POST", "/v1/audit-requests", wrong)[0] == 403)
            forged = deepcopy(body)
            forged["command"]["request"]["site_url"] = "http://169.254.169.254/"
            check(
                "FORGED_SOURCE_SCOPE_HTTP403", call("POST", "/v1/audit-requests", forged)[0] == 403
            )
            check(
                "UNKNOWN_PROFILE_HTTP406",
                call("POST", "/v1/audit-requests", body, headers={"Accept": "*/*"})[0] == 406,
            )
            check(
                "WRONG_CONTENT_TYPE_HTTP415",
                call(
                    "POST", "/v1/audit-requests", body, headers={"Content-Type": "application/json"}
                )[0]
                == 415,
            )
        code, accepted, _ = call("POST", "/v1/audit-requests", body)
        check(kind + "_HTTP202", code == 202)
        validate("VFAccepted", accepted)
        ref = accepted["audit_ref"]
        with old.connect() as c:
            native = c.execute(
                "SELECT native_task FROM g1_http.admissions WHERE audit_ref=%s", (ref,)
            ).fetchone()[0]
            job = c.execute(
                "SELECT state,attempts FROM ra4a.jobs WHERE job_id=%s", (native["job_id"],)
            ).fetchone()
            check(
                kind + "_ORIGINAL_PG_COMMITTED_BEFORE202",
                job == ("PENDING", 0) and native["run_id"] == accepted["run_id"],
            )
        code, retry, _ = call("POST", "/v1/audit-requests", body)
        check(kind + "_IDEMPOTENT_SAME_RECEIPT", code == 202 and retry == accepted)
        if kind == "manufacturer":
            from contracts.l2_launch.contract import permission_document
            from contracts.l2_launch.vf_b import submission_document

            variant, vi = submission(plan, authority)
            variant["command"]["request"]["idempotency_key"] = body["command"]["request"][
                "idempotency_key"
            ]
            vi["request_sha256"] = digest(variant["command"]["request"])
            variant["command"]["permission_reference"]["proof"] = authority.sign(
                "permission", "permission", permission_document(variant["command"], plan.policy)
            )
            variant["submission_proof"] = authority.sign(
                "permission", "permission", submission_document(variant)
            )
            with old.connect() as c:
                c.execute(
                    "INSERT INTO g1_http.invitations VALUES(%s,%s,%s)",
                    (variant["invitation_ref"], "tenant-test", Jsonb(vi)),
                )
            check(
                "SAME_KEY_VALID_CHANGED_INTENT_HTTP409",
                call("POST", "/v1/audit-requests", variant)[0] == 409,
            )
            quota, qi = submission(plan, authority)
            with old.connect() as c:
                c.execute(
                    "INSERT INTO g1_http.invitations VALUES(%s,%s,%s)",
                    (quota["invitation_ref"], "tenant-test", Jsonb(qi)),
                )
            check(
                "CURRENT_ORIGINAL_QUEUE_QUOTA_HTTP429",
                call("POST", "/v1/audit-requests", quota)[0] == 429,
            )
            bare = Client(8767, str(ca), tls["vf"]["der_sha256"])
            check("BARE_AUDIT_REF_HTTP403", bare.request("GET", "/v1/audits/" + ref)[0] == 403)
        token_return, grant, proof = return_grant(ref, body["subject_ref"], plan.policy, authority)
        code, _, _ = owner_client.request(
            "POST",
            "/__fixture__/return-grants/" + ref,
            {"grant": grant, "proof": proof},
            owner=True,
        )
        check(kind + "_SEPARATE_OWNER_RETURN_GRANT", code == 201)
        check(kind + "_CHALLENGE", call("GET", "/v1/return-challenge")[0] == 200)
        check(
            kind + "_ACTUAL_COOKIE_EXCHANGE",
            call("POST", "/v1/audits/" + ref + "/return/exchange", {"return_token": token_return})[
                0
            ]
            == 200,
        )
        check(
            kind + "_REAL_STATUS_QUEUED",
            call("GET", "/v1/audits/" + ref)[1].get("task", {}).get("status") == "QUEUED",
        )
        if kind == "manufacturer":
            check(
                "UNFINISHED_NEVER_COMPLETED",
                call("GET", "/v1/audits/" + ref)[1].get("display_state") == "accepted",
            )
            check(
                "ACTUAL_CSRF_DENIED",
                call("GET", "/v1/audits/" + ref, headers={"X-G1-CSRF": "wrong-token"})[0] == 403,
            )
            check(
                "EXCHANGED_RETURN_TOKEN_REPLAY_DENIED",
                call(
                    "POST", "/v1/audits/" + ref + "/return/exchange", {"return_token": token_return}
                )[0]
                == 403,
            )
        worker, log = spawn("worker", 10002, worker_path, "integration.l2_launch.g1.worker")
        worker.wait(timeout=30)
        check(kind + "_ORIGINAL_WORKER_COMMIT", worker.returncode == 0)
        with old.connect() as c:
            actual = c.execute(
                "SELECT state,attempts FROM ra4a.jobs WHERE job_id=%s", (native["job_id"],)
            ).fetchone()
            results = c.execute(
                "SELECT count(*) FROM ra4b_p2.m1_results WHERE job_id=%s", (native["job_id"],)
            ).fetchone()[0]
            check(
                kind + "_SINGLE_ORIGINAL_RESULT", actual == ("TEST_ONLY_DONE", 1) and results == 1
            )
        code, status, _ = call("GET", "/v1/audits/" + ref)
        check(kind + "_CURRENT_HTTP_STATUS", code == 200)
        check(
            kind + "_UNPUBLISHED_REPORT_DENIED",
            call("GET", "/v1/audits/" + ref + "/report")[0] == 403,
        )
        if kind in ("manufacturer", "distributor"):
            code, pins, _ = owner_client.request(
                "GET", "/__fixture__/audits/" + ref + "/pins", owner=True
            )
            check(
                kind + "_ORIGINAL_C2_FIVE_DIMENSIONS",
                code == 200
                and pins.get("original_findings", 0) > 5
                and pins.get("blueprint_packages") == 7,
            )
            check(
                kind + "_CONTROLLED_REVIEW_ONLY",
                owner_client.request(
                    "POST",
                    "/__fixture__/audits/" + ref + "/review",
                    {"pins": pins, "action": "APPROVE_SYNTHETIC_ONLY"},
                    owner=True,
                )[0]
                == 200,
            )
            document = {
                "tenant_id": "tenant-test",
                "audit_ref": ref,
                "subject_ref": body["subject_ref"],
                "purpose": "SYNTHETIC_PREVIEW_ONLY",
                "pins": pins,
                "expires_at": (datetime.now(UTC) + timedelta(minutes=4)).isoformat(),
            }
            check(
                kind + "_OWNER_PREVIEW_PERMIT",
                owner_client.request(
                    "POST",
                    "/__fixture__/audits/" + ref + "/preview-permit",
                    {"document": document, "proof": authority.sign("owner", "share", document)},
                    owner=True,
                )[0]
                == 201,
            )
            code, preview, _ = call(
                "GET",
                "/__synthetic__/audits/" + ref + "/preview",
                headers={"If-Match": pins["view_sha256"]},
            )
            check(
                kind + "_SAME_TASK_SYNTHETIC_PREVIEW",
                code == 200
                and preview.get("audit_ref") == ref
                and digest(preview) == pins["view_sha256"],
            )
            check(
                kind + "_STALE_VIEW_DENIED",
                call(
                    "GET",
                    "/__synthetic__/audits/" + ref + "/preview",
                    headers={"If-Match": "0" * 64},
                )[0]
                == 409,
            )
            check(
                kind + "_STILL_UNPUBLISHED", call("GET", "/v1/audits/" + ref + "/report")[0] == 403
            )
        with old.connect() as c:
            receipt = c.execute(
                "SELECT source_sha256,report_sha256,html_sha256,input_sha256,reference_sha256,policy_id,policy_version,lease_seq,transaction_id,lease_until,created_at,source_record FROM ra4b_p2.m1_results WHERE job_id=%s",
                (native["job_id"],),
            ).fetchone()
        actual_pack = json.loads(bytes(receipt[-1]))["pack"]
        check(
            kind + "_FRESH_SAME_RUN_PACK",
            actual_pack["run_id"] == native["run_id"]
            and actual_pack["run_id"] != plan.native.pack.document["run_id"],
        )
        if kind == "manufacturer":
            code, bundle, _ = owner_client.request(
                "GET", "/__fixture__/audits/" + ref + "/evidence", owner=True
            )
            from vrae.domain.reviews import report_content_hash

            check(
                "PRIVATE_ORIGINAL_BUNDLE_SAME_NATIVE_RUN",
                code == 200
                and bundle["report"]["run_id"] == native["run_id"]
                and bundle["source_command"] == body["command"],
            )
            check(
                "PRIVATE_BUNDLE_PRESERVES_CONTROLLED_REVIEW_NOT_RELEASE",
                bundle["report"]["status"] == "REVIEW_REQUIRED"
                and bundle["controlled_review"]["formal_human_review"] is False
                and bundle["external_release"] is False,
            )
            check(
                "PRIVATE_BUNDLE_ORIGINAL_FACT_CONTENT_HASH",
                report_content_hash(bundle["report"], bundle["findings"])
                == bundle["report"]["content_hash"],
            )
        tasks.append(
            {
                "kind": kind,
                "audit_ref": ref,
                **native,
                "status": status,
                "original_pg_commit": dict(
                    zip(
                        (
                            "source_sha256",
                            "report_sha256",
                            "html_sha256",
                            "capture_digest",
                            "reference_sha256",
                            "policy_id",
                            "policy_version",
                            "lease_seq",
                            "transaction_id",
                            "lease_until",
                            "committed_at",
                        ),
                        receipt[:-1],
                    )
                ),
                "actual_pack_run_id": actual_pack["run_id"],
                "source_policy_sha256": digest(plan.policy),
                "permission_sha256": digest(body["command"]["permission_reference"]),
                "signed_intent_sha256": digest(body),
                "template_pack_ref": plan.native.pack.ref,
                "report_pins": pins if kind in ("manufacturer", "distributor") else None,
            }
        )
    check(
        "SOURCE_SHA_HTTP_HEADER_MATCHES_RUNTIME",
        all(
            event["source_sha"] == cfg["source_sha"]
            for event in vf_client.trace + owner_client.trace
        ),
    )
    check(
        "SINGLE_TRUTHFUL_NO_MODEL_HTTP_HEADER",
        all(event["ai_state"] == "NO_MODEL" for event in vf_client.trace + owner_client.trace),
    )
    write(
        OUT / "t0.json",
        {
            "scope": "T0_PARTIAL_REAL_HTTP_NOT_G1_PASS",
            "checks": checks,
            "tasks": tasks,
            "network": network,
            "ai_state": "NO_MODEL",
            "live_capture": False,
            "public_release": False,
            "pending": [
                "Chrome four viewports",
                "kill lease reclaim deadletter",
                "full runtime/PG container recreation and restore",
                "key rotation",
                "inquiry retry WAITING_ACK",
                "Owner exact-head final acceptance",
                "independent exact SHA reviews",
            ],
        },
    )
    write(OUT / "http.json", vf_client.trace + owner_client.trace)
    print('{"stage":"G1_T0_REAL_HTTP_SLICE_COMPLETE","g1_final_pass":false}', flush=True)
    if "--hold" in sys.argv or "--recovery" in sys.argv:
        from integration.l2_launch.g1.owner_cli import serve

        print('{"stage":"G1_LOCAL_OWNER_CONSOLE_STARTING","public":false}', flush=True)

        def lifecycle(operation):
            nonlocal facade, facade_log
            if operation == "service-down":
                stop(facade)
            elif operation == "service-up":
                if facade.poll() is None:
                    raise ValueError("FACADE_ALREADY_RUNNING")
                facade, facade_log = spawn(
                    "facade-restarted", 10003, facade_path, "integration.l2_launch.g1.http_server"
                )
                wait(lambda: b"G1_REAL_LOOPBACK_TLS_READY" in facade_log.read_bytes())
            else:
                raise ValueError("FIXTURE_OPERATION_DENIED")
            return {"controlled_service_operation": operation, "running": facade.poll() is None}

        serve(old, authority, ca, tls, owner, worker_path, hydrate, spawn, lifecycle)


if __name__ == "__main__":
    try:
        main()
    finally:
        for child in reversed(CHILDREN):
            try:
                stop(child)
            except Exception:
                pass

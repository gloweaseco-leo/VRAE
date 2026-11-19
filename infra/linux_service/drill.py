"""Exercise the actual deployment control script on owned local resources."""

import hashlib
import io
import json
import subprocess
import sys
import tarfile
import time
import uuid
from infra.linux_service import control as ctl
from infra.linux_service.build import build


def exercise(docker, seed, image, private, public, state):
    owner = "vrae-service-" + uuid.uuid4().hex[:10]
    restored = owner + "-restore"
    config = private / "service-inputs"
    backup = private / "cold-backup"
    completed = False
    events = []
    cleanup = []
    retained = None

    def wait(predicate, seconds=90):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if predicate():
                return
            time.sleep(0.5)
        raise RuntimeError("SERVICE_DRILL_BOUNDED_WAIT")

    def runtime_ok(n):
        d = ctl.inspect("container", n["runtime"])
        if not d["State"]["Running"] or d.get("RestartCount", 0) > 0:
            raise RuntimeError("PERSISTENT_RUNTIME_EXITED")
        probe = subprocess.run(
            ["docker", "exec", n["runtime"], "test", "-f", "/run/service/ready.json"],
            capture_output=True,
        )
        return probe.returncode == 0

    def fixture_site(n):
        wait(
            lambda: (
                subprocess.run(
                    ["docker", "exec", n["runtime"], "test", "-f", "/tmp/lab/ready"],
                    capture_output=True,
                ).returncode
                == 0
            )
        )

    def attach(n):
        networks = json.loads(
            docker("inspect", "--format", "{{json .NetworkSettings.Networks}}", seed["client"])
        )
        for net in networks:
            docker("network", "disconnect", net, seed["client"])
        docker("network", "connect", n["net"], seed["client"])

    def client(n, phase, report=False):
        wait(lambda: runtime_ok(n))
        # Readiness is an actual external mTLS request, not parent ready metadata.
        for _ in range(30):
            cmd = [
                "docker",
                "exec",
                "-u",
                "10004",
                seed["client"],
                "python",
                "-m",
                "infra.linux_service.client"
                if report
                else "integration.authorized_targets.checks.external_client",
                phase,
            ]
            result = subprocess.run(cmd, capture_output=True)
            if result.returncode == 0:
                d = json.loads(result.stdout)
                events.append(d)
                return d
            # Retry transport startup only, never retry a failed business assertion.
            if b"ConnectionRefusedError" not in result.stderr:
                break
            time.sleep(0.2)
        (private / ("persistent-" + phase + ".stderr")).write_bytes(result.stderr)
        raise RuntimeError("PERSISTENT_EXTERNAL_" + phase + "_RED")

    try:
        docker("cp", seed["runtime"] + ":/evidence/service-operator", str(config))
        # Build has a git-tracked-only context; operator secrets cannot enter it.
        tag = "vrae-service-drill:" + owner
        build(image, tag)
        service_image = ctl.inspect("image", tag)["Id"]
        manifest = json.loads((config / "manifest.json").read_bytes())
        manifest["image"] = service_image
        (config / "manifest.json").write_text(json.dumps(manifest))
        (config / "manifest.json").chmod(0o600)
        # Cold-transfer the controlled seed's original PG volume, preserving all IDs.
        docker(
            "exec",
            "-u",
            "postgres",
            seed["pg"],
            "pg_ctl",
            "-D",
            "/var/lib/postgresql/data",
            "-m",
            "fast",
            "-w",
            "stop",
        )
        docker("stop", "-t", "10", seed["pg"])
        backup.mkdir(mode=0o700)
        raw = ctl.volume_archive(seed["data"], image)
        (backup / "data.tar.gz").write_bytes(raw)
        empty = io.BytesIO()
        with tarfile.open(fileobj=empty, mode="w:gz"):
            pass
        (backup / "ledger.tar.gz").write_bytes(empty.getvalue())
        (backup / "backup.json").write_text(
            json.dumps(
                {
                    "files": {
                        f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in backup.iterdir()
                    }
                }
            )
        )
        n = ctl.restore(owner, config, backup)
        attach(n)
        wait(lambda: runtime_ok(n))
        fixture_site(n)
        client(n, "restart")
        client(n, "prepare", report=True)
        repeat = subprocess.run(
            [
                "docker",
                "exec",
                "-u",
                "10004",
                seed["client"],
                "python",
                "-m",
                "infra.linux_service.repeat",
            ],
            capture_output=True,
        )
        (private / "continuous-worker.stderr").write_bytes(repeat.stderr)
        if repeat.returncode:
            raise RuntimeError("CONTINUOUS_NEW_TASKS_RED")
        events.append(json.loads(repeat.stdout))

        def ai_ready():
            count = (
                ctl.docker(
                    "exec",
                    "-u",
                    "postgres",
                    n["pg"],
                    "psql",
                    "-U",
                    "postgres",
                    "-d",
                    "vrae_ra4a_p1",
                    "-Atc",
                    "SELECT count(*) FROM target_v1.ai_receipts WHERE operation_id LIKE 'service-ai-%' AND tenant_id='tenant-beta' AND state='AI_UNAVAILABLE' AND receipt->>'reason'='PROVIDER_GO_NOT_GRANTED'",
                )
                .decode()
                .strip()
            )
            return int(count) >= 4

        wait(ai_ready)
        events.append(
            {"phase": "c1_current_postcommit_no_fee", "passed": True, "model_dispatch": 0}
        )
        isolation = "from pathlib import Path\nout=[]\nfor p in ['/run/service/review/config.json','/ledger']:\n try: f=Path(p); f.read_bytes() if f.is_file() else list(f.iterdir());out.append(False)\n except PermissionError:out.append(True)\nassert all(out);print('PRIVATE_REVIEW_ISOLATED')"
        ctl.docker("exec", "-u", "10001", n["runtime"], "python", "-c", isolation)
        events.append({"phase": "api_cannot_read_review_keys_or_ledger", "passed": True})
        # Killing only the Worker proves parent supervision without changing PG.
        status = json.loads(ctl.docker("exec", n["runtime"], "cat", "/run/service/ready.json"))
        old = status["children"]["worker"]
        ctl.docker(
            "exec",
            "-u",
            "65532",
            n["runtime"],
            "python",
            "-c",
            "import os,signal;os.kill(" + str(old) + ",signal.SIGKILL)",
        )
        wait(
            lambda: (
                json.loads(ctl.docker("exec", n["runtime"], "cat", "/run/service/ready.json"))[
                    "children"
                ]["worker"]
                != old
            )
        )
        events.append({"phase": "worker_sigkill_restarted", "passed": True})
        ctl.restart(owner, config)
        wait(lambda: runtime_ok(n))
        fixture_site(n)
        client(n, "restart")
        client(n, "retained", report=True)
        # Exercise actual immutable-image replacement and rollback with an
        # equivalent-source image; no schema compatibility claim is inferred.
        variant_tag = tag + "-upgrade"
        build(service_image, variant_tag)
        variant = ctl.inspect("image", variant_tag)["Id"]
        assert variant != service_image
        ctl.upgrade(owner, config, variant)
        wait(lambda: runtime_ok(n))
        fixture_site(n)
        client(n, "upgraded", report=True)
        ctl.rollback(owner, config)
        wait(lambda: runtime_ok(n))
        fixture_site(n)
        client(n, "rolled-back", report=True)
        events.append(
            {
                "phase": "immutable_image_upgrade_and_rollback",
                "passed": True,
                "equivalent_source": True,
            }
        )
        # Actual stopped PG+Ledger backup, then a new independent deployment.
        saved = private / "service-backup"
        receipt = ctl.backup(owner, config, saved)
        ctl.stop(owner)
        if state.get("keep_local") or state.get("host_probe"):
            manifest = json.loads((config / "manifest.json").read_bytes())
            manifest["publish"] = ["127.0.0.1:18769:8769", "127.0.0.1:18770:8770"]
            (config / "manifest.json").write_text(json.dumps(manifest))
        n2 = ctl.restore(restored, config, saved)
        attach(n2)
        wait(lambda: runtime_ok(n2))
        fixture_site(n2)
        client(n2, "restart")
        client(n2, "restored", report=True)
        assert receipt["quiescent"]
        events.append(
            {"phase": "cold_backup_restore", "passed": True, "backup_sha256": receipt["files"]}
        )
        if state.get("keep_local") or state.get("host_probe"):
            caller = private / "caller"
            docker("cp", seed["client"] + ":/client", str(caller))
            (caller / "session.json").write_bytes(
                docker("exec", "-u", "10004", seed["client"], "cat", "/state/session.json")
            )
            (caller / "session.json").chmod(0o600)
            app = json.loads((caller / "config.json").read_bytes())
            report = json.loads((caller / "service-report.json").read_bytes())
            probe = {
                "host": "localhost",
                "api_port": 18769,
                "review_port": 18770,
                "ca": str((caller / "ca.pem").resolve()),
                "certificate": str((caller / "client.pem").resolve()),
                "key": str((caller / "client-key.pem").resolve()),
                "api_bearer": app["bearer"],
                "review_bearer": report["bearer"],
                "report_profile": "VERIFIED_HUMAN_CUSTOMER_REPORT" if report.get("verified") else None,
            }
            (caller / "probe-config.json").write_text(json.dumps(probe))
            (caller / "probe-config.json").chmod(0o600)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "infra.linux_service.probe",
                    "--config",
                    str(caller / "probe-config.json"),
                ],
                capture_output=True,
                cwd=ctl.ROOT,
            )
            (private / "host-probe.stderr").write_bytes(result.stderr)
            if result.returncode:
                raise RuntimeError("HOST_LOCAL_MTLS_RED")
            events.append(
                {"phase": "host_local_mtls", "passed": True, "result": json.loads(result.stdout)}
            )
            retained = restored if state.get("keep_local") else None
            (private / "local-deployment.json").write_text(
                json.dumps(
                    {
                        "name": retained,
                        "config": str(config),
                        "caller_config": str(caller / "probe-config.json"),
                        "api": "https://localhost:18769",
                        "report": "https://localhost:18770",
                    },
                    indent=2,
                )
            )
        completed = True
    finally:
        for item in (owner, restored):
            n = ctl.names(item)
            if item == retained:
                cleanup.append(
                    {"kind": "deployment", "name": item, "retained_on_user_request": True}
                )
                continue
            if ctl.owned("container", n["runtime"], item):
                log = subprocess.run(["docker", "logs", n["runtime"]], capture_output=True)
                (private / (item + "-runtime.log")).write_bytes(log.stdout + log.stderr)
                (private / (item + "-inspect.json")).write_bytes(
                    ctl.docker("container", "inspect", n["runtime"])
                )
            for kind, key in [
                ("container", "relay"),
                ("container", "runtime"),
                ("container", "pg"),
                ("volume", "data"),
                ("volume", "ledger"),
                ("volume", "operator"),
                ("network", "net"),
                ("network", "ingress"),
            ]:
                verified = bool(ctl.owned(kind, n[key], item))
                if verified:
                    if kind == "container":
                        ctl.docker("rm", "-f", n[key])
                    elif kind == "network":
                        attached = json.loads(
                            docker(
                                "inspect",
                                "--format",
                                "{{json .NetworkSettings.Networks}}",
                                seed["client"],
                            )
                        )
                        if n[key] in attached:
                            docker("network", "disconnect", n[key], seed["client"])
                        ctl.docker("network", "rm", n[key])
                    else:
                        ctl.docker("volume", "rm", n[key])
                cleanup.append(
                    {
                        "kind": kind,
                        "name": n[key],
                        "label_verified_before_delete": verified,
                        "already_absent": not verified,
                        "absent": ctl.inspect(kind, n[key]) is None,
                    }
                )
        (public / "linux-service.json").write_text(
            json.dumps(
                {
                    "contract": "vrae.persistent-service-drill.v1",
                    "source_sha": state["g1_source_sha"],
                    "completed": completed,
                    "events": events,
                    "cleanup": cleanup,
                    "public_host_deployed": False,
                    "host_access": "LOCAL_DOCKER_ONLY",
                    "retained_local_deployment": retained,
                    "customer_targets": 0,
                    "model_dispatch": 0,
                },
                indent=2,
            )
        )

"""Exercise the actual deployment control script on owned local resources."""

import hashlib
import io
import json
import subprocess
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

    def wait(predicate, seconds=90):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if predicate():
                return
            time.sleep(0.5)
        raise RuntimeError("SERVICE_DRILL_BOUNDED_WAIT")

    def runtime_ok(n):
        d = ctl.inspect("container", n["runtime"])
        if not d["State"]["Running"]:
            raise RuntimeError("PERSISTENT_RUNTIME_EXITED")
        probe = subprocess.run(
            ["docker", "exec", n["runtime"], "test", "-f", "/run/service/ready.json"],
            capture_output=True,
        )
        return probe.returncode == 0

    def fixture_site(n):
        code = """from pathlib import Path
import shutil,subprocess
p=Path('/tmp/lab');p.mkdir(exist_ok=True)
for src,dst in [('source-ca.pem','cert.pem'),('source-key.pem','key.pem'),('site.json','site.json')]:shutil.copyfile('/operator/'+src,p/dst)
for ip in ['93.184.216.20/32','93.184.216.53/32']:subprocess.run(['ip','addr','add',ip,'dev','lo'],capture_output=True)
"""
        ctl.docker("exec", n["runtime"], "python", "-c", code)
        ctl.docker(
            "exec",
            "-d",
            n["runtime"],
            "python",
            "-m",
            "integration.authorized_targets.checks.site",
            "/tmp/lab/site.json",
        )
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
        # Actual stopped PG+Ledger backup, then a new independent deployment.
        saved = private / "service-backup"
        receipt = ctl.backup(owner, config, saved)
        ctl.stop(owner)
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
        completed = True
    finally:
        for item in (owner, restored):
            n = ctl.names(item)
            if ctl.owned("container", n["runtime"], item):
                (private / (item + "-runtime.log")).write_bytes(
                    ctl.docker("logs", n["runtime"], check=False)
                )
            for kind, key in [
                ("container", "runtime"),
                ("container", "pg"),
                ("volume", "data"),
                ("volume", "ledger"),
                ("volume", "operator"),
                ("network", "net"),
            ]:
                if ctl.owned(kind, n[key], item):
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
                cleanup.append({"kind": kind, "absent": ctl.inspect(kind, n[key]) is None})
        (public / "linux-service.json").write_text(
            json.dumps(
                {
                    "contract": "vrae.persistent-service-drill.v1",
                    "source_sha": state["g1_source_sha"],
                    "completed": completed,
                    "events": events,
                    "cleanup": cleanup,
                    "public_host_deployed": False,
                    "host_access": "NOT_PROVIDED",
                    "customer_targets": 0,
                    "model_dispatch": 0,
                },
                indent=2,
            )
        )

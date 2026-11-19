"""Drive an independent trusted service container against the actual API."""

import json
import subprocess
import time
from infra.authorized_targets.runner import LABEL


def exercise(docker, names, image, public):
    end = time.monotonic() + 240
    while time.monotonic() < end:
        ready = subprocess.run(
            ["docker", "exec", names["runtime"], "test", "-f", "/evidence/api-ready.json"],
            capture_output=True,
        )
        if ready.returncode == 0:
            break
        alive = json.loads(
            docker("inspect", "--format", "{{json .State.Running}}", names["runtime"])
        )
        if not alive:
            raise RuntimeError("API_PARENT_EXITED_BEFORE_READY")
        time.sleep(0.25)
    else:
        raise RuntimeError("API_BOUNDED_READY_TIMEOUT")
    label = json.loads(docker("inspect", "--format", "{{json .Config.Labels}}", names["runtime"]))[
        LABEL
    ]
    docker(
        "run",
        "-d",
        "--name",
        names["client"],
        "--label",
        LABEL + "=" + label,
        "--network",
        names["net"],
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        "10004:10004",
        "--tmpfs",
        "/state:rw,nosuid,nodev,size=2m,uid=10004,gid=10004,mode=700",
        "--mount",
        "type=volume,src=" + names["source"] + ",dst=/work,readonly",
        "--mount",
        "type=volume,src=" + names["client-secrets"] + ",dst=/client,readonly",
        image,
        "python",
        "-c",
        "import time;time.sleep(900)",
    )

    def wait_file(name, seconds=180):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            p = subprocess.run(
                ["docker", "exec", names["runtime"], "test", "-f", "/evidence/" + name],
                capture_output=True,
            )
            if p.returncode == 0:
                return
            alive = json.loads(
                docker("inspect", "--format", "{{json .State.Running}}", names["runtime"])
            )
            if not alive:
                raise RuntimeError("API_PARENT_EXITED_DURING_" + name)
            time.sleep(0.25)
        raise RuntimeError("API_BOUNDED_STAGE_TIMEOUT_" + name)

    for phase in ("submit", "read", "outage", "recovered", "restart"):
        if phase == "read":
            wait_file("api-captured.json")
        if phase == "outage":
            docker(
                "exec",
                "-u",
                "postgres",
                names["pg"],
                "pg_ctl",
                "-D",
                "/var/lib/postgresql/data",
                "-m",
                "fast",
                "-w",
                "stop",
            )
        if phase == "recovered":
            docker(
                "exec",
                "-u",
                "postgres",
                names["pg"],
                "pg_ctl",
                "-D",
                "/var/lib/postgresql/data",
                "-l",
                "/var/lib/postgresql/data/api-restart.log",
                "-o",
                "-c listen_addresses=127.0.0.1",
                "-w",
                "start",
            )
        if phase == "restart":
            wait_file("api-restarted.json")
        raw = docker(
            "exec",
            "-u",
            "10004",
            names["client"],
            "python",
            "-m",
            "integration.authorized_targets.checks.external_client",
            phase,
        )
        result = json.loads(raw)
        assert result["passed"] and result["phase"] == phase
        (public / ("external-" + phase + ".json")).write_bytes(raw)
        docker(
            "exec",
            names["runtime"],
            "python",
            "-c",
            "from pathlib import Path;Path('/client-share/" + phase + ".done').touch()",
        )

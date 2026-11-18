"""Local no-route drill. No cloud client; exact owned Docker resources only."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tarfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
LABEL = "vrae.l2_launch"
COMMAND_LOG_DIR = None


def run(argv, *, data=None, timeout=600):
    result = subprocess.run(argv, cwd=ROOT, input=data, capture_output=True, timeout=timeout)
    if result.returncode:
        if COMMAND_LOG_DIR is not None:
            index = str(time.time_ns())
            (COMMAND_LOG_DIR / (index + ".stdout.log")).write_bytes(result.stdout)
            (COMMAND_LOG_DIR / (index + ".stderr.log")).write_bytes(result.stderr)
        # Docker errors can contain bootstrap material; keep complete output private.
        raise RuntimeError(
            "COMMAND_FAILED: " + argv[0] + " " + argv[1] + " exit=" + str(result.returncode)
        )
    return result.stdout


def docker(*args, data=None, timeout=600):
    return run(["docker", *args], data=data, timeout=timeout)


def write(path, value):
    path.write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


def main():
    global COMMAND_LOG_DIR
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument(
        "--build", action="store_true", help="Build original pinned dependency image locally"
    )
    args = parser.parse_args()
    assert args.label.replace("-", "").isalnum() and len(args.label) < 64
    private = ROOT / "infra/l2_launch/.private" / args.label
    private.mkdir(parents=True, exist_ok=False)
    COMMAND_LOG_DIR = private
    public = private / "public"
    public.mkdir()
    slug = str(sys.version_info.major) + str(sys.version_info.minor)
    assert slug in ("311", "313")
    image = "vrae-ra4b-p1:" + slug
    base = json.loads((ROOT / "integration/ra4b/python-images.json").read_bytes())[
        f"3.{sys.version_info.minor}"
    ]
    if args.build:
        context = private / "build"
        context.mkdir()
        for name in (
            "requirements-ra1a.lock",
            "requirements-ra4a.lock",
            "requirements-ra4b-p1.lock",
        ):
            shutil.copyfile(ROOT / name, context / name)
        shutil.copyfile(ROOT / "integration/ra4b/Dockerfile", context / "Dockerfile")
        result = subprocess.run(
            ["docker", "build", "--build-arg", "PYTHON_BASE=" + base, "-t", image, str(context)],
            cwd=ROOT,
            capture_output=True,
            timeout=900,
        )
        (private / "build.stdout.log").write_bytes(result.stdout)
        (private / "build.stderr.log").write_bytes(result.stderr)
        result.check_returncode()
    image_id = docker("image", "inspect", "--format", "{{.Id}}", image).decode().strip()
    pg_image = (ROOT / "infra/ra4a/image.txt").read_text().strip()
    ident = "vrae-l2-launch-" + uuid.uuid4().hex[:12]
    names = {
        "pg": ident + "-pg",
        "runtime": ident + "-runtime",
        "data": ident + "-data",
        "evidence": ident + "-evidence",
        "source": ident + "-source",
        "stage": ident + "-stage",
    }
    ownership = {
        "label_key": LABEL,
        "label_value": ident,
        "names": names,
        "runtime_image_id": image_id,
        "pg_image": pg_image,
        "python_base": base,
        "no_ports": True,
        "network": "none",
    }
    write(public / "ownership.json", ownership)
    password = secrets.token_urlsafe(32)
    secret = private / "pg-password"
    secret.write_text(password, encoding="ascii")
    secret.chmod(0o600)
    roles = (
        "ra4a_test_a_app",
        "ra4a_test_b_app",
        "ra4a_test_a_worker",
        "ra4a_test_b_worker",
        "ra4a_test_unassigned",
    )
    state = {
        "host": "127.0.0.1",
        "port": 5432,
        "dbname": "vrae_ra4a_p1",
        "admin_password": password,
        "runtime_passwords": {role: secrets.token_urlsafe(24) for role in roles},
    }
    started = time.monotonic()
    failures = []
    created = []
    outcomes = []
    try:
        for key in ("data", "evidence", "source"):
            docker("volume", "create", "--label", LABEL + "=" + ident, names[key])
            created.append(("volume", names[key]))
        # Tracked files only. Caller stages new implementation before execution.
        paths = run(["git", "ls-files", "-z"]).decode().split("\0")
        manifest = []
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w:gz", compresslevel=1) as tar:
            for name in sorted(p for p in paths if p and not p.startswith(("docs/", ".git/"))):
                path = ROOT / name
                if not path.is_file():
                    continue
                raw = path.read_bytes()
                info = tarfile.TarInfo(name)
                info.size = len(raw)
                info.mode = 0o644
                tar.addfile(info, io.BytesIO(raw))
                manifest.append({"path": name, "sha256": hashlib.sha256(raw).hexdigest()})
        write(
            public / "source.json",
            {
                "sha": run(["git", "rev-parse", "HEAD"]).decode().strip(),
                "tracked_diff_sha256": hashlib.sha256(
                    run(["git", "diff", "HEAD", "--binary"])
                ).hexdigest(),
                "manifest": manifest,
            },
        )
        docker(
            "run",
            "--rm",
            "--name",
            names["stage"],
            "--label",
            LABEL + "=" + ident,
            "-i",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--mount",
            "type=volume,src=" + names["source"] + ",dst=/source",
            image_id,
            "python",
            "-c",
            "import sys,tarfile; tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz').extractall('/source',filter='data')",
            data=archive.getvalue(),
        )
        docker(
            "run",
            "-d",
            "--name",
            names["pg"],
            "--label",
            LABEL + "=" + ident,
            "--network",
            "none",
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--pids-limit",
            "128",
            "--env",
            "POSTGRES_DB=vrae_ra4a_p1",
            "--env",
            "POSTGRES_PASSWORD_FILE=/run/launch-password",
            "--mount",
            "type=bind,src=" + str(secret) + ",dst=/run/launch-password,readonly",
            "--mount",
            "type=volume,src=" + names["data"] + ",dst=/var/lib/postgresql/data",
            pg_image,
        )
        created.append(("container", names["pg"]))

        def pg(*cmd, data=None):
            return docker(
                "exec",
                "-i",
                names["pg"],
                "sh",
                "-c",
                'IFS= read -r PGPASSWORD; export PGPASSWORD; exec "$@"',
                "launch",
                *cmd,
                data=password.encode() + b"\n" + (data or b""),
            )

        deadline = time.monotonic() + 60
        while True:
            try:
                version = (
                    pg(
                        "psql",
                        "-h",
                        "127.0.0.1",
                        "-U",
                        "postgres",
                        "-d",
                        "vrae_ra4a_p1",
                        "-Atc",
                        "SHOW server_version_num",
                    )
                    .decode()
                    .strip()
                )
                assert version.startswith("16")
                break
            except RuntimeError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.25)
        assert docker("port", names["pg"]).strip() == b""

        def phase(name):
            state["phase"] = name
            docker(
                "run",
                "--name",
                names["runtime"],
                "--label",
                LABEL + "=" + ident,
                "-i",
                "--network",
                "container:" + names["pg"],
                "--read-only",
                "--cap-drop",
                "ALL",
                "--cap-add",
                "SETUID",
                "--cap-add",
                "SETGID",
                "--cap-add",
                "CHOWN",
                "--security-opt",
                "no-new-privileges:true",
                "--memory",
                "768m",
                "--cpus",
                "1",
                "--pids-limit",
                "128",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=192m,mode=1777",
                "--mount",
                "type=volume,src=" + names["source"] + ",dst=/work,readonly",
                "--mount",
                "type=volume,src=" + names["evidence"] + ",dst=/evidence",
                "--workdir",
                "/work",
                "--env",
                "PYTHONPATH=/work",
                "--env",
                "PYTHONDONTWRITEBYTECODE=1",
                image_id,
                "python",
                "-B",
                "-m",
                "integration.l2_launch.runtime.lab",
                data=json.dumps(state).encode(),
                timeout=600,
            )
            destination = private / name
            destination.mkdir()
            docker("cp", names["runtime"] + ":/evidence/.", str(destination))
            outcome = json.loads((destination / (name + "-result.json")).read_bytes())
            write(public / (name + "-result.json"), outcome)
            outcomes.append(outcome)
            next_state = json.loads((destination / "private-state.json").read_bytes())
            docker("rm", names["runtime"])
            return next_state

        state = phase("first")
        before = pg("pg_dump", "-h", "127.0.0.1", "-U", "postgres", "-Fc", "vrae_ra4a_p1")
        (private / "committed.pg_dump").write_bytes(before)
        docker("cp", str(private / "committed.pg_dump"), names["pg"] + ":/tmp/launch-backup.dump")
        pg(
            "pg_restore",
            "-h",
            "127.0.0.1",
            "-U",
            "postgres",
            "-d",
            "vrae_ra4a_p1",
            "--clean",
            "--if-exists",
            "--exit-on-error",
            "/tmp/launch-backup.dump",
        )
        state = phase("restore")
        first, out = outcomes[0]["result"], outcomes[1]["result"]
        pins = (
            "task",
            "pack_ref",
            "report_id",
            "version",
            "content_hash",
            "display_hash",
            "controlled_receipt_sha256",
        )
        assert all(first[k] == out[k] for k in pins), "RESTORE_CHANGED_REPORT_OR_RECEIPT"
        revoked = pg("pg_dump", "-h", "127.0.0.1", "-U", "postgres", "-Fc", "vrae_ra4a_p1")
        (private / "revoked.pg_dump").write_bytes(revoked)
        docker("cp", str(private / "revoked.pg_dump"), names["pg"] + ":/tmp/launch-backup.dump")
        pg(
            "pg_restore",
            "-h",
            "127.0.0.1",
            "-U",
            "postgres",
            "-d",
            "vrae_ra4a_p1",
            "--clean",
            "--if-exists",
            "--exit-on-error",
            "/tmp/launch-backup.dump",
        )
        state = phase("revoked")
        write(
            public / "backup-restore.json",
            {
                "original_pg_database_only": True,
                "stopped_writers": True,
                "same_cluster_roles_retained": True,
                "pg_dump_bytes_measured": len(before),
                "pg_dump_sha256": hashlib.sha256(before).hexdigest(),
                "revoked_dump_sha256": hashlib.sha256(revoked).hexdigest(),
                "all_report_version_and_receipt_pins_equal": True,
                "durable_pg_revocation_after_restore": True,
                "cross_store_atomic_online_backup": False,
                "full_disaster_recovery": False,
            },
        )
        secret_values = [password]
        for folder in ("first", "restore", "revoked"):
            saved = json.loads((private / folder / "private-state.json").read_bytes())
            secret_values.extend(saved["runtime_passwords"].values())
            secret_values.append(saved["old_bearer"])
        for path in public.glob("*.json"):
            raw = path.read_bytes()
            assert not any(value.encode() in raw for value in secret_values), (
                "PUBLIC_SECRET_DETECTED"
            )
        write(
            public / "privacy.json",
            {
                "explicit_public_metadata_only": True,
                "bootstrap_and_app_secrets_absent": True,
                "raw_logs_and_backups_uploaded": False,
            },
        )
        write(
            public / "result.json",
            {
                "status": "PASS",
                "candidate": "R1B_PRIVATE_RUNTIME_CANDIDATE_DEPLOYMENT_GO_PENDING",
                "release_status": "R1_ENGINEERING_CANDIDATE_NO_LIVE_SOURCE_NO_EXTERNAL_RELEASE",
                "checks_measured": sum(len(o["checks"]) for o in outcomes),
                "elapsed_seconds_measured": time.monotonic() - started,
                "cloud_resources_created": 0,
                "model_calls": 0,
                "money_status": "UNKNOWN",
                "cpu_ram_capacity": "ESTIMATED_UNMEASURED",
                "checks": [c for o in outcomes for c in o["checks"]],
            },
        )
    except BaseException as exc:
        failures.append(type(exc).__name__ + ": " + str(exc))
        if str(exc) == "PUBLIC_SECRET_DETECTED":
            quarantine = private / "publication-quarantine"
            quarantine.mkdir()
            for path in public.glob("*.json"):
                path.replace(quarantine / path.name)
        write(public / "failure.json", {"first_failure_preserved": True, "error": failures[-1]})
        # Raw trace/logs/configuration stay private, never a CI artifact.
        try:
            (private / "failed-evidence").mkdir()
            docker("cp", names["runtime"] + ":/evidence/.", str(private / "failed-evidence"))
            (private / "docker-failed.log").write_bytes(docker("logs", names["runtime"]))
        except Exception:
            pass
        raise
    finally:
        # Discover by EXACT unique label; verify each expected name before removal.
        removed = []
        absent = []
        expected_containers = {names["runtime"], names["stage"], names["pg"]}
        for name in (names["runtime"], names["stage"], names["pg"]):
            inspect = subprocess.run(["docker", "container", "inspect", name], capture_output=True)
            if inspect.returncode:
                absent.append(name)
                continue
            item = json.loads(inspect.stdout)[0]
            assert (
                item["Name"].lstrip("/") in expected_containers
                and item["Config"]["Labels"].get(LABEL) == ident
            )
            docker("rm", "-f", item["Id"])
            removed.append(name)
        for kind, name in reversed(created):
            if kind != "volume":
                continue
            item = json.loads(docker("volume", "inspect", name))[0]
            assert item["Name"] == name and item["Labels"].get(LABEL) == ident
            docker("volume", "rm", name)
            removed.append(name)
        leftover = docker("ps", "-aq", "--filter", "label=" + LABEL + "=" + ident).decode().strip()
        volumes = (
            docker("volume", "ls", "-q", "--filter", "label=" + LABEL + "=" + ident)
            .decode()
            .strip()
        )
        write(
            public / "cleanup.json",
            {
                "owned_label": ident,
                "removed": removed,
                "already_absent": absent,
                "owned_containers_absent": not leftover,
                "owned_volumes_absent": not volumes,
                "global_prune": False,
                "unrelated_resources": "UNTOUCHED",
            },
        )
        secret.unlink(missing_ok=True)
        assert not leftover and not volumes, "OWNED_CLEANUP_INCOMPLETE"
        print(
            json.dumps(
                {
                    "public_evidence": str(public),
                    "cleanup_verified": not leftover and not volumes,
                    "failures": len(failures),
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()

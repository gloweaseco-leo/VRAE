"""Authorized-target actual HTTPS/PG/DNS/TLS vertical; exclusively labeled resources, no ports."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import secrets
import subprocess
import tarfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
LABEL = "vrae.authorized_targets"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--image", default="vrae-g1:313")
    parser.add_argument("--delivery-bridge", action="store_true")
    parser.add_argument("--report-api", action="store_true")
    args = parser.parse_args()
    if args.report_api and not args.delivery_bridge:
        parser.error('--report-api requires --delivery-bridge')
    assert args.label.replace("-", "").isalnum() and len(args.label) < 64
    private = ROOT / "infra/authorized_targets/.private" / args.label
    private.mkdir(parents=True, exist_ok=False)
    public = private / "public"
    public.mkdir()

    def write(path, value):
        path.write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf8")

    def run(*argv, data=None, timeout=600):
        p = subprocess.run(argv, cwd=ROOT, input=data, capture_output=True, timeout=timeout)
        if p.returncode:
            stamp = str(time.time_ns())
            (private / (stamp + ".stderr")).write_bytes(p.stderr)
            (private / (stamp + ".stdout")).write_bytes(p.stdout)
            raise RuntimeError("TARGET_COMMAND_FAILED " + argv[0] + " " + argv[1])
        return p.stdout

    def docker(*argv, **kw):
        return run("docker", *argv, **kw)

    ident = "vrae-targets-" + uuid.uuid4().hex[:12]
    names = {k: ident + "-" + k for k in ("pg", "runtime", "data", "source", "evidence", "stage")}
    image = docker("image", "inspect", "--format", "{{.Id}}", args.image).decode().strip()
    pg_image = (ROOT / "infra/ra4a/image.txt").read_text().strip()
    write(
        public / "ownership.json",
        {
            "label": {LABEL: ident},
            "names": names,
            "image_id": image,
            "pg_image": pg_image,
            "network": "none",
            "published_ports": [],
        },
    )
    password = secrets.token_urlsafe(32)
    secret = private / "pg-password"
    secret.write_text(password)
    secret.chmod(0o600)
    roles = (
        "ra4a_test_a_app",
        "ra4a_test_b_app",
        "ra4a_test_a_worker",
        "ra4a_test_b_worker",
        "ra4a_test_unassigned",
    )
    state = {
        "delivery_bridge": args.delivery_bridge,
        "report_api": args.report_api,
        "host": "127.0.0.1",
        "port": 5432,
        "dbname": "vrae_ra4a_p1",
        "admin_password": password,
        "g1_source_sha": run("git", "rev-parse", "HEAD").decode().strip(),
        "g1_source_dirty": bool(run("git", "status", "--porcelain").strip()),
        "g1_owned_run_id": ident,
        "runtime_passwords": {r: secrets.token_urlsafe(24) for r in roles},
    }
    created = []
    failure = None
    try:
        for key in ("data", "source", "evidence"):
            docker("volume", "create", "--label", LABEL + "=" + ident, names[key])
            created.append(("volume", names[key]))
        paths = (
            run("git", "ls-files", "--cached", "--others", "--exclude-standard", "-z")
            .decode()
            .split("\0")
        )
        archive = io.BytesIO()
        manifest = []
        with tarfile.open(fileobj=archive, mode="w:gz", compresslevel=1) as tar:
            for name in sorted(set(p for p in paths if p and not p.startswith(("docs/", ".git/")))):
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
                "head": run("git", "rev-parse", "HEAD").decode().strip(),
                "diff_sha256": hashlib.sha256(run("git", "diff", "HEAD", "--binary")).hexdigest(),
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
            image,
            "python",
            "-c",
            "import sys,tarfile;tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz').extractall('/source',filter='data')",
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
            "POSTGRES_PASSWORD_FILE=/run/g1-password",
            "--mount",
            "type=bind,src=" + str(secret) + ",dst=/run/g1-password,readonly",
            "--mount",
            "type=volume,src=" + names["data"] + ",dst=/var/lib/postgresql/data",
            pg_image,
        )
        created.append(("container", names["pg"]))
        end = time.monotonic() + 90
        while True:
            p = subprocess.run(
                [
                    "docker",
                    "exec",
                    names["pg"],
                    "pg_isready",
                    "-U",
                    "postgres",
                    "-d",
                    "vrae_ra4a_p1",
                ],
                capture_output=True,
            )
            if p.returncode == 0:
                break
            if time.monotonic() > end:
                raise RuntimeError("TARGET_PG_NOT_READY")
            time.sleep(0.3)
        docker(
            "create",
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
            "NET_BIND_SERVICE",
            "--cap-add",
            "SETGID",
            "--cap-add",
            "CHOWN",
            "--cap-add",
            "NET_ADMIN",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "768m",
            "--cpus",
            "2",
            "--pids-limit",
            "160",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=192m",
            "--tmpfs",
            "/run/vrae-targets:rw,nosuid,nodev,size=2m",
            "--mount",
            "type=volume,src=" + names["source"] + ",dst=/work,readonly",
            "--mount",
            "type=volume,src=" + names["evidence"] + ",dst=/evidence",
            image,
            "python",
            "-m",
            "integration.authorized_targets.lab",
        )
        created.append(("container", names["runtime"]))
        with (
            (private / "supervisor.stdout").open("wb") as out,
            (private / "supervisor.stderr").open("wb") as err,
        ):
            process = subprocess.Popen(
                ["docker", "start", "-a", "-i", names["runtime"]],
                stdin=subprocess.PIPE,
                stdout=out,
                stderr=err,
            )
            process.stdin.write(json.dumps(state).encode())
            process.stdin.close()
            process.wait(timeout=900)
        # docker start returns zero even if child failed; inspect is authoritative.
        code = int(docker("inspect", "--format", "{{.State.ExitCode}}", names["runtime"]).decode())
        docker(
            "cp", names["runtime"] + ":/evidence/.private-root", str(private / "runtime-private")
        )

        files = ['targets.json'] + (['delivery.json'] if args.delivery_bridge else [])
        files += ['report-api.json'] if args.report_api else []
        for file in files:
            found = subprocess.run(
                ["docker", "cp", names["runtime"] + ":/evidence/" + file, str(public / file)],
                capture_output=True,
            )
            if code == 0:
                assert found.returncode == 0
        if code:
            raise RuntimeError(
                "TARGET_VERTICAL_RUNTIME_RED exit=" + str(code) + " private=" + str(private)
            )
    except BaseException as error:
        failure = type(error).__name__ + ": " + str(error)
        write(
            public / "first-red.json",
            {"status": "RED", "failure": failure, "customer_release": False},
        )
    finally:
        cleanup = []
        # Include the auto-removed staging helper in the absence receipt too.
        for key in ("runtime", "pg", "stage", "evidence", "source", "data"):
            kind = "container" if key in ("runtime", "pg", "stage") else "volume"
            name = names[key]
            template = "{{json .Config.Labels}}" if kind == "container" else "{{json .Labels}}"
            inspected = subprocess.run(
                ["docker", kind, "inspect", "--format", template, name], capture_output=True
            )
            verified = False
            if inspected.returncode == 0:
                assert json.loads(inspected.stdout).get(LABEL) == ident
                verified = True
                docker("rm", "-f", name) if kind == "container" else docker("volume", "rm", name)
            absent = subprocess.run(["docker", kind, "inspect", name], capture_output=True)
            assert (
                absent.returncode
                and name.encode() in absent.stderr
                and any(v in absent.stderr.lower() for v in (b"no such", b"not found"))
            ), "TARGET_CLEANUP_ABSENCE_UNPROVEN"
            cleanup.append(
                {
                    "kind": kind,
                    "name": name,
                    "label_verified_before_delete": verified,
                    "already_auto_removed": not verified,
                    "absent": True,
                }
            )
        write(public / "cleanup.json", cleanup)
    if failure:
        raise RuntimeError(failure)
    print(
        json.dumps(
            {
                "status": "CONTROLLED_TARGET_VERTICAL_ONLY",
                "customer_release": False,
                "evidence": str(public),
            }
        )
    )


if __name__ == "__main__":
    main()

"""One finite permission audit in accepted Linux images and owned network-none PG16."""

import hashlib
import io
import json
from pathlib import Path
import secrets
import re
import subprocess
import sys
import tarfile
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
LABEL = "vrae.ra4b_p2.m1"


def main(*, consumer=False):
    minor = sys.argv[1]
    assert minor in ("311", "313")
    label = sys.argv[2] if len(sys.argv) > 2 else minor
    experiment = True
    assert re.fullmatch(r"[a-z0-9-]{3,40}", label)
    out = ROOT / "docs/03-engineering/ra4b-p2/.runtime" / ("m1-" + label)
    out.mkdir(parents=True, exist_ok=False)
    # Host runner and capability-restricted container root have distinct UIDs.
    # Producer files stay immutable; host writes only separate attestations.
    out.chmod(0o777)
    ident = "vrae-m1-" + uuid.uuid4().hex[:12]
    resources = [
        ("container", ident + "-client"),
        ("container", ident + "-pg"),
        ("volume", ident + "-source"),
        ("volume", ident + "-data"),
    ]

    def docker(*args, data=None, check=True):
        p = subprocess.run(["docker", *args], input=data, capture_output=True, timeout=360)
        if check and p.returncode:
            (out / "docker-failure.stderr").write_bytes(p.stderr)
            raise RuntimeError("S2_OWNED_DOCKER_FAILED")
        return p

    image = (
        docker("image", "inspect", "vrae-ra4b-p1:" + minor, "--format", "{{.Id}}")
        .stdout.decode()
        .strip()
    )
    pg_image = (ROOT / "infra/ra4a/image.txt").read_text().strip()
    password = secrets.token_urlsafe(32)
    state = {
        "container": ident + "-pg",
        "host": "127.0.0.1",
        "port": 5432,
        "dbname": "vrae_ra4a_p1",
        "admin_password": password,
        "runtime_passwords": {
            r: secrets.token_urlsafe(24)
            for r in (
                "ra4a_test_a_app",
                "ra4a_test_b_app",
                "ra4a_test_a_worker",
                "ra4a_test_b_worker",
                "ra4a_test_unassigned",
            )
        },
    }
    env = out / "postgres.env"
    env.write_bytes(
        (
            "POSTGRES_PASSWORD="
            + password
            + "\nPOSTGRES_DB=vrae_ra4a_p1\nPOSTGRES_INITDB_ARGS=--auth-host=scram-sha-256\n"
        ).encode()
    )
    archive = io.BytesIO()
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    names = {
        n
        for n in tracked
        if n.startswith(
            (
                "vrae/",
                "apps/",
                "worker/",
                "integration/",
                "tests/",
                "contracts/",
                "industry-packs/",
                "db/",
            )
        )
    }
    names.update(
        p.relative_to(ROOT).as_posix() for p in (ROOT / "integration/ra4b_p2").rglob("*.py")
    )
    for directory, pattern in [("vrae/application/ra4b_p2", "*.py"), ("db/ra4b_p2", "*.sql")]:
        names.update(p.relative_to(ROOT).as_posix() for p in (ROOT / directory).rglob(pattern))
    source_manifest = {}
    with tarfile.open(fileobj=archive, mode="w:gz") as tar:
        for name in sorted(names):
            raw = (ROOT / name).read_bytes()
            source_manifest[name] = hashlib.sha256(raw).hexdigest()
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(raw))
    (out / "source-manifest.json").write_text(json.dumps(source_manifest, sort_keys=True, indent=2))
    cleanup = []
    try:
        for _, name in resources[2:]:
            docker("volume", "create", "--label", LABEL + "=" + ident, name)
        docker(
            "run",
            "-d",
            "--name",
            ident + "-pg",
            "--label",
            LABEL + "=" + ident,
            "--network",
            "none",
            "--env-file",
            str(env),
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--pids-limit",
            "128",
            "--mount",
            "type=volume,src=" + ident + "-data,dst=/var/lib/postgresql/data",
            pg_image,
        )
        env.unlink()
        deadline = time.monotonic() + 60
        while docker(
            "exec",
            ident + "-pg",
            "pg_isready",
            "-h",
            "127.0.0.1",
            "-U",
            "postgres",
            "-d",
            "vrae_ra4a_p1",
            check=False,
        ).returncode:
            assert time.monotonic() < deadline, "PG16_STARTUP_TIMEOUT"
            time.sleep(0.25)
        docker(
            "run",
            "--rm",
            "-i",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--mount",
            "type=volume,src=" + ident + "-source,dst=/source",
            image,
            "python",
            "-c",
            "import sys,tarfile; tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz').extractall('/source',filter='data')",
            data=archive.getvalue(),
        )
        p = docker(
            "run",
            "--rm",
            "-i",
            "--name",
            ident + "-client",
            "--label",
            LABEL + "=" + ident,
            "--network",
            "container:" + ident + "-pg",
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
            "no-new-privileges",
            "--memory",
            "768m",
            "--pids-limit",
            "128",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=256m",
            "--mount",
            "type=volume,src=" + ident + "-source,dst=/work,readonly",
            "--mount",
            "type=bind,src=" + str(out) + ",dst=/evidence",
            image,
            "python",
            "-m",
            "pytest",
            "-q",
            "-s",
            "--tb=short",
            "-p",
            "no:cacheprovider",
            (
                "integration/ra4b_p2/m1/consumer_cases.py" if consumer else "integration/ra4b_p2/m1/native_cases.py"
                if experiment
                else "integration/ra4b_p2/audit_cases.py"
            ),
            "--junitxml=/evidence/native-junit.xml",
            data=json.dumps(state).encode(),
            check=False,
        )
        (out / "stdout.log").write_bytes(p.stdout)
        (out / "stderr.log").write_bytes(p.stderr)
        raw = (out / "native-junit.xml").read_bytes()
        cs = list(ET.fromstring(raw).iter("testcase"))
        red = [
            c.get("name")
            for c in cs
            if any(c.find(k) is not None for k in ("failure", "error", "skipped"))
        ]
        receipt = {
            "kind": "M1_CONSUMER_INTEGRATION_NOT_M2_M3_EXIT" if consumer else "M1_NATIVE_GENERATED_RESULT_NOT_FULL_BETA_EXIT",
            "minor": minor,
            "image_id": image,
            "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
            .decode()
            .strip(),
            "returncode": p.returncode,
            "cases": len(cs),
            "red_or_skipped": red,
            "native_junit_sha256": hashlib.sha256(raw).hexdigest(),
            "network": "NONE_PG_SHARED_LOOPBACK_ONLY",
            "audit_sources_sha256": {
                p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (ROOT / "integration/ra4b_p2").rglob("*.py")
            },
        }
        (out / "receipt.json").write_bytes((json.dumps(receipt, indent=2) + "\n").encode())
        print(json.dumps(receipt), flush=True)
        assert p.returncode == 0 and not red, "REAL_NATIVE_AUDIT_RED"
        if consumer:
            assert len(cs) == 2, "CONSUMER_CASE_INVENTORY"
            return
        # A second client joins the restarted PG namespace, with no migration,
        # seed, result rewrite or role/credential substitution.
        docker("restart", ident + "-pg")
        deadline = time.monotonic() + 60
        while docker("exec", ident + "-pg", "pg_isready", "-q", check=False).returncode:
            assert time.monotonic() < deadline, "M1_PG_RESTART_TIMEOUT"
            time.sleep(0.25)
        recovered = out / "recovered"
        recovered.mkdir()
        recovered.chmod(0o777)
        result = docker(
            "run",
            "--rm",
            "-i",
            "--name",
            ident + "-client",
            "--label",
            LABEL + "=" + ident,
            "--network",
            "container:" + ident + "-pg",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "768m",
            "--pids-limit",
            "128",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=256m",
            "--mount",
            "type=volume,src=" + ident + "-source,dst=/work,readonly",
            "--mount",
            "type=bind,src=" + str(recovered) + ",dst=/evidence",
            "--mount",
            "type=bind,src="
            + str(out / "private-restart-state.json")
            + ",dst=/run/m1-state.json,readonly",
            "--mount",
            "type=bind,src=" + str(out / "m1-proof.json") + ",dst=/run/m1-before.json,readonly",
            image,
            "python",
            "-m",
            "pytest",
            "-q",
            "--tb=short",
            "-p",
            "no:cacheprovider",
            "integration/ra4b_p2/m1/recover_cases.py",
            "--junitxml=/evidence/native-junit.xml",
            check=False,
        )
        (recovered / "stdout.log").write_bytes(result.stdout)
        (recovered / "stderr.log").write_bytes(result.stderr)
        restart_xml = (recovered / "native-junit.xml").read_bytes()
        restart_cases = list(ET.fromstring(restart_xml).iter("testcase"))
        restart_red = [
            c.get("name")
            for c in restart_cases
            if any(c.find(k) is not None for k in ("failure", "error", "skipped"))
        ]
        restart_receipt = {
            "actual_pg_container_restart": True,
            "no_migrate_or_seed": True,
            "cases": len(restart_cases),
            "red_or_skipped": restart_red,
            "native_junit_sha256": hashlib.sha256(restart_xml).hexdigest(),
            "returncode": result.returncode,
        }
        (recovered / "receipt.json").write_text(json.dumps(restart_receipt, indent=2))
        print(json.dumps(restart_receipt), flush=True)
        assert result.returncode == 0 and not restart_red and len(restart_cases) == 2, (
            "M1_REAL_PG_RESTART_RED"
        )
    finally:
        env.unlink(missing_ok=True)
        for kind, name in resources:
            p = docker(kind, "inspect", name, check=False)
            if p.returncode == 0:
                template = "{{json .Config.Labels}}" if kind == "container" else "{{json .Labels}}"
                labels = json.loads(docker(kind, "inspect", "--format", template, name).stdout)
                assert labels.get(LABEL) == ident
                docker(*(["rm", "-f", name] if kind == "container" else ["volume", "rm", name]))
            p = docker(kind, "inspect", name, check=False)
            assert p.returncode and (
                b"no such" in p.stderr.lower() or b"not found" in p.stderr.lower()
            )
            cleanup.append({"kind": kind, "name": name, "absent": True})
        (out / "cleanup.json").write_bytes((json.dumps(cleanup, indent=2) + "\n").encode())


if __name__ == "__main__":
    main()

"""Disposable PG16 lab; bounded target SQL readiness and verified owned cleanup."""

import argparse
import json
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = HERE / ".venv" / "lab-state.json"
LABEL = "vrae.ra4a.p1"
DB = "vrae_ra4a_p1"
DIAGNOSTIC = None
REDACTIONS = []


def record(event, **values):
    if DIAGNOSTIC is None:
        return
    def clean(value):
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        if isinstance(value, str):
            for secret in REDACTIONS:
                value = value.replace(secret, "[REDACTED]")
            return value[-8000:]
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value
    with DIAGNOSTIC.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"event": event, "monotonic": time.monotonic(),
                                 **clean(values)}) + "\n")


def invoke(*args, data=None, timeout=30, trace=True):
    try:
        result = subprocess.run(["docker", *args], input=data, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        record("docker_timeout", command=list(args), timeout=timeout,
               stdout=exc.stdout or b"", stderr=exc.stderr or b"")
        raise
    if trace:
        record("docker_command", command=list(args), returncode=result.returncode,
               stdout=result.stdout, stderr=result.stderr)
    return result


def docker(*args, data=None):
    result = invoke(*args, data=data)
    result.check_returncode()
    return result.stdout.decode("utf-8")


def snapshot(ident):
    # Selected non-secret fields only; never full inspect/Env or database contents.
    for label, args in (
        ("postgres_log_tail", ["logs", "--tail", "60", ident]),
        ("container_state_image", ["inspect", "--format",
         '{{json .State}} {{json .Image}} {{json .Config.Image}}', ident]),
    ):
        p = invoke(*args, timeout=15, trace=False)
        record(label, returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)


def output_path(path):
    path = path.resolve()
    assert any(path.is_relative_to((ROOT / ('docs/03-engineering/' + name)).resolve())
               for name in ('ra4a-p1', 'ra4a-p2a'))
    return path


def validate_names(s):
    assert re.fullmatch(r"vrae-ra4a-p1-[0-9a-f]{12}", s["container"])
    assert s["network"] == s["container"] + "-local"
    assert s["data_volume"] == s["container"] + "-data"


def inspect_owned(kind, name):
    template = "{{json .Config.Labels}}" if kind == "container" else "{{json .Labels}}"
    p = invoke(kind, "inspect", "--format", template, name)
    if p.returncode:
        # A permission/daemon failure is not evidence of resource absence.
        message = p.stderr.decode("utf-8", errors="replace").lower()
        assert name.lower() in message and ("no such" in message or "not found" in message), message
        return False
    assert json.loads(p.stdout)[LABEL] == "TEST_ONLY", "OWNERSHIP_LABEL_MISMATCH"
    return True


def cleanup(s, output):
    validate_names(s)
    output = output_path(output)
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for kind, name in (("container", s["container"]), ("network", s["network"]),
                       ("volume", s["data_volume"])):
        row = {"kind": kind, "name": name}
        try:
            row["present_before"] = inspect_owned(kind, name)
            if row["present_before"]:
                args = ("rm", "-f", name) if kind == "container" else (kind, "rm", name)
                p = invoke(*args)
                row["remove_returncode"] = p.returncode
                assert p.returncode == 0, "OWNED_REMOVE_FAILED"
            row["absent_after"] = not inspect_owned(kind, name)
            assert row["absent_after"], "OWNED_RESOURCE_STILL_PRESENT"
        except Exception as exc:
            row["error"] = type(exc).__name__ + ": " + str(exc)[:500]
            row["absent_after"] = False
        results.append(row)
    proof = {**{k: s[k] for k in ("container", "network", "data_volume")},
             "actual_results": results,
             "owned_container_removed": results[0]["absent_after"],
             "owned_network_removed": results[1]["absent_after"],
             "owned_volume_removed": results[2]["absent_after"]}
    (output / "teardown.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    assert all(r["absent_after"] and "error" not in r for r in results), "OWNED_CLEANUP_FAILED"
    return proof


def wait_target(ident, password, seconds):
    deadline = time.monotonic() + seconds
    first_failure = True
    while time.monotonic() < deadline:
        # Official init's temporary server accepts Unix sockets only. Require the
        # final server's TCP listener, authenticated SCRAM, and actual target SQL.
        p = invoke("exec", "-i", ident, "sh", "-c",
                   'IFS= read -r PGPASSWORD; export PGPASSWORD; exec "$@"',
                   "ra4a-readiness", "psql", "-h", "127.0.0.1", "-U", "postgres",
                   "-d", DB, "-v", "ON_ERROR_STOP=1", "-At", "-F", "|", "-c",
                   "SELECT current_database(), current_setting('server_version_num')",
                   data=(password + "\n").encode(), timeout=min(5, max(.1, deadline-time.monotonic())))
        if p.returncode == 0:
            fields = p.stdout.decode().strip().split("|")
            assert len(fields) == 2 and fields[0] == DB, "UNEXPECTED_TARGET_DATABASE"
            assert 160000 <= int(fields[1]) < 170000, "UNEXPECTED_POSTGRES_VERSION"
            return fields[1]
        error = p.stderr.decode("utf-8", errors="replace").lower()
        # Auth/config/syntax/unexpected failures are immediately fatal.
        transient = ("connection refused", "does not exist", "server closed the connection",
                     "database system is starting up", "database system is shutting down")
        assert p.returncode == 2 and any(x in error for x in transient), "NON_TRANSIENT_TARGET_SQL_FAILURE"
        if first_failure:
            snapshot(ident)
            first_failure = False
        time.sleep(min(.25, max(0, deadline - time.monotonic())))
    raise RuntimeError("REAL_PG_STARTUP_DEADLINE")


def start(output, seconds):
    global DIAGNOSTIC
    assert not STATE.exists(), "Existing owned lab: stop it explicitly first"
    assert 0 <= seconds <= 60
    output = output_path(output)
    output.mkdir(parents=True, exist_ok=False)
    DIAGNOSTIC = output / "startup.jsonl"
    ident = "vrae-ra4a-p1-" + uuid.uuid4().hex[:12]
    image = (HERE / "image.txt").read_text().strip()
    s = {"container": ident, "network": ident + "-local", "data_volume": ident + "-data",
         "image": image, "startup_output": str(output)}
    validate_names(s)
    (output / "ownership.json").write_text(json.dumps(s, indent=2) + "\n", encoding="utf-8")
    password = secrets.token_urlsafe(32)
    REDACTIONS.append(password)
    record("owned_resources", **s, startup_deadline_seconds=seconds)
    try:
        docker("network", "create", "--label", LABEL + "=TEST_ONLY", s["network"])
        docker("volume", "create", "--label", LABEL + "=TEST_ONLY", s["data_volume"])
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as cfg:
            cfg.write("POSTGRES_PASSWORD=" + password + "\nPOSTGRES_DB=" + DB + "\n"
                      "POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256\n")
            cfg_path = Path(cfg.name)
        try:
            docker("run", "-d", "--name", ident, "--network", s["network"],
                   "--label", LABEL + "=TEST_ONLY", "--env-file", str(cfg_path),
                   "-p", "127.0.0.1::5432", "--mount",
                   "type=volume,src=" + s["data_volume"] + ",dst=/var/lib/postgresql/data",
                   "--memory", "512m", "--cpus", "1", "--pids-limit", "128", image)
        finally:
            cfg_path.unlink()
        digests = json.loads(docker("image", "inspect", "--format", "{{json .RepoDigests}}", image))
        assert any(d.endswith("@" + image.split("@")[1]) for d in digests), "IMAGE_DIGEST_MISMATCH"
        version = wait_target(ident, password, seconds)
        binding = docker("port", ident, "5432/tcp").strip()
        assert binding.startswith("127.0.0.1:") and "\n" not in binding, "UNEXPECTED_PORT_BINDING"
        snapshot(ident)
        s.update({"host": "127.0.0.1", "port": int(binding.rsplit(":", 1)[1]), "dbname": DB,
                  "admin_password": password, "server_version_num": version,
                  "runtime_passwords": {n: secrets.token_urlsafe(24) for n in
                    ("ra4a_test_a_app", "ra4a_test_b_app", "ra4a_test_a_worker",
                     "ra4a_test_b_worker", "ra4a_test_unassigned")}})
        REDACTIONS.extend(s["runtime_passwords"].values())
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(s, indent=2), encoding="utf-8")
        record("target_sql_ready", dbname=DB, server_version_num=version,
               loopback_publication_only=True, kernel_egress_denial=False)
        print(json.dumps({"container": ident, "image": image, "server_version_num": version,
                          "target_sql_ready": True, "startup_output": str(output)}))
    except BaseException as exc:
        record("startup_failure", error_type=type(exc).__name__, error=str(exc))
        try:
            snapshot(ident)
        finally:
            cleanup(s, output / "failure-cleanup")
        if STATE.exists():
            STATE.unlink()
        raise


def stop(output, startup_output):
    global DIAGNOSTIC
    output = output_path(output)
    output.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC = output / "cleanup.jsonl"
    if STATE.exists():
        s = json.loads(STATE.read_text())
        REDACTIONS.extend([s["admin_password"], *s["runtime_passwords"].values()])
    else:
        assert startup_output is not None, "MISSING_STARTUP_OWNERSHIP_RECEIPT"
        s = json.loads((output_path(startup_output) / "ownership.json").read_text())
    validate_names(s)
    if inspect_owned("container", s["container"]):
        snapshot(s["container"])
        # Same sanitized bounded logs/state are in cleanup.jsonl. Never export Env.
    cleanup(s, output)
    if STATE.exists():
        STATE.unlink()
    print("OWNED_PG_CONTAINER_NETWORK_VOLUME_ABSENCE_VERIFIED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("start", "stop"))
    parser.add_argument("--output", type=Path, default=Path("docs/03-engineering/ra4a-p1/startup"))
    parser.add_argument("--startup-output", type=Path)
    parser.add_argument("--startup-timeout", type=float, default=60)
    args = parser.parse_args()
    if args.action == "start":
        start(args.output, args.startup_timeout)
    else:
        stop(args.output, args.startup_output)

"""Owned Linux runtime test: no outside route, UID-isolated API and Worker."""

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))


def command(argv, dest, *, data=None, timeout=600):
    result = subprocess.run(argv, cwd=ROOT, input=data, capture_output=True, timeout=timeout)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.with_suffix(".stdout.log").write_bytes(result.stdout)
    dest.with_suffix(".stderr.log").write_bytes(result.stderr)
    from integration.ra4b.evidence import PREFIX, console_stage
    for line in result.stdout.decode(errors="replace").splitlines():
        if line.startswith(PREFIX):
            try:
                print(json.dumps({"safe_stage_result": console_stage(json.loads(line[len(PREFIX):]))}), flush=True)
            except (ValueError, TypeError):
                pass  # Raw output is never echoed; genuine exit is checked below.
    print(json.dumps({"stage": dest.name, "exit": result.returncode}), flush=True)
    result.check_returncode()
    return result.stdout


def source_names():
    names = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")) - {""}
    for folder in ("apps/api", "worker/ra4b", "vrae/application/ra4b", "integration/ra4b"):
        names.update(p.relative_to(ROOT).as_posix() for p in (ROOT / folder).rglob("*") if p.is_file())
    names.update(("db/migrations/0004_ra4b_test_only_api.sql", "requirements-ra4b-p1.lock"))
    names.add(".github/workflows/ra4b-p1.yml")
    return sorted(names)


def source_files(include_docs=True):
    for name in source_names():
        if name.startswith("docs/03-engineering/ra4b-p1/") or "__pycache__" in name or name == ".git" or name.startswith(".git/"):
            continue
        if not include_docs and name.startswith("docs/"):
            continue
        source = ROOT / name
        if source.is_file():
            yield name, source.read_bytes()


def snapshot_source(target, include_docs=True):
    manifest = []
    for name, raw in source_files(include_docs):
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        manifest.append({"path": name, "sha256": hashlib.sha256(raw).hexdigest(),
                         "lf_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()})
    return manifest


def source_tar(path, include_docs=True):
    manifest = []
    with tarfile.open(path, "w:gz", compresslevel=1) as archive:
        for name, raw in source_files(include_docs):
            item = tarfile.TarInfo(name)
            item.size, item.mode = len(raw), 0o644
            archive.addfile(item, io.BytesIO(raw))
            manifest.append({"path": name, "sha256": hashlib.sha256(raw).hexdigest(),
                             "lf_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()})
        raw = json.dumps(manifest).encode()
        item = tarfile.TarInfo("RA4B_SOURCE_MANIFEST.json")
        item.size = len(raw)
        archive.addfile(item, io.BytesIO(raw))
    return manifest


def main(label):
    assert label.replace("-", "").isalnum()
    out = (HERE / ".runtime/owner-review" if "--private-output" in sys.argv else HERE) / label
    out.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir(exist_ok=False)
    private = HERE / ".runtime" / label
    private.mkdir(parents=True, exist_ok=False)
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    context = private / "build"
    context.mkdir()
    for name in ("requirements-ra1a.lock", "requirements-ra4a.lock", "requirements-ra4b-p1.lock"):
        shutil.copyfile(ROOT / name, context / name)
    shutil.copyfile(ROOT / "integration/ra4b/Dockerfile", context / "Dockerfile")
    image = "vrae-ra4b-p1:" + version.replace(".", "")
    base = json.loads((ROOT / "integration/ra4b/python-images.json").read_bytes())[version]
    command(["docker", "build", "--build-arg", "PYTHON_BASE=" + base, "-t", image, str(context)], out / "build", timeout=900)
    image_id = command(["docker", "image", "inspect", "--format", "{{.Id}}", image], out / "image").decode().strip()
    if "--build-only" in sys.argv:
        return 0
    archive = private / "source.tar.gz"
    manifest = source_tar(archive, include_docs=False)
    (out / "source.json").write_text(json.dumps({"python": sys.version, "image_id": image_id, "source": manifest}, indent=2))
    from infra.ra4a import lab
    from integration.ra4a import support
    lab.STATE = support.STATE = private / "state.json"
    lab.output_path = lambda p: p.resolve() if p.resolve().is_relative_to(HERE) else (_ for _ in ()).throw(ValueError("OUTPUT_BOUNDARY"))
    state = None
    client_name = "vrae-ra4b-client-" + uuid.uuid4().hex[:12]
    source_volume = client_name + "-source"
    command(["docker", "volume", "create", "--label", "vrae.ra4b.p1=TEST_ONLY", source_volume], out / "source-volume-create")
    try:
        # A native Linux source volume removes Windows bind-import latency.
        # Runtime mounts remain read-only; the measured 8s/HTTP/lease bounds
        # and all unprivileged child security settings are unchanged.
        command(["docker", "run", "--rm", "-i", "--network", "none", "--read-only", "--cap-drop", "ALL",
                 "--mount", "type=volume,src=" + source_volume + ",dst=/source", image_id,
                 "python", "-c", "import sys,tarfile; tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz').extractall('/source',filter='data')"],
                out / "source-volume-stage", data=archive.read_bytes())
        lab.start(out / "startup", 60)
        from integration.ra4b.support import migrate
        migrate()
        state = json.loads(lab.STATE.read_bytes())
        assert lab.inspect_owned("container", state["container"])
        lab.docker("network", "disconnect", state["network"], state["container"])
        for phase in ("runtime", "recovered"):
            dest = out / phase
            dest.mkdir()
            from integration.ra4b.evidence import prepare_output
            output_group = prepare_output(dest)
            argv = ["docker", "run", "--rm", "-i", "--name", client_name,
                    "--label", "vrae.ra4b.p1=TEST_ONLY", "--network", "container:" + state["container"],
                    "--read-only", "--cap-drop", "ALL", "--cap-add", "SETUID", "--cap-add", "SETGID", "--cap-add", "CHOWN",
                    "--security-opt", "no-new-privileges", "--memory", "768m", "--pids-limit", "128",
                    "--tmpfs", "/tmp:rw,nosuid,nodev,size=256m",
                    *output_group, "--mount", "type=volume,src=" + source_volume + ",dst=/work,readonly",
                    "--mount", "type=bind,src=" + str(dest.resolve()) + ",dst=/evidence",
                    image_id, "python", "integration/ra4b/runtime_check.py"]
            if phase == "recovered":
                argv.append("--recovered")
            stop = threading.Event()
            control_errors = []

            def outage():
                paused = False
                try:
                    # The enclosing subprocess's 180-second budget bounds this
                    # wait; do not start a competing clock before client startup.
                    while not stop.wait(0.05):
                        if (dest / "db-down-ready.json").exists():
                            break
                    if stop.is_set():
                        return
                    lab.docker("pause", state["container"])
                    paused = True
                    (dest / "pg-paused.json").write_text('{"actual_owned_pg_paused":true}')
                    deadline = time.monotonic() + 15
                    while not stop.wait(0.05) and not (dest / "db-down-result.json").exists():
                        if time.monotonic() > deadline:
                            raise RuntimeError("OUTAGE_RESULT_DEADLINE")
                except Exception as e:
                    control_errors.append(type(e).__name__ + ": " + str(e))
                finally:
                    if paused:
                        lab.docker("unpause", state["container"])
                        (dest / "pg-resumed.json").write_text('{"actual_owned_pg_unpaused":true}')

            control = None
            if phase == "runtime":
                control = threading.Thread(target=outage)
                control.start()
            try:
                command(argv, dest / "supervisor", data=json.dumps(state).encode(), timeout=180)
            finally:
                stop.set()
                if control:
                    control.join(35)
                    assert not control.is_alive() and not control_errors, control_errors
            if phase == "runtime":
                state["expected_receipts"] = json.loads((dest / "receipts.json").read_bytes())
                # Real dump and restore stay inside this owned PG container; never publish DB bytes.
                command(["docker", "exec", state["container"], "pg_dump", "-U", "postgres", "-Fc", "-d", state["dbname"], "-f", "/tmp/b4.dump"], out / "dump")
                command(["docker", "exec", state["container"], "pg_restore", "-U", "postgres", "--clean", "--if-exists", "--create", "--exit-on-error", "-d", "postgres", "/tmp/b4.dump"], out / "restore")
                command(["docker", "restart", state["container"]], out / "pg-restart", timeout=60)
                lab.wait_target(state["container"], state["admin_password"], 60)
        (out / "result.json").write_text(json.dumps({"status": "PASS", "python": version, "actual_dump_restore_restart": True,
                                                     "gate": "B4_P1_CANDIDATE_NOT_G1_EXIT"}, indent=2))
    finally:
        # A failed/timeout client is removed by exact name and owned label only.
        check = subprocess.run(["docker", "inspect", "--format", '{{index .Config.Labels "vrae.ra4b.p1"}}', client_name], capture_output=True, timeout=20)
        if check.returncode == 0:
            assert check.stdout.strip() == b"TEST_ONLY"
            subprocess.run(["docker", "rm", "-f", client_name], check=True, capture_output=True, timeout=20)
        if lab.STATE.exists():
            state = json.loads(lab.STATE.read_bytes())
            lab.stop(out / "teardown", out / "startup")
        owned = subprocess.check_output(["docker", "volume", "inspect", "--format", '{{index .Labels "vrae.ra4b.p1"}}', source_volume]).strip()
        assert owned == b"TEST_ONLY"
        command(["docker", "volume", "rm", source_volume], out / "source-volume-remove")
        absent = subprocess.run(["docker", "volume", "inspect", source_volume], capture_output=True)
        assert absent.returncode and b"no such volume" in absent.stderr.lower()
        (out / "source-volume-cleanup.json").write_text(json.dumps({"owned_only": True, "absent": True, "volume": source_volume}))
        if state:
            secrets = [state["admin_password"], *state["runtime_passwords"].values()]
            assert not any(s.encode() in p.read_bytes() for p in out.rglob("*") if p.is_file() for s in secrets)
            (out / "credential-scan.json").write_text(json.dumps({"actual_secret_count": len(secrets), "matches": 0}))


if __name__ == "__main__":
    os.environ["PYTHONUTF8"] = "1"
    raise SystemExit(main(sys.argv[1]))

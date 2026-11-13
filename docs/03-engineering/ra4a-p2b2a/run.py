"""Executable local evidence workflow; no hosted services or repository mutations.

Usage: <isolated-python> docs/03-engineering/ra4a-p2b2a/run.py run <label>
Each Python run starts a fresh digest-pinned PG16 cluster and always tears it down.
Accepted helpers are imported unchanged; only their output/state paths are relocated.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
STATE_NAME = os.environ.get("RA4A_P2B2A_STATE", "lab-state")
assert STATE_NAME.replace("-", "").replace(".", "").isalnum()
STATE = HERE / ".runtime" / (STATE_NAME + ".json")


def scan_public_output(output, secrets, *, publish=False):
    assert output.resolve().is_relative_to(HERE)
    paths = [p for p in output.rglob("*") if p.is_file()
             and ".runtime" not in p.parts and "__pycache__" not in p.parts]
    token_pattern = rb"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{20,}"
    for path in paths:
        raw = path.read_bytes()
        if any(secret.encode() in raw for secret in secrets) or re.search(token_pattern, raw):
            raise RuntimeError("PUBLIC_EVIDENCE_CREDENTIAL_OR_TOKEN_LEAK_DENIED")
    result = {"actual_lab_secret_count": len(secrets), "scanned_public_files": len(paths),
              "actual_credential_scan": "NO_MATCHES", "bearer_token_scan": "NO_MATCHES",
              "publication_allowed": True}
    if publish:
        (output / "credential-scan.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def bootstrap():
    from infra.ra4a import lab
    from integration.ra4a import support

    lab.STATE = STATE
    support.STATE = STATE

    def output_path(path):
        path = Path(path).resolve()
        assert path.is_relative_to(HERE)
        return path

    lab.output_path = output_path
    return lab


def stage(name, out):
    lab = bootstrap()
    if name == "start":
        lab.start(out, 60)
        return 0
    if name == "stop":
        state = json.loads(STATE.read_text())
        secrets = [state["admin_password"], *state["runtime_passwords"].values()]
        # Always tear down even if the public-output privacy gate fails.
        try:
            scan_public_output(out.parent, secrets)
        finally:
            lab.stop(out, None)
        scan_public_output(out.parent, secrets, publish=True)
        return 0
    if name == "cleanup":
        if STATE.exists() or (out.parent / "start/ownership.json").exists():
            lab.stop(out, out.parent / "start")
        else:
            print("NO_STARTUP_OWNERSHIP_RECEIPT_NO_LAB_STARTED")
        return 0
    if name == "publication":
        proof = json.loads((out / "credential-scan.json").read_text())
        assert proof["publication_allowed"] is True and proof["actual_lab_secret_count"] > 0
        print("PUBLIC_EVIDENCE_CREDENTIAL_AND_TOKEN_SCAN_VERIFIED")
        return 0
    if name == "migrate1":
        from integration.ra4a.support import migrate
        migrate()
        return 0
    if name == "migrate2":
        from integration.ra4a.p2a_support import migrate_p2a
        migrate_p2a()
        return 0
    if name == "migrate3":
        from integration.ra4a.p2b1_support import migrate_p2b1
        migrate_p2b1()
        return 0
    if name == "lint":
        return subprocess.call([sys.executable, "-m", "ruff", "check", "vrae/identity",
                                "tests/identity", "integration/ra4a/p2b2a", str(HERE),
                                "--select", "E4,E7,E9,F"], cwd=ROOT)
    if name == "pip":
        return subprocess.call([sys.executable, "-m", "pip", "check"], cwd=ROOT)
    if name == "mypy":
        return subprocess.call([sys.executable, "-m", "mypy", "vrae"], cwd=ROOT)
    import pytest

    envs = {"RA4A_EVIDENCE_DIR": str(out), "RA4A_P2A_EVIDENCE_DIR": str(out),
            "RA4A_P2B1_EVIDENCE_DIR": str(out)}
    os.environ.update(envs)
    args = ["-q", "--import-mode=importlib", "-o", "consider_namespace_packages=true",
            "--junitxml=" + str(out / "tests.xml")]
    if name == "legacy":
        args += ["tests", "--ignore=tests/identity"]
    elif name == "crypto":
        args += ["tests/identity/crypto_cases.py"]
    elif name in ("pg1", "pg2"):
        args += ["integration/ra4a"]
    elif name == "p2a":
        args += ["-p", "integration.ra4a.p2a_plugin",
                 "--confcutdir=integration/ra4a/p2a", "integration/ra4a/p2a/cases.py",
                 "integration/ra4a/p2a/security_cases.py"]
    elif name in ("p2b1", "identity-pg"):
        target = "p2b1" if name == "p2b1" else "p2b2a"
        args += ["-p", "integration.ra4a.p2b1_plugin",
                 "--confcutdir=integration/ra4a/" + target]
        args += (["integration/ra4a/p2b1/cases.py", "integration/ra4a/p2b1/parity_cases.py"]
                 if name == "p2b1" else ["integration/ra4a/p2b2a/cases.py"])
    else:
        raise ValueError("UNKNOWN_STAGE")
    result = pytest.main(args)
    loaded = {name: str(module.STATE) for name, module in list(sys.modules.items())
              if name in ("integration.ra4a.support", "ra4a.support",
                          "integration.ra4a.p2a_support", "ra4a.p2a_support",
                          "integration.ra4a.p2b1_support", "ra4a.p2b1_support")}
    assert all(Path(path) == STATE for path in loaded.values()), "TEST_STATE_MODULE_SPLIT"
    (out / "module-state-paths.json").write_text(json.dumps(loaded, indent=2) + "\n", encoding="utf-8")
    return result


def run(label, pg_only=False, identity_only=False):
    assert label.replace("-", "").replace(".", "").isalnum()
    out = HERE / label
    out.mkdir(exist_ok=False)
    manifest = []
    for folder in ("vrae", "tests", "integration/ra4a", "db/migrations", "infra/ra4a"):
        for p in sorted((ROOT / folder).rglob("*")):
            if not p.is_file() or any(x in p.parts for x in ("__pycache__", ".venv")):
                continue
            raw = p.read_bytes()
            manifest.append({"path": p.relative_to(ROOT).as_posix(),
                             "byte_sha256": hashlib.sha256(raw).hexdigest(),
                             "lf_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()})
    import importlib.metadata
    record = {"python": sys.version, "executable": sys.executable,
              "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
              "parents": subprocess.check_output(["git", "show", "-s", "--format=%P", "HEAD"], cwd=ROOT).decode().split(),
              "github_sha": os.environ.get("GITHUB_SHA"),
              "github_head_ref": os.environ.get("GITHUB_HEAD_REF"),
              "dependencies": {p: importlib.metadata.version(p) for p in ("cryptography", "psycopg", "pytest")},
              "status": "TEST_ONLY_ENGINEERING_EVIDENCE_OWNER_REVIEW_REQUIRED",
              "source": manifest, "commands": []}

    def execute(name):
        dest = out / name
        if name != "start":
            dest.mkdir()
        argv = [sys.executable, str(Path(__file__).resolve()), "stage", name, str(dest)]
        before = time.monotonic()
        child_env = dict(os.environ, RA4A_P2B2A_STATE=label, PYTHONIOENCODING="utf-8",
                         PYTHONUTF8="1")
        if name == "start":
            private_temp = HERE / ".runtime/temp"
            private_temp.mkdir(parents=True, exist_ok=True)
            child_env.update(TMP=str(private_temp), TEMP=str(private_temp))
        p = subprocess.run(argv, cwd=ROOT, capture_output=True, env=child_env)
        dest.mkdir(exist_ok=True)
        row = {"stage": name, "argv": argv, "exit": p.returncode,
               "seconds": time.monotonic() - before}
        for kind, raw in (("stdout", p.stdout), ("stderr", p.stderr)):
            (dest / (kind + ".log")).write_bytes(raw)
            row[kind + "_sha256"] = hashlib.sha256(raw).hexdigest()
        record["commands"].append(row)
        (out / "execution.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(row), flush=True)
        if p.returncode:
            print("Captured diagnostics remain in the run directory; publication requires the privacy gate.")
            raise RuntimeError("LOCAL_STAGE_FAILED_" + name)

    started = False
    try:
        for name in (("lint", "pip", "mypy", "crypto") if pg_only or identity_only
                     else ("lint", "pip", "mypy", "crypto", "legacy")):
            execute(name)
        execute("start")
        started = True
        stages = (("migrate1", "migrate2", "migrate3", "identity-pg") if identity_only
                  else ("migrate1", "pg1", "migrate2", "pg2", "p2a", "migrate3", "p2b1", "identity-pg"))
        for name in stages:
            execute(name)
    finally:
        if started or (HERE / ".runtime" / (label + ".json")).exists():
            execute("stop")


if __name__ == "__main__":
    if sys.argv[1] == "stage":
        raise SystemExit(stage(sys.argv[2], Path(sys.argv[3])))
    assert sys.argv[1] == "run"
    run(sys.argv[2], pg_only="--pg-only" in sys.argv[3:],
        identity_only="--identity-only" in sys.argv[3:])

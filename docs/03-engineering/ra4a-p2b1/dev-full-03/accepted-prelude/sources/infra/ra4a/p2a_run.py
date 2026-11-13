"""Actual P1-v1/P1-v2/P2A phases, independently counted and raw evidence retained."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("output", type=Path)
    p.add_argument("--phase", choices=("full", "p2a"), default="full")
    a = p.parse_args()
    out = a.output.resolve()
    assert any(out.is_relative_to((ROOT / ('docs/03-engineering/' + name)).resolve())
               for name in ('ra4a-p2a','ra4a-p2b1'))
    out.mkdir(parents=True, exist_ok=False)
    record = {
        "python": sys.version,
        "checkout": os.environ.get("GITHUB_SHA"),
        "actual_source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
        .decode()
        .strip(),
        "phase": a.phase,
        "commands": [],
    }
    source = []
    for directory in (
        "vrae/persistence",
        "integration/ra4a",
        "tests/persistence",
        "infra/ra4a",
        "db/migrations",
    ):
        for path in sorted((ROOT / directory).rglob("*")):
            if path.is_file() and ".venv" not in path.parts and "__pycache__" not in path.parts:
                snapshot = out / "sources" / path.relative_to(ROOT)
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                snapshot.write_bytes(path.read_bytes())
                source.append(
                    {
                        "path": path.relative_to(ROOT).as_posix(),
                        "sha256": hashlib.sha256(
                            path.read_bytes().replace(b"\r\n", b"\n")
                        ).hexdigest(),
                    }
                )
    (out / "source-manifest.json").write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
    stages = []
    if a.phase == "full":
        stages.append(("p1-v1", ["infra/ra4a/run.py", str(out / "p1-v1")], {}))
    stages.append(("migration", ["-m", "integration.ra4a.p2a_support"], {}))
    if a.phase == "full":
        (out / "p1-v2").mkdir()
        stages.append(
            (
                "p1-v2",
                [
                    "-m",
                    "pytest",
                    "-q",
                    "integration/ra4a",
                    "--junitxml=" + str(out / "p1-v2/tests.xml"),
                ],
                {"RA4A_EVIDENCE_DIR": str(out / "p1-v2")},
            )
        )
    (out / "p2a").mkdir()
    stages.append(
        (
            "p2a",
            [
                "-m",
                "pytest",
                "-q",
                "-x",
                "-p",
                "integration.ra4a.p2a_plugin",
                "--confcutdir=integration/ra4a/p2a",
                "integration/ra4a/p2a/cases.py",
                "integration/ra4a/p2a/security_cases.py",
                "--junitxml=" + str(out / "p2a/tests.xml"),
            ],
            {"RA4A_P2A_EVIDENCE_DIR": str(out / "p2a")},
        )
    )
    for name, argv, overrides in stages:
        before = time.monotonic()
        result = subprocess.run(
            [sys.executable, *argv],
            cwd=ROOT,
            env=dict(os.environ, **overrides),
            capture_output=True,
        )
        for label, raw in (("stdout", result.stdout), ("stderr", result.stderr)):
            (out / (name + "." + label + ".log")).write_bytes(raw)
        row = {
            "stage": name,
            "exit": result.returncode,
            "seconds": time.monotonic() - before,
            "argv": [sys.executable, *argv],
            "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
        }
        record["commands"].append(row)
        (out / "commands.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(row), flush=True)
        if result.returncode:
            print(result.stdout.decode(errors="replace")[-6000:])
            print(result.stderr.decode(errors="replace")[-2000:])
            raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()

"""Record real local/hosted PG test execution, never convert RED to PASS."""

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
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(ROOT.resolve())
    output.mkdir(parents=True, exist_ok=False)
    sources = []
    for folder in (
        "vrae/persistence",
        "tests/persistence",
        "integration/ra4a",
        "db/migrations",
        "infra/ra4a",
    ):
        for path in sorted((ROOT / folder).rglob("*")):
            if not path.is_file() or ".venv" in path.parts or "__pycache__" in path.parts:
                continue
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            sources.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "lf_sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
    (output / "source-manifest.json").write_text(
        json.dumps(
            {
                "actual_git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
                .decode()
                .strip(),
                "files": sources,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    commands = [
        ("compile", ["-m", "compileall", "-q", "vrae/persistence"]),
        (
            "ruff",
            [
                "-m",
                "ruff",
                "check",
                "vrae",
                "tests",
                "integration/ra4a",
                "infra/ra4a",
                "--select",
                "E4,E7,E9,F",
            ],
        ),
        ("mypy", ["-m", "mypy", "vrae"]),
        (
            "pure",
            ["-m", "pytest", "-q", "tests/persistence", "--junitxml=" + str(output / "pure.xml")],
        ),
        (
            "postgres",
            [
                "-m",
                "pytest",
                "-q",
                "-x",
                "integration/ra4a",
                "--junitxml=" + str(output / "postgres.xml"),
            ],
        ),
        ("pip", ["-m", "pip", "check"]),
    ]
    env = dict(os.environ, RA4A_EVIDENCE_DIR=str(output))
    record = {
        "python": sys.version,
        "executable": sys.executable,
        "github_checkout": os.environ.get("GITHUB_SHA"),
        "commands": [],
    }
    for name, argv in commands:
        before = time.monotonic()
        p = subprocess.run([sys.executable, *argv], cwd=ROOT, env=env, capture_output=True)
        for label, raw in [("stdout", p.stdout), ("stderr", p.stderr)]:
            (output / (name + "." + label + ".log")).write_bytes(raw)
        row = {
            "name": name,
            "argv": [sys.executable, *argv],
            "exit": p.returncode,
            "seconds": time.monotonic() - before,
            "stdout_sha256": hashlib.sha256(p.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(p.stderr).hexdigest(),
        }
        record["commands"].append(row)
        (output / "commands.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(row), flush=True)
        if p.returncode:
            print(p.stdout.decode("utf-8", errors="replace")[-5000:], flush=True)
            print(p.stderr.decode("utf-8", errors="replace")[-1000:], flush=True)
            raise SystemExit(p.returncode)


if __name__ == "__main__":
    main()

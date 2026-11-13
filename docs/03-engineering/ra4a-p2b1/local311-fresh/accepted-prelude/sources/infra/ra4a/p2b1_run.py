"""Actual full accepted prelude then independently counted P2B1 PG cases."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--phase", choices=("full", "p2b1"), default="full")
    parser.add_argument("--case", default=None)
    args = parser.parse_args()
    out = args.output.resolve()
    assert out.is_relative_to((ROOT / "docs/03-engineering/ra4a-p2b1").resolve())
    out.mkdir(parents=True, exist_ok=False)
    if args.phase == "full":
        from integration.ra4a.support import connect

        with connect() as c:
            assert (
                c.execute("SELECT to_regclass('ra4a_private.migrations')").fetchone()[0] is None
            ), "P2B1_FRESH_CLUSTER_REQUIRED"
    record = {
        "python": sys.version,
        "checkout": os.environ.get("GITHUB_SHA"),
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
        .decode()
        .strip(),
        "phase": args.phase,
        "commands": [],
    }
    sources = []
    for directory in (
        "vrae/persistence",
        "integration/ra4a",
        "tests/persistence",
        "infra/ra4a",
        "db/migrations",
    ):
        for base, dirs, files in os.walk(ROOT / directory):
            dirs[:] = sorted(d for d in dirs if d not in (".venv", "__pycache__"))
            for name in sorted(files):
                p = Path(base) / name
                raw = p.read_bytes()
                dest = out / "sources" / p.relative_to(ROOT)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(raw)
                sources.append(
                    {
                        "path": p.relative_to(ROOT).as_posix(),
                        "sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
                    }
                )
    (out / "source-manifest.json").write_text(
        json.dumps(sources, indent=2) + "\n", encoding="utf-8"
    )
    stages = []
    if args.phase == "full":
        stages.append(
            ("accepted-prelude", ["infra/ra4a/p2a_run.py", str(out / "accepted-prelude")], {})
        )
    stages.append(("migration-v3", ["-m", "integration.ra4a.p2b1_support"], {}))
    (out / "p2b1").mkdir()
    test_args = [
        "-m",
        "pytest",
        "-q",
        "-x",
        "-p",
        "integration.ra4a.p2b1_plugin",
        "--confcutdir=integration/ra4a/p2b1",
        "integration/ra4a/p2b1/cases.py",
        "--junitxml=" + str(out / "p2b1/tests.xml"),
    ]
    if args.case:
        test_args += ["-k", args.case]
    stages.append(("p2b1", test_args, {"RA4A_P2B1_EVIDENCE_DIR": str(out / "p2b1")}))
    for name, argv, overrides in stages:
        before = time.monotonic()
        result = subprocess.run(
            [sys.executable, *argv],
            cwd=ROOT,
            env=dict(os.environ, **overrides),
            capture_output=True,
            check=False,
        )
        for label, raw in (("stdout", result.stdout), ("stderr", result.stderr)):
            (out / (name + "." + label + ".log")).write_bytes(raw)
        row = {
            "stage": name,
            "argv": [sys.executable, *argv],
            "exit": result.returncode,
            "seconds": time.monotonic() - before,
            "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
        }
        record["commands"].append(row)
        (out / "commands.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(row), flush=True)
        if result.returncode:
            print(result.stdout.decode(errors="replace")[-6500:])
            print(result.stderr.decode(errors="replace")[-1800:])
            raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()

"""Record latest-main integration checks without changing historical evidence."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
TARGET = Path(__file__).resolve().parent / f"python{sys.version_info.major}{sys.version_info.minor}"
TARGET.mkdir(exist_ok=True)
commands = [
    ["-m", "compileall", "-q", "vrae"],
    ["-m", "ruff", "check", "vrae", "tests", "--select", "E4,E7,E9,F"],
    ["-m", "mypy", "vrae"],
    ["-m", "pytest", "-q", "tests/rules/test_info01.py"],
    ["-m", "pytest", "-q"],
    ["-m", "pip", "check"],
    *[[f"scripts/verify_{name}.py"] for name in
      ("ra2a", "ra2b0", "ra2b1", "ra2b2", "ra2c0", "ra2b3", "ra2d0")],
]
results = []
for index, args in enumerate(commands, 1):
    proc = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True)
    log = f"{index}.log"
    (TARGET / log).write_bytes(proc.stdout + proc.stderr)
    results.append({"command": [sys.executable, *args], "exit_code": proc.returncode,
                    "log": log})
    print(f"{index}: exit={proc.returncode} {' '.join(args)}", flush=True)
(TARGET / "summary.json").write_text(json.dumps({
    "python": sys.version,
    "head_at_run": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "main": "1f88cc4148d2e905c387af82f5943683d3507a72",
    "checks": results,
}, indent=2) + "\n", encoding="utf-8")
sys.exit(int(any(item["exit_code"] for item in results)))

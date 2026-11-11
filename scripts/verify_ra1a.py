"""Reproducible full-gate runner; logs every command, exit, source hash and environment."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
output = Path(sys.argv[1]).resolve()
output.mkdir(parents=True, exist_ok=True)
lab = os.environ.get("VRAE_ISOLATED_LAB") == "1"
commands = [
    [sys.executable, "-m", "compileall", "-q", "vrae"],
    [sys.executable, "-m", "ruff", "check", "vrae", "tests", "--select", "E4,E7,E9,F"],
    [sys.executable, "-m", "mypy", "vrae"],
    [sys.executable, "-m", "pytest", "-q", *(["-s", "-p", "no:cacheprovider"] if lab else [])],
    [sys.executable, "-m", "pip", "check"],
]
files = sorted(p for folder in ("vrae", "tests", "contracts", "industry-packs", "infra/ra1a", "scripts", ".github/workflows")
               for p in (root / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
files += [root / "pyproject.toml", root / "requirements-ra1a.lock"]
summary = {"python": sys.version, "platform": platform.platform(), "prefix": sys.prefix,
           "base_prefix": sys.base_prefix, "isolated_lab": lab,
           "versions": {p: importlib.metadata.version(p) for p in
                        ("pytest", "jsonschema", "ruff", "mypy", "PyYAML", "h11", "dnspython")},
           "source_sha256": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in files}, "results": []}
for index, command in enumerate(commands):
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    name = f"{index + 1}-{command[2]}.log"
    (output / name).write_text("COMMAND=" + repr(command) + "\n" + result.stdout + result.stderr
                               + f"\nEXIT_CODE={result.returncode}\n", encoding="utf-8")
    summary["results"].append({"command": command, "started": started,
        "ended": datetime.now(timezone.utc).isoformat(), "exit_code": result.returncode, "log": name})
    print(name, "EXIT_CODE", result.returncode, flush=True)
    print(result.stdout if lab else result.stdout[-2000:], result.stderr, flush=True)
(output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
freeze = subprocess.run([sys.executable, "-m", "pip", "freeze", "--all"], capture_output=True, text=True)
(output / "freeze.txt").write_text(freeze.stdout, encoding="utf-8")
print("ENVIRONMENT=" + json.dumps({k:v for k,v in summary.items() if k != "source_sha256"}), flush=True)
sys.exit(int(any(r["exit_code"] for r in summary["results"])))

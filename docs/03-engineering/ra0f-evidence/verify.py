"""Run the complete RA-0 gates on the real checkout, retaining every exit code."""
import importlib.metadata
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[3]
label = sys.argv[1]
out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent
out.mkdir(parents=True, exist_ok=True)
source_files = sorted(p for folder in ("vrae", "tests", "contracts/v1", "industry-packs", ".github/workflows")
                      for p in (root / folder).rglob("*")
                      if p.is_file() and "__pycache__" not in p.parts)
source_files.append(root / "pyproject.toml")
commands = [
    [sys.executable, "-m", "compileall", "-q", "vrae"],
    [sys.executable, "-m", "ruff", "check", "vrae", "tests", "--select", "E4,E7,E9,F"],
    [sys.executable, "-m", "mypy", "vrae"],
    [sys.executable, "-m", "pytest", "-q"],
    [sys.executable, "-m", "pip", "check"],
]
summary = {"python": sys.version, "executable": sys.executable,
           "prefix": sys.prefix, "base_prefix": sys.base_prefix,
           "versions": {p: importlib.metadata.version(p) for p in
                        ("pytest", "jsonschema", "ruff", "mypy", "PyYAML")},
           "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
           "source_sha256": {str(p.relative_to(root)).replace("\\", "/"):
                             hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files},
           "results": []}
for index, command in enumerate(commands):
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    name = f"{label}-{index + 1}-{command[2]}.log"
    (out / name).write_text("COMMAND=" + repr(command) + "\n" + result.stdout + result.stderr
                            + f"\nEXIT_CODE={result.returncode}\n", encoding="utf-8")
    summary["results"].append({"command": command, "exit_code": result.returncode,
                               "started": started, "ended": datetime.now(timezone.utc).isoformat(), "log": name})
    print(name, result.returncode, result.stdout[-1500:], result.stderr[-500:], flush=True)
(out / f"{label}-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
freeze = subprocess.run([sys.executable, "-m", "pip", "freeze", "--all"], capture_output=True, text=True)
(out / f"{label}-freeze.txt").write_text(freeze.stdout, encoding="utf-8")
sys.exit(int(any(r["exit_code"] for r in summary["results"])))

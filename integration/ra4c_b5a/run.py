"""One fresh dual-minor CI job: security, separate HTTP/browser, safe export."""

import json
import os
import re
import subprocess
import sys

from .lab import ROOT, RUNTIME
from .publication import export, failure_export, source


def main():
    label = sys.argv[1]
    assert re.fullmatch(r"[a-z0-9-]{3,35}", label)
    private = RUNTIME / (label + "-driver")
    private.mkdir(parents=True, exist_ok=False)
    source_before = source()
    (private / "source-at-start.json").write_text(
        json.dumps(source_before, indent=2), encoding="utf-8"
    )
    for stage, module, suffix in (
        ("security", "dev_run", "-security"),
        ("browser", "browser_run", "-browser"),
    ):
        p = subprocess.run(
            [sys.executable, "-B", "-m", "integration.ra4c_b5a." + module, label + suffix],
            cwd=ROOT,
            env=dict(os.environ, PYTHONUTF8="1"),
            capture_output=True,
        )
        (private / (stage + "-stdout.log")).write_bytes(p.stdout)
        (private / (stage + "-stderr.log")).write_bytes(p.stderr)
        print(json.dumps({"stage": stage, "returncode": p.returncode}), flush=True)
        if p.returncode:
            failure_export(label, stage, p.returncode)
            raise SystemExit(p.returncode)
    assert source_before == source(), "B5A_SOURCE_CHANGED_DURING_ACTUAL_GATES"
    output = export(label)
    print(json.dumps({"status": "B5A_LOCAL_GATES_PASS", "public_output": str(output)}), flush=True)


if __name__ == "__main__":
    main()

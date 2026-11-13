"""Private development evidence; never print raw HTTP/JUnit failure payloads."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET


def main():
    label = sys.argv[1]
    assert re.fullmatch(r"[a-z0-9-]{3,48}", label)
    root = Path(__file__).resolve().parents[2]
    out = root / "integration/ra4c_b5a/.runtime" / ("results-" + label)
    out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, B5A_RUN=label, PYTHONUTF8="1")
    argv = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        "--import-mode=importlib",
        "--confcutdir=integration/ra4c_b5a",
        "integration/ra4c_b5a/cases.py",
        "--basetemp=" + str(out / "temp"),
        "--junitxml=" + str(out / "raw-junit.xml"),
        *sys.argv[2:],
    ]
    result = subprocess.run(argv, cwd=root, env=env, capture_output=True)
    (out / "stdout.log").write_bytes(result.stdout)
    (out / "stderr.log").write_bytes(result.stderr)
    cases = ET.parse(out / "raw-junit.xml").getroot().findall(".//testcase")
    red = [
        c.get("name")
        for c in cases
        if any(c.find(k) is not None for k in ["failure", "error", "skipped"])
    ]
    receipt = {
        "returncode": result.returncode,
        "tests": len(cases),
        "red_or_skipped_names": red,
        "raw_junit_sha256": hashlib.sha256((out / "raw-junit.xml").read_bytes()).hexdigest(),
    }
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt), flush=True)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()

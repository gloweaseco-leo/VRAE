"""Run accepted suites in place; only outputs and STATE are relocated to B5A."""

import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

from .lab import Lab, ROOT


def main():
    label = sys.argv[1]
    assert re.fullmatch(r"[a-z0-9-]{3,48}", label)
    private = ROOT / "integration/ra4c_b5a/.runtime" / label
    private.mkdir(exist_ok=False)
    records = []

    def command(name, args, extra=None):
        folder = private / name
        folder.mkdir()
        env = dict(os.environ, PYTHONUTF8="1")
        env.update(extra or {})
        result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True)
        (folder / "stdout.log").write_bytes(result.stdout)
        (folder / "stderr.log").write_bytes(result.stderr)
        xml = folder / "raw-junit.xml"
        item = {
            "stage": name,
            "returncode": result.returncode,
            "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
        }
        if xml.exists():
            cases = ET.parse(xml).findall(".//testcase")
            item.update(
                tests=len(cases),
                red=[
                    c.get("name")
                    for c in cases
                    if any(c.find(k) is not None for k in ("failure", "error", "skipped"))
                ],
            )
        records.append(item)
        (private / "receipt.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        print(json.dumps(item), flush=True)
        assert result.returncode == 0, "ACCEPTED_SUITE_RED_" + name

    c3root = private / "c3"
    c3env = {
        "B5A_C3_ROOT": str(c3root),
        "PYTHONPATH": str(ROOT / "integration/ra4c_b5a/compat")
        + os.pathsep
        + os.environ["PYTHONPATH"],
        "RA4C0_PYTHON": sys.executable,
        "NODE_OPTIONS": "--import=" + (ROOT / "integration/ra4c_b5a/legacy_paths.mjs").as_uri(),
    }
    if "--review-only" not in sys.argv[2:]:
        command(
            "c3-accepted",
            [
                sys.executable,
                "-B",
                "-m",
                "integration.ra4c_b5a.legacy_c3",
                str(c3root / "evidence/full"),
            ],
            c3env,
        )
    lab = Lab(label + "-review")
    try:
        lab.start()
        for stage, paths, plugin in [
            (
                "p2b1",
                ["integration/ra4a/p2b1/cases.py", "integration/ra4a/p2b1/parity_cases.py"],
                True,
            ),
            ("b2-pure", ["tests/identity/crypto_cases.py"], False),
            ("b2-pg", ["integration/ra4a/p2b2a/cases.py"], True),
        ]:
            if "--identity-only" in sys.argv[2:] and stage == "p2b1":
                continue
            folder = private / stage
            extra = {"B5A_LEGACY_STATE": str(lab.state_path), "RA4A_P2B1_EVIDENCE_DIR": str(folder)}
            plugins = ["-p", "integration.ra4c_b5a.pytest_adapter"]
            if plugin:
                plugins += ["-p", "integration.ra4a.p2b1_plugin"]
            command(
                stage,
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "pytest",
                    "-q",
                    "--tb=short",
                    "--import-mode=importlib",
                    "--confcutdir=integration/ra4a/p2b1",
                    *plugins,
                    *paths,
                    "--basetemp=" + str(private / (stage + "-temp")),
                    "--junitxml=" + str(folder / "raw-junit.xml"),
                ],
                extra,
            )
    finally:
        lab.stop()


if __name__ == "__main__":
    main()

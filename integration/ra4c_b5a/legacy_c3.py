"""Accepted C3 lab APIs and exact original tests, with B5A-only output paths.

The original CLI's ``-m lab`` creates a second module namespace and resets its
output root. Call its public bootstrap APIs here instead; do not change guards.
"""

import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

from integration.ra4c3 import lab


def main():
    out = lab.bounded(sys.argv[1])
    out.mkdir(parents=True, exist_ok=False)
    state, profile = (
        out.parent.parent / "runtime/state.json",
        out.parent.parent / "runtime/profile.json",
    )
    records = []

    def command(name, args, extra=None):
        folder = out / name
        folder.mkdir()
        env = dict(
            os.environ,
            RA4C3_STATE=str(state),
            RA4C3_PROFILE=str(profile),
            RA4A_EVIDENCE_DIR=str(folder),
            RA4A_P2A_EVIDENCE_DIR=str(folder),
        )
        env.update(extra or {})
        result = subprocess.run(args, cwd=lab.ROOT, env=env, capture_output=True)
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
        (out / "commands.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        print(json.dumps(item), flush=True)
        assert result.returncode == 0, "ORIGINAL_C3_STAGE_RED_" + name

    def pytest(name, args):
        command(
            name,
            [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "-q",
                "--import-mode=importlib",
                *args,
                "--basetemp=" + str(out.parent.parent / ("temp-" + name)),
                "--junitxml=" + str(out / name / "raw-junit.xml"),
            ],
        )

    try:
        lab.start(state, out / "startup", option_a_local_trial=True)
        value = json.loads(state.read_text())
        value["data_volume"] = value["volume"]
        state.write_text(json.dumps(value), encoding="utf-8")
        plugin = ["-p", "integration.ra4c3.pytest_adapter"]
        pytest("p1-v1", [*plugin, "integration/ra4a"])
        lab.migrate(state)
        pytest("p1-v2", [*plugin, "integration/ra4a"])
        pytest(
            "p2a",
            [
                *plugin,
                "-p",
                "integration.ra4a.p2a_plugin",
                "--confcutdir=integration/ra4a/p2a",
                "integration/ra4a/p2a/cases.py",
                "integration/ra4a/p2a/security_cases.py",
            ],
        )
        pytest("pure", ["tests/persistence"])
        lab.seed(state, profile)
        pytest(
            "c3",
            [
                "integration/ra4c3/test_readside.py",
                "integration/ra4c3/test_lab_cleanup.py",
                "integration/ra4c3/test_restart_read.py",
            ],
        )
        pytest("full", ["tests"])
        command("browser", ["node", "docs/03-engineering/ra4c3-pg-read/browser-test.mjs"])
    finally:
        if state.exists():
            held = json.loads(state.read_text())
            (out.parent.parent / "scan-credentials.json").write_text(
                json.dumps([held["admin_password"], *held["runtime_passwords"].values()]),
                encoding="utf-8",
            )
            lab.stop(state, out / "teardown")
        profile.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

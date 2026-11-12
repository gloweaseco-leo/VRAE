"""Read-only CI receipt. Does not select, skip or change any test outcome."""

import hashlib
import json
import os
from pathlib import Path
import sys

_CALLS = []


def pytest_runtest_logreport(report):
    if report.nodeid.startswith("tests/reviewing/") and report.when == "call":
        _CALLS.append(
            {
                "id": report.nodeid,
                "outcome": report.outcome,
                "properties": list(report.user_properties),
            }
        )


def pytest_sessionfinish(session, exitstatus):
    selected = [i.nodeid for i in session.items if i.nodeid.startswith("tests/reviewing/")]
    if not selected:
        return
    root = Path(__file__).resolve().parents[2]
    hashes = []
    for folder in ("vrae/reviewing", "tests/reviewing"):
        for path in sorted((root / folder).rglob("*")):
            if path.suffix not in (".py", ".json") or "__pycache__" in path.parts:
                continue
            raw = path.read_bytes()
            hashes.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "actual_bytes_sha256": hashlib.sha256(raw).hexdigest(),
                    "lf_bytes_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
                }
            )
    receipt = {
        "kind": "RA3D_D1D2_ACTUAL_OFFLINE_TEST_CALLS_NOT_REAL_APPROVAL",
        "python": sys.version,
        "github_checkout": os.environ.get("GITHUB_SHA"),
        "collected": len(selected),
        "called": len(_CALLS),
        "passed": sum(c["outcome"] == "passed" for c in _CALLS),
        "calls": _CALLS,
        "source_hashes": hashes,
        "session_exit": int(exitstatus),
        "real_human_decisions": 0,
        "native_approvals": 0,
        "share_grants": 0,
    }
    terminal = session.config.pluginmanager.getplugin("terminalreporter")
    if terminal is not None:
        terminal.write_line("RA3D_D1D2_ACTUAL_RECEIPT=" + json.dumps(receipt, sort_keys=True))

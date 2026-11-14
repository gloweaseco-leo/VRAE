"""One frozen-source, real PG/signed HTTP/Chromium run with bounded safe exports."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / "integration/ra4c_b5p0/.runtime"
DOC = ROOT / "docs/03-engineering/ra4c-b5p0/evidence"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source():
    files = list((ROOT / "apps/operator_console").glob("b5p0_*.py"))
    files += list((ROOT / "tests/operator_console").glob("test_b5p0_*.py"))
    files += [
        p
        for p in (ROOT / "integration/ra4c_b5p0").rglob("*")
        if p.is_file() and not any(x in {".runtime", "__pycache__"} for x in p.parts)
    ]
    workflow = ROOT / ".github/workflows/ra4c-b5p0.yml"
    if workflow.exists():
        files.append(workflow)
    return {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in sorted(files)}


def main():
    label = sys.argv[1]
    assert re.fullmatch(r"[a-z0-9-]{3,30}", label)
    private = PRIVATE / (label + "-driver")
    private.mkdir(parents=True, exist_ok=False)
    public = DOC / label
    public.mkdir(parents=True, exist_ok=False)
    before = source()
    native = private / "native-junit.xml"
    env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", B5P0_LABEL=label)
    p = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--tb=short",
            "--show-capture=no",
            "tests/operator_console/test_b5p0_boundaries.py",
            "integration/ra4c_b5p0/cases.py",
            "--junitxml=" + str(native),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
    )
    (private / "security-stdout.log").write_bytes(p.stdout)
    (private / "security-stderr.log").write_bytes(p.stderr)
    cases = list(ET.parse(native).getroot().iter("testcase")) if native.exists() else []
    red = [
        c.attrib["name"]
        for c in cases
        if any(c.find(x) is not None for x in ("failure", "error", "skipped"))
    ]
    summary = {
        "python": sys.version.split()[0],
        "security_returncode": p.returncode,
        "tests": len(cases),
        "passed": len(cases) - len(red),
        "red_or_skipped": red,
        "native_junit_sha256": sha(native.read_bytes()) if native.exists() else None,
        "source_unchanged": source() == before,
        "authority": "TEST_ONLY_REVIEW_INTENT",
        "effective_approval": False,
        "external_visibility": False,
    }
    if len(cases) != 55:
        summary["unexpected_test_count"] = True
    (public / "source.json").write_text(json.dumps(before, sort_keys=True), encoding="utf-8")
    if p.returncode or red or len(cases) != 55 or source() != before:
        (public / "summary.json").write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")
        print(json.dumps(summary), flush=True)
        raise SystemExit(1)
    browser_label = label + "-browser"
    browser = subprocess.run(
        [sys.executable, "-B", "-m", "integration.ra4c_b5p0.browser_run", browser_label],
        cwd=ROOT,
        env=env,
        capture_output=True,
    )
    (private / "browser-stdout.log").write_bytes(browser.stdout)
    (private / "browser-stderr.log").write_bytes(browser.stderr)
    summary["browser_returncode"] = browser.returncode
    summary["source_unchanged"] = source() == before
    if browser.returncode or source() != before:
        (public / "summary.json").write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")
        print(json.dumps(summary), flush=True)
        raise SystemExit(1)
    browser_dir = PRIVATE / browser_label / "browser-output"
    report = json.loads((browser_dir / "browser.json").read_bytes())
    assert len(report["shots"]) == 12
    assert all(row["pass"] for row in report["records"]) and not report["exceptions"]
    summary["browser_assertions"] = len(report["records"])
    summary["screenshots"] = 12
    # Exact allowlist; scan text exports against actual private credentials/caps.
    secrets = []
    for path in PRIVATE.glob(label + "*/**/scan-secrets.json"):
        secrets += json.loads(path.read_bytes())
    safe = {
        "native-junit.xml": native.read_bytes(),
        "browser.json": (browser_dir / "browser.json").read_bytes(),
        "browser-receipt.json": (browser_dir / "browser-receipt.json").read_bytes(),
        "postgres-observations.json": json.dumps(
            [
                json.loads(p.read_bytes())
                for p in sorted(PRIVATE.glob(label + "-security-*/case-*/observations.json"))
            ],
            sort_keys=True,
        ).encode(),
        "cleanup.json": json.dumps(
            [json.loads(p.read_bytes()) for p in sorted(PRIVATE.glob(label + "*/**/cleanup.json"))],
            sort_keys=True,
        ).encode(),
    }
    for name, raw in safe.items():
        assert not any(value and value.encode() in raw for value in secrets)
        assert not re.search(rb"Bearer\s+|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.", raw)
        (public / name).write_bytes(raw)
    for shot in report["shots"]:
        assert re.fullmatch(r"(form|receipt)-(1280|375|320)-(404|200)\.png", shot["file"])
        raw = (browser_dir / shot["file"]).read_bytes()
        assert sha(raw) == shot["sha256"]
        (public / shot["file"]).write_bytes(raw)
    assert source() == before
    cleanups = [json.loads(p.read_bytes()) for p in PRIVATE.glob(label + "*/**/cleanup.json")]
    assert len(cleanups) >= len(cases) - 2 + 1
    assert all(
        c.get("database_dropped") is True
        or (c.get("port_closed") and all(r["absent"] for r in c["resources"]))
        for c in cleanups
    )
    summary["cleanup_observed"] = True
    summary["cleanup_environments"] = len(cleanups)
    (public / "summary.json").write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")
    from .publication import seal

    seal(public)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()

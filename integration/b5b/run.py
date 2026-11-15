"""Frozen-source native PG/HTTP/Chromium execution and allowlisted publication."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zlib

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = Path(__file__).resolve().parent / ".runtime"
PUBLIC = ROOT / "docs/03-engineering/b5b/evidence"
TARGETS = [
    "tests/operator_console/test_b5p0_boundaries.py",
    "integration/ra4c_b5p0/cases.py",
    "integration/b5b/cases.py",
    "integration/b5b/pure_cases.py",
]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source():
    files = list((ROOT / "apps/operator_console").glob("*.py"))
    for name in (
        "integration/b5b",
        "integration/ra4c_b5p0",
        "integration/ra4c_b5a",
        "vrae/b3_p0",
        "vrae/b6_p0",
    ):
        files += [
            p
            for p in (ROOT / name).rglob("*")
            if p.is_file() and not {".runtime", "__pycache__"} & set(p.parts)
        ]
    files += [ROOT / p for p in TARGETS if not p.startswith("integration/b5b/")]
    files += [ROOT / ".github/workflows/b5b.yml"]
    tracked = {}
    for entry in subprocess.check_output(["git", "ls-tree", "-rz", "HEAD"], cwd=ROOT).split(b"\0"):
        if entry:
            header, name = entry.split(b"\t", 1)
            tracked[name.decode()] = header.decode().split()[2]
    result = {}
    for p in sorted(set(files)):
        name = p.relative_to(ROOT).as_posix()
        raw = p.read_bytes()
        assert (
            hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            == tracked[name]
        ), name
        result[name] = sha(raw)
    return result


def main(label):
    assert re.fullmatch(r"[a-z0-9-]{3,25}", label)
    private = PRIVATE / (label + "-driver")
    public = PUBLIC / label
    private.mkdir(parents=True, exist_ok=False)
    public.mkdir(parents=True, exist_ok=False)
    frozen = source()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    env = dict(
        os.environ,
        PYTHONUTF8="1",
        PYTHONDONTWRITEBYTECODE="1",
        B5B_LABEL=label + "-new",
        B5P0_LABEL=label + "-legacy",
    )
    native = private / "native-junit.xml"
    with (
        (private / "native.stdout.log").open("wb") as out,
        (private / "native.stderr.log").open("wb") as err,
    ):
        result = subprocess.run(
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
                *TARGETS,
                "--junitxml=" + str(native),
                "--basetemp=" + str(private / "pytest-tmp"),
            ],
            cwd=ROOT,
            env=env,
            stdout=out,
            stderr=err,
        )
    cases = list(ET.fromstring(native.read_bytes()).iter("testcase")) if native.exists() else []
    bad = [c for c in cases if any(c.find(k) is not None for k in ("failure", "error", "skipped"))]
    summary = {
        "source_head": head,
        "python": sys.version.split()[0],
        "native_exit": result.returncode,
        "native_tests": len(cases),
        "native_passed": len(cases) - len(bad),
        "native_red_or_skipped": len(bad),
        "worker_result": "BLOCKED_NO_ACCEPTED_LEASE_BOUND_RESULT_PORT",
        "Reviewer_task_status": "BLOCKED_NO_ACCEPTED_REVIEWER_TASK_STATUS_PORT",
        "authority": "TEST_ONLY_REVIEW_INTENT",
        "effective_approval": False,
        "external_delivery_allowed": False,
    }

    def publish_summary(status):
        summary["status"] = status
        summary["source_unchanged"] = source() == frozen
        (public / "summary.json").write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")
        (public / "source.json").write_text(json.dumps(frozen, sort_keys=True), encoding="utf-8")
        print(json.dumps(summary), flush=True)

    if result.returncode or bad or len(cases) != 94:
        # Preserve genuine native failure outcomes using the accepted B4
        # sanitizer; never publish raw traceback/credentials or fabricate XML.
        if native.exists():
            from integration.ra4b.evidence import sanitized_junit

            raw_native = native.read_bytes()
            curated, _ = sanitized_junit(raw_native)
            (public / "native-junit.xml").write_bytes(curated)
            (public / "native-retention.json").write_text(
                json.dumps(
                    {
                        "raw_native_sha256": sha(raw_native),
                        "raw_native_crc32": format(zlib.crc32(raw_native) & 0xFFFFFFFF, "08x"),
                        "public_curated_sha256": sha(curated),
                        "cases": len(cases),
                        "passed": len(cases) - len(bad),
                        "raw_xml_private": True,
                        "stdout_constructed_xml": False,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
        publish_summary("TRUE_NATIVE_RED_RETAINED_PRIVATE")
        raise SystemExit(1)
    with (
        (private / "browser.stdout.log").open("wb") as out,
        (private / "browser.stderr.log").open("wb") as err,
    ):
        browser = subprocess.run(
            [sys.executable, "-B", "-m", "integration.b5b.browser_run", label + "-browser"],
            cwd=ROOT,
            env=env,
            stdout=out,
            stderr=err,
        )
    if browser.returncode:
        publish_summary("TRUE_BROWSER_RED_RETAINED_PRIVATE")
        raise SystemExit(1)
    browser_root = PRIVATE / (label + "-browser")
    roots = list((ROOT / "integration/ra4c_b5p0/.runtime").glob(label + "-legacy-security-*"))
    roots += list(PRIVATE.glob(label + "-new-pg-*")) + [browser_root]
    assert len(roots) == 3
    cleanup = [json.loads(p.read_bytes()) for root in roots for p in root.rglob("cleanup.json")]
    assert len(cleanup) == 86
    assert all(
        c.get("database_dropped") is True
        or c.get("port_closed") is True
        and len(c["resources"]) == 3
        and all(r["absent"] for r in c["resources"])
        for c in cleanup
    )
    observations = [
        json.loads(p.read_bytes()) for root in roots for p in root.rglob("observations.json")
    ]
    assert len(observations) == 84
    assert all(o["protected_roots_before"] == o["protected_roots_after"] for o in observations)
    secrets = []
    for root in roots:
        for p in root.rglob("scan-secrets.json"):
            secrets += json.loads(p.read_bytes())
        for p in root.rglob("bridge.json"):
            secrets.append(json.loads(p.read_bytes())["key_secret"])
    safe = {
        "native-junit.xml": native.read_bytes(),
        "cleanup.json": json.dumps(cleanup, sort_keys=True).encode(),
        "postgres-observations.json": json.dumps(observations, sort_keys=True).encode(),
        "browser-summary.json": (browser_root / "browser-summary.json").read_bytes(),
    }
    retention = {
        "sha256": sha(native.read_bytes()),
        "crc32": format(zlib.crc32(native.read_bytes()) & 0xFFFFFFFF, "08x"),
        "cases": 94,
        "passed": 94,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "stdout_constructed_xml": False,
    }
    safe["native-retention.json"] = json.dumps(retention, sort_keys=True).encode()
    counts = {}
    for name, shots in [("accepted", 12), ("b5b", 18)]:
        folder = browser_root / (name + "-browser")
        raw = (folder / "browser.json").read_bytes()
        report = json.loads(raw)
        assert (
            len(report["shots"]) == shots
            and all(a["pass"] for a in report["records"])
            and not report["exceptions"]
        )
        assert json.loads((folder / "browser-process-cleanup.json").read_bytes())["exit_observed"]
        counts[name] = len(report["records"])
        safe["browser-" + name + ".json"] = raw
        for shot in report["shots"]:
            assert re.fullmatch(
                r"(form|receipt|preview|document|blocked)-(1280|375|320)-(404|200)\.png",
                shot["file"],
            )
            image = (folder / shot["file"]).read_bytes()
            assert sha(image) == shot["sha256"]
            safe[name + "-" + shot["file"]] = image
    assert counts["accepted"] == 63
    for name, raw in safe.items():
        if not name.endswith(".png"):
            assert not any(secret and secret.encode() in raw for secret in secrets)
            assert not re.search(rb"Bearer\s+|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.", raw)
        (public / name).write_bytes(raw)
    assert source() == frozen
    summary.update(
        {
            "browser_assertions": counts,
            "screenshots": 30,
            "cleanup_records": 86,
            "protected_originals_unchanged": True,
            "external_delivery_sends": 0,
            "publication_secret_matches": 0,
            "public_file_sha256": {name: sha(raw) for name, raw in safe.items()},
        }
    )
    publish_summary("B5B_INCREMENTAL_NATIVE_PASS_RESULT_PORTS_STILL_BLOCKED")


if __name__ == "__main__":
    main(sys.argv[1])

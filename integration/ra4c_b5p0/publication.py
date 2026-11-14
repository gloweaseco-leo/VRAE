"""Bounded, hash-checked evidence; no private source or credentials are published."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
BASE = "ae2505f74f7a81d7a563c05d1a811aaa526c2839"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def allowed(path):
    return bool(
        re.fullmatch(
            r"apps/operator_console/b5p0_[^/]+\.py|integration/ra4c_b5p0/.+|"
            r"tests/operator_console/test_b5p0_[^/]+\.py|docs/03-engineering/ra4c-b5p0/.+|"
            r"\.github/workflows/ra4c-b5p0\.yml",
            path,
        )
    )


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def inventory():
    baseline = git("ls-tree", "-r", "-z", BASE)
    original = {}
    for row in baseline.split(b"\0"):
        if row:
            fields, path = row.split(b"\t", 1)
            mode, kind, oid = fields.decode().split()
            assert kind == "blob"
            original[path.decode()] = (mode, oid)
    # Existing index entries retain both the accepted blob and mode. Working
    # tree changes are checked separately by Git's actual clean filters.
    index = {}
    for row in git("ls-files", "-s", "-z").split(b"\0"):
        if row:
            fields, path = row.split(b"\t", 1)
            mode, oid, stage = fields.decode().split()
            assert stage == "0"
            index[path.decode()] = (mode, oid)
    assert all(index.get(path) == item for path, item in original.items())
    for row in git("diff", "--name-status", BASE).decode().splitlines():
        status, path = row.split("\t", 1)
        assert status == "A" and allowed(path), (status, path)
    untracked = git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0")
    assert all(not path or allowed(path) for path in untracked)
    changed = sorted(set(index) - set(original) | {p for p in untracked if p})
    return {
        "accepted_base": BASE,
        "accepted_files": len(original),
        "accepted_git_tree_listing_sha256": sha(baseline),
        "accepted_blobs_and_modes_unchanged": True,
        "allowed_new_paths": changed,
    }


def seal(folder):
    folder = Path(folder)
    rows = {
        p.name: {"sha256": sha(p.read_bytes()), "bytes": p.stat().st_size}
        for p in sorted(folder.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    (folder / "manifest.json").write_bytes(encode(rows))
    verify(folder)


def verify(folder):
    from .run import source

    folder = Path(folder)
    allowed_names = {
        "native-junit.xml",
        "browser.json",
        "browser-receipt.json",
        "summary.json",
        "source.json",
        "postgres-observations.json",
        "cleanup.json",
        "manifest.json",
    } | {
        f"{kind}-{width}-{case}.png"
        for kind in ("form", "receipt")
        for width in (1280, 375, 320)
        for case in (404, 200)
    }
    assert {p.name for p in folder.iterdir()} == allowed_names
    manifest = json.loads((folder / "manifest.json").read_bytes())
    assert set(manifest) == allowed_names - {"manifest.json"}
    for name, item in manifest.items():
        raw = (folder / name).read_bytes()
        assert item == {"sha256": sha(raw), "bytes": len(raw)}
        if not name.endswith(".png"):
            assert not re.search(
                rb"Bearer\s+|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.|postgresql://|BEGIN PRIVATE KEY",
                raw,
            )
    assert json.loads((folder / "source.json").read_bytes()) == source()
    summary = json.loads((folder / "summary.json").read_bytes())
    assert summary["tests"] == summary["passed"] == 55
    assert not summary["red_or_skipped"]
    assert summary["security_returncode"] == summary["browser_returncode"] == 0
    assert summary["source_unchanged"] and summary["cleanup_observed"]
    native = (folder / "native-junit.xml").read_bytes()
    assert sha(native) == summary["native_junit_sha256"]
    suites = ET.fromstring(native)
    assert len(list(suites.iter("testcase"))) == 55
    for node in suites.iter():
        assert node.tag in {"testsuites", "testsuite", "testcase"}
        assert not (node.text or "").strip()
    browser = json.loads((folder / "browser.json").read_bytes())
    assert len(browser["records"]) == summary["browser_assertions"]
    assert all(row["pass"] for row in browser["records"]) and not browser["exceptions"]
    assert len(browser["shots"]) == summary["screenshots"] == 12
    for shot in browser["shots"]:
        assert manifest[shot["file"]]["sha256"] == shot["sha256"]
    observations = json.loads((folder / "postgres-observations.json").read_bytes())
    assert len(observations) == 53
    assert len({item["case_id"] for item in observations}) == 53
    states = {row["sqlstate"] for item in observations for row in item["sqlstates"]}
    assert {"P0002", "42501"} <= states
    cleanup = json.loads((folder / "cleanup.json").read_bytes())
    assert len(cleanup) == 55  # 53 real case DBs + security PG16 + browser PG16.
    assert all(
        c.get("database_dropped") is True
        or (c.get("port_closed") and all(r["absent"] for r in c["resources"]))
        for c in cleanup
    )
    return {"status": "B5P0_PUBLICATION_VERIFIED", "files": len(allowed_names), "tests": 55}


if __name__ == "__main__":
    if sys.argv[1] == "inventory":
        print(json.dumps(inventory(), ensure_ascii=False))
    else:
        print(json.dumps(verify(sys.argv[1])))

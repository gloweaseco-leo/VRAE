"""Offline source/JUnit/example attestation, never an availability claim."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

from contracts.l2_launch.contract import validate
from tests.l2_launch.make_examples import build

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/03-engineering/l2-launch"
BASE = "89a5115e3b8c4ab782bc140d3d278ffc83e7cc7a"
PREFIXES = ("contracts/l2_launch/", "docs/03-engineering/l2-launch/", "tests/l2_launch/")
CI = ".github/workflows/l2-launch-r0.yml"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def verify_inputs():
    baseline = json.loads((DOC / "inputs.json").read_text(encoding="utf-8"))
    assert baseline["vrae_base_sha"] == BASE
    for path, record in baseline["frozen_sources"].items():
        raw = git("show", BASE + ":" + path)
        assert hashlib.sha256(raw).hexdigest() == record["sha256"], path
        assert (
            git("hash-object", "--path", path, path).decode().strip() == record["git_blob_sha1"]
        ), path
    paths = git("diff", "--name-only", BASE, "--").decode().splitlines()
    paths += git("ls-files", "--others", "--exclude-standard").decode().splitlines()
    assert all(p.startswith(PREFIXES) or p == CI for p in paths), paths
    return baseline


def verify_examples():
    expected = build()
    folder = ROOT / "contracts/l2_launch/examples"
    assert {p.stem for p in folder.glob("*.json")} == set(expected)
    for name, sample in expected.items():
        actual = json.loads((folder / (name + ".json")).read_text(encoding="utf-8"))
        assert actual == sample, name
        validate(actual["type"], actual["body"])
    return len(expected)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    baseline = verify_inputs()
    example_count = verify_examples()
    raw = Path(args.junit).read_bytes()
    suite = ET.fromstring(raw)
    cases = suite.findall(".//testcase")
    consumer = [c for c in cases if "l2_launch.consumer_cases" in c.get("classname", "")]
    vfb_consumer = [c for c in consumer if c.get("name", "").startswith("test_vfb_")]
    assert (
        len(consumer) >= 160
        and len(vfb_consumer) >= 80
        and not suite.findall(".//failure")
        and not suite.findall(".//error")
        and not suite.findall(".//skipped")
    )
    files = [
        p
        for base in PREFIXES
        for p in (ROOT / base).rglob("*")
        if p.is_file()
        and p.suffix in {".py", ".json", ".md"}
        and "__pycache__" not in p.parts
        and ".runtime" not in p.parts
    ]
    files.append(ROOT / CI)
    hashes = {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(files)
    }
    clean = not git("status", "--porcelain", "--untracked-files=all").strip()
    receipt = {
        "scope": "R0_CONTRACT_CANDIDATE_NOT_G0_NOT_A_LIVE_SERVICE",
        "source_sha": git("rev-parse", "HEAD").decode().strip(),
        "source_binding": "CLEAN_COMMIT" if clean else "WORKING_TREE_UNCOMMITTED",
        "base_sha": BASE,
        "native_python": sys.version,
        "platform": platform.system(),
        "consumer_pass": len(consumer),
        "vf_b_consumer_pass": len(vfb_consumer),
        "total_selected_pass": len(cases),
        "examples": example_count,
        "junit_sha256": hashlib.sha256(raw).hexdigest(),
        "frozen_sources_verified": len(baseline["frozen_sources"]),
        "vf_source_commit": baseline["vf_source"]["commit"],
        "vf_source_sha256": baseline["vf_source"]["sha256"],
        "vf_b_candidate_source": baseline["vf_b_candidate"],
        "source_files_sha256": hashes,
        "network_boundary": "PYTHON_SOCKET_DNS_DENY_HOOK_NOT_KERNEL_ISOLATION",
        "target_network_attempts": 0,
        "real_client_data": False,
        "real_provider_calls": 0,
        "formal_human_review": False,
        "real_share_grants": False,
        "real_vf_receipts": False,
        "live_availability": "NOT_AVAILABLE",
    }
    output = Path(args.output).resolve()
    assert output.is_relative_to((DOC / ".runtime").resolve()), "OWNED_EVIDENCE_PATH_REQUIRED"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in receipt.items() if k != "source_files_sha256"}))


if __name__ == "__main__":
    main()

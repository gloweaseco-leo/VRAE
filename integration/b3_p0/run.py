"""Fresh local/hosted PG16 run; preserve raw private failures and scan bounded exports."""

import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

from .support import ROOT, encode, sha


def source():
    names = []
    for base in ["db/b3_p0", "vrae/b3_p0", "contracts/b3_p0", "integration/b3_p0", "tests/b3_p0"]:
        names += [
            p
            for p in (ROOT / base).rglob("*")
            if p.is_file() and not any(v in {".runtime", "__pycache__"} for v in p.parts)
        ]
    workflow = ROOT / ".github/workflows/b3-p0.yml"
    if workflow.exists():
        names.append(workflow)
    return {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in sorted(names)}


def main():
    label = sys.argv[1]
    assert re.fullmatch(r"[a-z0-9-]{3,35}", label)
    private = ROOT / "integration/b3_p0/.runtime" / label
    private.mkdir(parents=True, exist_ok=False)
    out = ROOT / "docs/03-engineering/b3-p0/evidence" / label
    out.mkdir(parents=True, exist_ok=False)
    before = source()
    (private / "source-start.json").write_bytes(encode(before))
    native = private / "native-junit.xml"
    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONUTF8="1",
        B3_RUN_LABEL=label + "-pg",
        B3_OBSERVATIONS=str(private / "observations"),
        TMP=str(private),
        TEMP=str(private),
    )
    p = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-q",
            "tests/b3_p0",
            "integration/b3_p0",
            "--tb=short",
            "-p",
            "no:cacheprovider",
            "--show-capture=no",
            "--junitxml=" + str(native),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
    )
    (private / "stdout.log").write_bytes(p.stdout)
    (private / "stderr.log").write_bytes(p.stderr)
    suites = ET.parse(native).getroot() if native.exists() else None
    testcases = list(suites.iter("testcase")) if suites is not None else []
    failed = [
        t for t in testcases if any(t.find(k) is not None for k in ("failure", "error", "skipped"))
    ]
    summary = {
        "python": sys.version.split()[0],
        "returncode": p.returncode,
        "tests": len(testcases),
        "passed": len(testcases) - len(failed),
        "failures_errors_skips": len(failed),
        "source_unchanged": before == source(),
        "native_junit_sha256": sha(native.read_bytes()) if native.exists() else None,
        "private_stdout_sha256": sha(p.stdout),
        "private_stderr_sha256": sha(p.stderr),
        "authority": "TEST_ONLY_REVIEW_INTENT",
        "effective_approval": False,
        "external_visibility": False,
        "schema_sha256": sha(
            (ROOT / "db/b3_p0/testonly_schema.sql").read_bytes().replace(b"\r\n", b"\n")
        ),
        "failed_case_ids": [t.attrib.get("name") for t in failed],
    }
    # No raw failure trace, SQL result, source object, DSN or credential is exported.
    (out / "summary.json").write_bytes(encode(summary))
    (out / "source.json").write_bytes(encode(before))
    if p.returncode == 0 and not failed and before == source() and len(testcases) >= 100:
        # Passing native XML is allowlisted only after an exact structural check.
        for node in suites.iter():
            assert node.tag in {"testsuites", "testsuite", "testcase"}
            assert not (node.text or "").strip()
            for value in node.attrib.values():
                assert not any(
                    s in value.lower()
                    for s in [
                        "password=",
                        "postgresql://",
                        "objects_base64",
                        "begin private key",
                        "set-cookie",
                    ]
                )
        (out / "native-junit.xml").write_bytes(native.read_bytes())
        observations = {
            p.name: json.loads(p.read_bytes()) for p in (private / "observations").glob("*.json")
        }
        raw_observations = encode(observations)
        assert not any(
            s in raw_observations.lower()
            for s in [
                b"password",
                b"postgresql://",
                b"objects_base64",
                b"raw_command",
                b"canonical_command",
                b"witness_id",
            ]
        )
        (out / "observations.json").write_bytes(raw_observations)
        print(json.dumps(summary), flush=True)
        return
    print(json.dumps(summary), flush=True)
    raise SystemExit(p.returncode or 1)


if __name__ == "__main__":
    main()

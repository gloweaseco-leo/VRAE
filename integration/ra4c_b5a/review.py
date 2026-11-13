"""Reviewable source/publication gate before the single authorized Draft push."""

import json
from pathlib import Path
import re
import subprocess
import sys

from .publication import ROOT, RUNTIME, ENTRY, sha, source


def main():
    original = set(
        subprocess.check_output(["git", "ls-tree", "-r", "--name-only", ENTRY], cwd=ROOT)
        .decode()
        .splitlines()
    )
    changed = set(
        subprocess.check_output(["git", "diff", "--name-only", ENTRY], cwd=ROOT)
        .decode()
        .splitlines()
    )
    changed.update(
        subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT)
        .decode()
        .splitlines()
    )
    assert not changed & original, "ACCEPTED_SOURCE_MODIFIED"
    patterns = [
        r"apps/operator_console/b5a_[a-z0-9_]+\.py",
        r"tests/operator_console/test_b5a_[a-z0-9_]+\.py",
        r"integration/ra4c_b5a/(?!.*(?:\.runtime|__pycache__))(?:[a-z0-9_/-]+\.(?:py|mjs)|\.gitignore)",
        r"docs/03-engineering/ra4c-b5a/[a-zA-Z0-9_./-]+\.(?:md|json|xml|png)",
        r"\.github/workflows/ra4c-b5a\.yml",
    ]
    assert changed and all(any(re.fullmatch(p, name) for p in patterns) for name in changed), (
        "OUT_OF_SCOPE_PATH"
    )
    secrets = []
    for file in RUNTIME.rglob("scan-credentials.json"):
        secrets += json.loads(file.read_text(encoding="utf-8"))
    forbidden = [
        re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY"),
        re.compile(rb"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
        re.compile(rb"postgres(?:ql)?://[^\s\"']+:[^\s\"']+@"),
    ]
    records = []
    for name in sorted(changed):
        file = ROOT / name
        assert file.is_file() and not file.is_symlink()
        raw = file.read_bytes()
        assert not any(
            s.encode() in raw or (s.startswith("Bearer ") and s[7:].encode() in raw)
            for s in secrets
            if len(s) >= 12
        ), "ACTUAL_CREDENTIAL_SCAN_RED"
        assert not any(p.search(raw) for p in forbidden), "SECRET_PATTERN_SCAN_RED"
        records.append({"path": name, "bytes": len(raw), "sha256": sha(raw)})
    proof = {
        "status": "NEW_PATHS_ONLY_SOURCE_AND_ACTUAL_CREDENTIAL_SCAN_PASS",
        "files": records,
        "source": source(),
        "mode": "TEST_ONLY_READ_ONLY_NO_APPROVAL_NO_SHARE",
    }
    if len(sys.argv) == 2:
        output = Path(sys.argv[1]).resolve()
        assert output.is_relative_to(ROOT / "docs/03-engineering/ra4c-b5a")
        output.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"status": proof["status"], "files": len(records), "accepted_files_modified": 0}
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

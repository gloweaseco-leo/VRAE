"""Publish complete cleared evidence, or safe failure metadata without raw secrets."""

import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
PATTERNS = (rb"password=[A-Za-z0-9_-]{24,}", rb"Bearer [A-Za-z0-9_-]{32,}",
            rb'"(?:password|admin_password|bearer)"\s*:\s*"[A-Za-z0-9_-]{24,}"',
            rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
            rb"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{20,}")


def main(slug):
    assert slug in ("311", "313")
    output = HERE / ("ci-public-" + slug)
    output.mkdir(exist_ok=False)
    phases = [HERE / ("ci-" + name + "-" + slug) for name in ("pg", "unit", "runtime")]
    blockers, ledger, counts = [], [], {}
    for phase in phases:
        if not (phase / "result.json").exists():
            blockers.append({"phase": phase.name, "reason": "INCOMPLETE_OR_FAILED_GATE"})
        if phase.name.startswith(("ci-pg-", "ci-runtime-")):
            scan = phase / "credential-scan.json"
            if not scan.exists() or json.loads(scan.read_bytes()).get("matches") != 0:
                blockers.append({"phase": phase.name, "reason": "ACTUAL_CREDENTIAL_CLEARANCE_MISSING"})
        for path in sorted(phase.rglob("*")):
            if not path.is_file():
                continue
            raw = path.read_bytes()
            relative = path.relative_to(HERE).as_posix()
            ledger.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest()})
            if any(re.search(pattern, raw) for pattern in PATTERNS):
                blockers.append({"path": relative, "reason": "SENSITIVE_PATTERN_PUBLICATION_DENIED"})
            if path.suffix == ".xml":
                root = ET.fromstring(raw)
                counts[relative] = {"cases": len(list(root.iter("testcase"))), "failures": len(list(root.iter("failure"))),
                                    "errors": len(list(root.iter("error"))), "skipped": len(list(root.iter("skipped")))}
    report = {"status": "BLOCKED_SAFE_FAILURE_METADATA_ONLY" if blockers else "CLEARED_COMPLETE_EVIDENCE",
              "blockers": blockers, "native_junit_counts": counts, "raw_source_sha256": ledger,
              "gate": "B4_P1_CANDIDATE_NOT_G1_EXIT", "real_human_approvals": 0, "share_grants": 0}
    (output / "publication.json").write_text(json.dumps(report, indent=2) + "\n")
    if blockers:
        print(json.dumps({"publication": "BLOCKED", "blocker_count": len(blockers)}))
        return 1
    for phase in phases:
        shutil.copytree(phase, output / phase.name)
    print(json.dumps({"publication": "CLEARED", "files": len(ledger)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))

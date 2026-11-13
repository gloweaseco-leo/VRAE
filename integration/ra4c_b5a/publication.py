"""Allowlisted, fail-closed public export. Native XML/logs remain protected."""

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

from .lab import ROOT, RUNTIME

ENTRY = "6257ad3acb09d046d954301117134f6992c02d84"
OWN = ROOT / "docs/03-engineering/ra4c-b5a"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def public_junit(raw):
    """Rebuild names/status only; never copy exception text or XML properties."""
    cases = ET.fromstring(raw).findall(".//testcase")
    suite = ET.Element(
        "testsuite",
        name="B5A actual Reviewer PG16 HTTP",
        tests=str(len(cases)),
        failures=str(sum(c.find("failure") is not None for c in cases)),
        errors=str(sum(c.find("error") is not None for c in cases)),
        skipped=str(sum(c.find("skipped") is not None for c in cases)),
    )
    for c in cases:
        name = c.attrib["name"]
        base = name.split("[", 1)[0]
        assert re.fullmatch(r"test_[a-zA-Z0-9_]+", base)
        # Parameter IDs can themselves contain HTTP bodies/paths. Keep a stable
        # case identity without copying any parameter input into public XML.
        public_name = base + ("__param_" + sha(name.encode())[:12] if name != base else "")
        safe = ET.SubElement(suite, "testcase", name=public_name, classname="B5A")
        for kind in ("failure", "error", "skipped"):
            if c.find(kind) is not None:
                ET.SubElement(safe, kind, message="Protected original retained; digest in receipt")
    return ET.tostring(suite, encoding="utf-8", xml_declaration=True)


def source():
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT).decode().strip()

    original = dict(line.split("\t", 1)[::-1] for line in git("ls-tree", "-r", ENTRY).splitlines())
    changed = git("diff", "--name-only", ENTRY).splitlines()
    assert not set(original) & set(changed), "ACCEPTED_SOURCE_CHANGED"
    pins = {}
    for name in (
        "vrae/identity/boundary.py",
        "apps/operator_console/native.py",
        "apps/operator_console/targets.py",
        "apps/operator_console/service.py",
        "apps/operator_console/proposal_views.py",
        "vrae/persistence/private_bytes.py",
        "db/migrations/0001_ra4a_test_only.sql",
        "db/migrations/0002_ra4a_private_bytes.sql",
        "db/migrations/0003_ra4a_test_review_cas.sql",
    ):
        raw = (ROOT / name).read_bytes().replace(b"\r\n", b"\n")
        pins[name] = {"git_entry": original[name], "lf_sha256": sha(raw)}
    additions = {}
    for pattern in (
        "apps/operator_console/b5a_*.py",
        "integration/ra4c_b5a/**/*.py",
        "integration/ra4c_b5a/*.mjs",
        "tests/operator_console/test_b5a_*.py",
        ".github/workflows/ra4c-b5a.yml",
    ):
        for file in ROOT.glob(pattern):
            if ".runtime" not in file.parts:
                additions[file.relative_to(ROOT).as_posix()] = sha(
                    file.read_bytes().replace(b"\r\n", b"\n")
                )
    return {
        "accepted_entry": ENTRY,
        "head": git("rev-parse", "HEAD"),
        "head_and_ordered_parents": git("log", "-1", "--format=%H %P"),
        "accepted_files_modified": [],
        "accepted_interface_pins": pins,
        "b5a_working_source_lf_sha256": additions,
    }


def scan(folder):
    folder = Path(folder).resolve()
    assert folder.is_relative_to(OWN.resolve())
    secrets = []
    for file in RUNTIME.rglob("scan-credentials.json"):
        secrets += json.loads(file.read_text(encoding="utf-8"))
    forbidden = [
        re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY"),
        re.compile(rb"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
        re.compile(rb"postgres(?:ql)?://[^\s\"']+:[^\s\"']+@"),
    ]
    files = []
    for file in sorted(folder.rglob("*")):
        if not file.is_file():
            continue
        raw = file.read_bytes()
        assert not any(secret.encode() in raw for secret in secrets if len(secret) >= 12), (
            "CREDENTIAL_SCAN_RED"
        )
        assert not any(p.search(raw) for p in forbidden), "SECRET_PATTERN_SCAN_RED"
        files.append(
            {"path": file.relative_to(folder).as_posix(), "bytes": len(raw), "sha256": sha(raw)}
        )
    return {"status": "ALLOWLIST_AND_ACTUAL_CREDENTIAL_SCAN_PASS", "files": files}


def export(label, *, security_label=None, browser_label=None):
    assert re.fullmatch(r"[a-z0-9-]{3,48}", label)
    out = OWN / "evidence" / label
    out.mkdir(parents=True, exist_ok=False)
    security_label = security_label or label + "-security"
    browser_label = browser_label or label + "-browser"
    assert all(re.fullmatch(r"[a-z0-9-]{3,48}", x) for x in (security_label, browser_label))
    security = RUNTIME / ("results-" + security_label)
    receipt = json.loads((security / "receipt.json").read_text())
    assert receipt["returncode"] == 0 and not receipt["red_or_skipped_names"]
    raw = (security / "raw-junit.xml").read_bytes()
    (out / "security-junit.xml").write_bytes(public_junit(raw))
    (out / "security-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    private = RUNTIME / security_label
    for name in ("zero-business-writes.json", "reviewer-sqlstate.json", "cleanup.json"):
        shutil.copyfile(private / name, out / name)
    browser = OWN / "evidence" / browser_label
    report = json.loads((browser / "receipt.json").read_text())
    assert report["business_tables_unchanged"] and report["sqlstate42501_observed"]
    (out / "browser").mkdir()
    for file in browser.iterdir():
        assert file.name in ("browser.json", "receipt.json", "assertions.json") or re.fullmatch(
            r"(?:review|composer|result)-(?:1280|375|320)-(?:404|200)\.png", file.name
        )
        shutil.copyfile(file, out / "browser" / file.name)
    (out / "source.json").write_text(json.dumps(source(), indent=2), encoding="utf-8")
    gate = scan(out)
    (out / "publication.json").write_text(json.dumps(gate, indent=2), encoding="utf-8")
    return out


def failure_export(label, stage, returncode):
    """Publish fixed RED facts and status-only XML, never raw failure payloads."""
    assert re.fullmatch(r"[a-z0-9-]{3,35}", label) and stage in ("security", "browser")
    out = OWN / "evidence" / label
    out.mkdir(parents=True, exist_ok=False)
    facts = {"status": "RED", "stage": stage, "returncode": returncode}
    raw_path = RUNTIME / ("results-" + label + "-security") / "raw-junit.xml"
    if raw_path.exists():
        raw = raw_path.read_bytes()
        (out / "security-junit.xml").write_bytes(public_junit(raw))
        facts["protected_native_junit_sha256"] = sha(raw)
    (out / "failure.json").write_text(json.dumps(facts, indent=2), encoding="utf-8")
    (out / "source.json").write_text(json.dumps(source(), indent=2), encoding="utf-8")
    (out / "publication.json").write_text(json.dumps(scan(out), indent=2), encoding="utf-8")


if __name__ == "__main__":
    import sys

    assert len(sys.argv) == 3 and sys.argv[1] == "verify"
    label = sys.argv[2]
    assert re.fullmatch(r"[a-z0-9-]{3,48}", label)
    output = OWN / "evidence" / label
    assert (output / "publication.json").is_file()
    scan(output)
    print("B5A_BOUNDED_PUBLICATION_PASS")

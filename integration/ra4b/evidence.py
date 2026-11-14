"""B4 test-output access and bounded diagnostics; no application authority."""
import hashlib
import json
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET

PREFIX = "RA4B_SAFE_STAGE_RESULT="
EVIDENCE_ROOT = Path(__file__).resolve().parents[2] / "docs/03-engineering/ra4b-p1"


def prepare_output(path, *, fixture_gid=None):
    path = Path(path)
    assert path.resolve().is_relative_to(EVIDENCE_ROOT.resolve()) and path.is_dir() and not path.is_symlink()
    info = path.stat()
    if hasattr(os, "getuid"):
        assert info.st_uid == os.getuid(), "FRESH_OUTPUT_MUST_BE_OWNED_BY_LAB_RUNNER"
    # Only the fresh test-output directory. Do not chmod configs, workspace,
    # input graphs, or role credentials. Others lose access; no capabilities,
    # network, user identity or database grants are added.
    path.chmod(0o770)
    gid = info.st_gid if fixture_gid is None else fixture_gid
    assert isinstance(gid, int) and (gid == 0 or 1000 <= gid < 2**31), "NO_PRIVILEGED_SYSTEM_GROUP"
    return ["--group-add", str(gid)]


def probe_output(path=Path("/evidence")):
    path = Path(path)
    assert path == Path("/evidence") and not path.is_symlink()
    info = path.stat()
    record = {"uid": os.getuid(), "gid": os.getgid(), "groups": os.getgroups(),
              "output_uid": info.st_uid, "output_gid": info.st_gid, "output_mode": oct(info.st_mode & 0o777)}
    probe = path / (".ra4b-output-probe-" + str(os.getpid()))
    fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    probe.unlink()
    return record


def safe_case_name(value):
    base = re.sub(r"[^A-Za-z0-9_.:-]", "_", value.split("[", 1)[0])[:160]
    return base + "#" + hashlib.sha256(value.encode()).hexdigest()[:16]


def native_counts(path):
    try:
        if not Path(path).is_file():
            return None
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    return {"cases": len(list(root.iter("testcase"))), "failures": len(list(root.iter("failure"))),
            "errors": len(list(root.iter("error"))), "skipped": len(list(root.iter("skipped")))}


def emit_stage(record, *, primary_failure=False):
    # Callers construct this closed schema from stage enums, exception class,
    # errno, native counts and numeric filesystem facts. Never add exception
    # messages, repr(args), payloads, raw traces, DSNs, headers or credentials.
    print(PREFIX + json.dumps(record, sort_keys=True), flush=True)
    try:
        name = "runtime-stage-result.json" if record.get("phase") == "RUNTIME" else "unit-stage-result.json"
        Path("/evidence", name).write_text(json.dumps(record, indent=2))
    except OSError:
        if not primary_failure:
            raise


def sanitized_junit(raw):
    original = ET.fromstring(raw)
    cases = list(original.iter("testcase"))
    counts = {"tests": len(cases), "failures": len(list(original.iter("failure"))),
              "errors": len(list(original.iter("error"))), "skipped": len(list(original.iter("skipped")))}
    root = ET.Element("testsuites", name="NATIVE_JUNIT_SANITIZED_PUBLIC_VIEW")
    suite = ET.SubElement(root, "testsuite", name="pytest", **{k: str(v) for k, v in counts.items()})
    for case in cases:
        attrs = {"classname": re.sub(r"[^A-Za-z0-9_.]", "_", case.get("classname", ""))[:256],
                 "name": safe_case_name(case.get("name", ""))}
        entry = ET.SubElement(suite, "testcase", **attrs)
        for kind in ("failure", "error", "skipped"):
            for body in case.findall(kind):
                element = ET.SubElement(entry, kind, message="ORIGINAL_NATIVE_" + kind.upper() + "_REDACTED")
                element.text = "Original detail SHA256=" + hashlib.sha256(ET.tostring(body)).hexdigest()
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), counts


def console_stage(record):
    """Only fixed enums/class identifiers, numbers and count maps reach stdout."""
    result = {}
    for key in ("phase", "stage", "status", "exception_type"):
        value = record.get(key)
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", value):
            result[key] = value
    for key in ("errno", "native_exit"):
        value = record.get(key)
        if value is None or isinstance(value, int):
            result[key] = value
    counts = record.get("native_counts")
    if isinstance(counts, dict):
        result["native_counts"] = {k: v for k, v in counts.items() if k in ("cases", "failures", "errors", "skipped") and isinstance(v, int)}
    return result

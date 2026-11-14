"""Synthetic formatter/gate unit cases; never PG/Worker acceptance evidence."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ci_publication as subject  # noqa: E402


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def fixture(root):
    for phase, status in (("pg", "PG_AND_FROZEN_PRELUDE_PASS_NOT_FINAL_RUNTIME_PASS"),
                          ("unit", "ORDINARY_PASS_SEPARATE_ISOLATED_GATES_REQUIRED"), ("runtime", "PASS")):
        folder = root / ("ci-" + phase + "-311")
        put(folder / "result.json", {"status": status})
        put(folder / ("teardown.json" if phase == "unit" else "teardown/teardown.json"),
            {"owned_container_removed": True, "owned_network_removed": True, "owned_volume_removed": True})
        if phase != "unit":
            put(folder / "credential-scan.json", {"matches": 0, "actual_secret_count": 0})
    unit = root / "ci-unit-311"
    (unit / "tests.xml").write_text('<testsuites><testsuite><testcase classname="synthetic.publication" name="schema_case[user@example.invalid]"/></testsuite></testsuites>')
    return unit


def exported_text(output):
    # The SHA ledger mentions omitted paths, but contains no raw input values.
    return "\n".join(p.read_text() for p in output.rglob("*") if p.is_file())


def test_raw_dump_graph_and_logs_are_not_exported(tmp_path):
    unit = fixture(tmp_path)
    marker = "SYNTHETIC_NONPUBLIC_RAW_CONTENT_" + "x" * 40
    for name in ("example.dump", "example.bin", "stdout.log"):
        (unit / name).write_text(marker)
    output = tmp_path / "public"
    assert subject.main("311", evidence_root=tmp_path, output_dir=output) == 0
    assert marker not in exported_text(output)
    assert not any(p.suffix in {".dump", ".bin", ".log"} for p in output.rglob("*"))
    assert "user@example.invalid" not in (output / "ci-unit-311/tests.xml").read_text()


def test_native_failure_exit_and_counts_remain_failure(tmp_path):
    unit = fixture(tmp_path)
    marker = "SYNTHETIC_PRIVATE_ASSERTION_DETAIL_" + "q" * 40
    root = ET.Element("testsuite")
    case = ET.SubElement(root, "testcase", classname="synthetic.publication", name="failed_case[private-parameter]")
    ET.SubElement(case, "failure", message=marker).text = marker
    (unit / "tests.xml").write_bytes(ET.tostring(root))
    output = tmp_path / "public"
    assert subject.main("311", evidence_root=tmp_path, output_dir=output) == 1
    report = json.loads((output / "publication.json").read_bytes())
    assert report["native_junit_counts"]["ci-unit-311/tests.xml"]["failures"] == 1
    assert len(list(ET.parse(output / "ci-unit-311/tests.xml").getroot().iter("failure"))) == 1
    assert marker not in exported_text(output)


def test_missing_gate_is_explicit_harness_error(tmp_path):
    fixture(tmp_path)
    (tmp_path / "ci-unit-311/result.json").unlink()
    output = tmp_path / "public"
    assert subject.main("311", evidence_root=tmp_path, output_dir=output) == 1
    assert list(ET.parse(output / "harness-stages.xml").getroot().iter("error"))


def test_stdout_only_permission_diagnostic_is_bounded(tmp_path):
    unit = fixture(tmp_path)
    marker = "SYNTHETIC_UNTRUSTED_ERROR_MESSAGE_" + "z" * 40
    (unit / "supervisor.stdout.log").write_text(subject.PREFIX + json.dumps({"phase": "UNIT", "stage": "OUTPUT_PREFLIGHT",
        "status": "FAIL", "exception_type": "PermissionError", "errno": 13, "untrusted_message": marker}))
    output = tmp_path / "public"
    assert subject.main("311", evidence_root=tmp_path, output_dir=output) == 1
    report = json.loads((output / "publication.json").read_bytes())
    assert report["bounded_stage_results"][0]["errno"] == 13
    assert marker not in exported_text(output)
    assert list(ET.parse(output / "harness-stages.xml").getroot().iter("error"))


def test_catalog_call_payloads_are_never_copied(tmp_path):
    fixture(tmp_path)
    marker = "SYNTHETIC_NONPUBLIC_CALL_PAYLOAD_" + "x" * 40
    put(tmp_path / "ci-pg-311/pg-catalog-and-calls.json", {"roles": [["ra4b_test_a_app", False]], "calls": [{"payload": marker}]})
    output = tmp_path / "public"
    assert subject.main("311", evidence_root=tmp_path, output_dir=output) == 0
    catalog = json.loads((output / "ci-pg-311/pg-catalog-and-calls.json").read_bytes())
    assert "roles" in catalog and "calls" not in catalog and marker not in exported_text(output)


def test_secret_scan_still_blocks_but_never_exports_value(tmp_path):
    unit = fixture(tmp_path)
    marker = "SYNTHETIC_TEST_SECRET_" + "S" * 40
    (unit / "stderr.log").write_text("password=" + marker)
    output = tmp_path / "public"
    assert subject.main("311", evidence_root=tmp_path, output_dir=output) == 1
    assert marker not in exported_text(output)
    report = json.loads((output / "publication.json").read_bytes())
    assert any(r["reason"] == "SENSITIVE_PATTERN_RAW_PUBLICATION_DENIED" for r in report["blockers"])


def test_non_null_native_authority_is_not_public_metadata(tmp_path):
    fixture(tmp_path)
    put(tmp_path / "ci-runtime-311/runtime-result.json", {"status": "PASS", "native_approval": "APPROVED"})
    output = tmp_path / "public"
    assert subject.main("311", evidence_root=tmp_path, output_dir=output) == 1
    assert not (output / "ci-runtime-311/runtime-result.json").exists()


def test_native_xml_retention_digest_survives_without_private_parameter_ids(tmp_path):
    unit = fixture(tmp_path)
    marker = "SYNTHETIC_PRIVATE_PARAMETER_" + "x" * 40
    put(unit / "native-junit-retention.json", {
        "status": "NATIVE_JUNIT_RETAINED_AFTER_COMPLETE_CLEANUP",
        "sha256": "a" * 64, "crc32": "a1b2c3d4", "bytes": 123,
        "cases": 1, "passed": 1, "skipped": 0, "failed": 0, "errors": 0,
        "raw_xml_private": True, "stdout_used_to_construct_xml": False,
        "test_ids": [marker],
    })
    output = tmp_path / "public"
    assert subject.main("311", evidence_root=tmp_path, output_dir=output) == 0
    retained = json.loads((output / "ci-unit-311/native-junit-retention.json").read_bytes())
    assert retained["sha256"] == "a" * 64 and retained["crc32"] == "a1b2c3d4"
    assert "test_ids" not in retained and marker not in exported_text(output)

"""Full suite in an isolated Linux Python minor with a secret-free source copy."""

from collections import Counter
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import uuid
import hashlib
import zlib
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))


INVENTORY_REFERENCE = ROOT / "docs/03-engineering/ra4c-b5p0/inventory-compat/accepted-original-inventory.json"
INVENTORY_REFERENCE_SHA256 = "2f8a0119af678ce79b6bf0734eab080659497fa6727c4298769227c62617ae5a"
APPROVED_B5_IDS = (
    ("tests.operator_console.test_b5p0_boundaries", "test_synthetic_mapping_is_deterministic_and_exactly_scoped"),
    ("tests.operator_console.test_b5p0_boundaries", "test_recovery_journal_preserves_original_key_across_new_instance"),
)


def _multiset_sha256(counter):
    rows = [[classname, name, count] for (classname, name), count in sorted(counter.items())]
    return hashlib.sha256(json.dumps(rows, ensure_ascii=True, separators=(",", ":")).encode("ascii")).hexdigest()


def _verify_b5_inventory(cases, minor):
    """Only the independently frozen original multiset plus these two B5 IDs.

    Reference IDs came from clean accepted447005b native executions per minor,
    never subtraction from PR89. Future B6 tests require separate Owner scope.
    """
    raw_reference = INVENTORY_REFERENCE.read_bytes()
    assert hashlib.sha256(raw_reference).hexdigest() == INVENTORY_REFERENCE_SHA256
    reference = json.loads(raw_reference)
    assert reference["accepted_source_commit"] == "447005b2951f43e8d8643632d663de268f278329"
    assert minor in {"3.11", "3.13"}
    baseline = reference["python"][minor]
    assert baseline["cases"] == 2473 and baseline["skips"] == 25
    assert len(cases) == 2475
    assert all(c.find(tag) is None for c in cases for tag in ("failure", "error"))
    assert all(c.get("classname") and c.get("name") for c in cases)
    actual = Counter((c.get("classname"), c.get("name")) for c in cases)
    original = actual.copy()
    for key in APPROVED_B5_IDS:
        assert actual[key] == 1, "APPROVED_B5_ID_MISSING_OR_DUPLICATED"
        approved_case = next(c for c in cases if (c.get("classname"), c.get("name")) == key)
        assert all(approved_case.find(tag) is None for tag in ("skipped", "failure", "error"))
        original[key] -= 1
        del original[key]  # Exactly one verified instance was removed.
    assert sum(original.values()) == 2473
    original_digest = _multiset_sha256(original)
    assert original_digest == baseline["id_multiset_sha256"], "ACCEPTED_ORIGINAL_ID_MULTISET_CHANGED"
    skipped = [c for c in cases if c.find("skipped") is not None]
    assert len(skipped) == 25 and all(c.find("skipped").get("type") == "pytest.skip" for c in skipped)
    skipped_digest = _multiset_sha256(Counter((c.get("classname"), c.get("name")) for c in skipped))
    assert skipped_digest == baseline["skipped_id_multiset_sha256"], "ACCEPTED_SKIPPED_IDS_CHANGED"
    return {"kind": "EXACT_ORIGINAL_MULTISET_PLUS_TWO_APPROVED_B5_IDS", "python": minor,
            "reference_sha256": INVENTORY_REFERENCE_SHA256, "baseline_cases": 2473, "actual_cases": 2475,
            "approved_cases": 2, "skipped_cases": 25, "actual_multiset_sha256": _multiset_sha256(actual),
            "actual_original_multiset_sha256": original_digest,
            "baseline_original_multiset_sha256": baseline["id_multiset_sha256"],
            "actual_skipped_multiset_sha256": skipped_digest,
            "baseline_skipped_multiset_sha256": baseline["skipped_id_multiset_sha256"],
            "baseline_raw_native_junit_sha256": baseline["raw_native_junit_sha256"]}


def _write_host_retention(out, producer_raw, retention):
    """Create a host-owned attestation; never open the producer for writing."""
    producer = out / "result.json"
    assert producer.read_bytes() == producer_raw, "PRODUCER_RESULT_CHANGED"
    status = json.loads(producer_raw)["status"]
    assert status == "ORDINARY_PASS_SEPARATE_ISOLATED_GATES_REQUIRED"
    before_sha256 = hashlib.sha256(producer_raw).hexdigest()
    # Exclusive creation prevents replacing either producer or existing receipt.
    with (out / "native-junit-retention.json").open("x", encoding="utf-8", newline="\n") as receipt:
        if hasattr(os, "getuid"):
            assert os.fstat(receipt.fileno()).st_uid == os.getuid(), "RECEIPT_NOT_HOST_OWNED"
        after_raw = producer.read_bytes()
        assert after_raw == producer_raw, "PRODUCER_RESULT_CHANGED"
        retention.update({"producer_result_before_sha256": before_sha256,
                          "producer_result_after_sha256": hashlib.sha256(after_raw).hexdigest(),
                          "producer_result_status": status, "producer_result_unchanged": True})
        receipt.write(json.dumps(retention, indent=2))
        receipt.flush()
        os.fsync(receipt.fileno())
    assert producer.read_bytes() == producer_raw, "PRODUCER_RESULT_CHANGED_AFTER_RECEIPT"


def main(label):
    from runtime_lab import command, source_tar
    from integration.ra4b.evidence import prepare_output
    fixture = "--linux-output-owner-fixture" in sys.argv
    preflight_only = "--output-preflight-only" in sys.argv
    reuse_image = "--reuse-pinned-image" in sys.argv
    assert not preflight_only or fixture
    out = (HERE / ".runtime/owner-review" if "--private-output" in sys.argv else HERE) / label
    out.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir(exist_ok=False)
    output_group = prepare_output(out, fixture_gid=1001 if fixture else None)
    private = HERE / ".runtime" / label
    private.mkdir(parents=True, exist_ok=False)
    context = private / "build"
    context.mkdir()
    for name in ("requirements-ra1a.lock", "requirements-ra4a.lock", "requirements-ra4b-p1.lock"):
        shutil.copyfile(ROOT / name, context / name)
    shutil.copyfile(ROOT / "integration/ra4b/Dockerfile", context / "Dockerfile")
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    ordinary_timeout = 3600
    if "--local-313-ordinary-wait-5400" in sys.argv:
        assert "--private-output" in sys.argv and "--linux-output-owner-fixture" in sys.argv
        assert version == "3.13"
        ordinary_timeout = 5400
    image = "vrae-ra4b-p1:" + version.replace(".", "")
    base = json.loads((ROOT / "integration/ra4b/python-images.json").read_bytes())[version]
    if reuse_image:
        expected_index = sys.argv.index("--expected-image-sha256") + 1
        actual_image = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", image]).decode().strip()
        assert actual_image == sys.argv[expected_index], "EXISTING_PINNED_IMAGE_MISMATCH"
        (out / "pinned-image.json").write_text(json.dumps({"image_id": actual_image, "base": base, "rebuild": False}))
        image = actual_image  # A concurrent tag change cannot change this run.
    else:
        command(["docker", "build", "--build-arg", "PYTHON_BASE=" + base, "-t", image, str(context)], out / "build", timeout=900)
    archive = private / "source.tar.gz"
    manifest = source_tar(archive)
    (out / "source.json").write_text(json.dumps(manifest, indent=2))
    ident = "vrae-ra4b-unit-" + uuid.uuid4().hex[:12]
    volume = ident + "-source"
    output_volume = ident + "-evidence" if fixture else None
    created = []
    try:
        command(["docker", "volume", "create", "--label", "vrae.ra4b.unit=TEST_ONLY", volume], out / "volume-create")
        created.append(volume)
        mount = "type=bind,src=" + str(out.resolve()) + ",dst=/evidence"
        if output_volume:
            # A native persistent Docker volume preserves the completed native
            # JUnit after the test container exits. tmpfs loses its bytes when
            # the last mount disappears, before docker cp can export them.
            command(["docker", "volume", "create", "--label", "vrae.ra4b.unit=TEST_ONLY", output_volume], out / "evidence-volume-create")
            created.append(output_volume)
            initializer = ident + "-output-init"
            try:
                # Bootstrap only the empty output volume; no source, tests,
                # application or credentials enter this initializer. Its CHOWN
                # capability is never present in the actual test container.
                command(["docker", "run", "--name", initializer, "--label", "vrae.ra4b.unit=TEST_ONLY",
                         "--network", "none", "--read-only", "--cap-drop", "ALL", "--cap-add", "CHOWN",
                         "--group-add", "1001", "--security-opt", "no-new-privileges", "--memory", "64m", "--pids-limit", "16",
                         "--mount", "type=volume,src=" + output_volume + ",dst=/evidence", image, "python", "-c",
                         "import os,json,pathlib; p=pathlib.Path('/evidence'); os.chmod(p,0o770); os.chown(p,1001,1001); "
                         "s=p.stat(); (p/'output-volume-ready.json').write_text(json.dumps({'uid':s.st_uid,'gid':s.st_gid,'mode':oct(s.st_mode&0o777)}))"],
                        out / "evidence-volume-owner")
                command(["docker", "cp", initializer + ":/evidence/output-volume-ready.json", str(out)], out / "evidence-export-preflight")
                assert json.loads((out / "output-volume-ready.json").read_bytes()) == {"uid": 1001, "gid": 1001, "mode": "0o770"}
            finally:
                owner = subprocess.check_output(["docker", "inspect", "--format", '{{index .Config.Labels "vrae.ra4b.unit"}}', initializer]).strip()
                assert owner == b"TEST_ONLY"
                command(["docker", "rm", "-f", initializer], out / "evidence-owner-remove")
            mount = "type=volume,src=" + output_volume + ",dst=/evidence"
        command(["docker", "run", "-i", "--name", ident, "--label", "vrae.ra4b.unit=TEST_ONLY", "--network", "none", "--read-only", "--cap-drop", "ALL",
             "--security-opt", "no-new-privileges", "--memory", "2g", "--cpus", "2", "--pids-limit", "128",
             "--tmpfs", "/tmp:rw,nosuid,nodev,size=512m", "--mount", "type=volume,src=" + volume + ",dst=/work",
             *output_group, "--mount", mount, image,
             "python", "-c", "import sys,tarfile,runpy; tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz').extractall('/work',filter='data'); runpy.run_path('/work/integration/ra4b/" + ("output_marker.py" if preflight_only else "unit_check.py") + "',run_name='__main__')"],
             out / "supervisor", data=archive.read_bytes(), timeout=ordinary_timeout)
    finally:
        check = subprocess.run(["docker", "inspect", "--format", '{{index .Config.Labels "vrae.ra4b.unit"}}', ident], capture_output=True, timeout=20)
        if check.returncode == 0:
            assert check.stdout.strip() == b"TEST_ONLY"
            state = subprocess.check_output(["docker", "inspect", "--format", "{{json .State}}", ident])
            actual = json.loads(state)
            inspected = json.loads(subprocess.check_output(["docker", "inspect", ident]))[0]
            limits = inspected["HostConfig"]
            (out / "container-result.json").write_text(json.dumps({"status": actual["Status"], "exit": actual["ExitCode"],
                "oom_killed": actual["OOMKilled"], "linux_output_owner_fixture": fixture,
                "sandbox": {"network_none": limits["NetworkMode"] == "none", "readonly_root": limits["ReadonlyRootfs"],
                    "zero_added_capabilities": not limits["CapAdd"], "cap_drop_all": limits["CapDrop"] == ["ALL"],
                    "no_new_privileges": "no-new-privileges" in limits["SecurityOpt"], "memory_bytes": limits["Memory"],
                    "nano_cpus": limits["NanoCpus"], "pids_limit": limits["PidsLimit"],
                    "supplementary_gids": [int(g) for g in limits["GroupAdd"]], "image_sha256": inspected["Image"].removeprefix("sha256:")}}, indent=2))
            if output_volume:
                command(["docker", "cp", ident + ":/evidence/.", str(out)], out / "copy-native-evidence")
            command(["docker", "rm", "-f", ident], out / "container-remove")
        absent_container = subprocess.run(["docker", "container", "inspect", ident], capture_output=True)
        assert absent_container.returncode and b"no such" in absent_container.stderr.lower()
        for i, owned_volume in enumerate(created):
            owned = subprocess.check_output(["docker", "volume", "inspect", "--format", '{{index .Labels "vrae.ra4b.unit"}}', owned_volume]).strip()
            assert owned == b"TEST_ONLY"
            command(["docker", "volume", "rm", owned_volume], out / ("volume-remove-" + str(i)))
            absent = subprocess.run(["docker", "volume", "inspect", owned_volume], capture_output=True, timeout=20)
            assert absent.returncode and b"no such volume" in absent.stderr.lower()
        (out / "teardown.json").write_text(json.dumps({"owned_container_removed": True, "owned_volume_removed": True,
            "volumes": created, "container": ident}))
    # Independent host-side proof runs only AFTER the complete owned cleanup.
    if preflight_only:
        from integration.ra4b.output_marker import MARKER
        held = (out / "synthetic-marker.xml").read_bytes()
        assert held == MARKER
        proof = json.loads((out / "synthetic-marker-proof.json").read_bytes())
        assert proof["pytest_invocations"] == 0 and proof["effective_capabilities_zero"] and proof["fsync_completed"]
        result = {"status": "NONTEST_NATIVE_PERSISTENCE_PREFLIGHT_PASS", "not_a_pytest_suite": True,
            "after_complete_owned_container_and_volume_cleanup": True, "bytes": len(held),
            "sha256": hashlib.sha256(held).hexdigest(), "crc32": format(zlib.crc32(held) & 0xffffffff, "08x")}
        assert result["sha256"] == proof["sha256"] and result["crc32"] == proof["crc32"]
        (out / "persistence-preflight-result.json").write_text(json.dumps(result, indent=2))
    else:
        raw = (out / "tests.xml").read_bytes()
        root = ET.fromstring(raw)
        cases = list(root.iter("testcase"))
        skipped = [case for case in cases if case.find("skipped") is not None]
        # Raw native XML is retained only after the complete owned cleanup.
        minor = f"{sys.version_info.major}.{sys.version_info.minor}"
        producer_raw = (out / "result.json").read_bytes()
        native_result = json.loads(producer_raw)
        assert native_result["status"] == "ORDINARY_PASS_SEPARATE_ISOLATED_GATES_REQUIRED"
        assert native_result["python"].startswith(minor + ".")
        assert native_result["discovered"] == len(cases)
        assert native_result["ordinary_passed"] == len(cases) - len(skipped)
        actual_container = json.loads((out / "container-result.json").read_bytes())
        assert actual_container["exit"] == 0 and not actual_container["oom_killed"]
        from integration.beta_disc_report.inventory import verify_inventory
        accepted_cases, disc_inventory_proof = verify_inventory(cases)
        inventory_proof = _verify_b5_inventory(accepted_cases, minor)
        inventory_proof["disc_additive_inventory"] = disc_inventory_proof
        assert not list(root.iter("failure")) and not list(root.iter("error"))
        qa = [case for case in cases if "test_ra3c_owner_adjudicated_v2" in case.get("classname", "")]
        review = [case for case in cases if case.get("classname", "").startswith("tests.reviewing.")]
        assert len(qa) == 118 and len(review) == 127 and not any(case.find("skipped") is not None for case in qa + review)
        assert sum(case.get("classname") == "tests.collection.test_isolated" for case in skipped) == 24
        assert sum(case.get("classname") == "tests.browser.test_isolated_browser" for case in skipped) == 1
        retention = {"status": "NATIVE_JUNIT_RETAINED_AFTER_COMPLETE_CLEANUP",
            "sha256": hashlib.sha256(raw).hexdigest(), "crc32": format(zlib.crc32(raw) & 0xffffffff, "08x"),
            "bytes": len(raw), "cases": len(cases), "passed": len(cases) - len(skipped), "skipped": len(skipped),
            "failed": 0, "errors": 0, "qa_passed": len(qa), "review_passed": len(review),
            "test_ids": [case.get("classname", "") + "::" + case.get("name", "") for case in cases],
            "raw_xml_private": True, "stdout_used_to_construct_xml": False}
        inventory_proof["native_junit_sha256"] = hashlib.sha256(raw).hexdigest()
        inventory_proof["crc32"] = format(zlib.crc32(raw) & 0xffffffff, "08x")
        # The frozen publisher retains its fixed public hash/count projection;
        # the additional host attestation and raw IDs stay in private retention.
        retention["exact_test_id_inventory"] = inventory_proof
        _write_host_retention(out, producer_raw, retention)


if __name__ == "__main__":
    main(sys.argv[1])

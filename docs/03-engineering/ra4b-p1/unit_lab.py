"""Full suite in an isolated Linux Python minor with a secret-free source copy."""

import json
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
             out / "supervisor", data=archive.read_bytes(), timeout=3600)
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
        # User authorized accepted main ae2505f: CBC plus five B3 contracts.
        # The unchanged full selection is now 2448 PASS + 25 original SKIP.
        assert len(cases) == 2473 and len(skipped) == 25
        assert not list(root.iter("failure")) and not list(root.iter("error"))
        qa = [case for case in cases if "test_ra3c_owner_adjudicated_v2" in case.get("classname", "")]
        review = [case for case in cases if case.get("classname", "").startswith("tests.reviewing.")]
        assert len(qa) == 118 and len(review) == 127 and not any(case.find("skipped") is not None for case in qa + review)
        assert sum(case.get("classname") == "tests.collection.test_isolated" for case in skipped) == 24
        assert sum(case.get("classname") == "tests.browser.test_isolated_browser" for case in skipped) == 1
        (out / "native-junit-retention.json").write_text(json.dumps({"status": "NATIVE_JUNIT_RETAINED_AFTER_COMPLETE_CLEANUP",
            "sha256": hashlib.sha256(raw).hexdigest(), "crc32": format(zlib.crc32(raw) & 0xffffffff, "08x"),
            "bytes": len(raw), "cases": len(cases), "passed": len(cases) - len(skipped), "skipped": len(skipped),
            "failed": 0, "errors": 0, "qa_passed": len(qa), "review_passed": len(review),
            "test_ids": [case.get("classname", "") + "::" + case.get("name", "") for case in cases],
            "raw_xml_private": True, "stdout_used_to_construct_xml": False}, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])

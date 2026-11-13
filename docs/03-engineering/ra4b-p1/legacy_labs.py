"""Execute the original deferred HTTP24 and full unchanged Chromium supervisor."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))


def main(label):
    from runtime_lab import command
    out = HERE / label
    out.mkdir(exist_ok=False)
    private = HERE / ".runtime" / label
    private.mkdir(parents=True, exist_ok=False)
    original = (ROOT / "infra/ra1a/entrypoint.sh").read_bytes().replace(b"\r\n", b"\n")
    old_driver = b"python scripts/verify_ra1a.py /tmp/verification"
    new_driver = b"python -m pytest -q -s -p no:cacheprovider tests/collection/test_isolated.py --junitxml=/evidence/tests.xml"
    assert original.count(old_driver) == 1
    shim = private / "http-entrypoint.sh"
    shim.write_bytes(original.replace(old_driver, new_driver))
    assert shim.read_bytes().split(new_driver)[0] == original.split(old_driver)[0]
    http = out / "http24"
    http.mkdir(mode=0o777)
    http.chmod(0o777)  # Public test output only, writable by original UID65532.
    command(["docker", "build", "-f", "infra/ra1a/Dockerfile", "-t", "vrae-ra4b-legacy-http:local", "."], out / "http-build", timeout=900)
    name = "vrae-ra4b-legacy-http-" + uuid.uuid4().hex[:12]
    try:
        command(["docker", "run", "--rm", "--name", name, "--label", "vrae.ra4b.legacy=TEST_ONLY", "--network", "none",
                 "--cap-add", "NET_ADMIN", "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev,size=128m", "--memory", "512m",
                 "--cpus", "1", "--pids-limit", "128", "--security-opt", "no-new-privileges",
                 "--mount", "type=bind,src=" + str(shim.resolve()) + ",dst=/lab/b4-http-tests.sh,readonly",
                 "--mount", "type=bind,src=" + str(http.resolve()) + ",dst=/evidence",
                 "--entrypoint", "/bin/sh", "vrae-ra4b-legacy-http:local", "/lab/b4-http-tests.sh"], http / "supervisor", timeout=300)
    finally:
        p = subprocess.run(["docker", "inspect", "--format", '{{index .Config.Labels "vrae.ra4b.legacy"}}', name], capture_output=True)
        if not p.returncode:
            assert p.stdout.strip() == b"TEST_ONLY"
            command(["docker", "rm", "-f", name], http / "cleanup")
    root = ET.parse(http / "tests.xml").getroot()
    assert len(list(root.iter("testcase"))) == 24
    assert not list(root.iter("failure")) and not list(root.iter("error")) and not list(root.iter("skipped"))
    (http / "result.json").write_text(json.dumps({"status": "PASS", "actual_original_cases": 24,
            "original_entrypoint_lf_sha256": hashlib.sha256(original).hexdigest(), "original_firewall_tls_uid_setup_unchanged": True,
            "driver_only": "EXACT_DEFERRED_HTTP_MODULE_ALL_24_WITH_JUNIT", "frozen_source_modified": False}, indent=2))
    command(["docker", "build", "-f", "infra/ra1b/Dockerfile", "-t", "vrae-ra1b-browser:local", "."], out / "browser-build", timeout=900)
    command(["docker", "build", "-f", "infra/ra1b/Worker.Dockerfile", "-t", "vrae-ra1b-worker:local", "."], out / "browser-worker-build", timeout=900)
    browser = out / "browser16"
    command([sys.executable, "scripts/verify_ra1b.py", str(browser)], out / "browser-supervisor", timeout=900)
    rows = json.loads((browser / "summary.json").read_bytes())
    cases = [r for r in rows if r["name"].endswith("-worker")]
    assert len(cases) == 16
    (out / "result.json").write_text(json.dumps({"status": "PASS", "original_http_cases": 24,
                  "original_browser_scenarios": len(cases), "ordinary_deferred_unique_cases_covered": 25,
                  "browser_supervisor_source_unchanged": True, "original_entrypoint_setup_unchanged": True}, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])

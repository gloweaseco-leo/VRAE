"""Actual restricted Linux UID check; no DB/network/real credentials."""
import json
import os
from pathlib import Path
import subprocess
import sys

from .catalog import SOURCE_REF
from .provisioning import extend_app_sources


def main():
    assert os.geteuid() == 0
    folder = Path("/tmp/b4-app")
    folder.mkdir(mode=0o700)
    path = folder / "config.json"
    original = {"mode": "TEST_ONLY_RA4B_P1", "kind": "APP", "role": "ra4b_test_a_app",
        "host": "127.0.0.1", "port": 5432, "dbname": "vrae_ra4a_p1", "tenant": "tenant-test",
        "password": "not-real-credentials-0123456789", "bearer": "not-an-issued-test-token",
        "sources": {"accepted-404": {"unchanged": 1}, "accepted-200": {"unchanged": 2}}}
    path.write_text(json.dumps(original))
    path.chmod(0o600)
    os.chown(path, 10001, 10001)
    os.chown(folder, 10001, 10001)
    updated = json.loads(json.dumps(original))
    extend_app_sources(updated, {"sha256": "a" * 64, "policy_id": "pol-001", "policy_version": 1})
    result = subprocess.run([sys.executable, "-B", "-m", "integration.l2_ops.provisioning", str(path)],
        input=json.dumps(updated).encode(), capture_output=True, user=10001, group=10001, extra_groups=[],
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONPATH": "/work", "VRAE_RA4B_TEST_ONLY": "1"}, timeout=10)
    assert result.returncode == 0, "OWNER_WRITE_FAILED"
    check = subprocess.run([sys.executable, "-c", "import json,os,stat; p='/tmp/b4-app/config.json'; print(json.dumps({'sources':list(json.load(open(p))['sources']),'uid':os.lstat(p).st_uid,'mode':stat.S_IMODE(os.lstat(p).st_mode)}))"],
        capture_output=True, user=10001, group=10001, extra_groups=[], timeout=10)
    assert check.returncode == 0 and SOURCE_REF.encode() in check.stdout
    denied = subprocess.run([sys.executable, "-c", "open('/tmp/b4-app/config.json').read()"],
        capture_output=True, user=10003, group=10003, extra_groups=[], timeout=10)
    assert denied.returncode != 0 and b"PermissionError" in denied.stderr
    info = json.loads(check.stdout)
    assert info["uid"] == 10001 and info["mode"] == 0o600
    print(json.dumps({"app_owner_uid": 10001, "mode": "0600", "consumer_uid10003_denied": True,
                      "network": "none", "actual_linux_uid_check": "PASS"}))


if __name__ == "__main__":
    main()

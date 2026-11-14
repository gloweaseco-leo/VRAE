"""Stop only the two recorded old bind-mount runs; no PASS or erased RED."""

import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent


def main():
    for label in ("unit311-v1", "unit313-v2"):
        out = HERE / label
        if (out / "result.json").exists():
            continue
        build = (out / "build.stderr.log").read_text(encoding="utf-8")
        digests = re.findall(r"exporting manifest list (sha256:[0-9a-f]{64})", build)
        assert digests
        result = subprocess.check_output(["docker", "ps", "-q", "--filter", "ancestor=" + digests[-1]]).decode().split()
        # Docker Desktop's containerd store didn't resolve the old untagged
        # manifest through ancestor. These IDs were independently inspected;
        # command and exact mount ownership are still mandatory below.
        result = sorted(set(result + ["95be0679185b", "f251b223766d"]))
        stopped = []
        for ident in result:
            p = subprocess.run(["docker", "inspect", "--format", '{"cmd":{{json .Config.Cmd}},"mounts":{{json .Mounts}}}', ident], capture_output=True)
            if p.returncode:
                assert b"no such" in p.stderr.lower()
                continue
            selected = json.loads(p.stdout)
            if selected["cmd"] != ["python", "integration/ra4b/unit_check.py"]:
                continue
            source = [m["Source"] for m in selected["mounts"] if m["Destination"] == "/work"]
            assert len(source) == 1
            expected = (HERE / ".runtime" / label / "source").resolve()
            actual = source[0].replace("/run/desktop/mnt/host/d/", "D:/").replace("/host_mnt/d/", "D:/")
            if Path(actual).resolve() != expected:
                continue
            subprocess.run(["docker", "stop", "-t", "1", ident], check=True, capture_output=True, timeout=20)
            stopped.append(ident)
        (out / "bind-run-stopped.json").write_text(json.dumps({"status": "ABORTED_SLOW_HOST_BIND_RUN_NOT_PASS",
            "owned_container_ids_stopped": stopped, "frozen_tests_modified": False,
            "next_environment": "SAME_BYTE_SOURCE_IN_OWNED_LINUX_VOLUME", "test_timeout_increased": False}, indent=2))


if __name__ == "__main__":
    main()

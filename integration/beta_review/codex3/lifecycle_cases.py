"""One targeted native lifecycle: real PG/API/SSR, signed read, explicit own cleanup."""

import json
import subprocess
import sys
import time

from .local_app import folder_for, start, status
from .runner import ROOT, write


def test_one_command_existing_component_preview_lifecycle():
    import os

    label = os.environ["C3_LOCAL_APP_RUN"]
    minor = os.environ["C3_LOCAL_APP_MINOR"]
    folder = folder_for(label)
    result, code = start(label, minor, True)
    assert code == 0 and result["preview_is_generated_job_report"] is False
    ready = False
    try:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            current = status(label)
            if current["state"] == "COMPONENT_PREVIEW_READY":
                ready = True
                break
            assert current["state"] in ("STARTING", "ABSENT")
            time.sleep(0.25)
        assert ready, "LOCAL_COMPONENT_START_NOT_READY"
        assert current["business_flow"] == "BLOCKED_MISSING_ACCEPTED_PORTS"
        import http.client
        from contextlib import closing
        from urllib.parse import urlsplit

        url = urlsplit(current["url"])
        assert url.hostname == "127.0.0.1"
        with closing(http.client.HTTPConnection(url.hostname, url.port, timeout=25)) as http:
            http.request("GET", url.path)
            response = http.getresponse()
            body = response.read()
            assert response.status == 200 and b"b5a" in body.lower()
        # Existing real signature/challenge/cookie flow, no browser token injection.
        process = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/beta_internal.py"),
                "session",
                "--run",
                label,
                "--task",
                "200",
            ],
            check=False,
            cwd=ROOT,
            capture_output=True,
            timeout=60,
        )
        assert process.returncode == 0
        native = json.loads((folder / "native/native-result.json").read_bytes())
        assert native["native_python"].startswith(minor + ".")
        assert len(native["records"]) == 2
        assert all(
            r["commit_observed_before_worker"]
            and r["worker_uid"] == 10002
            and r["generated_report_by_worker"] is False
            for r in native["records"]
        )
    finally:
        if folder.exists():
            write(folder / "stop.json", {"stop": True})
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline and status(label)["state"] != "CLOSED":
                time.sleep(0.25)
            assert status(label)["state"] == "CLOSED", "OWN_CLEANUP_NOT_CONFIRMED"
    assert ready

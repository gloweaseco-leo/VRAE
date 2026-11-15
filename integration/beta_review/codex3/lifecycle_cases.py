"""One targeted native lifecycle: real PG/API/SSR, signed read, explicit own cleanup."""

import json
import subprocess
import sys
import time

from .local_app import folder_for, request_stop, start, status
from .runner import ROOT


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
        session = json.loads((folder / "operator-session.private.json").read_bytes())[0]
        assert session["case"] == "200" and session["origin"] == f"http://127.0.0.1:{url.port}"
        from integration.ra4c_b5a.support import Client

        reader = Client(session["origin"])
        reader.cookies = session["cookies"]
        code, body, _ = reader.request("GET", session["path"])
        assert session["entry_kind"] == "B5P0_SEALED_INTERNAL_INTENT"
        assert session["path"] == "/b5a/tasks/task-200/rehearsal"
        assert code == 200 and b'id="proposal-form"' in body and b'id="save-rehearsal"' in body
        assert b"NOT APPROVED" in body and session["expected_draft_ref"].encode() in body
        assert reader.request("GET", "/b5a/tasks/task-404/rehearsal")[0] == 403
        assert reader.request("GET", session["path"] + "?version=999")[0] == 409
        browser = subprocess.run(
            [
                "node",
                str(ROOT / "integration/beta_review/codex3/browser.mjs"),
                str(folder / "operator-session.private.json"),
                str(folder / "operator-entry-browser"),
            ],
            cwd=ROOT,
            capture_output=True,
            timeout=180,
            check=False,
        )
        (folder / "operator-entry-browser.private.stderr.log").write_bytes(browser.stderr)
        assert browser.returncode == 0
        observed = json.loads(browser.stdout)
        assert observed["status"] == "PASS" and len(observed["screenshots"]) == 3
        assert observed["scope"] == "SIGNED_SEALED_INTERNAL_INTENT_NOT_WORKER_OUTPUT"

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
            request_stop(label)
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline and status(label)["state"] != "CLOSED":
                time.sleep(0.25)
            final = status(label)
            assert final["state"] == "CLOSED", "OWN_CLEANUP_NOT_CONFIRMED"
            assert final["component_result"] == "COMPONENTS_VERIFIED_CHAIN_BLOCKED"
            ended = folder.parent / "local-launches" / label / "supervisor-end.json"
            deadline = time.monotonic() + 10
            while not ended.exists() and time.monotonic() < deadline:
                time.sleep(0.1)
            assert ended.exists() and json.loads(ended.read_bytes())["exitcode"] == 0
    assert ready

"""Run original PR89 browser assertions and B5B journeys on ONE real SSR."""

import json
import os
import subprocess
import sys
import time
from .process import Child
from .support import Runtime, ROOT


def main(label):
    r = Runtime(label)
    child = None
    initialized = False
    node = None
    results = []
    try:
        r.bootstrap()
        child = Child(r)
        initialized = True
        child.start()
        before = r.roots()
        for script, name in [
            ("integration/ra4c_b5p0/browser.mjs", "accepted"),
            ("integration/b5b/browser.mjs", "b5b"),
        ]:
            out = r.lab.private / (name + "-browser")
            out.mkdir()
            env = dict(os.environ)
            env["B5P0_CHROMIUM"] = os.environ.get(
                "B5B_CHROMIUM",
                os.environ.get(
                    "B5P0_CHROMIUM", "C:/Program Files/Google/Chrome/Application/chrome.exe"
                ),
            )
            with (r.lab.private / (name + "-node.stderr.log")).open("wb") as errors:
                node = subprocess.Popen(
                    ["node", script],
                    cwd=ROOT,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=errors,
                    text=True,
                    encoding="utf-8",
                    env=env,
                )
                node.stdin.write(
                    json.dumps(
                        {
                            "type": "init",
                            "base": child.origin + "/b5a/",
                            "output": str(out),
                            "private": str(r.lab.private),
                        }
                    )
                    + "\n"
                )
                node.stdin.flush()
                done = None
                for line in node.stdout:
                    msg = json.loads(line)
                    if msg.get("kind") == "done":
                        done = msg
                        break
                    if msg["kind"] == "sign":
                        now = int(time.time())
                        value = r.issuer.token(
                            {"iat": now, "nbf": now, "exp": now + 90, "nonce": msg["nonce"]}
                        )
                        r.secrets.append(value)
                    elif msg["kind"] == "revoke" and name == "b5b":
                        with r.lab.connect() as admin:
                            admin.execute(
                                "UPDATE ra4a_review_test.assignments SET active=false WHERE db_role='p2b1_test_a_reviewer'"
                            )
                        value = True
                    else:
                        raise AssertionError("B5B_UNKNOWN_FIXTURE_RPC")
                    node.stdin.write(json.dumps({"id": msg["id"], "result": value}) + "\n")
                    node.stdin.flush()
                code = node.wait(timeout=30)
                assert done and done["pass"] and code == 0, "B5B_ACTUAL_CHROMIUM_RED"
            cleanup = json.loads((out / "browser-process-cleanup.json").read_bytes())
            assert cleanup["exit_observed"]
            report = json.loads((out / "browser.json").read_bytes())
            assert all(a["pass"] for a in report["records"]) and not report["exceptions"]
            assert len(report["shots"]) == (12 if name == "accepted" else 18)
            if name == "accepted":
                assert len(report["records"]) == 63
            results.append(
                {
                    "suite": name,
                    "assertions": len(report["records"]),
                    "screenshots": len(report["shots"]),
                    "chromium_exit_observed": True,
                }
            )
        assert (
            r.roots() == before
            and r.data()["intents"] == r.data()["audit"] == r.data()["outbox"] == 2
        )
        (r.lab.private / "browser-summary.json").write_text(
            json.dumps(
                {
                    "suites": results,
                    "counts": r.data(),
                    "protected_roots_unchanged": True,
                    "admin_or_APP_profile_in_SSR": False,
                    "worker_result": "BLOCKED_NO_ACCEPTED_LEASE_BOUND_RESULT_PORT",
                    "Reviewer_task_status": "BLOCKED_NO_ACCEPTED_REVIEWER_TASK_STATUS_PORT",
                }
            ),
            encoding="utf-8",
        )
    finally:
        if node and node.poll() is None:
            node.terminate()
            node.wait(timeout=15)
        if initialized:
            child.stop()
        r.stop()


if __name__ == "__main__":
    main(sys.argv[1])

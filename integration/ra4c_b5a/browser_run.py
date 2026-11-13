"""Private signer/fixture controller -> separate restricted HTTP + real Chromium.

IPC is private pipes, never a browser-accessible control server. Token messages
are never logged. Only fixed synthetic actions are available to the test child.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from .support import Runtime
from .cases import snapshot
from tests.identity.issuer import Issuer


def main():
    label = sys.argv[1]
    assert re.fullmatch(r"[a-z0-9-]{3,48}", label)
    root = Path(__file__).resolve().parents[2]
    output = root / "docs/03-engineering/ra4c-b5a/evidence" / label
    output.mkdir(parents=True, exist_ok=False)
    runtime = Runtime(label)
    child = node = None
    profile = None
    try:
        runtime.bootstrap()
        baseline = snapshot(runtime)
        profile = runtime.lab.private / "reviewer-profile.json"
        value = runtime.profile()
        assert set(value["settings"]) == {"host", "port", "dbname", "user", "password"}
        assert value["settings"]["user"] == "p2b1_test_a_reviewer"
        profile.write_text(json.dumps(value), encoding="utf-8")
        if os.name != "nt":
            profile.chmod(0o600)
        audit = runtime.lab.private / "http-audit.jsonl"
        stderr = (runtime.lab.private / "http-stderr.log").open("wb")

        def launch():
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "integration.ra4c_b5a.http_server",
                    "--profile",
                    str(profile),
                    "--audit",
                    str(audit),
                ],
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=stderr,
                env=dict(os.environ, PYTHONUTF8="1"),
            )
            startup = json.loads(process.stdout.readline())
            return process, startup["url"].removesuffix("/b5a/login")

        def reads():
            return sum(
                json.loads(line)["event"] == "actual_load_target_returned"
                for line in audit.read_text().splitlines()
            )

        child, origin = launch()
        node_errors = (runtime.lab.private / "node-stderr.log").open("wb")
        node = subprocess.Popen(
            ["node", "integration/ra4c_b5a/browser.mjs"],
            cwd=root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=node_errors,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        node.stdin.write(
            json.dumps(
                {
                    "type": "init",
                    "base": origin,
                    "output": str(output),
                    "private": str(runtime.lab.private),
                }
            )
            + "\n"
        )
        node.stdin.flush()
        done = None
        for line in node.stdout:
            message = json.loads(line)
            if message.get("kind") == "done":
                done = message
                break
            result = None
            if message["kind"] == "sign":
                assert message["case"] in ("404", "200")
                nonce = message["nonce"]
                assert type(nonce) is str and 16 <= len(nonce) <= 128
                now = int(time.time())
                result = runtime.issuer.token(
                    {"iat": now, "nbf": now, "exp": now + 90, "nonce": nonce}
                )
                runtime.secrets.append(result)
            elif message["kind"] in ("revoke", "restore"):
                with runtime.lab.connect() as c:
                    c.execute(
                        "UPDATE ra4a_review_test.assignments SET active=%s WHERE db_role='p2b1_test_a_reviewer'",
                        (message["kind"] == "restore",),
                    )
                result = {"done": True}
            elif message["kind"] == "reads":
                result = reads()
            elif message["kind"] in ("profile-revoke", "profile-restore"):
                value["anchor"]["revoked"] = (
                    ["old", "new"] if message["kind"] == "profile-revoke" else []
                )
                profile.write_text(json.dumps(value), encoding="utf-8")
                result = {"done": True}
            elif message["kind"] == "restart":
                child.terminate()
                child.wait(timeout=15)
                runtime.issuer = Issuer()
                value = runtime.profile()
                profile.write_text(json.dumps(value), encoding="utf-8")
                child, origin = launch()
                result = {"base": origin}
            else:
                raise RuntimeError("B5A_UNKNOWN_PRIVATE_FIXTURE_ACTION")
            node.stdin.write(json.dumps({"id": message["id"], "result": result}) + "\n")
            node.stdin.flush()
        code = node.wait(timeout=30)
        assert done and done["pass"] and code == 0, "ACTUAL_CHROMIUM_RED"
        assert snapshot(runtime) == baseline, "BROWSER_BUSINESS_DATABASE_CHANGED"
        events = [json.loads(line) for line in audit.read_text().splitlines()]
        assert any(e["event"] == "actual_reviewer_identity" for e in events)
        assert any(e["event"] == "read_denied" and e["sqlstate"] == "42501" for e in events)
        proof = {
            "status": "ACTUAL_CHROMIUM_SEPARATE_REVIEWER_PROCESS_PASS",
            "assertions": done["assertions"],
            "screenshots": done["screenshots"],
            "actual_reviewer_rows": sum(
                e["event"] == "actual_load_target_returned" for e in events
            ),
            "sqlstate42501_observed": True,
            "admin_profile_in_http": False,
            "business_table_fingerprints": baseline,
            "business_tables_unchanged": True,
            "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root)
            .decode()
            .strip(),
        }
        (output / "receipt.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(proof), flush=True)
    finally:
        if node and node.poll() is None:
            node.terminate()
            node.wait(timeout=15)
        if child and child.poll() is None:
            child.terminate()
            child.wait(timeout=15)
        if profile:
            profile.unlink(missing_ok=True)
        runtime.lab.private.joinpath("scan-credentials.json").write_text(
            json.dumps(
                [
                    runtime.lab.state["admin_password"],
                    *runtime.lab.state["runtime_passwords"].values(),
                    *runtime.secrets,
                ]
            ),
            encoding="utf-8",
        )
        runtime.stop()


if __name__ == "__main__":
    main()

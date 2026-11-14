"""Private signer/admin controller; separate real SSR process and Chromium."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from .support import Runtime


def main():
    label = sys.argv[1]
    r = Runtime(label)
    child = node = None
    root = Path(__file__).resolve().parents[2]
    out = r.lab.private / "browser-output"
    out.mkdir(parents=True, exist_ok=False)
    try:
        r.bootstrap()
        before = r.roots()
        originals = [r.original_facts(case) for case in ("404", "200")]
        profile = r.lab.private / "reviewer.json"
        bridge = r.lab.private / "bridge.json"
        profile.write_text(json.dumps(r.profile()), encoding="utf-8")
        bridge.write_text(json.dumps(r.bridge_profile()), encoding="utf-8")
        audit = r.lab.private / "http-audit.jsonl"
        with (r.lab.private / "http-stderr.log").open("wb") as errors:
            child = subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "integration.ra4c_b5p0.http_server",
                    "--profile",
                    str(profile),
                    "--bridge",
                    str(bridge),
                    "--audit",
                    str(audit),
                ],
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=errors,
                env=dict(os.environ, PYTHONUTF8="1"),
            )
            origin = json.loads(child.stdout.readline())["url"].removesuffix("/b5a/login")
            with (r.lab.private / "node-stderr.log").open("wb") as node_errors:
                node = subprocess.Popen(
                    ["node", "integration/ra4c_b5p0/browser.mjs"],
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
                    assert msg["kind"] == "sign"
                    now = int(time.time())
                    token = r.issuer.token(
                        {"iat": now, "nbf": now, "exp": now + 90, "nonce": msg["nonce"]}
                    )
                    r.secrets.append(token)
                    node.stdin.write(json.dumps({"id": msg["id"], "result": token}) + "\n")
                    node.stdin.flush()
                code = node.wait(timeout=30)
                assert done and done["pass"] and code == 0, "ACTUAL_B5P0_CHROMIUM_RED"
                chromium_cleanup = json.loads((out / "browser-process-cleanup.json").read_bytes())
                assert chromium_cleanup["exit_observed"], "CHROMIUM_PROCESS_NOT_CLOSED"
            assert r.roots() == before
            assert r.data()["intents"] == r.data()["audit"] == r.data()["outbox"] == 2
            events = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
            assert any(e["event"] == "receipt_verified" for e in events)
            receipt = {
                "status": "ACTUAL_B5P0_PG_HTTP_CHROMIUM_PASS",
                "assertions": done["assertions"],
                "screenshots": done["screenshots"],
                "counts": r.data(),
                "protected_roots_unchanged": True,
                "source_catalog_sha256": before,
                "admin_profile_in_http": False,
                "chromium_cleanup": chromium_cleanup,
                "original_descriptors": originals,
                "actual_sqlstates": sorted({e["sqlstate"] for e in events if e.get("sqlstate")}),
                "commit_entries": sum(e["event"] == "commit_entry" for e in events),
                "candidate_bindings_verified": sum(
                    e["event"] == "b3_candidate_binding_verified" for e in events
                ),
            }
            (out / "browser-receipt.json").write_text(
                json.dumps(receipt, indent=2), encoding="utf-8"
            )
            print(json.dumps(receipt), flush=True)
    finally:
        if node and node.poll() is None:
            node.terminate()
            node.wait(timeout=15)
        if child and child.poll() is None:
            child.terminate()
            child.wait(timeout=15)
        r.stop()


if __name__ == "__main__":
    main()

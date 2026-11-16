"""Private local operator/acceptance driver; signing never enters the SSR."""

import json
import os
import secrets
import subprocess
import time

from .local_app import control_write, folder_for, launch_for, status
from .runner import ROOT


def control(label, operation, **args):
    folder = folder_for(label)
    request = folder / "m3-control" / (secrets.token_hex(12) + ".request.json")
    control_write(request, {"operation": operation, **args})
    request.chmod(0o600)
    response = request.with_name(request.name.replace(".request.json", ".response.json"))
    deadline = time.monotonic() + (150 if operation == "restart-pg" else 100)
    while not response.exists():
        if (launch_for(label) / "supervisor-end.json").exists():
            raise RuntimeError("M3_SUPERVISOR_EXIT_SEE_PRIVATE_EVIDENCE")
        assert time.monotonic() < deadline, "M3_PRIVATE_CONTROL_DEADLINE"
        time.sleep(0.05)
    result = json.loads(response.read_bytes())
    if isinstance(result, dict) and "denied" in result:
        raise RuntimeError(result["denied"])
    return result


def run(label, *, interactive=False):
    current = status(label)
    assert current["state"] == "M3_READY"
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    assert current["source_sha"] == head, "M3_FROZEN_SOURCE_REQUIRED"
    folder = folder_for(label)
    name = "browser-acceptance"
    if interactive:
        index = 1
        while (folder / ("browser-interactive-" + str(index))).exists():
            index += 1
        name = "browser-interactive-" + str(index)
    output = folder / name
    output.mkdir(exist_ok=False)
    errors = (output / "node.stderr.private.log").open("wb")
    env = {
        **os.environ,
        "B5P0_CHROMIUM": os.environ.get(
            "B5B_CHROMIUM", "C:/Program Files/Google/Chrome/Application/chrome.exe"
        ),
    }
    node = subprocess.Popen(
        ["node", "integration/beta_review/codex3/m3_browser.mjs"],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=errors,
        text=True,
        encoding="utf-8",
        env=env,
    )
    try:
        pins = json.loads((folder / "bootstrap-pins.private.json").read_bytes())
        node.stdin.write(
            json.dumps(
                {
                    "type": "init",
                    "base": current["url"],
                    "output": str(output),
                    "private": str(output),
                    "bootstrap_pins": pins,
                    "interactive": interactive,
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
            if message["kind"] == "sign":
                value = control(label, "sign", nonce=message["nonce"])
            elif message["kind"] == "result":
                value = control(label, "await-job", job=message["job"])
            elif message["kind"] == "restart":
                value = control(label, "restart-pg")
            else:
                raise ValueError("M3_BROWSER_RPC_DENIED")
            node.stdin.write(json.dumps({"id": message["id"], "result": value}) + "\n")
            node.stdin.flush()
        node.wait(timeout=30)
        assert done and done["pass"] and node.returncode == 0, "M3_REAL_BROWSER_RED"
        return {**done, "source_sha": head, "private_evidence": str(output)}
    finally:
        if node.poll() is None:
            node.terminate()
            node.wait(timeout=15)
        errors.close()

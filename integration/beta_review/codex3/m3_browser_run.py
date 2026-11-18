"""Private local operator/acceptance driver; signing never enters the SSR."""

import json
import os
import secrets
import subprocess
import time
import sys

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


def run(label, *, interactive=False, preparation_only=False, native_l2=False, s2_l2=False, executive=False):
    current = status(label)
    assert current["state"] == "M3_READY"
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    assert current["source_sha"] == head, "M3_FROZEN_SOURCE_REQUIRED"
    folder = folder_for(label)
    name = "browser-s2-l2" if s2_l2 else "browser-native-l2" if native_l2 else "browser-preparation" if preparation_only else "browser-acceptance"
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
    receiver = None
    last_row = None
    previous_receipt = None
    queued = None
    try:
        if executive:
            receiver = subprocess.Popen([sys.executable, '-B', '-m', 'integration.l2_executive.receiver'],
                cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8')
            public_key = json.loads(receiver.stdout.readline())['public_key']
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
                    "preparation_only": preparation_only,
                    "native_l2": native_l2,
                    "s2_l2": s2_l2,
                    "s4_executive": executive,
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
            elif message["kind"] == "native-proof":
                value = control(label, "native-proof")
            elif message["kind"] in ("s0-audit-queue", "s0-audit-result"):
                value = control(label, message["kind"], case=message["case"])
            elif message['kind'] == 's4-queue' and executive:
                operation = message['operation']
                queued = secrets.token_hex(16)
                command = {'request_id': queued, 'operation': operation}
                if operation == 'configure':
                    command['public_key'] = public_key
                elif operation == 'receive':
                    if message.get('negative') == 'old_attempt':
                        assert previous_receipt is not None
                        receipt, signature = previous_receipt
                    else:
                        assert last_row is not None
                        receipt = {**{k: last_row[k] for k in ('scope_sha256', 'brief_sha256', 'attempt', 'nonce')},
                                   'state': message['state']}
                        receiver.stdin.write(json.dumps(receipt)+'\n')
                        receiver.stdin.flush()
                        signature = json.loads(receiver.stdout.readline())['signature']
                        if message.get('negative') == 'signature':
                            signature = ('00' if signature[:2] != '00' else '01') + signature[2:]
                        else:
                            previous_receipt = receipt, signature
                    command.update(receipt=receipt, signature=signature)
                else:
                    assert operation == 'read'
                value = control(label, 's4-intake-queue', command=command)
            elif message['kind'] == 's4-result' and executive:
                result = control(label, 's4-intake-result')['s4_result']
                assert result['request_id'] == queued
                if result['ok']:
                    last_row = result['row']
                # Never publish the private attempt nonce or signed receipt.
                row = result.get('row')
                value = {'ok': result['ok'], 'code': result.get('code'), 'row': None if row is None else
                    {k: v for k, v in row.items() if k != 'nonce'}}
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
        if receiver is not None and receiver.poll() is None:
            receiver.terminate()
            receiver.wait(timeout=15)

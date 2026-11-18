"""Private S5 capture on the existing owned SSR; publish only bounded metadata."""

import hashlib
import json
import subprocess
from typing import Any
from integration.l2_ops.acceptance import owned, command


def capture(private, label, expected):
    record, _ = owned(private, label, expected)
    container = record["volume"] + "-ssr"
    info = json.loads(command(["docker", "inspect", container]))[0]
    assert info["Config"]["Labels"]["vrae.beta.codex3"] == label
    target = private / "s5-private-state"
    target.mkdir(exist_ok=False)
    result = subprocess.run(
        ["docker", "cp", container + ":/state/l2-native/s5", str(target)], capture_output=True
    )
    out: dict[str, Any] = {
        "version": "S5_SAFE_STATE_OBSERVATION_1",
        "private_text_published": False,
        "copied": result.returncode == 0,
        "failures": [],
        "history": [],
        "ledger_refs": [],
        "files": {},
    }
    if result.returncode == 0:
        for path in target.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            raw = path.read_bytes()
            out["files"][str(path.relative_to(target)).replace("\\", "/")] = hashlib.sha256(
                raw
            ).hexdigest()
            if path.name == "activation-timing.json":
                out["activation_timing"] = json.loads(raw)
            if path.name.endswith("-failure.json"):
                d = json.loads(raw)
                out["failures"].append(
                    {
                        k: d[k]
                        for k in (
                            "phase",
                            "exception_type",
                            "private_log_sha256",
                            "private_log_bytes",
                        )
                    }
                )
            if path.name.endswith("-intent.json"):
                d = json.loads(raw)
                out["history"].append(
                    {k: d[k] for k in ("mode", "state", "receipt_ref", "context_ref") if k in d}
                )
            if path.name == "latest-pin.json":
                out["ledger_refs"].append(json.loads(raw)["ledger_ref"])
    (private / "s5-safe-observation.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out

"""Local lifecycle for the existing single signed SSR; no second web application."""

import argparse
import json
import os
import re
import subprocess
import sys

from .runner import PRIVATE, ROOT, cmd, write

ACCEPTED_MAIN = "611f6b1c318168d86ebabe937d8e6f2480c341c4"
MISSING_PORTS = (
    "C1_CURRENT_LEASE_GENERATED_RESULT_COMMIT_AND_ASSIGNED_REVIEWER_READ",
    "C2_SIGNED_SSR_NEW_TASK_GENERATED_REPORT_REVIEW_RECEIPT_EXPORT",
)


def folder_for(label):
    if not re.fullmatch(r"[a-z0-9-]{3,48}", label):
        raise ValueError("INVALID_RUN")
    folder = PRIVATE / label
    if folder.resolve().parent != PRIVATE.resolve() or folder.is_symlink():
        raise ValueError("OWN_PRIVATE_RUN_REQUIRED")
    return folder


def doctor():
    # Read the accepted commit's tree, never sibling branches or unmerged files.
    cmd(["git", "merge-base", "--is-ancestor", ACCEPTED_MAIN, "HEAD"])
    paths = cmd(["git", "ls-tree", "-r", "--name-only", ACCEPTED_MAIN]).decode().splitlines()
    return {
        "accepted_main_inspected": ACCEPTED_MAIN,
        "candidate_sha": cmd(["git", "rev-parse", "HEAD"]).decode().strip(),
        "mode": "SYNTHETIC_ONLY_INTERNAL_NOT_APPROVED",
        "business_flow": "BLOCKED_MISSING_ACCEPTED_PORTS",
        "missing_ports": list(MISSING_PORTS),
        "accepted_C1_result_namespace_files": [
            p for p in paths if p.startswith(("db/ra4b_p2/", "vrae/application/ra4b_p2/"))
        ],
        "accepted_C2_dynamic_SSR_files": [
            p for p in paths if p.startswith("apps/operator_console/b5b")
        ],
        "existing_component_preview_available": True,
        "preview_is_generated_job_report": False,
        "browser_red_preserved": "c3-s2-disc-311-v1:375/200/signed-login:CDP_TIMEOUT_Page.navigate",
        "real_site_model_customer_delivery": False,
    }


def status(label):
    folder = folder_for(label)
    if not folder.is_dir():
        return {"run": label, "state": "ABSENT"}
    if (folder / "stop.json").exists():
        # A stop request is not cleanup evidence.
        state = "STOP_REQUESTED"
    elif (folder / "started.json").exists():
        state = "COMPONENT_PREVIEW_READY"
    else:
        state = "STARTING"
    result = {"run": label, "state": state, "business_flow": "BLOCKED_MISSING_ACCEPTED_PORTS"}
    started = folder / "started.json"
    if started.exists():
        value = json.loads(started.read_text(encoding="utf-8"))
        from urllib.parse import urlsplit

        u = urlsplit(value["origin"])
        if u.scheme != "http" or u.hostname != "127.0.0.1" or not u.port:
            raise ValueError("LOOPBACK_ORIGIN_REQUIRED")
        result["url"] = value["origin"] + "/b5a/login"
        result["source_sha"] = value["source_sha"]
    evidence = ROOT / "docs/03-engineering/beta-closure/codex3/.private" / label / "result.json"
    if evidence.exists():
        final = json.loads(evidence.read_text(encoding="utf-8"))
        cleanup = final.get("cleanup", [])
        result["state"] = (
            "CLOSED" if cleanup and not final.get("cleanup_errors") else "CLEANUP_REQUIRES_REVIEW"
        )
        result["component_result"] = final["status"]
    return result


def start(label, minor, component_preview):
    evidence = doctor()
    if not component_preview:
        # A proper whole-app launch will bind C1/C2 ports after Owner merges them.
        # Do not fall back to presenting sealed fixture reports as generated output.
        return {**evidence, "started": False}, 2
    folder = folder_for(label)
    PRIVATE.mkdir(parents=True, exist_ok=True)
    if folder.exists():
        raise ValueError("RUN_ALREADY_EXISTS")
    launch = PRIVATE / "local-launches" / label
    launch.mkdir(parents=True, exist_ok=False)
    log = launch / "local-supervisor.private.log"
    env = {
        **os.environ,
        "BETA_CODEX3_PRIVATE_EVIDENCE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
    }
    command = [
        sys.executable,
        "-B",
        str(ROOT / "scripts/beta_internal.py"),
        "start",
        "--run",
        label,
        "--minor",
        minor,
        "--phase",
        "s2",
    ]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with log.open("xb") as stream:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=stream,
            creationflags=flags,
        )
    write(
        launch / "local-launch.json",
        {
            "supervisor_pid": process.pid,
            "source_sha": evidence["candidate_sha"],
            "mode": "EXISTING_COMPONENT_PREVIEW_NOT_WHOLE_APP_PASS",
        },
    )
    return {
        "run": label,
        "state": "STARTING",
        "business_flow": evidence["business_flow"],
        "preview_is_generated_job_report": False,
        "auto_stop_seconds": 1800,
    }, 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("doctor", "start", "status", "stop"))
    parser.add_argument("--run")
    parser.add_argument("--minor", choices=("3.11", "3.13"), default="3.11")
    parser.add_argument("--component-preview", action="store_true")
    args = parser.parse_args(argv)
    code = 0
    if args.action == "doctor":
        result = doctor()
    elif not args.run:
        parser.error("--run is required")
    elif args.action == "start":
        result, code = start(args.run, args.minor, args.component_preview)
    elif args.action == "status":
        result = status(args.run)
    else:
        folder = folder_for(args.run)
        launch = PRIVATE / "local-launches" / args.run
        if not (launch / "local-launch.json").is_file():
            raise ValueError("OWN_LOCAL_LAUNCH_REQUIRED")
        write(folder / "stop.json", {"stop": True})
        result = status(args.run)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

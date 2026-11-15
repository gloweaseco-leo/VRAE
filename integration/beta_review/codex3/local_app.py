"""Local lifecycle for the existing single signed SSR; no second web application."""

import argparse
import json
import os
import re
import subprocess
import sys

from .runner import PRIVATE, ROOT, cmd, write

ACCEPTED_MAIN = "08a999d8b7061af925f1f35cfcc55193a3c73b35"
M1_MODE = "M1_GENERATED_REPORTS_M2_UI_PENDING"
LEGACY_MODE = "EXISTING_COMPONENT_PREVIEW_NOT_WHOLE_APP_PASS"
MISSING_PORTS = ("C2_SIGNED_SSR_NEW_TASK_GENERATED_REPORT_REVIEW_RECEIPT_EXPORT",)


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
        "business_flow": "M1_ACCEPTED_M2_PENDING",
        "M1_accepted": True,
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


def launch_for(label):
    folder_for(label)
    base = PRIVATE / "local-launches"
    launch = base / label
    if base.is_symlink() or launch.is_symlink():
        raise ValueError("OWN_LOCAL_LAUNCH_REQUIRED")
    return launch


def control_write(path, value):
    temporary = path.with_name(path.name + "." + str(os.getpid()) + ".tmp")
    write(temporary, value)
    temporary.replace(path)


def request_stop(label):
    launch = launch_for(label)
    metadata = json.loads((launch / "local-launch.json").read_text(encoding="utf-8"))
    if metadata.get("mode") not in (LEGACY_MODE, M1_MODE):
        raise ValueError("OWN_LOCAL_LAUNCH_REQUIRED")
    if metadata.get("run", label) != label:
        raise ValueError("OWN_LOCAL_LAUNCH_REQUIRED")
    # Never create the run directory: the existing Run owns exclusive creation.
    control_write(launch / "stop.json", {"stop": True})
    return status(label)


def status(label):
    folder = folder_for(label)
    launch = launch_for(label)
    reserved = (launch / "local-launch.json").is_file()
    mode = (
        json.loads((launch / "local-launch.json").read_bytes()).get("mode")
        if reserved
        else LEGACY_MODE
    )
    if not folder.is_dir() and not reserved:
        return {"run": label, "state": "ABSENT"}
    if (launch / "stop.json").exists() or (folder / "stop.json").exists():
        state = "STOP_REQUESTED"
    elif (folder / "started.json").exists():
        state = "M1_READY_M2_UI_PENDING" if mode == M1_MODE else "COMPONENT_PREVIEW_READY"
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
    if mode == M1_MODE:
        result["business_flow"] = M1_MODE
        result["review_ui"] = "PENDING_OWNER_MERGED_M2"
        result["legacy_ssr_url"] = result.pop("url", None)
        result["ssr_is_generated_job_reviewer"] = False
    evidence = ROOT / "docs/03-engineering/beta-closure/codex3/.private" / label / "result.json"
    if evidence.exists():
        final = json.loads(evidence.read_text(encoding="utf-8"))
        cleanup = final.get("cleanup", [])
        result["state"] = (
            "CLOSED" if cleanup and not final.get("cleanup_errors") else "CLEANUP_REQUIRES_REVIEW"
        )
        result["component_result"] = final["status"]
        result.pop("url", None)
        result.pop("legacy_ssr_url", None)
    elif (launch / "supervisor-end.json").exists():
        end = json.loads((launch / "supervisor-end.json").read_text(encoding="utf-8"))
        cancelled = launch / "cancelled-before-start.json"
        before_start = cancelled.exists() and json.loads(cancelled.read_text(encoding="utf-8")) == {
            "cancelled_before_run": True,
            "resources_started": False,
        }
        result["state"] = (
            "CLOSED"
            if before_start and end["exitcode"] == 0
            else "FAILED_START_CLEANUP_UNCONFIRMED"
        )
        result["component_result"] = (
            "CANCELLED_BEFORE_RESOURCES" if before_start else "STARTUP_FAILED"
        )
        result.pop("url", None)
        result.pop("legacy_ssr_url", None)
    return result


def supervise(label, minor):
    from . import runner

    launch = launch_for(label)
    metadata = json.loads((launch / "local-launch.json").read_text(encoding="utf-8"))
    if metadata.get("run") != label or metadata.get("mode") not in (LEGACY_MODE, M1_MODE):
        raise ValueError("OWN_LOCAL_LAUNCH_REQUIRED")
    code = 0
    previous = sys.argv
    try:
        if (launch / "stop.json").is_file():
            control_write(
                launch / "cancelled-before-start.json",
                {
                    "cancelled_before_run": True,
                    "resources_started": False,
                },
            )
        else:
            sys.argv = [
                "beta_internal.py",
                "start",
                "--run",
                label,
                "--minor",
                minor,
                "--phase",
                "s2",
            ]
            if metadata["mode"] == M1_MODE:
                from .m3_application import main as generated_main

                generated_main(label, minor)
            else:
                runner.main()
    except BaseException:
        code = 1
        raise
    finally:
        sys.argv = previous
        control_write(launch / "supervisor-end.json", {"exitcode": code})
    return code


def start(label, minor, component_preview):
    evidence = doctor()
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
    metadata = {
        "run": label,
        "supervisor_pid": None,
        "source_sha": evidence["candidate_sha"],
        "mode": LEGACY_MODE if component_preview else M1_MODE,
    }
    control_write(launch / "local-launch.json", metadata)
    command = [
        sys.executable,
        "-B",
        "-m",
        "integration.beta_review.codex3.local_app",
        "supervise",
        "--run",
        label,
        "--minor",
        minor,
    ]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
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
    except OSError:
        control_write(launch / "supervisor-end.json", {"exitcode": 1})
        raise
    metadata["supervisor_pid"] = process.pid
    control_write(launch / "local-launch.json", metadata)
    return {
        "run": label,
        "state": "STARTING",
        "business_flow": evidence["business_flow"],
        "preview_is_generated_job_report": False,
        "auto_stop_seconds": 1800,
    }, 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "doctor",
            "start",
            "status",
            "stop",
            "supervise",
            "submit",
            "task",
            "report",
            "restart-pg",
        ),
    )
    parser.add_argument("--run")
    parser.add_argument("--minor", choices=("3.11", "3.13"), default="3.11")
    parser.add_argument("--component-preview", action="store_true")
    parser.add_argument("--source", choices=("404", "200"))
    parser.add_argument("--key")
    parser.add_argument("--job")
    parser.add_argument("--wait", type=int, default=90)
    args = parser.parse_args(argv)
    code = 0
    if args.action == "doctor":
        result = doctor()
    elif not args.run:
        parser.error("--run is required")
    elif args.action in ("submit", "task", "report", "restart-pg"):
        from . import m3_results

        if args.action == "submit":
            if args.source is None:
                parser.error("--source is required")
            result = m3_results.submit(args.run, args.source, args.key)
        elif args.action == "restart-pg":
            result = m3_results.restart_pg(args.run)
        else:
            if not args.job:
                parser.error("--job is required")
            if not 0 <= args.wait <= 120:
                parser.error("--wait must be 0..120")
            result = (
                m3_results.task_status(args.run, args.job)
                if args.action == "task"
                else m3_results.materialize(args.run, args.job, args.wait)
            )
    elif args.action == "supervise":
        return supervise(args.run, args.minor)
    elif args.action == "start":
        result, code = start(args.run, args.minor, args.component_preview)
    elif args.action == "status":
        result = status(args.run)
    else:
        result = request_stop(args.run)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

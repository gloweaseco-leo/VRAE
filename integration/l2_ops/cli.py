"""L2 operations in the existing beta entrypoint. No alternate web server."""
import argparse
import json
import subprocess
import sys

from vrae.l2_ops.ingest import load_source
from vrae.l2_ops.native_input import load_native


def main(argv=None):
    parser = argparse.ArgumentParser(description="L2 controlled source preparation")
    sub = parser.add_subparsers(dest="operation", required=True)
    source = sub.add_parser("source-check", help="Validate/hash local evidence without external access")
    source.add_argument("manifest")
    native = sub.add_parser("native-check", help="Replay an existing native capture; no task or diagnosis")
    native.add_argument("manifest")
    native.add_argument("--reference", required=True)
    native.add_argument("--pack-ref", required=True)
    native.add_argument("--capture-run-id", required=True)
    intake = sub.add_parser("worker-intake", help="Real controlled APP202/Worker input; deep stage remains pending")
    intake.add_argument("--label", required=True)
    intake.add_argument("--minor", required=True, choices=("3.11", "3.13"))
    intake.add_argument("--source-profile", choices=("industrial-v1", "industrial-p40-v3"), default="industrial-v1")
    intake.add_argument("--native-l2", action="store_true")
    for operation in ("app-start", "app-status", "app-stop", "app-verify"):
        app = sub.add_parser(operation, help="Original one SSR, L2 preparation only; no fake deep report")
        app.add_argument("--run", required=True)
        if operation == "app-start":
            app.add_argument("--minor", choices=("3.11", "3.13"), default="3.11")
    args = parser.parse_args(argv)
    if args.operation.startswith("app-"):
        from integration.beta_review.codex3.local_app import start, status, request_stop
        if args.operation == "app-verify":
            from integration.beta_review.codex3.m3_browser_run import run
            from . import readiness
            result, code = run(args.run, preparation_only=not readiness.enabled(), native_l2=readiness.enabled()), 0
        elif args.operation == "app-start":
            result, code = start(args.run, args.minor, False, workbench=True, l2_prepare=True)
        else:
            result = status(args.run) if args.operation == "app-status" else request_stop(args.run)
            code = 0
        from integration.beta_review.codex3.local_app import folder_for
        readiness_file = folder_for(args.run) / "l2-readiness.json"
        if readiness_file.is_file():
            held = json.loads(readiness_file.read_bytes())
            result["l2_mode"] = held["mode"]
            result["p40_submit_enabled"] = held["p40_submit_enabled"]
        else:
            result["l2_mode"] = "PREPARATION_NOT_L2_E2E"
            result["p40_submit_enabled"] = False
        print(json.dumps(result, ensure_ascii=False))
        return code
    if args.operation == "worker-intake":
        return subprocess.run([sys.executable, "-m", "integration.l2_ops.verify_worker",
                               "--label", args.label, "--minor", args.minor, "--source-profile", args.source_profile,
                               *(["--native-l2"] if args.native_l2 else [])], check=False).returncode
    if args.operation == "native-check":
        result = load_native(load_source(args.manifest), args.reference,
                             expected_pack_ref=args.pack_ref,
                             expected_capture_run_id=args.capture_run_id).metadata()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    result = load_source(args.manifest).document()
    print(json.dumps({"state": "SOURCE_VALIDATED_NOT_DIAGNOSED", "source": result,
                      "worker_task_created": False}, ensure_ascii=False, indent=2))
    return 0

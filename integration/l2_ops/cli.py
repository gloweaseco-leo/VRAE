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
    args = parser.parse_args(argv)
    if args.operation == "worker-intake":
        return subprocess.run([sys.executable, "-m", "integration.l2_ops.verify_worker",
                               "--label", args.label, "--minor", args.minor], check=False).returncode
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

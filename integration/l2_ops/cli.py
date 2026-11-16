"""L2 operations in the existing beta entrypoint. No alternate web server."""
import argparse
import json

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
    args = parser.parse_args(argv)
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

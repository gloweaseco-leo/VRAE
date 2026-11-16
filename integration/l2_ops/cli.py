"""L2 operations in the existing beta entrypoint. No alternate web server."""
import argparse
import json

from vrae.l2_ops.ingest import load_source


def main(argv=None):
    parser = argparse.ArgumentParser(description="L2 controlled source preparation")
    sub = parser.add_subparsers(dest="operation", required=True)
    source = sub.add_parser("source-check", help="Validate/hash local evidence without external access")
    source.add_argument("manifest")
    args = parser.parse_args(argv)
    result = load_source(args.manifest).document()
    print(json.dumps({"state": "SOURCE_VALIDATED_NOT_DIAGNOSED", "source": result,
                      "worker_task_created": False}, ensure_ascii=False, indent=2))
    return 0

"""Explicit local/offline quality intake. No key generation, signing or network."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.benchmark import human_gold as legacy  # noqa: E402
from tests.benchmark.s2_quality import build_benchmark, canonical, fail  # noqa: E402
from tests.benchmark.s2_review import (  # noqa: E402
    packet_for,
    blank_review,
    export_packet,
    validate_packet,
    import_review,
    deduplicate,
    read_json,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("evaluate", "packet", "assess", "dedupe", "verify-export", "legacy")
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--review", type=Path, action="append", default=[])
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--signature", type=Path)
    parser.add_argument("--allowed-signers", type=Path)
    parser.add_argument("--anchor-sha256")
    parser.add_argument("--owner-identity")
    args = parser.parse_args()
    if args.review and args.command not in ("assess", "dedupe", "legacy"):
        parser.error("review input only accepted by explicit read-only intake commands")
    supplied = (args.allowed_signers, args.anchor_sha256, args.owner_identity)
    if any(supplied) and not all(supplied):
        parser.error(
            "Owner trust must be complete and out of band; never read from a review document"
        )
    trust = legacy.OwnerTrust(*supplied) if all(supplied) else None
    proof = dict(
        repository=ROOT, approval_file=args.approval, signature_file=args.signature, trust=trust
    )
    if args.command == "legacy":
        if len(args.review) > 1:
            parser.error("one original exact26 review document required")
        original = legacy.load_packet(ROOT)
        review = read_json(args.review[0]) if args.review else legacy.empty_review(original)
        result = legacy.assess_reviews(original, review, **proof)
    else:
        report = build_benchmark(ROOT)
        expected = packet_for(report)
        if args.packet:
            validate_packet(read_json(args.packet), expected_packet=expected)
        if args.command == "packet":
            if not args.output:
                parser.error("--output required for explicit unsigned export")
            packet = export_packet(report, args.output)
            legacy.write_blank_packet(legacy.load_packet(ROOT), args.output / "original-26")
            result = dict(
                packet_ref=packet["packet_ref"],
                report_ref=report["report_ref"],
                units=len(packet["units"]),
                state="UNREVIEWED_NOT_HUMAN_GOLD",
                signed=False,
            )
        elif args.command == "assess":
            if len(args.review) > 1:
                parser.error("one Owner-signed review set required; dedupe is content-only")
            review = read_json(args.review[0]) if args.review else blank_review(expected)
            result = import_review(expected, review, expected_packet=expected, **proof)
        elif args.command == "dedupe":
            result = deduplicate(expected, [read_json(p) for p in args.review])
        elif args.command == "verify-export":
            if not args.output:
                parser.error("--output identifies existing export folder")
            if canonical(read_json(args.output / "benchmark.json")) != canonical(report):
                fail("BENCHMARK_INDEPENDENT_REPLAY_MISMATCH")
            validate_packet(read_json(args.output / "s2-packet.json"), expected_packet=expected)
            result = dict(
                status="INDEPENDENT_NATIVE_REPLAY_VERIFIED",
                packet_ref=expected["packet_ref"],
                human_gold=False,
            )
        else:
            result = {
                k: report[k]
                for k in (
                    "version",
                    "scope",
                    "report_ref",
                    "generic_rules_exercised",
                    "s2_evaluator_support",
                    "synthetic_consistency",
                    "human_quality",
                    "scope_manifests",
                    "original_26",
                    "s2_exit",
                    "network_calls",
                    "model_calls",
                )
            }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()

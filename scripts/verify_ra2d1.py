"""Read-only by default. Import decisions, never create a signature or approval."""
import argparse
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from tests.benchmark.human_gold import (load_packet, empty_review, write_blank_packet,
    import_csv, assess_reviews, OwnerTrust, ReviewError)  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--export', action='store_true', help='Explicit blank packet export; refuses to overwrite changed review files.')
parser.add_argument('--reviews', type=Path)
parser.add_argument('--csv-origin', choices=('UNREVIEWED_TEMPLATE', 'SIMULATED_NOT_HUMAN_GOLD', 'EXTERNAL_HUMAN'),
                    default='UNREVIEWED_TEMPLATE')
parser.add_argument('--owner-approval', type=Path)
parser.add_argument('--owner-signature', type=Path)
parser.add_argument('--trusted-owner-signers', type=Path)
parser.add_argument('--trusted-owner-sha256')
parser.add_argument('--owner-identity')
args = parser.parse_args()
packet = load_packet(root)
if args.export:
    write_blank_packet(packet, root / 'docs/03-engineering/ra2d1-review')
review = empty_review(packet)
if args.reviews:
    raw = args.reviews.read_bytes()
    if len(raw) > 1_000_000:
        raise ReviewError('REVIEW_FILE_TOO_LARGE')
    text = raw.decode('utf-8-sig')
    review = import_csv(packet, text, origin=args.csv_origin) if args.reviews.suffix.lower() == '.csv' else json.loads(text)
options = (args.owner_approval, args.owner_signature, args.trusted_owner_signers,
           args.trusted_owner_sha256, args.owner_identity)
if any(options) and not all(options):
    parser.error('External approval, signature and all out-of-band trust settings must be supplied together.')
trust = OwnerTrust(args.trusted_owner_signers, args.trusted_owner_sha256, args.owner_identity) if all(options) else None
result = assess_reviews(packet, review, repository=root, approval_file=args.owner_approval,
    signature_file=args.owner_signature, trust=trust)
print(json.dumps(result, sort_keys=True))

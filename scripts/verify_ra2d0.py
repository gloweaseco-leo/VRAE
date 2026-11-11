"""Replay seven authored samples; never output an unreviewed quality PASS."""
import argparse
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from tests.benchmark.quality import evaluate_directory, prepare  # noqa: E402

MANIFEST_REF = 'cdea4fd2db9abcdce16e31632c9f6c96ff27fe32eb7a37ffc8711b432655a8fa'
parser = argparse.ArgumentParser()
parser.add_argument('--write-samples', action='store_true', help='Explicit candidate fixture resealing; cannot approve Gold.')
parser.add_argument('--write-report', action='store_true')
args = parser.parse_args()
samples = root / 'tests/benchmark/samples'
if args.write_samples:
    actual = prepare(samples)
    if actual != MANIFEST_REF:
        raise ValueError('BENCHMARK_MANIFEST_CHANGED_REQUIRES_REVIEW')
report = evaluate_directory(samples, expected_manifest_ref=MANIFEST_REF)
if args.write_report:
    output = root / 'docs/03-engineering/ra2d0-evidence/report.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + '\n', encoding='utf-8')
rules = [r for site in report['sites'] for r in site['rules']]
print(json.dumps({'status': report['status'], 'report_ref': report['report_ref'],
    'manifest_ref': MANIFEST_REF, 'samples': report['site_count'], 'site_types': report['distinct_site_types'],
    'candidate_consistency': report['synthetic_case_consistency'],
    'observed_outcomes': {status: sum(r['outcomes'][status] for r in rules)
                          for status in ('PASS', 'FAIL_WITH_EVIDENCE', 'UNKNOWN', 'ACCESS_BLOCKED')},
    'human_gold_evaluation': report['human_gold_evaluation'],
    'rejected_counterexamples': report['counterexamples']}, sort_keys=True))

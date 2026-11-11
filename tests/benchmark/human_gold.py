"""Offline human intake; metadata strings and generated inputs confer no authority."""
import csv
from dataclasses import dataclass
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import subprocess
from typing import Literal, TypedDict

from vrae.collection.manifest import document_hash
from .quality import evaluate_directory, RESULTS, score_candidate

VERSION = 'ra2d1-1.0.0'
MANIFEST_REF = 'cdea4fd2db9abcdce16e31632c9f6c96ff27fe32eb7a37ffc8711b432655a8fa'
BENCHMARK_REF = 'bench-20f34b51f69666edd89d26fcb54a569375edbba73f49b0a2cd9968a4064ccca4'
PACKET_REF = 'review-packet-f47c45fbe0a9362f7181bf708d644b9f1b4af420e8fadd237e5772e78d139f16'
SCOPE = 'ONE_CAPTURED_HREF_OR_EXPLICIT_EVIDENCE_GAP'
HUMAN_FIELDS = ('human_verdict', 'rationale', 'reviewer_identity', 'reviewed_at',
                'conflict_decision', 'owner_approval_reference')
STATES = ('UNREVIEWED', 'REVIEWED', 'REJECTED', 'CONFLICTED')
ORIGINS = ('UNREVIEWED_TEMPLATE', 'SIMULATED_NOT_HUMAN_GOLD', 'EXTERNAL_HUMAN')


class ReviewRow(TypedDict):
    unit_ref: str
    binding_sha256: str
    scope: str
    status: Literal['UNREVIEWED', 'REVIEWED', 'REJECTED', 'CONFLICTED']
    human_verdict: str | None
    rationale: str | None
    reviewer_identity: str | None
    reviewed_at: str | None
    conflict_decision: str | None
    owner_approval_reference: str | None


class ReviewError(ValueError):
    """Invalid binding/authority input; no sample content in errors."""


def _fail(reason='HUMAN_REVIEW_INTEGRITY'):
    raise ReviewError(reason)


def _bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def load_packet(root: Path):
    """Always replay all seven original samples before exposing/importing decisions."""
    report = evaluate_directory(root / 'tests/benchmark/samples', expected_manifest_ref=MANIFEST_REF)
    sealed = json.loads((root / 'docs/03-engineering/ra2d0-evidence/report.json').read_text(encoding='utf-8'))
    if report != sealed or report['report_ref'] != BENCHMARK_REF:
        _fail('SEALED_BENCHMARK_REPORT_MISMATCH')
    rows = []
    for site in report['sites']:
        for todo in site['review_todos']:
            binding = {'site_id': site['site_id'], 'site_type': site['site_type'], 'scope': SCOPE,
                'pins': site['pins'], 'controlled_sample_sha256': site['controlled_sample_sha256'],
                **{key: todo[key] for key in ('unit', 'candidate_label_ref', 'candidate_expected',
                    'candidate_rationale', 'observed_result', 'observation_id', 'execution_locator',
                    'finding_id', 'source_page', 'target_response', 'citations')}}
            binding['unit_ref'] = 'unit-' + document_hash(binding)
            rows.append(binding)
    if len(rows) != 26 or len({r['unit_ref'] for r in rows}) != 26:
        _fail()
    packet = {'version': VERSION, 'manifest_ref': MANIFEST_REF, 'benchmark_report_ref': BENCHMARK_REF,
              'private': True, 'approval_status': 'NOT_APPROVED', 'rows': rows}
    packet['packet_ref'] = 'review-packet-' + document_hash(packet)
    if packet['packet_ref'] != PACKET_REF:
        _fail('REVIEW_PACKET_PIN_MISMATCH')
    return packet


def empty_review(packet):
    return {'schema_version': '1.0', 'packet_ref': packet['packet_ref'],
        'manifest_ref': MANIFEST_REF, 'benchmark_report_ref': BENCHMARK_REF,
        'origin': 'UNREVIEWED_TEMPLATE', 'rows': [
            {'unit_ref': row['unit_ref'], 'binding_sha256': document_hash(row),
             'scope': SCOPE, 'status': 'UNREVIEWED', **{field: None for field in HUMAN_FIELDS}}
            for row in packet['rows']]}


def validate_review(packet, review):
    if (packet.get('packet_ref') != PACKET_REF or 'review-packet-' + document_hash({
            k: v for k, v in packet.items() if k != 'packet_ref'}) != PACKET_REF):
        _fail('REVIEW_PACKET_PIN_MISMATCH')
    expected = empty_review(packet)
    if len(_bytes(review)) > 1_000_000 or set(review) != set(expected):
        _fail()
    if (review['origin'] not in ORIGINS or any(review[key] != expected[key]
            for key in ('schema_version', 'packet_ref', 'manifest_ref', 'benchmark_report_ref'))):
        _fail()
    if not isinstance(review['rows'], list) or len(review['rows']) != 26:
        _fail('EXACT_26_UNITS_REQUIRED')
    bindings = {row['unit_ref']: row for row in packet['rows']}
    normalized, seen = [], set()
    for row in review['rows']:
        if (not isinstance(row, dict) or set(row) - set(expected['rows'][0])
                or row.get('unit_ref') not in bindings or row['unit_ref'] in seen):
            _fail('DUPLICATE_UNKNOWN_OR_OVERCLAIMED_UNIT')
        seen.add(row['unit_ref'])
        if (row.get('binding_sha256') != document_hash(bindings[row['unit_ref']])
                or row.get('scope') != SCOPE or row.get('status') not in STATES):
            _fail('UNIT_BINDING_OR_STATE_MISMATCH')
        for field in HUMAN_FIELDS:
            if row.get(field) is not None and (not isinstance(row[field], str) or len(row[field]) > 2000):
                _fail()
        normalized.append({**{field: None for field in HUMAN_FIELDS}, **row})
    return normalized


def _reviewed(row):
    if row['status'] != 'REVIEWED':
        return False
    if row['human_verdict'] not in RESULTS or any(not row[field] or not row[field].strip()
            for field in HUMAN_FIELDS):
        return False
    if row['conflict_decision'] not in ('NO_CONFLICT', 'RESOLVED'):
        return False
    try:
        return datetime.fromisoformat(row['reviewed_at'].replace('Z', '+00:00')).utcoffset() is not None
    except (ValueError, TypeError):
        return False


def _reserved_demo(row):
    # Reserved technical marker, not a heuristic for deciding whether a name is human.
    return any((row.get(field) or '').startswith('SIMULATED_')
               for field in ('reviewer_identity', 'owner_approval_reference'))


@dataclass(frozen=True)
class OwnerTrust:
    """Privileged OUT-OF-BAND Owner config, never accepted from the review document."""
    allowed_signers: Path
    allowed_signers_sha256: str
    owner_identity: str


def _verify_signature(raw, signature: Path, trust: OwnerTrust, repository: Path):
    # No keys, signing operation or bundled trust anchor is provided by this tool.
    # Owner must independently establish who controls this external public key.
    anchor = trust.allowed_signers.resolve()
    if anchor.is_relative_to(repository.resolve()) or not trust.owner_identity:
        return False
    try:
        if hashlib.sha256(anchor.read_bytes()).hexdigest() != trust.allowed_signers_sha256:
            return False
        result = subprocess.run(['ssh-keygen', '-Y', 'verify', '-f', str(anchor),
            '-I', trust.owner_identity, '-n', 'vrae-human-gold', '-s', str(signature)],
            input=raw, capture_output=True, timeout=10)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def verified_owner_rows(packet, review, *, repository, approval_file=None, signature_file=None, trust=None):
    """Verify Owner's external signed assertion of actual independent human review."""
    if review['origin'] != 'EXTERNAL_HUMAN' or approval_file is None or signature_file is None or trust is None:
        return set(), 'EXTERNAL_OWNER_VERIFICATION_REQUIRED'
    try:
        raw = Path(approval_file).read_bytes()
        if len(raw) > 1_000_000:
            _fail()
        approval = json.loads(raw)
        required = {'schema_version', 'purpose', 'review_set_sha256', 'packet_ref', 'owner_identity',
                    'independent_human_review_confirmed', 'owner_verified_at', 'approved_rows'}
        if (set(approval) != required or approval['schema_version'] != '1.0'
                or approval['purpose'] != 'VRAE_INDEPENDENT_HUMAN_REVIEW_ATTESTATION'
                or approval['review_set_sha256'] != document_hash(review)
                or approval['packet_ref'] != packet['packet_ref']
                or approval['owner_identity'] != trust.owner_identity
                or approval['independent_human_review_confirmed'] is not True
                or datetime.fromisoformat(approval['owner_verified_at'].replace('Z', '+00:00')).utcoffset() is None):
            return set(), 'OWNER_ATTESTATION_NOT_VALID'
        if not _verify_signature(raw, Path(signature_file), trust, repository):
            return set(), 'OWNER_SIGNATURE_NOT_VERIFIED'
        source_rows = {row['unit_ref']: row for row in review['rows']}
        approved = set()
        for entry in approval['approved_rows']:
            if (set(entry) != {'unit_ref', 'review_row_sha256'} or entry['unit_ref'] in approved
                    or entry['unit_ref'] not in source_rows
                    or entry['review_row_sha256'] != document_hash(source_rows[entry['unit_ref']])):
                return set(), 'OWNER_ROW_ATTESTATION_MISMATCH'
            approved.add(entry['unit_ref'])
        return approved, 'OWNER_SIGNATURE_AND_EXACT_ROWS_VERIFIED'
    except (ValueError, KeyError, TypeError, OSError, AttributeError):
        return set(), 'OWNER_ATTESTATION_NOT_VALID'


def selective_counts(bindings, rows):
    """Pure arithmetic; the caller must distinguish DEMO from verified human authority."""
    counts = dict(TP=0, FP=0, FN=0, TN=0, unresolved_expected_defects=0,
                  unsupported_defect=0, unjustified_pass=0, mismatch=0)
    abstentions = 0
    types = set()
    for row in rows:
        binding = bindings[row['unit_ref']]
        observed = binding['observed_result']
        for key, value in score_candidate(row['human_verdict'], observed).items():
            counts[key] += value
        if row['human_verdict'] not in ('PASS', 'FAIL_WITH_EVIDENCE') or observed not in ('PASS', 'FAIL_WITH_EVIDENCE'):
            abstentions += 1
        else:
            types.add(binding['site_type'])
    return {**counts, 'abstentions': abstentions, 'scored_site_types': len(types),
            'binary_units': sum(counts[k] for k in ('TP', 'FP', 'FN', 'TN'))}


def _quality_gate(complete, dense, false_fact):
    if not complete:
        return 'QUALITY_GATE_NOT_EVALUABLE'
    if false_fact:
        return 'QUALITY_GATE_FAIL_FALSE_FACT'
    return 'QUALITY_GATE_OWNER_DECISION_REQUIRED' if dense else 'QUALITY_GATE_NOT_EVALUABLE'


def assess_reviews(packet, review, *, repository=None, approval_file=None, signature_file=None, trust=None):
    rows = validate_review(packet, review)
    bindings = {row['unit_ref']: row for row in packet['rows']}
    approved, authority = verified_owner_rows(packet, review,
        repository=repository or Path(__file__).resolve().parents[2],
        approval_file=approval_file, signature_file=signature_file, trust=trust)
    eligible = [row for row in rows if _reviewed(row) and not _reserved_demo(row) and row['unit_ref'] in approved]
    scores = selective_counts(bindings, eligible)
    dense = scores['binary_units'] >= 5 and scores['scored_site_types'] >= 3
    metrics = {field: scores[field] if dense else None for field in ('TP', 'FP', 'FN', 'TN')}
    metrics.update(precision=scores['TP'] / (scores['TP'] + scores['FP']) if dense and scores['TP'] + scores['FP'] else None,
                   recall=scores['TP'] / (scores['TP'] + scores['FN']) if dense and scores['TP'] + scores['FN'] else None)
    complete = len(eligible) == 26
    false_fact = scores['FP'] + scores['unsupported_defect'] + scores['unjustified_pass']
    gate = _quality_gate(complete, dense, false_fact)
    result = {'status': 'HUMAN_REVIEW_READY', 'version': VERSION, 'packet_ref': packet['packet_ref'],
        'candidate_test_agreement': {'status': 'CANDIDATE_ONLY_NOT_HUMAN_GOLD', 'units': 26,
            'matching_units': sum(row['candidate_expected'] == row['observed_result'] for row in packet['rows'])},
        'review_set_sha256': document_hash(review), 'input_origin': review['origin'],
        'authority_state': authority, 'eligible_verified_rows': len(eligible), 'pending_rows': 26 - len(eligible),
        'reserved_simulated_rows': sum(_reserved_demo(row) for row in rows),
        'rejected_rows': sum(row['status'] == 'REJECTED' for row in rows),
        'conflicted_rows': sum(row['status'] == 'CONFLICTED' for row in rows),
        'incomplete_or_invalid_reviewed_rows': sum(row['status'] == 'REVIEWED' and not _reviewed(row) for row in rows),
        'gold_status': 'HUMAN_GOLD_VERIFIED_SYNTHETIC_ONLY' if complete else 'GOLD_LABEL_PENDING',
        'quality_gate': gate, 'provisional_human_synthetic_metrics': metrics,
        'provisional_false_fact_flags': false_fact,
        'selective_coverage': {'eligible_rows': len(eligible), 'total_units': 26,
            'binary_units': scores['binary_units'], 'abstentions': scores['abstentions'],
            'scored_site_types': scores['scored_site_types'], 'disagreements': scores['mismatch'],
            'unresolved_expected_defects': scores['unresolved_expected_defects'],
            'unsupported_defect': scores['unsupported_defect'], 'unjustified_pass': scores['unjustified_pass']},
        'minimum_metric_support': {'binary_units': 5, 'site_types': 3},
        'production_performance': 'NOT_ESTABLISHED', 'ra2d_final_pass': False, 'ra3_authorized': False,
        'human_must_supply': ['Actual independent evidence inspection and bounded verdict/rationale',
            'Real reviewer identity, timezone-aware time, conflict decision and Owner reference',
            'External Owner-signed exact review/row attestation and independently trusted public-key configuration']}
    if review['origin'] == 'SIMULATED_NOT_HUMAN_GOLD':
        result['simulation_diagnostics'] = {'status': 'SIMULATED_NOT_HUMAN_GOLD',
            **selective_counts(bindings, [row for row in rows if _reviewed(row)])}
    return result


FIXED_COLUMNS = ('unit_ref', 'binding_sha256', 'site_id', 'site_type', 'rule_id', 'rule_version',
    'scope', 'source_url', 'target_url', 'source_observed_at', 'raw_href', 'anchor_locator',
    'http_status', 'redirect_trace', 'evidence_refs', 'candidate_expected')
EDIT_COLUMNS = ('status', *HUMAN_FIELDS)


def _csv_fixed(binding):
    unit = binding['unit']
    target = binding['target_response']
    citation = binding['citations'][0] if binding['citations'] else {}
    refs = [ref for c in binding['citations'] for ref in (c['evidence_ref'], c.get('target_evidence_ref')) if ref]
    return {'unit_ref': binding['unit_ref'], 'binding_sha256': document_hash(binding),
        'site_id': binding['site_id'], 'site_type': binding['site_type'],
        'rule_id': unit['rule_id'], 'rule_version': unit['rule_version'], 'scope': binding['scope'],
        **{key: unit[key] or '' for key in ('source_url', 'target_url', 'source_observed_at')},
        'raw_href': citation.get('raw_href', ''),
        'anchor_locator': json.dumps({k: citation.get(k) for k in ('locator', 'line', 'column', 'anchor_index')}, sort_keys=True),
        'http_status': str(target['http_status']) if target else '',
        'redirect_trace': json.dumps(target['redirect_trace'] if target else [], sort_keys=True),
        'evidence_refs': json.dumps(refs), 'candidate_expected': binding['candidate_expected']}


def export_csv(packet):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=[*FIXED_COLUMNS, *EDIT_COLUMNS], lineterminator='\n')
    writer.writeheader()
    for binding in packet['rows']:
        writer.writerow({**_csv_fixed(binding), 'status': 'UNREVIEWED', **{f: '' for f in HUMAN_FIELDS}})
    return output.getvalue()


def import_csv(packet, text, *, origin='UNREVIEWED_TEMPLATE'):
    reader = csv.DictReader(io.StringIO(text, newline=''))
    if reader.fieldnames != [*FIXED_COLUMNS, *EDIT_COLUMNS]:
        _fail('CSV_CONTRACT_MISMATCH')
    bindings = {row['unit_ref']: row for row in packet['rows']}
    document = empty_review(packet)
    document['origin'], document['rows'] = origin, []
    for row in reader:
        if (set(row) != set((*FIXED_COLUMNS, *EDIT_COLUMNS)) or any(value is None for value in row.values())
                or row.get('unit_ref') not in bindings
                or any(row.get(k) != v for k, v in _csv_fixed(bindings[row['unit_ref']]).items())):
            _fail('CSV_IMMUTABLE_EVIDENCE_CHANGED')
        document['rows'].append({'unit_ref': row['unit_ref'], 'binding_sha256': row['binding_sha256'],
            'scope': row['scope'], 'status': row['status'], **{key: row.get(key) or None for key in HUMAN_FIELDS}})
    validate_review(packet, document)
    return document


def export_markdown(packet):
    lines = ['# Private synthetic evidence review — 26 UNREVIEWED units', '',
        'Inspect original sample bodies and response metadata BEFORE considering the candidate expectation.',
        'Fill reviewer.csv / review-input.json separately; no Gold approval is created by editing a name or flag.',
        'Full href locators, traces, evidence refs and blank human fields are in reviewer.csv and packet.json.', '',
        '| # | Site / rule@version | Source → target | HTTP / observed / candidate | Human verdict / rationale / identity / time / conflict / Owner ref |',
        '| --- | --- | --- | --- | --- |']
    for index, binding in enumerate(packet['rows'], 1):
        unit, target = binding['unit'], binding['target_response']
        source_url = unit['source_url'] or '(source not captured)'
        target_url = unit['target_url'] or '(no supported href observed)'
        lines.append(f"| {index} | {binding['site_id']} / {unit['rule_id']}@{unit['rule_version']} | "
            f"{source_url} → {target_url} | {target['http_status'] if target else 'N/A'} / "
            f"{binding['observed_result']} / {binding['candidate_expected']} | UNREVIEWED — all human fields blank |")
    return '\n'.join(lines) + '\n'


def write_blank_packet(packet, folder):
    files = {'packet.json': json.dumps(packet, sort_keys=True, indent=2) + '\n',
        'review-input.json': json.dumps(empty_review(packet), sort_keys=True, indent=2) + '\n',
        'reviewer.csv': export_csv(packet), 'reviewer.md': export_markdown(packet)}
    if any((folder / name).exists() and (folder / name).read_text(encoding='utf-8') != text
           for name, text in files.items()):
        _fail('EXPORT_WOULD_OVERWRITE_CHANGED_REVIEW')
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (folder / name).write_text(text, encoding='utf-8')

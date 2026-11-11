"""Small offline benchmark: candidate consistency is never human Gold quality."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import re
from urllib.parse import urljoin

from vrae.collection.manifest import document_hash
from vrae.collection.policy import canonical_url
from vrae.evidence import EvidencePack, build_pack
from vrae.findings import build_findings, FindingError, FindingPackage
from vrae.rules import execute, verify_execution
from .scenarios import capture, scenarios

VERSION = 'ra2d0-1.0.0'
BASE = 'e544fd31c9db66dfc7e5760d58e0503ff3fa5162'
EVALUATOR = 'ra2b1-1.0.0'
ENABLED = ('DISC-01', 'DISC-02', 'CTA-02')
RESULTS = ('PASS', 'FAIL_WITH_EVIDENCE', 'UNKNOWN', 'ACCESS_BLOCKED')
PENDING = ('reviewer', 'reviewed_at', 'adjudication', 'conflict_resolution', 'owner_approval_reference')
UNIT_FIELDS = ('rule_id', 'rule_version', 'source_url', 'target_url', 'source_observed_at', 'anchor_index')


class BenchmarkError(ValueError):
    """Reject untrusted samples/labels; never authorize Gold or public claims."""


def _fail(reason='BENCHMARK_INTEGRITY'):
    raise BenchmarkError(reason)


def _write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def controlled_sample_ref(sample):
    return document_hash({'fixture': sample['fixture'], 'pins': sample['pins']})


def prepare(directory: Path):
    """Explicitly seal authored inputs and candidate labels, never approve a label."""
    directory.mkdir(parents=True, exist_ok=True)
    entries = []
    for case in scenarios():
        fixture = {k: v for k, v in case.items() if k != 'labels'}
        pack = build_pack([capture(fixture)])
        execution = execute(pack, expected_pack_ref=pack.ref, evaluator_version=EVALUATOR)
        package = build_findings(pack, execution, expected_pack_ref=pack.ref,
            expected_execution_ref=execution['execution_ref'], expected_evaluator_version=EVALUATOR)
        pins = {'expected_pack_ref': pack.ref, 'expected_execution_ref': execution['execution_ref'],
            'expected_evaluator_version': EVALUATOR, 'expected_package_ref': package.ref}
        sample = {'fixture': fixture, 'pins': pins, 'evidence_document': pack.document,
            'objects_base64': {k: base64.b64encode(v).decode('ascii') for k, v in pack.objects.items()},
            'finding_package': package.document, 'candidate_labels': deepcopy(case['labels'])}
        sample['controlled_sample_sha256'] = controlled_sample_ref(sample)
        for label in sample['candidate_labels']:
            label['controlled_sample_sha256'] = sample['controlled_sample_sha256']
        name = case['site_id'] + '.json'
        _write(directory / name, sample)
        entries.append({'site_id': case['site_id'], 'file': name, 'sha256': document_hash(sample),
                        'controlled_sample_sha256': sample['controlled_sample_sha256']})
    manifest = {'schema_version': '1.0', 'harness_version': VERSION, 'baseline': BASE,
                'label_authority': 'CANDIDATE_ONLY_NO_HUMAN_APPROVAL', 'samples': entries}
    _write(directory / 'manifest.json', manifest)
    return document_hash(manifest)


def _key(unit):
    return tuple(unit[field] for field in UNIT_FIELDS)


def unit_for(rule, row):
    source = row.get('source_page', row.get('homepage'))
    target = row['target_response']
    citation = row['citations'][0] if row['citations'] else None
    url = target['url'] if target else None
    if url is None and citation is not None and source is not None:
        url = canonical_url(urljoin(source['final_url'] or source['url'], citation['raw_href']))
    return {'rule_id': rule['rule_id'], 'rule_version': rule['rule_version'],
        'source_url': source['url'] if source else None, 'target_url': url,
        'source_observed_at': source['observed_at'] if source else None,
        'anchor_index': citation['anchor_index'] if citation else None}


def validate_candidates(sample):
    if sample['controlled_sample_sha256'] != controlled_sample_ref(sample):
        _fail()
    seen = set()
    for label in sample['candidate_labels']:
        if (label['status'] != 'CANDIDATE' or any(label[field] is not None for field in PENDING)
                or label['scope'] != 'ONE_CAPTURED_HREF_OR_EXPLICIT_EVIDENCE_GAP'):
            _fail('GOLD_LABEL_PENDING_NO_APPROVAL_AUTHORITY')
        if (label['controlled_sample_sha256'] != sample['controlled_sample_sha256']
                or label['rule_id'] not in ENABLED or label['rule_version'] != '1.0.0'
                or label['expected'] not in RESULTS or not label['rationale'] or _key(label) in seen):
            _fail()
        seen.add(_key(label))


def replay_sample(sample):
    """Verify archived objects, complete execution/package, AND raw fixture recapture."""
    validate_candidates(sample)
    pins = sample['pins']
    pack = EvidencePack.load(sample['evidence_document'], {
        k: base64.b64decode(v, validate=True) for k, v in sample['objects_base64'].items()
    }, expected_ref=pins['expected_pack_ref'])
    execution = sample['finding_package']['rule_execution']
    verify_execution(execution, pack, expected_pack_ref=pins['expected_pack_ref'],
                     expected_evaluator_version=pins['expected_evaluator_version'])
    FindingPackage.load(sample['finding_package'], pack, **pins)
    if build_pack([capture(sample['fixture'])]).ref != pack.ref:
        _fail('RAW_FIXTURE_CAPTURE_MISMATCH')
    return pack, execution


def score_candidate(expected, actual):
    """Selective confusion: UNKNOWN/BLOCKED on either side are never TN/PASS."""
    result = dict(TP=0, FP=0, FN=0, TN=0, unresolved_expected_defects=0,
                  unsupported_defect=0, unjustified_pass=0, mismatch=int(expected != actual))
    binary = ('PASS', 'FAIL_WITH_EVIDENCE')
    if expected in binary and actual in binary:
        cell = {('FAIL_WITH_EVIDENCE', 'FAIL_WITH_EVIDENCE'): 'TP',
                ('PASS', 'FAIL_WITH_EVIDENCE'): 'FP', ('FAIL_WITH_EVIDENCE', 'PASS'): 'FN',
                ('PASS', 'PASS'): 'TN'}[(expected, actual)]
        result[cell] = 1
    elif expected == 'FAIL_WITH_EVIDENCE':
        result['unresolved_expected_defects'] = 1
    elif actual == 'FAIL_WITH_EVIDENCE':
        result['unsupported_defect'] = 1
    elif actual == 'PASS':
        result['unjustified_pass'] = 1
    return result


def assess_sample(sample, execution):
    labels = {_key(label): label for label in sample['candidate_labels']}
    package = sample['finding_package']
    findings = {i['finding']['observation_id']: i for i in package['items']}
    positives = {p['observation_id'] for p in package['checked_positive_paths']}
    metrics, todos, observed = [], [], set()
    for rule in execution['executions']:
        if rule['rule_id'] not in ENABLED:
            continue
        outcomes = {status: 0 for status in RESULTS}
        counts = dict(TP=0, FP=0, FN=0, TN=0, unresolved_expected_defects=0,
                      unsupported_defect=0, unjustified_pass=0, mismatch=0)
        for index, row in enumerate(rule['observations']):
            unit = unit_for(rule, row)
            key = _key(unit)
            if key in observed:
                _fail('DUPLICATE_BENCHMARK_UNIT')
            observed.add(key)
            actual = row['observation']['result']
            outcomes[actual] += 1
            oid = row['observation']['observation_id']
            finding = findings.get(oid)
            if ((actual == 'PASS' and (oid not in positives or finding is not None))
                    or (actual == 'FAIL_WITH_EVIDENCE' and (finding is None or finding['finding']['kind'] != 'OBSERVATION'))
                    or (actual in ('UNKNOWN', 'ACCESS_BLOCKED') and (finding is None
                        or finding['finding']['kind'] != 'UNKNOWN' or finding['finding']['evidence_ids']))):
                _fail('RULE_FINDING_ALIGNMENT_MISMATCH')
            candidate = labels.get(key)
            if candidate is not None:
                for name, value in score_candidate(candidate['expected'], actual).items():
                    counts[name] += value
            else:
                counts['mismatch'] += 1
            todos.append({'unit': unit, 'controlled_sample_sha256': sample['controlled_sample_sha256'],
                'candidate_label_ref': 'candidate-' + document_hash(candidate) if candidate else None,
                'candidate_expected': candidate['expected'] if candidate else None,
                'candidate_rationale': candidate['rationale'] if candidate else 'No authored label for this observed unit.',
                'observed_result': actual, 'observation_id': oid,
                'execution_locator': f"/executions/{execution['executions'].index(rule)}/observations/{index}",
                'finding_id': finding['finding']['finding_id'] if finding else None,
                'source_page': row.get('source_page', row.get('homepage')),
                'target_response': row['target_response'], 'citations': row['citations'],
                'review_status': 'GOLD_LABEL_PENDING', 'human_label': None, **{field: None for field in PENDING},
                'review_instructions': 'Inspect original fixture/body and bound evidence; adjudicate this href only. Resolve conflicts explicitly; no automatic Gold promotion.'})
        missing = sum(label['rule_id'] == rule['rule_id'] and key not in observed for key, label in labels.items())
        total = sum(outcomes.values())
        metrics.append({'rule_id': rule['rule_id'], 'rule_version': rule['rule_version'],
            'observed_unit_count': total, 'outcomes': outcomes, 'candidate_confusion': counts,
            'binary_scored_units': sum(counts[k] for k in ('TP', 'FP', 'FN', 'TN')),
            'unknown_rate': outcomes['UNKNOWN'] / total if total else None,
            'blocked_rate': outcomes['ACCESS_BLOCKED'] / total if total else None,
            'uncovered_candidate_units': missing,
            'human_gold_confusion': dict(TP=None, FP=None, FN=None, TN=None)})
    for key, candidate in labels.items():
        if key not in observed:
            todos.append({'unit': {field: candidate[field] for field in UNIT_FIELDS},
                'controlled_sample_sha256': sample['controlled_sample_sha256'],
                'candidate_label_ref': 'candidate-' + document_hash(candidate),
                'candidate_expected': candidate['expected'], 'observed_result': None,
                'review_status': 'GOLD_LABEL_PENDING', 'human_label': None,
                **{field: None for field in PENDING},
                'review_instructions': 'Candidate unit was not observed; do not score as TN or complete coverage.'})
    return {'site_id': sample['fixture']['site_id'], 'site_type': sample['fixture']['site_type'],
        'annotation': sample['fixture']['annotation'], 'pins': sample['pins'],
        'controlled_sample_sha256': sample['controlled_sample_sha256'], 'rules': metrics,
        'deferred_rule_count': 13, 'deferred_rule_ids': [e['rule_id'] for e in execution['executions'] if not e['enabled']],
        'mobile_layout_coverage': 'NOT_OBSERVED_NOT_SCORED',
        'human_gold_confusion': dict(TP=None, FP=None, FN=None, TN=None),
        'review_todos': todos, 'original_coverage': execution['coverage']}


def counterexamples(sample, pack):
    """Actually execute invalid-artifact replay; rejections never enter TP/TN counts."""
    results = []
    for mutation in ('missing_target_response', 'whole_site_overclaim', '403_as_defect'):
        document = deepcopy(sample['finding_package'])
        item = next(i for i in document['items'] if i['finding']['kind'] == 'OBSERVATION')
        if mutation == 'missing_target_response':
            del item['provenance']['target_response']
        elif mutation == 'whole_site_overclaim':
            item['finding']['statement'] = 'The entire website lacks products and cannot receive inquiries'
        else:
            item = next(i for i in document['items'] if i['outcome'] == 'ACCESS_BLOCKED')
            item['finding']['kind'] = 'OBSERVATION'
            item['finding']['statement'] = '403 proves this website has no inquiry capability'
        document['package_ref'] = 'fp-' + document_hash({k: v for k, v in document.items() if k != 'package_ref'})
        pins = {**sample['pins'], 'expected_package_ref': document['package_ref']}
        try:
            FindingPackage.load(document, pack, **pins)
        except FindingError:
            results.append({'case': mutation, 'result': 'REJECTED', 'counted_as_accurate_result': False})
        else:
            _fail('BENCHMARK_COUNTEREXAMPLE_ACCEPTED')
    return results


def evaluate_directory(directory: Path, *, expected_manifest_ref: str):
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    if document_hash(manifest) != expected_manifest_ref or manifest['baseline'] != BASE or manifest['harness_version'] != VERSION:
        _fail('BENCHMARK_MANIFEST_PIN_MISMATCH')
    entries = manifest['samples']
    if not 5 <= len(entries) <= 12 or len({entry['site_id'] for entry in entries}) != len(entries):
        _fail()
    sites, negative_results = [], []
    for entry in entries:
        if not re.fullmatch(r'[a-z0-9_]+\.json', entry['file']):
            _fail()
        raw = (directory / entry['file']).read_bytes()
        if len(raw) > 8_000_000:
            _fail()
        sample = json.loads(raw)
        if (document_hash(sample) != entry['sha256'] or sample['fixture']['site_id'] != entry['site_id']
                or sample['controlled_sample_sha256'] != entry['controlled_sample_sha256']):
            _fail()
        pack, execution = replay_sample(sample)
        sites.append(assess_sample(sample, execution))
        if entry['site_id'] == 'mixed_broken_paths':
            negative_results = counterexamples(sample, pack)
    if len({site['site_type'] for site in sites}) < 5 or len(negative_results) != 3:
        _fail()
    report = {'status': 'SYNTHETIC_BENCHMARK_READY', 'harness_version': VERSION,
        'baseline': BASE, 'manifest_ref': expected_manifest_ref, 'site_count': len(sites),
        'distinct_site_types': len({site['site_type'] for site in sites}),
        'synthetic_case_consistency': {'scope': 'CANDIDATE_COMPARISON_NOT_HUMAN_GOLD',
            'mismatches': sum(rule['candidate_confusion']['mismatch'] for site in sites for rule in site['rules']),
            'uncovered_candidate_units': sum(rule['uncovered_candidate_units'] for site in sites for rule in site['rules'])},
        'human_gold_evaluation': {'status': 'GOLD_LABEL_PENDING', 'quality_gate': 'QUALITY_GATE_NOT_EVALUABLE',
            'reviewed_units': 0, 'independent_reviewers': [], 'TP': None, 'FP': None, 'FN': None, 'TN': None,
            'precision': None, 'recall': None, 'denominator': None,
            'reason': 'N/A: no independently human-reviewed, Owner-signed Gold labels. This work package cannot approve them.'},
        'counterexamples': negative_results, 'sites': sites,
        'limits': ['OFFLINE_SYNTHETIC_CONSISTENCY_ONLY', 'ONLY_DISC01_DISC02_CTA02_EVALUATED',
            'UNKNOWN_BLOCKED_NEVER_TN', 'NO_ACCURACY_TARGET_OR_QUALITY_PASS_CLAIM',
            'HUMAN_ADJUDICATION_AND_CONFLICT_RESOLUTION_PENDING', 'NO_INFO01_OR_CODEX2_DEPENDENCY']}
    report['report_ref'] = 'bench-' + document_hash(report)
    return report

"""Pure preparatory TRUST-01 adapter; no evaluator dispatch or identity certification."""
import json

from vrae.collection.manifest import document_hash
from vrae.domain.contracts import validate_contract
from vrae.evidence import EvidenceError, EvidencePack
from .trust_facts import extract

VERSION = 'ra2b6-trust01-adapter-1.0.0'
RULE = {'rule_id': 'TRUST-01', 'rule_version': '1.0.0', 'buyer_task': 'TRUST'}
MAX_BYTES = 8_000_000
PASS_STATEMENT = (
    'At this capture, website source contains explicit self-declared organization text, '
    'company introduction and at least one static public contact link.'
)
COVERAGE = (
    'All captured HTTP HOME/ABOUT/CONTACT pages and discovered unvisited candidates in this '
    'pinned pack only; URL-role and supported-structure bounds apply. Source self-declarations '
    'only, not rendered visibility, legal entity/ownership, factory, certificate, qualification, '
    'trustworthiness, contact validity, reachability, completed inquiry or whole-site coverage. '
    'Missing, ambiguous or blocked evidence is not a company or website defect.'
)


def _encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def _company_name(fact):
    if fact['kind'] != 'DECLARED_NAME':
        return False
    if fact['basis'] == 'ORGANIZATION_SCOPE_NAME_TEXT':
        return True
    label = fact.get('label_citation')
    # An explicit Brand name label alone does not declare an organization name.
    return bool(label and label['text'].strip().casefold() in {
        'company name', 'organization name', 'legal name',
        '\u516c\u53f8\u540d\u79f0', '\u4f01\u4e1a\u540d\u79f0',
        '\u7ec4\u7ec7\u540d\u79f0', '\u6cd5\u5b9a\u540d\u79f0'})


def _prepare(pack, expected_pack_ref):
    facts = extract(pack, expected_pack_ref=expected_pack_ref)
    pages = facts['pages']
    selected = [(page_index, fact_index, fact) for page_index, page in enumerate(pages)
                for fact_index, fact in enumerate(page['facts'])]
    names = {f['citation']['text'].strip().casefold() for _, _, f in selected if _company_name(f)}
    descriptions = [f for _, _, f in selected if f['kind'] == 'SELF_DESCRIPTION'
                    and f['citation']['text'].strip()]
    links = [f for _, _, f in selected if f['kind'] == 'STATIC_CONTACT_LINK']
    missing = [label for label, present in (
        ('UNAMBIGUOUS_DECLARED_ORGANIZATION_NAME', len(names) == 1),
        ('STRUCTURED_COMPANY_INTRODUCTION', bool(descriptions)), ('STATIC_PUBLIC_CONTACT_LINK', bool(links)))
        if not present]
    blocked = [i for i, page in enumerate(pages) if page['status'] == 'ACCESS_BLOCKED']
    unknown = [i for i, page in enumerate(pages) if page['status'] == 'UNKNOWN']
    if blocked:
        result, reason = 'ACCESS_BLOCKED', 'RELEVANT_CAPTURE_SCOPE_BLOCKED'
    elif (not pages or missing or unknown or facts['unvisited_candidates']
          or facts['status'] != 'EXTRACTED'):
        result, reason = 'UNKNOWN', 'TRUST_PREREQUISITES_OR_CAPTURE_SCOPE_UNRESOLVED'
    else:
        result, reason = 'PASS', 'ALL_THREE_SOURCE_PREREQUISITES_RETAINED_IN_BOUNDED_SCOPE'
    citations = []
    qualifying_refs = set()
    for page_index, fact_index, fact in selected:
        qualifies = _company_name(fact) or fact['kind'] in {'SELF_DESCRIPTION', 'STATIC_CONTACT_LINK'}
        for role, citation in (('VALUE', fact['citation']), ('LABEL', fact.get('label_citation'))):
            if citation is None:
                continue
            citations.append({**citation, 'fact_kind': fact['kind'], 'page_index': page_index,
                              'fact_index': fact_index, 'citation_role': role})
            if qualifies:
                qualifying_refs.add(citation['evidence_ref'])
    observation = {'schema_version': '1.0', **{k: facts[k] for k in ('tenant_id', 'run_id')},
        **{k: RULE[k] for k in ('rule_id', 'rule_version')},
        'result': result, 'kind': 'OBJECTIVE' if result == 'PASS' else 'UNKNOWN',
        'evidence_ids': sorted(qualifying_refs) if result == 'PASS' else [],
        'statement': PASS_STATEMENT if result == 'PASS' else (
            'At least one captured relevant page was blocked; no company trust judgment is made.'
            if result == 'ACCESS_BLOCKED' else
            'Insufficient unambiguous captured source evidence for all three bounded trust prerequisites.'),
        'coverage_note': COVERAGE}
    row = {'observation': observation, 'adapter_version': VERSION, 'rule_metadata': RULE,
        'reason': reason, 'citations': citations, 'source_facts': facts,
        'source_pages': [p['source_page'] for p in pages],
        'blocked_page_indices': blocked, 'unknown_page_indices': unknown,
        'missing_prerequisites': missing, 'unvisited_candidates': facts['unvisited_candidates'],
        'scope_policy': 'ALL_CAPTURED_AND_DISCOVERED_HOME_ABOUT_CONTACT',
        'recorded_capture_scope': [{
            'source_ref': s['source_ref'], **{k: s['document'][k] for k in
                ('tenant_id', 'run_id', 'policy_id', 'policy_version')},
            'terms_reference': s['document'].get('terms_reference'),
            'limit': 'RECORDED_SYNTHETIC_SCOPE_NOT_CURRENT_AUTHORIZATION',
        } for s in pack.document['sources']], 'coverage': facts['coverage']}
    observation['observation_id'] = 'obs-' + document_hash(row)
    validate_contract('Observation', observation)
    output = {'adapter_version': VERSION, 'phase': 'PREP_ONLY', 'trust01_enabled': False,
              'expected_pack_ref': expected_pack_ref, 'trust_facts_ref': facts['facts_ref'], 'rows': [row],
              'limit': 'PREPARATORY_ADAPTER_NOT_RULE_EXECUTION_OR_DETACHED_OBSERVATION_PROOF'}
    output['preparation_ref'] = 'tp-' + document_hash(output)
    return output


def prepare(pack: EvidencePack, *, expected_pack_ref: str) -> dict:
    """Prepare one conservative scope row; does not enable TRUST-01 in any evaluator."""
    try:
        output = _prepare(pack, expected_pack_ref)
        raw = _encode(output)
        if len(raw) > MAX_BYTES:
            raise ValueError('OUTPUT_BOUND')
        return json.loads(raw)  # Detach from module constants and all other input state.
    except Exception as exc:
        raise EvidenceError('TRUST01_ADAPTER_INTEGRITY') from exc


def evaluate_trust(pack: EvidencePack, *, expected_pack_ref: str) -> list[dict]:
    """Pure row producer for future separately authorized execution integration."""
    return prepare(pack, expected_pack_ref=expected_pack_ref)['rows']


def verify_preparation(output: dict, pack: EvidencePack, *, expected_pack_ref: str) -> None:
    """Compare a full independent replay, never a detached Observation or rehashed wrapper."""
    try:
        raw = _encode(output)
        if len(raw) > MAX_BYTES or raw != _encode(prepare(pack, expected_pack_ref=expected_pack_ref)):
            raise ValueError('MISMATCH')
    except Exception as exc:
        raise EvidenceError('TRUST01_ADAPTER_INTEGRITY') from exc

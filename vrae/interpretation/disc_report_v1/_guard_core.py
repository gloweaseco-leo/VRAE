"""Pinned DISC v1 proof/replay fork; no legacy dispatch or module mutation.

Context, canonical source catalog and authority-ceiling projection preserve the
previous explicit DISC branch. Only stateless accepted serialization/injection
utilities and the immutable result carrier are shared with the legacy Guard.
"""
import hashlib
import json
import re

from vrae.collection.manifest import document_hash
from vrae.domain.contracts import validate_contract
from vrae.findings import FindingPackage
from vrae.findings.builder import SOURCE_VERSION_PAIRS
from vrae.interpretation.guard import (
    GuardError, _contains_instruction, _detach, _encode, _fail,
)

VERSION = 'ra3b-disc-1.0.0'
FIELDS = {'hypotheses': {'OBJECTIVE_SOURCE_FACT', 'HYPOTHESIS'},
          'recommendations': {'RECOMMENDATION'}, 'missing_information': {'MISSING_INFORMATION'}}


def _context(pack, package, pins):
    if set(pins) != {'expected_pack_ref', 'expected_execution_ref', 'expected_package_ref',
                     'expected_builder_version', 'expected_evaluator_version',
                     'expected_scope', 'expected_guard_version'}:
        _fail('PIN_MISMATCH')
    if (pins['expected_guard_version'] != VERSION
            or (pins['expected_evaluator_version'], pins['expected_builder_version'])
                not in SOURCE_VERSION_PAIRS):
        _fail('VERSION_MISMATCH')
    scope = {k: pack.document[k] for k in ('tenant_id', 'run_id', 'policy_id', 'policy_version')}
    if _encode(scope) != _encode(pins['expected_scope']):
        _fail('SCOPE_MISMATCH')
    package.verify(pack, **{k: v for k, v in pins.items()
                           if k not in ('expected_scope', 'expected_guard_version')})
    doc = package.document
    return {'version': VERSION, 'pins': _detach(pins), 'scope': scope,
            'catalog_sha256': doc['catalog_sha256'], 'coverage': doc['coverage'],
            'recorded_capture_scope': doc['recorded_capture_scope']}


def _catalog(pack, package):
    """Allow only narrow, generated literal statements over replayed C3 rows."""
    output = []
    link_rules = ('CTA-02', 'DISC-01', 'DISC-02')
    allowed = ('TRUST-01', 'SEO-01', 'INFO-01') + link_rules
    execution = package.document['rule_execution']
    for rule in execution['executions']:
        for row in rule['observations']:
            obs = row['observation']
            partial_product = (execution['evaluator_version'] in ('ra2b6-1.0.2', 'ra2b6-1.0.3', 'ra2b6-1.0.4', 'ra2b6-1.0.5')
                and rule['rule_id'] == 'INFO-01' and obs['result'] == 'UNKNOWN'
                and row.get('source_text_presence') == 'OBSERVED')
            if obs['result'] not in ('PASS', 'FAIL_WITH_EVIDENCE') and not partial_product:
                continue
            if rule['rule_id'] not in allowed:
                continue
            if rule['rule_id'] in link_rules and obs['result'] != 'FAIL_WITH_EVIDENCE':
                continue
            for index, citation in enumerate(row['citations']):
                # A partial rule remains UNKNOWN. Only independently replayed
                # literal name/description spans can anchor conditional prose;
                # no missing/ambiguous specification becomes an objective fact.
                if partial_product and citation.get('fact_role') not in ('NAME', 'DESCRIPTION'):
                    continue
                raw = citation.get('raw_element') or citation.get('element', {}).get('raw_element')
                resolved = pack.resolve(citation['evidence_ref'], expected_pack_ref=pack.ref)
                body = resolved['content']
                if body is None:
                    continue
                sig = rule['rule_id'] in ('SEO-01',) + link_rules
                text = body.decode('utf-8-sig' if sig else 'utf-8')
                pos = citation.get('element', citation)
                start = sum(len(s) + 1 for s in text.split('\n')[:pos['line'] - 1]) + pos['column']
                if not raw:
                    end = text.index('>', start) + 1
                    if rule['rule_id'] == 'INFO-01':
                        tag = re.match(r'<([a-zA-Z0-9]+)', pos['start_tag'])
                        if tag is None:
                            _fail('SOURCE_POSITION')
                        closing = re.search(r'</' + tag[1] + r'\s*>', text[end:], re.I)
                        if closing is None:
                            _fail('SOURCE_POSITION')
                        end += closing.end()
                    raw = text[start:end]
                if text[start:start + len(raw)] != raw:
                    _fail('SOURCE_POSITION')
                byte_start = len(text[:start].encode('utf-8'))
                if body.startswith(b'\xef\xbb\xbf') and sig:
                    byte_start += 3
                quote = raw.encode('utf-8')
                if body[byte_start:byte_start + len(quote)] != quote:
                    _fail('SOURCE_POSITION')
                source = {'citation': citation, 'byte_start': byte_start,
                          'byte_end': byte_start + len(quote), 'quote': raw,
                          'coverage_status': resolved['evidence']['status']}
                statement = ('Captured untrusted website source element only; no authenticity, '
                             'identity, effectiveness or business outcome verified: '
                             + json.dumps(raw, ensure_ascii=False))
                proof_kind = 'LITERAL_SOURCE_ELEMENT'
                if obs['result'] == 'FAIL_WITH_EVIDENCE':
                    if rule['rule_id'] not in link_rules or row['target_response']['http_status'] not in (404, 410):
                        continue
                    source['target_response'] = row['target_response']
                    statement = (f"Captured static href {json.dumps(citation['raw_href'])} returned "
                                 f"HTTP {row['target_response']['http_status']} at capture time only.")
                    proof_kind = ('CAPTURED_CTA_HTTP_FAILURE' if rule['rule_id'] == 'CTA-02'
                                  else 'CAPTURED_DISC_HTTP_FAILURE')
                elif rule['rule_id'] not in ('TRUST-01', 'SEO-01', 'INFO-01'):
                    continue
                fact = {'observation_id': obs['observation_id'], 'rule_id': rule['rule_id'],
                        'rule_version': obs['rule_version'], 'citation_index': index,
                        'proof_kind': proof_kind, 'statement': statement,
                        'source': source, 'coverage_note': obs['coverage_note'],
                        'observation_result': obs['result']}
                fact['fact_ref'] = 'cf-' + document_hash(fact)
                output.append(fact)
    if len(output) > 512:
        _fail('SOURCE_BOUND')
    return output


def catalog(pack, package: FindingPackage, **pins):
    try:
        context = _context(pack, package, pins)
        return _detach({'context': context, 'facts': _catalog(pack, package)})
    except GuardError:
        raise
    except Exception:
        raise GuardError('SOURCE_INTEGRITY') from None


def _project(interpretation, bindings, pack, package, pins):
    interpretation, bindings = _detach(interpretation), _detach(bindings)
    validate_contract('AIInterpretation', interpretation)
    for field in ('interpretation_id', 'model_id', 'observation_ids', 'evidence_ids'):
        values = interpretation[field] if isinstance(interpretation[field], list) else [interpretation[field]]
        if any(isinstance(v, str) and (_contains_instruction(v) or
               _contains_instruction(re.sub(r'[_.-]+', ' ', v))) for v in values):
            _fail('UNTRUSTED_INSTRUCTION')
    current = catalog(pack, package, **pins)
    context, facts = current['context'], current['facts']
    fact_bytes = {_encode(fact) for fact in facts}
    if any(interpretation[k] != context['scope'][k] for k in ('tenant_id', 'run_id')):
        _fail('SCOPE_MISMATCH')
    if not isinstance(bindings, list) or len(bindings) > 256:
        _fail('BINDING_BOUND')
    claims = [(f'/{field}/{i}', text, FIELDS[field]) for field in FIELDS
              for i, text in enumerate(interpretation[field])]
    if len(claims) > 256 or len(claims) != len(bindings):
        _fail('CLAIM_COVERAGE')
    expected_fields = {'binding_version', 'pointer', 'text', 'claim_type', 'context',
                       'fact', 'binding_ref'}
    if any(not isinstance(b, dict) or set(b) != expected_fields for b in bindings):
        _fail('BINDING_SHAPE')
    by_pointer = {b['pointer']: b for b in bindings}
    if len(by_pointer) != len(bindings) or set(by_pointer) != {c[0] for c in claims}:
        _fail('CLAIM_COVERAGE')
    valid_obs = {r['observation']['observation_id'] for rule in
                 package.document['rule_execution']['executions'] for r in rule['observations']}
    valid_ev = {e['evidence_ref'] for e in pack.document['evidence']}
    if (not set(interpretation['observation_ids']) <= valid_obs
            or not set(interpretation['evidence_ids']) <= valid_ev):
        _fail('GLOBAL_REFERENCE')
    results = []
    for pointer, text, types in claims:
        b = by_pointer[pointer]
        computed_ref = 'cb-' + document_hash({k: v for k, v in b.items() if k != 'binding_ref'})
        reason = None
        if (b['binding_ref'] != computed_ref
                or b['binding_version'] != VERSION or _encode(b['context']) != _encode(context)):
            reason = 'BINDING_INTEGRITY'
        elif b['text'] != text or b['claim_type'] not in types:
            reason = 'CLAIM_MISMATCH'
        elif _encode(b['fact']) not in fact_bytes:
            reason = 'UNBOUND_SOURCE'
        elif (b['fact']['observation_id'] not in interpretation['observation_ids']
              or b['fact']['source']['citation']['evidence_ref'] not in interpretation['evidence_ids']):
            reason = 'CLAIM_REFERENCE'
        elif _contains_instruction(text) or _contains_instruction(b['fact']['source']):
            reason = 'UNTRUSTED_INSTRUCTION'
        elif interpretation['status'] != 'VALIDATED':
            reason = 'INTERPRETATION_NOT_ELIGIBLE'
        elif b['claim_type'] == 'OBJECTIVE_SOURCE_FACT' and text != b['fact']['statement']:
            reason = 'UNSUPPORTED_OBJECTIVE_ASSERTION'
        status = ('REJECTED' if reason else 'SOURCE_FACT_BINDING_VERIFIED'
                  if b['claim_type'] == 'OBJECTIVE_SOURCE_FACT' else 'HUMAN_REVIEW_REQUIRED')
        trace = reason or ('LITERAL_ONLY' if status == 'SOURCE_FACT_BINDING_VERIFIED'
                           else 'SEMANTICS_REQUIRE_HUMAN')
        results.append({'pointer': pointer, 'binding_ref': computed_ref,
                        'status': status, 'reason': trace})
    result = {'guard_version': VERSION, 'context': context,
              'interpretation_sha256': document_hash(interpretation),
              'bindings_sha256': hashlib.sha256(_encode(bindings)).hexdigest(), 'claims': results,
              'private': True, 'approval_status': 'NOT_APPROVED', 'shareable': False,
              'is_report': False, 'semantic_approval': False,
              'limitations': ['CONSISTENCY_NOT_AUTHENTICITY_OR_CURRENT_AUTHORIZATION',
                              'LITERAL_SOURCE_ONLY_NO_SEMANTIC_APPROVAL',
                              'NO_REPORT_OR_SHARING_AUTHORITY']}
    result['guard_ref'] = 'cg-' + document_hash(result)
    return result

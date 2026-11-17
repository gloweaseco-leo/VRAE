"""Pinned read-only adapter inputs, not provenance, permission or rule judgments."""
import json
import re
from typing import Protocol

from vrae.collection.manifest import document_hash
from vrae.evidence import EvidenceError, EvidencePack
from vrae.rules.readiness import GAPS

CONTRACT_VERSION = 's2-readonly-1.0.0'
UX_RULES = ('INFO-03', 'CTA-01', 'CTA-03', 'TECH-02')
STATIC_RULES = ('DISC-03', 'INFO-02', 'TRUST-02', 'TRUST-03', 'SEO-02', 'TECH-01')
SCOPE = ('tenant_id', 'run_id', 'policy_id', 'policy_version')


def _encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _fail():
    raise EvidenceError('S2_ADAPTER_INPUT_INTEGRITY')


class ReadOnlyAdapter(Protocol):
    """C2's reserved s2_ux.evaluate callable; not loaded or enabled in P0.

    Return native RuleExecution observation rows, recomputed by trusted server
    code. P1 integration must validate rows and independently replay this call;
    a browser-supplied result is never an evaluator implementation.
    """
    def __call__(self, pack: EvidencePack, *, expected_pack_ref: str,
                 request: dict, expected_request_ref: str) -> list[dict]: ...


def adapter_request(pack: EvidencePack, *, expected_pack_ref: str,
                    rule_id: str, expected_scope: dict) -> dict:
    """Build a detached DTO exclusively from a verified, caller-pinned pack.

    expected_scope must come from the server's current task context. Matching
    it is consistency only; the caller must retain its original signed/current
    authority context, expiry, policy and task/version checks independently.
    """
    try:
        if (type(expected_pack_ref) is not str
                or not re.fullmatch(r'ep-[0-9a-f]{64}', expected_pack_ref)
                or type(rule_id) is not str or rule_id not in UX_RULES):
            _fail()
        pack.verify(expected_ref=expected_pack_ref)
        doc = pack.document
        scope = {key: doc[key] for key in SCOPE}
        if (type(expected_scope) is not dict or set(expected_scope) != set(SCOPE)
                or any(type(expected_scope[k]) is not type(scope[k]) for k in SCOPE)
                or _encode(expected_scope) != _encode(scope)):
            _fail()
        evidence = [e for e in doc['evidence'] if e['status'] == 'OBSERVED'
                    and e['blob_ref'] is not None
                    and e['kind'] in ('HTTP_BODY', 'BROWSER_DOM', 'BROWSER_SCREENSHOT')]
        responses = []
        for source in doc['sources']:
            if source['kind'] != 'CaptureManifest':
                continue
            for index, page in enumerate(source['document']['pages']):
                pointer = f'/pages/{index}'
                snap = next(s for s in doc['snapshots'] if s['source_ref'] == source['source_ref']
                            and s['locator'] == pointer + '/snapshot')
                responses.append({'source_ref': source['source_ref'], 'locator': pointer,
                    'snapshot_ref': snap['snapshot_ref'], 'http_status': page['http_status'],
                    'redirect_trace': page['redirect_trace'], 'error': page['error'],
                    'evidence_authority': 'METADATA_NOT_AN_OBSERVATION_EVIDENCE_REF'})
        request = {'contract_version': CONTRACT_VERSION, 'rule_id': rule_id,
            'expected_pack_ref': expected_pack_ref, 'scope': scope,
            'snapshots': doc['snapshots'], 'evidence': evidence,
            'response_metadata': responses, 'recorded_coverage': doc['coverage'],
            'coverage_denominator': None,
            'coverage_limit': 'RECORDED_CAPTURE_NOT_A_PREAUTHORIZED_SITE_DENOMINATOR',
            'state': 'INPUT_CONSISTENCY_ONLY_ADAPTER_NOT_ENABLED_P0',
            'limitations': ['NO_CURRENT_AUTHORIZATION_OR_SIGNED_PROVENANCE_CHECK',
                'NO_BROWSER_FIELDS_PROMOTED_TO_EVIDENCEPACK_FIELDS',
                'NATIVE_DOM_DOES_NOT_ESTABLISH_CTA_HREF_OR_LAYOUT_GEOMETRY',
                'LANGUAGE_SEMANTICS_REQUIRE_HUMAN_REVIEW',
                'MISSING_UNOBSERVED_UNSUPPORTED_IS_UNKNOWN_NOT_A_SITE_DEFECT',
                'INDUSTRY_NOT_APPLICABLE_REQUIRES_EXPLICIT_VERSIONED_APPLICABILITY',
                'NO_NETWORK_FORM_SUBMISSION_MODEL_OR_BUSINESS_APPROVAL']}
        request['input_ref'] = 's2i-' + document_hash(request)
        return request
    except Exception as exc:
        raise EvidenceError('S2_ADAPTER_INPUT_INTEGRITY') from exc


def verify_adapter_request(request: dict, pack: EvidencePack, *, expected_pack_ref: str,
                           expected_rule_id: str, expected_scope: dict,
                           expected_request_ref: str) -> None:
    try:
        if (type(expected_request_ref) is not str
                or not re.fullmatch(r's2i-[0-9a-f]{64}', expected_request_ref)):
            _fail()
        expected = adapter_request(pack, expected_pack_ref=expected_pack_ref,
                                   rule_id=expected_rule_id, expected_scope=expected_scope)
        if expected['input_ref'] != expected_request_ref or _encode(request) != _encode(expected):
            _fail()
    except Exception as exc:
        raise EvidenceError('S2_ADAPTER_INPUT_INTEGRITY') from exc


def resolve_input(request: dict, pack: EvidencePack, *, expected_pack_ref: str,
                  expected_rule_id: str, expected_scope: dict, expected_request_ref: str,
                  evidence_ref: str) -> dict:
    """Resolve a real allowed ev-ref; DOM strings/object hashes/metadata are not refs."""
    verify_adapter_request(request, pack, expected_pack_ref=expected_pack_ref,
        expected_rule_id=expected_rule_id, expected_scope=expected_scope,
        expected_request_ref=expected_request_ref)
    if (type(evidence_ref) is not str
            or evidence_ref not in {e['evidence_ref'] for e in request['evidence']}):
        _fail()
    return pack.resolve(evidence_ref, expected_pack_ref=expected_pack_ref)


def _extend_execution(baseline: dict, pack: EvidencePack, *, expected_pack_ref: str) -> dict:
    """Annotate the sole executor's legacy result; no new rules claimed implemented."""
    from vrae.rules.execution import S2_VERSION
    result = json.loads(_encode(baseline))
    del result['execution_ref']
    result['evaluator_version'] = S2_VERSION
    doc = pack.document
    scope = {key: doc[key] for key in SCOPE}
    result['adapter_contract_version'] = CONTRACT_VERSION
    result['adapter_requests'] = {rule: adapter_request(pack, expected_pack_ref=expected_pack_ref,
        rule_id=rule, expected_scope=scope) for rule in UX_RULES}
    result['s2_capabilities'] = [{'rule_id': row['rule_id'],
        'owner': 'C2' if row['rule_id'] in UX_RULES else 'C1' if row['rule_id'] in STATIC_RULES else 'LEGACY',
        'implementation': 'LEGACY_BOUNDED' if row['enabled'] else 'NOT_IMPLEMENTED_P0',
        'legacy_gap': GAPS[row['rule_id']]} for row in result['executions']]
    result['limitations'].extend(['S2_P0_INTERFACES_ONLY_NOT_TEN_NEW_RULES_IMPLEMENTED',
        'NO_S2_ADAPTER_LOADED_OR_BROWSER_RESULT_ACCEPTED',
        'S2_NOT_ADMITTED_BY_LEGACY_FINDINGPACKAGE_OR_GUARD',
        'HUMAN_GOLD_PENDING_NO_QUALITY_METRIC'])
    result['execution_ref'] = 'rx-' + document_hash(result)
    return result

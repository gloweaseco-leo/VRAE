"""Replay C3 and RA-3B before constructing any private report content."""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
from urllib.parse import urlsplit

from vrae.domain.contracts import validate_contract
from vrae.domain.evidence import validate_evidence_graph
from vrae.domain.reviews import report_content_hash
from vrae.interpretation import GuardResult, catalog
from .common import VERSION, MAX_BYTES, ReportError, detach, digest, display_text, encode, fail
from .editorial import EDITORIAL_VERSION, LIMITATIONS, PROPOSALS
from .renderer import RENDERER_VERSION, asset_hash, render_document

SOURCE_PIN_KEYS = {'expected_pack_ref', 'expected_execution_ref', 'expected_package_ref',
                   'expected_builder_version', 'expected_evaluator_version', 'expected_scope',
                   'expected_guard_version'}
PIN_KEYS = SOURCE_PIN_KEYS | {'expected_guard_refs', 'expected_metadata_sha256',
                             'expected_reporting_version', 'expected_renderer_version'}
META_KEYS = {'report_id', 'version', 'created_at', 'created_by', 'mode', 'finding_selection'}
TASKS = [('DISCOVER', '找到产品', ('DISC-01', 'DISC-02', 'DISC-03')),
         ('UNDERSTAND', '理解产品', ('INFO-01', 'INFO-02', 'INFO-03')),
         ('TRUST', '核对企业', ('TRUST-01', 'TRUST-02', 'TRUST-03')),
         ('INQUIRE', '联系咨询', ('CTA-01', 'CTA-02', 'CTA-03')),
         ('SEARCH_TECHNICAL', '搜索基础', ('SEO-01', 'SEO-02', 'TECH-01', 'TECH-02'))]


def _metadata(metadata, pins):
    if (set(metadata) != META_KEYS or digest(metadata) != pins['expected_metadata_sha256']
            or metadata['mode'] != 'SYNTHETIC_PRIVATE_PREVIEW'
            or type(metadata['version']) is not int or not 1 <= metadata['version'] <= 9999):
        fail('REPORT_METADATA')
    for key in ('report_id', 'created_by'):
        if not isinstance(metadata[key], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{2,95}', metadata[key]):
            fail('REPORT_METADATA')
    stamp = datetime.fromisoformat(metadata['created_at'].replace('Z', '+00:00'))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        fail('REPORT_TIMESTAMP')
    selection = metadata['finding_selection']
    if selection is not None and (not isinstance(selection, list) or not 1 <= len(selection) <= 3
                                 or any(not isinstance(s, str) for s in selection)
                                 or len(set(selection)) != len(selection)):
        fail('REPORT_SELECTION')


def _claims(guard_inputs, pack, package, pins):
    pack.verify(expected_ref=pins['expected_pack_ref'])
    sources = pack.document['sources']
    if len(sources) != 1 or sources[0]['kind'] != 'CaptureManifest':
        fail('REPORT_SINGLE_CAPTURE_REQUIRED')
    if (not isinstance(guard_inputs, list) or len(guard_inputs) > 16
            or not isinstance(pins['expected_guard_refs'], list)
            or len(pins['expected_guard_refs']) != len(guard_inputs)
            or len(set(pins['expected_guard_refs'])) != len(guard_inputs)):
        fail('REPORT_GUARD_PINS')
    source_pins = {k: pins[k] for k in SOURCE_PIN_KEYS}
    known = catalog(pack, package, **source_pins)
    known_facts = {encode(f) for f in known['facts']}
    claims = []
    for bundle, expected in zip(guard_inputs, pins['expected_guard_refs']):
        if set(bundle) != {'interpretation', 'bindings', 'guard'}:
            fail('REPORT_GUARD_SHAPE')
        verified = GuardResult.load(bundle['guard'], bundle['interpretation'], bundle['bindings'],
                                    pack, package, expected_guard_ref=expected, **source_pins)
        if bundle['interpretation']['status'] != 'VALIDATED':
            fail('REPORT_GUARD_NOT_VALIDATED')
        if any(bundle['interpretation'][k] is not None for k in ('model_id', 'input_tokens', 'output_tokens')):
            fail('REPORT_SYNTHETIC_MODEL_MODE')
        by_pointer = {b['pointer']: b for b in bundle['bindings']}
        for result in verified.document['claims']:
            b = by_pointer[result['pointer']]
            if result['status'] not in ('SOURCE_FACT_BINDING_VERIFIED', 'HUMAN_REVIEW_REQUIRED'):
                fail('REPORT_CLAIM_REJECTED')
            # Do not trust status + an arbitrary binding object as semantic proof.
            if (encode(b['fact']) not in known_facts or b['binding_ref'] != result['binding_ref']
                    or b['binding_ref'] != 'cb-' + digest({k: v for k, v in b.items() if k != 'binding_ref'})):
                fail('REPORT_CLAIM_INTEGRITY')
            field, index = result['pointer'].split('/')[1:]
            if b['text'] != bundle['interpretation'][field][int(index)]:
                fail('REPORT_CLAIM_INTEGRITY')
            display_text(b['text'], 2000)
            display_text(b['fact']['source']['quote'])
            if result['status'] == 'SOURCE_FACT_BINDING_VERIFIED':
                if b['claim_type'] != 'OBJECTIVE_SOURCE_FACT' or b['text'] != b['fact']['statement']:
                    fail('REPORT_OBJECTIVE_CEILING')
            elif (b['claim_type'], b['text']) not in set(PROPOSALS.values()):
                fail('REPORT_UNSUPPORTED_PROSE')
            claims.append({'guard_ref': verified.ref, 'binding_ref': b['binding_ref'],
                           'pointer': b['pointer'], 'status': result['status'],
                           'claim_type': b['claim_type'], 'text': b['text'], 'fact': b['fact']})
    return claims


def _issues(package, claims, selection):
    objective = [c for c in claims if c['status'] == 'SOURCE_FACT_BINDING_VERIFIED'
                 and c['fact']['proof_kind'] == 'CAPTURED_CTA_HTTP_FAILURE']
    groups: dict[tuple, list] = {}
    unsupported = 0
    for item in package.document['items']:
        if item['outcome'] != 'FAIL_WITH_EVIDENCE':
            continue
        finding, row = item['finding'], item['provenance']
        matches = [c for c in objective if c['fact']['observation_id'] == finding['observation_id']]
        if item['rule_id'] != 'CTA-02':
            unsupported += 1
            continue
        if len(matches) != 1:
            fail('REPORT_MISSING_OR_AMBIGUOUS_FACT')
        claim = matches[0]
        bridge = item['guard_bridge']
        validate_evidence_graph(bridge['native_snapshot'], bridge['native_evidence'],
                                bridge['guard_observation'], finding)
        target = row['target_response']
        if (finding['kind'] != 'OBSERVATION' or target['http_status'] not in (404, 410)
                or encode(target) != encode(claim['fact']['source']['target_response'])
                or claim['fact']['rule_id'] != item['rule_id']):
            fail('REPORT_EDGE_INTEGRITY')
        proposals = {}
        for role, (kind, text) in PROPOSALS.items():
            matches = [c for c in claims if c['status'] == 'HUMAN_REVIEW_REQUIRED'
                       and c['claim_type'] == kind and c['text'] == text
                       and encode(c['fact']) == encode(claim['fact'])]
            if len(matches) != 1:
                fail('REPORT_MISSING_OR_AMBIGUOUS_PROPOSAL')
            proposals[role] = matches[0]
        key = (item['rule_id'], target['final_url'] or target['url'], target['http_status'])
        groups.setdefault(key, []).append({'finding': finding, 'fact_claim': claim,
            'proposals': proposals, 'native_bridge': bridge, 'source_page': row['source_page'],
            'target_response': target, 'coverage_note': item['coverage_note']})
    representatives = [sorted(items, key=lambda x: x['finding']['finding_id'])[0]
                       for _, items in sorted(groups.items())]
    if selection is not None:
        by_id = {i['finding']['finding_id']: i for items in groups.values() for i in items}
        if not set(selection) <= by_id.keys():
            fail('REPORT_SELECTION')
        chosen = [by_id[k] for k in selection]
        keys = {(i['target_response']['final_url'] or i['target_response']['url'],
                 i['target_response']['http_status']) for i in chosen}
        if len(keys) != len(chosen):
            fail('REPORT_DUPLICATE_ISSUE')
    else:
        chosen = representatives[:3]
    return chosen, len(representatives) - len(chosen), unsupported


def _project(pack, package, guard_inputs, metadata, pins):
    pins, metadata, guard_inputs = detach(pins), detach(metadata), detach(guard_inputs)
    if (set(pins) != PIN_KEYS or pins['expected_reporting_version'] != VERSION
            or pins['expected_renderer_version'] != RENDERER_VERSION):
        fail('REPORT_PIN_VERSION')
    _metadata(metadata, pins)
    claims = _claims(guard_inputs, pack, package, pins)
    issues, omitted, unsupported = _issues(package, claims, metadata['finding_selection'])
    positives = []
    for rule in ('INFO-01', 'TRUST-01', 'SEO-01'):
        values = [c for c in claims if c['status'] == 'SOURCE_FACT_BINDING_VERIFIED'
                  and c['fact']['rule_id'] == rule and c['fact']['observation_result'] == 'PASS']
        if values:
            positives.append(values[0])
    pages = []
    for source in pack.document['sources']:
        if source['kind'] != 'CaptureManifest':
            fail('REPORT_CAPTURE_KIND')
        for page in source['document']['pages']:
            snapshot = page['snapshot']
            for key in ('url', 'final_url'):
                if snapshot[key] is not None:
                    display_text(snapshot[key], 2048)
            pages.append({'url': snapshot['url'], 'final_url': snapshot['final_url'],
                'captured_at': snapshot['captured_at'], 'role': page['role'],
                'status': snapshot['status'], 'http_status': page['http_status'],
                'error_code': page['error']['code'] if page['error'] else None})
    if not pages or len(pages) > 128:
        fail('REPORT_CAPTURE_SCOPE')
    for issue in issues:
        for value in (issue['source_page']['url'], issue['target_response']['url'],
                      issue['fact_claim']['fact']['source']['citation']['raw_href']):
            display_text(value, 2048)
    execution = package.document['rule_execution']
    journey = []
    for task, label, rules in TASKS:
        rows = [{'rule_id': r['rule_id'], 'observation_id': row['observation']['observation_id'],
                 'result': row['observation']['result']} for r in execution['executions']
                if r['rule_id'] in rules for row in r['observations']]
        journey.append({'task': task, 'label': label, 'observations': rows})
    native = None
    if issues:
        native = {'schema_version': '1.0', **{k: pins['expected_scope'][k] for k in ('tenant_id', 'run_id')},
            'report_id': metadata['report_id'], 'report_version_id': 'rv-' + digest(
                {'metadata': metadata, 'source_pins': pins}), 'version': metadata['version'],
            'content_hash': '0' * 64, 'status': 'REVIEW_REQUIRED',
            'finding_ids': [i['finding']['finding_id'] for i in issues],
            'created_by': metadata['created_by'], 'created_at': metadata['created_at'],
            'approved_by': None, 'approved_at': None, 'audit_mode': 'L1'}
        native['content_hash'] = report_content_hash(native, [i['finding'] for i in issues])
        validate_contract('ReportVersion', native)
    document = {'reporting_version': VERSION, 'renderer_version': RENDERER_VERSION,
        'renderer_asset_sha256': asset_hash(), 'editorial_version': EDITORIAL_VERSION,
        'metadata': metadata, 'pins': pins, 'guard_inputs_sha256': digest({'bundles': guard_inputs}),
        'scope': pins['expected_scope'], 'kind': 'L1_REPORT_DRAFT' if issues else 'PRIVATE_COVERAGE_SUMMARY',
        'private': True, 'approval_status': 'NOT_APPROVED', 'shareable': False,
        'semantic_approval': False, 'native_report_version': native,
        'site_host': urlsplit(pages[0]['url']).hostname, 'examined_pages': pages,
        'issues': issues, 'positive_source_claims': positives, 'buyer_journey': journey,
        'omitted_eligible_issues': omitted, 'unsupported_rule_findings': unsupported,
        'recorded_coverage': package.document['coverage'], 'limitations': LIMITATIONS,
        'content_basis': 'C3_FIELDS_AND_REPLAYED_PER_CLAIM_GUARD_NOT_EXTERNAL_AUTHENTICITY',
        'model_limitation': 'SYNTHETIC_PROPOSALS_NO_PROVIDER_CALL_NO_SEMANTIC_APPROVAL'}
    document['editorial_content_sha256'] = digest(document)
    html = render_document(document)
    document['html_sha256'] = hashlib.sha256(html).hexdigest()
    document['draft_ref'] = 'rd-' + digest(document)
    return document, html


@dataclass(frozen=True, slots=True)
class ReportDraft:
    """Immutable bytes; direct construction is not verification. Use build/load/render."""
    _payload: bytes
    _html: bytes

    def __post_init__(self):
        if (not isinstance(self._payload, bytes) or not isinstance(self._html, bytes)
                or len(self._payload) > MAX_BYTES or len(self._html) > MAX_BYTES):
            fail('REPORT_BOUND')

    @property
    def document(self):
        return json.loads(self._payload)

    @property
    def html_bytes(self):
        return self._html

    @property
    def ref(self):
        return self.document['draft_ref']

    @classmethod
    def load(cls, document, html_bytes, pack, package, guard_inputs, metadata,
             *, expected_draft_ref, **pins):
        rebuilt = build_draft(pack, package, guard_inputs, metadata, **pins)
        try:
            if (rebuilt.ref != expected_draft_ref or encode(detach(document)) != rebuilt._payload
                    or html_bytes != rebuilt.html_bytes):
                fail('REPORT_REPLAY_MISMATCH')
        except ReportError:
            raise
        except Exception:
            raise ReportError('REPORT_REPLAY_MISMATCH') from None
        return rebuilt


def build_draft(pack, package, guard_inputs, metadata, **pins):
    try:
        document, html = _project(pack, package, guard_inputs, metadata, pins)
        return ReportDraft(encode(document), html)
    except ReportError:
        raise
    except Exception:
        raise ReportError('REPORT_INTEGRITY') from None


def render(document, html_bytes, pack, package, guard_inputs, metadata, *, expected_draft_ref, **pins):
    """Guarded export of exact bytes; never renders a naked untrusted document."""
    return ReportDraft.load(document, html_bytes, pack, package, guard_inputs, metadata,
                            expected_draft_ref=expected_draft_ref, **pins).html_bytes

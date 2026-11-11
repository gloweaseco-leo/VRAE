"""A Finding record alone never proves the bound target HTTP response."""
from copy import deepcopy
from dataclasses import dataclass
import json
import re

from vrae.collection.manifest import document_hash
from vrae.domain.contracts import validate_contract
from vrae.domain.evidence import validate_evidence_graph
from vrae.evidence import EvidencePack
from vrae.rules import verify_execution

VERSION = 'ra2c0-1.0.0'
EVALUATOR = 'ra2b1-1.0.0'
INFO_VERSION = 'ra2c1-1.0.0'
INFO_EVALUATOR = 'ra2b3-1.0.0'
SEO_VERSION = 'ra2c2-1.0.0'
SEO_EVALUATOR = 'ra2b4-1.0.0'
MAX_BYTES = 8_000_000


class FindingError(ValueError):
    """Safe error vocabulary, no original URL, content or exception text."""


def _fail():
    raise FindingError('FINDING_INTEGRITY')


def _encode(document):
    return json.dumps(document, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _bridge(pack, observation, finding):
    """Adapt IDs exactly for the unchanged RA-0 single-Evidence graph guard."""
    if finding['kind'] == 'UNKNOWN':
        # No fact IDs exist to adapt. This is a scope-only guard projection,
        # NOT a captured SourceSnapshot or an observed Evidence domain record.
        context = 'ctx-' + document_hash({'pack_ref': pack.ref, 'run_id': observation['run_id']})
        scope = {k: observation[k] for k in ('tenant_id', 'run_id')}
        snapshot = {**scope, 'snapshot_id': context, 'status': 'UNKNOWN', 'sha256': None}
        evidence = {**scope, 'snapshot_id': context, 'certainty': 'UNKNOWN'}
        validate_evidence_graph(snapshot, evidence, observation, finding)
        return {'kind': 'UNKNOWN_RUN_CONTEXT', 'context_id': context,
                'scope': scope, 'evidence_mapping': [],
                'limit': 'Guard scope projection only; no captured snapshot or fact evidence asserted.'}
    # Every supported broken-link Observation has exactly one retained source
    # HTTP_BODY ref. Target failure is proven separately by full execution replay.
    if len(observation['evidence_ids']) != 1:
        _fail()
    ref = observation['evidence_ids'][0]
    resolved = pack.resolve(ref, expected_pack_ref=pack.ref)
    item = resolved['evidence']
    if item['kind'] != 'HTTP_BODY' or resolved['content'] is None:
        _fail()
    source = next(s for s in pack.document['sources'] if s['source_ref'] == item['source_ref'])
    tokens = item['locator'].split('/')
    if source['kind'] != 'CaptureManifest' or len(tokens) != 4 or tokens[1] != 'pages' or tokens[3] != 'evidence':
        _fail()
    page = source['document']['pages'][int(tokens[2])]
    evidence, snapshot = page['evidence'], page['snapshot']
    validate_contract('Evidence', evidence)
    if (evidence != resolved['source_record'] or evidence['evidence_id'] != item['source_evidence_id']
            or snapshot['snapshot_id'] != resolved['snapshot']['source_snapshot_id']):
        _fail()
    adapted = deepcopy(observation)
    adapted['evidence_ids'] = [evidence['evidence_id']]
    finding['evidence_ids'] = [evidence['evidence_id']]
    validate_evidence_graph(snapshot, evidence, adapted, finding)
    return {'kind': 'EXACT_NATIVE_HTTP_ID_MAPPING',
        'evidence_mapping': [{'evidence_ref': ref, 'native_evidence_id': evidence['evidence_id'],
            'source_ref': item['source_ref'], 'source_locator': item['locator'],
            'snapshot_ref': item['snapshot_ref'], 'native_snapshot_id': snapshot['snapshot_id']}],
        'native_snapshot': snapshot, 'native_evidence': evidence,
        'guard_observation': adapted,
        'limit': 'Source body bridge only; target response proof requires the inseparable provenance edge.'}


def _project(pack, execution, *, expected_pack_ref, expected_execution_ref, expected_evaluator_version,
             expected_builder_version=VERSION):
    evaluator = {VERSION: EVALUATOR, INFO_VERSION: INFO_EVALUATOR,
                 SEO_VERSION: SEO_EVALUATOR}.get(expected_builder_version)
    if (evaluator is None or expected_evaluator_version != evaluator or not isinstance(expected_execution_ref, str)
            or not re.fullmatch(r'rx-[0-9a-f]{64}', expected_execution_ref)):
        _fail()
    raw = _encode(execution)
    if len(raw) > MAX_BYTES:
        _fail()
    execution = json.loads(raw)  # Detached canonical input before verification/consumption.
    if execution['execution_ref'] != expected_execution_ref:
        _fail()
    verify_execution(execution, pack, expected_pack_ref=expected_pack_ref,
                     expected_evaluator_version=expected_evaluator_version)
    if execution['catalog_version'] != '1.0.0':
        _fail()
    items, positives, product_facts, seo_signals = [], [], [], []
    ids: set[str] = set()
    for index, rule in enumerate(execution['executions']):
        for row_index, row in enumerate(rule['observations']):
            observation = row['observation']
            oid = observation['observation_id']
            if oid in ids or len(ids) >= 1024:
                _fail()
            ids.add(oid)
            locator = f'/executions/{index}/observations/{row_index}'
            result = observation['result']
            if result == 'PASS':
                positive = {'observation_id': oid, 'rule_id': rule['rule_id'],
                    'buyer_task': rule['buyer_task'], 'execution_locator': locator,
                    'provenance': row}
                if expected_builder_version == SEO_VERSION and rule['rule_id'] == 'SEO-01':
                    seo_signals.append(positive)
                elif expected_builder_version in (INFO_VERSION, SEO_VERSION) and rule['rule_id'] == 'INFO-01':
                    product_facts.append(positive)
                else:
                    positives.append(positive)
                continue
            if result not in ('FAIL_WITH_EVIDENCE', 'UNKNOWN', 'ACCESS_BLOCKED'):
                _fail()  # No independently justified NOT_APPLICABLE exists in this version.
            objective = result == 'FAIL_WITH_EVIDENCE'
            if objective:
                target = row['target_response']
                if (rule['rule_id'] not in ('DISC-01', 'DISC-02', 'CTA-02') or target is None
                        or target['http_status'] not in (404, 410) or not target['redirect_trace']
                        or target['error'] is None or target['error']['code'] != 'HTTP_ERROR'):
                    _fail()
                statement = (f"One captured static href returned HTTP {target['http_status']} at capture time; "
                             'limited to the bound source href and target response.')
            else:
                statement = observation['statement']
            finding = {'schema_version': '1.0', 'tenant_id': execution['tenant_id'],
                'run_id': execution['run_id'], 'observation_id': oid,
                'kind': 'OBSERVATION' if objective else 'UNKNOWN', 'evidence_ids': [],
                'statement': statement, 'buyer_task': rule['buyer_task'], 'severity': None,
                'rule_version': observation['rule_version']}
            bridge = _bridge(pack, observation, finding)
            finding['finding_id'] = 'finding-' + document_hash({
                'builder_version': expected_builder_version, 'expected_pack_ref': expected_pack_ref,
                'execution_ref': expected_execution_ref, 'finding': finding})
            validate_contract('Finding', finding)
            items.append({'finding': finding, 'rule_id': rule['rule_id'], 'outcome': result,
                'execution_locator': locator, 'gap_reason': row['reason'],
                'coverage_note': observation['coverage_note'], 'provenance': row, 'guard_bridge': bridge})
    if len(items) > 256 or len(positives) + len(product_facts) + len(seo_signals) > 512:
        _fail()
    result = {'schema_version': '1.0', 'builder_version': expected_builder_version, 'tenant_id': execution['tenant_id'],
        'run_id': execution['run_id'], 'expected_pack_ref': expected_pack_ref,
        'execution_ref': expected_execution_ref, 'evaluator_version': expected_evaluator_version,
        'catalog_version': execution['catalog_version'], 'catalog_sha256': execution['catalog_sha256'],
        'private': True, 'approval_status': 'NOT_APPROVED', 'shareable': False,
        'artifact_kind': 'INTERNAL_SYNTHETIC_DIAGNOSTIC',
        'rule_execution': execution,
        'items': sorted(items, key=lambda item: item['finding']['finding_id']),
        'checked_positive_paths': sorted(positives, key=lambda item: item['observation_id']),
        'coverage': execution['coverage'], 'recorded_capture_scope': execution['recorded_capture_scope'],
        'limitations': ['OFFLINE_CONSISTENCY_NOT_AUTHENTICITY_OR_CURRENT_AUTHORIZATION',
            'NO_VISIBILITY_SEMANTIC_IDENTITY_REVENUE_OR_WHOLE_SITE_CLAIM',
            'NAKED_FINDING_IS_NOT_TARGET_RESPONSE_PROOF', 'PRIVATE_UNAPPROVED_NOT_A_REPORT_OR_SHARE_GRANT']}
    if expected_builder_version in (INFO_VERSION, SEO_VERSION):
        result['checked_product_facts'] = sorted(product_facts, key=lambda item: item['observation_id'])
        result['limitations'].append(
            'PRODUCT_SOURCE_TEXT_ONLY_NOT_ACCURACY_COMPLETENESS_AUTHENTICITY_COMPREHENSION_OR_FIT')
    if expected_builder_version == SEO_VERSION:
        result['checked_seo_signals'] = sorted(seo_signals, key=lambda item: item['observation_id'])
        result['limitations'].extend([
            'SEO01_ORIGINAL_HOME_TITLE_CANONICAL_TAG_PRESENCE_ONLY_NOT_A_DEFECT',
            'NO_CANONICAL_TARGET_FETCH_INDEXING_RANKING_CRAWLABILITY_OR_SEO_HEALTH_CLAIM',
            'ROBOTS_SITEMAP_UNKNOWN_WITHOUT_SEPARATELY_RESOLVABLE_CAPTURE'])
    result['package_ref'] = 'fp-' + document_hash(result)
    if len(_encode(result)) > MAX_BYTES:
        _fail()
    return result


@dataclass(frozen=True, slots=True)
class FindingPackage:
    """Immutable canonical bytes; detached document copies; no update/share API."""
    _payload: bytes

    def __post_init__(self):
        if not isinstance(self._payload, bytes) or len(self._payload) > MAX_BYTES:
            _fail()

    @property
    def document(self):
        return json.loads(self._payload)

    @property
    def ref(self):
        return self.document['package_ref']

    @classmethod
    def load(cls, document, pack, *, expected_pack_ref, expected_execution_ref,
             expected_evaluator_version, expected_package_ref, expected_builder_version=VERSION):
        try:
            package = cls(_encode(document))
            package.verify(pack, expected_pack_ref=expected_pack_ref,
                expected_execution_ref=expected_execution_ref, expected_evaluator_version=expected_evaluator_version,
                expected_package_ref=expected_package_ref, expected_builder_version=expected_builder_version)
            return package
        except Exception as exc:
            raise FindingError('FINDING_INTEGRITY') from exc

    def verify(self, pack, *, expected_pack_ref, expected_execution_ref,
               expected_evaluator_version, expected_package_ref, expected_builder_version=VERSION):
        try:
            document = self.document
            if (not isinstance(expected_package_ref, str) or not re.fullmatch(r'fp-[0-9a-f]{64}', expected_package_ref)
                    or document['package_ref'] != expected_package_ref):
                _fail()
            rebuilt = _project(pack, document['rule_execution'], expected_pack_ref=expected_pack_ref,
                expected_execution_ref=expected_execution_ref, expected_evaluator_version=expected_evaluator_version,
                expected_builder_version=expected_builder_version)
            if _encode(document) != _encode(rebuilt):
                _fail()
        except Exception as exc:
            raise FindingError('FINDING_INTEGRITY') from exc


def build_findings(pack: EvidencePack, execution: dict, *, expected_pack_ref: str,
                   expected_execution_ref: str, expected_evaluator_version: str,
                   expected_builder_version: str = VERSION) -> FindingPackage:
    try:
        return FindingPackage(_encode(_project(pack, execution, expected_pack_ref=expected_pack_ref,
            expected_execution_ref=expected_execution_ref, expected_evaluator_version=expected_evaluator_version,
            expected_builder_version=expected_builder_version)))
    except Exception as exc:
        raise FindingError('FINDING_INTEGRITY') from exc

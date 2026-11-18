"""Configured source-context candidates, never a second engineering or fact engine."""
from datetime import date
import re

from vrae.collection.manifest import document_hash
from vrae.collection.discovery import page_role
from vrae.domain.contracts import validate_contract
from vrae.evidence import EvidenceError
from vrae.industry.l2_v1.pack import IndustryPins, load_s2
from vrae.industry.l2_v1.diagnose import text, usable, normalized, quantity, product_family
from vrae.industry.l2_v1.s2_sources import extract_tables, VERSION as SOURCE_VERSION

RULES = ('INFO-02', 'TRUST-02', 'TRUST-03')
RULE_VERSION = 's2-industrial-context-1.0.0'
LIMIT = ('Read-only captured source declarations and independently pinned IndustryPack only. '
         'No whole-site absence, verified SKU/legal identity, authenticated certificate, supplier '
         'qualification, contact ownership/delivery, engineering fit or current authorization. '
         'Unsupported material, missing buyer duty and ambiguous associations are not site faults.')


def _citations(record, *keys):
    return [citation for key in keys for citation in
            (record['fields'][key]['citations'] if record and record['fields'].get(key) else [])]


def _present(record, key):
    value = usable(record, key)
    return value is not None and len(value['text']) <= 2048


def _row(doc, config_ref, rule, result, reason, *, model=None, records=(), keys=(), details=None):
    citations = _citations(records[0], *keys) if len(records) == 1 else [
        c for record in records for c in _citations(record, *keys)]
    # Preserve separate original byte spans even when text/evidence repeats.
    citations = list({(c['evidence_ref'], c['byte_start'], c['byte_end']): c for c in citations}.values())
    observation = {'schema_version': '1.0', 'tenant_id': doc['tenant_id'], 'run_id': doc['run_id'],
        'rule_id': rule, 'rule_version': RULE_VERSION, 'result': result,
        'kind': 'OBJECTIVE' if result == 'PASS' else 'UNKNOWN',
        'evidence_ids': sorted({c['evidence_ref'] for c in citations}) if result == 'PASS' else [],
        'statement': {
            'INFO-02': 'Check source-local configured attributes, explicit units, declared revision and conditions.',
            'TRUST-02': 'Check model-linked source-declared proof display context; authenticity is unassessed.',
            'TRUST-03': 'Check exact identity/contact strings under the same source-declared identifier; legal identity is unverified.',
        }[rule] + ' Candidate result: ' + result + '.', 'coverage_note': LIMIT}
    row = {'observation': observation, 'model': model, 'reason': reason,
        'source_version': SOURCE_VERSION, 'industry_ref': config_ref,
        'admission': 'READ_ONLY_CANDIDATE_NOT_FINDING_OR_GUARD_FACT',
        'citations': citations, 'source_pages': [r['source_page'] for r in records],
        'details': details or {}}
    observation['observation_id'] = 'obs-' + document_hash(row)
    validate_contract('Observation', observation)
    return row


def project_industrial(pack, held):
    """Internal S2 composition; caller's scope and pack pin were checked upstream."""
    doc = pack.document
    envelope: dict = {'source_version': SOURCE_VERSION, 'rule_version': RULE_VERSION,
        'authority': 'READ_ONLY_CANDIDATES_NOT_FINDINGS', 'industry_ref': None,
        'engineering_fit': 'UNKNOWN', 'authentication': 'UNKNOWN',
        'limitations': [LIMIT, 'NO_NATIVE_FACT_PROMOTION',
                        'ONE_TABLE_PER_SOURCE_TWO_IDENTITY_PAGES_ONLY',
                        'NO_NEGATIVE_SITE_OR_QUALIFICATION_JUDGMENT']}
    if held is None:
        envelope['rows'] = [_row(doc, None, rule, 'UNKNOWN', 'INDEPENDENT_INDUSTRY_PINS_REQUIRED')
                            for rule in RULES]
        return envelope
    try:
        if (type(held) is not IndustryPins or type(held.tenant_id) is not str
                or held.tenant_id != doc['tenant_id'] or type(held.industry_ref) is not str):
            raise ValueError('PINS')
        config = load_s2(tenant_id=held.tenant_id, version=held.version, profile_id=held.profile_id)
        if held.industry_ref != config['industry_ref']:
            raise ValueError('CONFIGURATION_PIN')
    except Exception as exc:
        raise EvidenceError('S2_INDUSTRY_CONFIGURATION') from exc
    profile, ref = config['profile'], config['industry_ref']
    extension = profile['s2']
    selected = extension['profiles'][held.profile_id]
    tables = extract_tables(pack, profile)
    rows = []

    def add(rule, result, reason, **kwargs):
        rows.append(_row(doc, ref, rule, result, reason, **kwargs))

    def excluded(rule):
        if rule not in selected['excluded_rule_ids']:
            return False
        add(rule, 'NOT_APPLICABLE', selected['reason'], details={
            'configuration_locator': '/profile/s2/profiles/' + held.profile_id + '/excluded_rule_ids'})
        return True

    products = [r for r in tables if normalized(text(r, 'record_type') or '')
                == normalized(profile['record_types']['product'])]
    product_excluded = set()
    for product in products:
        model, family = text(product, 'model'), product_family(product, profile)
        if family in selected['excluded_families']:
            product_excluded.add(id(product))
            add('INFO-02', 'NOT_APPLICABLE', selected['reason'], model=model,
                records=(product,), keys=('record_type', 'model', 'family'), details={
                    'configuration_locator': '/profile/s2/profiles/' + held.profile_id + '/excluded_families'})
            continue
        identity_ok = (model is not None and len(model) <= 128 and family in profile['families']
                       and sum(text(p, 'model') == model for p in products) == 1)
        required = (profile['families'][family]['critical'] + extension['required_product_context']
                    if identity_ok else ['model', 'family', *extension['required_product_context']])
        missing = [k for k in required if not _present(product, k)]
        quantities = {}
        invalid = []
        if identity_ok:
            for key, dimension in profile['families'][family]['dimensions'].items():
                value = quantity(text(product, key), profile)
                if value is None or value[0] != dimension:
                    invalid.append(key)
                else:
                    quantities[key] = {'dimension': value[0], 'value': str(value[1])}
        complete = identity_ok and not missing and not invalid
        add('INFO-02', 'PASS' if complete else 'UNKNOWN',
            'CONFIGURED_SOURCE_FIELDS_UNITS_REVISION_CONDITIONS' if complete else 'MODEL_OR_CONFIGURED_FIELDS_UNRESOLVED',
            model=model, records=(product,), keys=('record_type', 'family', *required), details={
                'family': family, 'data_revision': text(product, 'revision'),
                'specification_conditions': text(product, 'conditions'),
                'missing_or_ambiguous': missing, 'unsupported_quantities': invalid,
                'normalized_quantities': quantities, 'engineering_fit': 'UNKNOWN',
                'model_scope': extension['source_scope'],
                'unparsed_resources': product['unparsed_resources']})

    if not products:
        add('INFO-02', 'UNKNOWN', 'NO_UNAMBIGUOUS_PRODUCT_RECORD')

    if not excluded('TRUST-02'):
        proofs = [r for r in tables if normalized(text(r, 'record_type') or '')
                  == normalized(profile['record_types']['supplier'])]
        for product in products:
            model = text(product, 'model')
            if id(product) in product_excluded:
                add('TRUST-02', 'NOT_APPLICABLE', selected['reason'], model=model,
                    records=(product,), keys=('family', 'model'), details={
                        'configuration_locator': '/profile/s2/profiles/' + held.profile_id + '/excluded_families'})
                continue
            matching = [p for p in proofs if model is not None and model in
                        [m.strip() for m in (text(p, 'models') or '').split(',')]]
            if (not matching or model is None or sum(text(p, 'model') == model for p in products) != 1
                    or product_family(product, profile) not in profile['families']):
                add('TRUST-02', 'UNKNOWN', 'MODEL_LINKED_PROOF_UNRESOLVED', model=model,
                    records=(product,), keys=('model', 'family'))
                continue
            for proof in matching:
                kind = text(proof, 'proof_kind')
                spec = extension['proof_types'].get(kind)
                required = ['record_type', 'models', 'proof_kind'] + (list(spec.values()) if spec else [])
                complete = spec is not None and all(_present(proof, k) for k in required)
                relation = 'UNKNOWN'
                if complete:
                    try:
                        stated = text(proof, spec['date'])
                        if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', stated):
                            raise ValueError('EXACT_DATE_REQUIRED')
                        stated_date = date.fromisoformat(stated)
                        capture_date = date.fromisoformat(proof['source_page']['observed_at'][:10])
                        relation = ('BEFORE_CAPTURE' if stated_date < capture_date else
                                    'AFTER_CAPTURE' if stated_date > capture_date else 'ON_CAPTURE_DATE')
                    except (ValueError, TypeError):
                        complete = False
                add('TRUST-02', 'PASS' if complete else 'UNKNOWN',
                    'SOURCE_PROOF_DISPLAY_CONTEXT_ONLY' if complete else 'PROOF_KIND_FIELDS_OR_DATE_UNRESOLVED',
                    model=model, records=(product, proof), keys=('model', 'family', *required), details={
                        'proof_kind': kind, 'date_relation': relation,
                        'authentication': 'UNKNOWN', 'human_review_required': True,
                        'date_limit': 'SOURCE_DATE_RELATION_NOT_AUTHENTICITY_VALIDITY_OR_COMPLIANCE'})
        if not products:
            add('TRUST-02', 'UNKNOWN', 'PRODUCT_ASSOCIATION_UNAVAILABLE')

    if not excluded('TRUST-03'):
        identities = [r for r in tables if normalized(text(r, 'record_type') or '')
                      == normalized(profile['record_types']['identity'])]
        identity_keys = ('record_type', 'entity_namespace', 'entity_id', *extension['identity_fields'])
        comparable = (len(identities) == 2 and all(_present(r, k) for r in identities for k in identity_keys)
            and all(text(r, 'entity_namespace') in extension['identity_namespaces'] for r in identities)
            and text(identities[0], 'entity_namespace') == text(identities[1], 'entity_namespace')
            and text(identities[0], 'entity_id') == text(identities[1], 'entity_id'))
        conflicts = ([k for k in extension['identity_fields']
                      if text(identities[0], k) != text(identities[1], k)] if comparable else [])
        add('TRUST-03', 'PASS' if comparable and not conflicts else 'UNKNOWN',
            'SOURCE_DECLARED_STRINGS_MATCH' if comparable and not conflicts else
            'CITED_LITERAL_CONFLICT_CANDIDATE' if conflicts else 'DECLARED_ENTITY_SCOPE_UNRESOLVED',
            records=tuple(identities), keys=identity_keys, details={
                'literal_conflicts': conflicts, 'human_review_required': bool(conflicts) or not comparable,
                'identity_assurance': 'SOURCE_DECLARED_IDENTIFIER_ONLY',
                'entity_merge_performed': False, 'legal_identity_verification': 'UNKNOWN'})

    for blocked in (r for r in tables if r['status'] != 'EXTRACTED'
                    and page_role(r['url']) in ('PRODUCT', 'ABOUT', 'CONTACT')):
        for rule in RULES:
            if rule not in selected['excluded_rule_ids']:
                state = 'ACCESS_BLOCKED' if blocked['status'] == 'ACCESS_BLOCKED' else 'UNKNOWN'
                add(rule, state, 'INCOMPLETE_SOURCE_RECORD_TYPE_UNDETERMINED', records=(blocked,),
                    details={'record_type': 'UNKNOWN', 'no_rule_specific_absence_assertion': True})
    envelope.update(industry_ref=ref, parent_industry_ref=config['parent_industry_ref'],
        configuration_version=held.version, selected_profile_id=held.profile_id,
        model_scope=extension['source_scope'], rows=rows,
        source_coverage=[{'source_page': r['source_page'], 'status': r['status'],
                          'reason': r['reason']} for r in tables])
    return envelope

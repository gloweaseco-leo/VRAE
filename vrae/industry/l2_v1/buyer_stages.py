"""Abrasive-wheel buyer-stage checklist. Draft, unsigned, not a customer gap list.

The on-disk document keeps approval fields null. Unsigned items can only be
REVIEW_REQUIRED. A signed copy may be evaluated in tests; this draft is never
published onto a customer DTO. CLARIFY_CHANNEL cannot become GAP_WITH_EVIDENCE.
"""
from copy import deepcopy
import json

from jsonschema import Draft202012Validator

from vrae.collection.manifest import document_hash
from .pack import DIRECTORY

PATH = DIRECTORY / 'buyer-stages-1.0.0.json'
CONTRACT = 'vrae.buyer-stages.v1'
GAP = 'PRODUCT_FULLY_PARSED_AND_PARAMETER_REGION_PRESENT_AND_GROUP_ABSENT_AND_NO_UNPARSED_TECH_MATERIAL_LINK'
ITEM_IDS = ('AW-SCREEN-01', 'AW-COMPARE-01', 'AW-CONFIRM-01', 'AW-INQUIRE-01')
SIGNED_STATUSES = (
    'SOURCE_AVAILABLE', 'GAP_WITH_EVIDENCE', 'CLARIFY_ROUTE_RECORDED',
    'CLARIFY_ROUTE_UNKNOWN', 'UNKNOWN', 'NOT_APPLICABLE')
SCHEMA = {
    '$schema': 'https://json-schema.org/draft/2020-12/schema',
    'type': 'object',
    'additionalProperties': False,
    'required': ['schema_version', 'version', 'profile', 'status', 'customer_publication', 'approval', 'items'],
    'properties': {
        'schema_version': {'const': 'buyer-stages-1.0.0'},
        'version': {'const': '1.0.0'},
        'profile': {'const': 'abrasive_wheel'},
        'status': {'const': 'DRAFT'},
        'customer_publication': {'const': False},
        'approval': {
            'type': 'object',
            'additionalProperties': False,
            'required': ['signer', 'signed_at', 'config_sha256'],
            'properties': {
                'signer': {'type': ['string', 'null'], 'minLength': 1, 'maxLength': 120},
                'signed_at': {'type': ['string', 'null'], 'minLength': 1, 'maxLength': 40},
                'config_sha256': {'type': ['string', 'null'], 'pattern': '^[0-9a-f]{64}$'},
            },
        },
        'items': {
            'type': 'array',
            'minItems': 4,
            'maxItems': 4,
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['item_id', 'stage', 'site_role', 'field_groups', 'evidence', 'gap_condition', 'not_a_gap'],
                'properties': {
                    'item_id': {'enum': list(ITEM_IDS)},
                    'stage': {'enum': ['SCREENING', 'COMPARISON', 'TECH_CONFIRMATION', 'INQUIRY']},
                    'site_role': {'enum': ['DISCOVERABLE', 'PUBLISH', 'CLARIFY_CHANNEL']},
                    'field_groups': {
                        'type': 'array', 'uniqueItems': True,
                        'items': {'enum': ['usage', 'dimensions', 'abrasive', 'grit', 'bond']},
                    },
                    'evidence': {
                        'type': 'array', 'uniqueItems': True,
                        'items': {'enum': ['CATEGORY', 'PRODUCT', 'CONTACT']},
                    },
                    'gap_condition': {'type': ['string', 'null'], 'enum': [GAP, None]},
                    'not_a_gap': {'type': 'array', 'items': {'type': 'string', 'maxLength': 80}},
                },
            },
        },
    },
}


class ChecklistError(ValueError):
    """Closed configuration error. No page text in the message."""


def _fail():
    raise ChecklistError('BUYER_STAGE_CHECKLIST')


def validate(document):
    try:
        Draft202012Validator(SCHEMA).validate(document)
    except Exception:
        _fail()
    if [item['item_id'] for item in document['items']] != list(ITEM_IDS):
        _fail()
    publish = next(item for item in document['items'] if item['item_id'] == 'AW-COMPARE-01')
    if publish['site_role'] != 'PUBLISH' or publish['gap_condition'] != GAP:
        _fail()
    for item in document['items']:
        if item['site_role'] == 'CLARIFY_CHANNEL' and item['gap_condition'] is not None:
            _fail()
    return document


def load():
    document = validate(json.loads(PATH.read_text(encoding='utf-8')))
    approval = document['approval']
    if any(approval[key] is not None for key in ('signer', 'signed_at', 'config_sha256')):
        _fail()
    return document


def config_sha256(document):
    body = deepcopy(validate(document))
    body['approval'] = {'signer': None, 'signed_at': None, 'config_sha256': None}
    return document_hash(body)


def signature_valid(document):
    approval = validate(document)['approval']
    signer, signed_at, digest = approval['signer'], approval['signed_at'], approval['config_sha256']
    return bool(signer and signed_at and digest and digest == config_sha256(document))


def _pages(pages):
    if type(pages) is not list or any(type(page) is not dict for page in pages):
        _fail()
    return pages


def _blocked(pages):
    return any(page.get('unparsed_tech_material_link') or page.get('parameter_parse_ambiguous')
               or page.get('fully_parsed') is False or page.get('parameter_region_present') is False
               for page in pages)


def _group_status(item, group, pages):
    if any(page.get('applicable') is False for page in pages) and not any(
            page.get('applicable') is not False for page in pages):
        return 'NOT_APPLICABLE'
    relevant = [page for page in pages if page.get('visited') is not False and page.get('applicable') is not False]
    if not relevant:
        return 'UNKNOWN'
    if any(group in (page.get('present_fields') or []) for page in relevant):
        return 'SOURCE_AVAILABLE'
    if item['site_role'] != 'PUBLISH' or item['gap_condition'] != GAP or _blocked(relevant):
        return 'UNKNOWN'
    return 'GAP_WITH_EVIDENCE'


def _item_status(item, pages):
    if item['site_role'] == 'CLARIFY_CHANNEL':
        if pages and all(page.get('applicable') is False for page in pages):
            return 'NOT_APPLICABLE'
        if any(page.get('clarify_route_recorded') for page in pages):
            return 'CLARIFY_ROUTE_RECORDED'
        return 'CLARIFY_ROUTE_UNKNOWN'
    groups = item['field_groups']
    if not groups:
        return 'UNKNOWN'
    statuses = [_group_status(item, group, pages) for group in groups]
    if item['item_id'] == 'AW-SCREEN-01':
        if 'SOURCE_AVAILABLE' in statuses:
            return 'SOURCE_AVAILABLE'
        return statuses[0]
    if all(status == 'SOURCE_AVAILABLE' for status in statuses):
        return 'SOURCE_AVAILABLE'
    if all(status == 'GAP_WITH_EVIDENCE' for status in statuses):
        return 'GAP_WITH_EVIDENCE'
    if all(status == 'NOT_APPLICABLE' for status in statuses):
        return 'NOT_APPLICABLE'
    return 'UNKNOWN'


def evaluate(document, pages):
    """Direct checklist judgment. Unsigned output is only REVIEW_REQUIRED."""
    document = validate(document)
    pages = _pages(pages)
    signed = signature_valid(document)
    items = []
    for item in document['items']:
        if not signed:
            status = 'REVIEW_REQUIRED'
            groups = [{'field_group': group, 'status': 'REVIEW_REQUIRED'} for group in item['field_groups']]
        elif item['site_role'] == 'CLARIFY_CHANNEL':
            status = _item_status(item, pages)
            groups = [{'field_group': group, 'status': status} for group in item['field_groups']]
        else:
            groups = [{'field_group': group, 'status': _group_status(item, group, pages)}
                      for group in item['field_groups']]
            status = _item_status(item, pages)
        if item['site_role'] == 'CLARIFY_CHANNEL' and (
                status == 'GAP_WITH_EVIDENCE' or any(g['status'] == 'GAP_WITH_EVIDENCE' for g in groups)):
            _fail()
        if not signed and (status != 'REVIEW_REQUIRED' or any(
                g['status'] in ('GAP_WITH_EVIDENCE', 'SOURCE_AVAILABLE', 'CLARIFY_ROUTE_RECORDED') for g in groups)):
            _fail()
        items.append({'item_id': item['item_id'], 'stage': item['stage'], 'site_role': item['site_role'],
                      'status': status, 'groups': groups, 'is_defect': False})
    return {'contract': CONTRACT, 'version': document['version'], 'profile': document['profile'],
            'config_sha256': config_sha256(document), 'signed': signed,
            'customer_publication': False, 'diagnostic_attachment': None, 'items': items}


def customer_projection(evaluation):
    """This abrasive draft is not a customer result, signed or not."""
    if evaluation.get('customer_publication') is not False or evaluation.get('profile') != 'abrasive_wheel':
        _fail()
    return None


def diagnostic_attachment():
    """Version and hash for a new diagnostic path. Unsigned items stay REVIEW_REQUIRED."""
    document = load()
    evaluated = evaluate(document, [])
    if any(item['status'] != 'REVIEW_REQUIRED' for item in evaluated['items']):
        _fail()
    return {'version': document['version'], 'config_sha256': evaluated['config_sha256'],
            'signed': False, 'customer_gap_judgments': False, 'items': evaluated['items']}


def info02_result(evaluation):
    """Map a checklist judgment onto INFO-02. Unsigned cannot fail."""
    publish = [item for item in evaluation['items'] if item['site_role'] == 'PUBLISH']
    if not evaluation.get('signed'):
        return 'UNKNOWN', 'CHECKLIST_UNSIGNED_REVIEW_REQUIRED'
    if any(item['status'] == 'NOT_APPLICABLE' for item in publish) and all(
            item['status'] == 'NOT_APPLICABLE' for item in publish):
        return 'NOT_APPLICABLE', 'CHECKLIST_NOT_APPLICABLE'
    if any(item['status'] == 'GAP_WITH_EVIDENCE' or any(
            group['status'] == 'GAP_WITH_EVIDENCE' for group in item['groups']) for item in publish):
        return 'FAIL_WITH_EVIDENCE', 'PUBLISH_GROUP_ABSENT'
    if publish and all(item['status'] == 'SOURCE_AVAILABLE' for item in publish):
        return 'PASS', 'PUBLISH_GROUPS_SOURCE_AVAILABLE'
    return 'UNKNOWN', 'PUBLISH_GROUPS_UNRESOLVED'

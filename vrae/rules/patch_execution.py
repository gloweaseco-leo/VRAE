"""Explicit parser patch; the accepted execution.py Git blob stays unchanged."""
import json

from vrae.collection.manifest import document_hash
from vrae.evidence import EvidenceError
from .execution import execute as original_execute, TRUST_VERSION
from .readiness import catalog
from .seo01 import evaluate_seo01

PATCH_VERSION = 'ra2b6-1.0.1'
GENERIC_VERSION = 'ra2b6-1.0.2'


def execute(pack, *, expected_pack_ref, evaluator_version=TRUST_VERSION):
    if evaluator_version not in (PATCH_VERSION, GENERIC_VERSION):
        return original_execute(pack, expected_pack_ref=expected_pack_ref,
                                evaluator_version=evaluator_version)
    result = original_execute(pack, expected_pack_ref=expected_pack_ref, evaluator_version=TRUST_VERSION)
    rule = next(r for r in catalog()['rules'] if r['rule_id'] == 'SEO-01')
    target = next(r for r in result['executions'] if r['rule_id'] == 'SEO-01')
    target['observations'] = evaluate_seo01(pack, pack.document, rule,
        expected_pack_ref=expected_pack_ref, compatible=True)
    # SEO observations do not enter static buyer path composition. All other
    # rows and limitations are the original executor's independently replayed output.
    if evaluator_version == GENERIC_VERSION:
        from .info01 import evaluate_product_info
        from .contact_static import evaluate as contact
        for entry in result['executions']:
            rule = next(r for r in catalog()['rules'] if r['rule_id'] == entry['rule_id'])
            if entry['rule_id'] == 'INFO-01':
                entry['observations'] = evaluate_product_info(pack, pack.document, rule,
                    expected_pack_ref=expected_pack_ref, generic=True)
            elif entry['rule_id'] == 'CTA-01':
                entry['observations'] = contact(pack, pack.document, rule)
    result['evaluator_version'] = evaluator_version
    del result['execution_ref']
    result['execution_ref'] = 'rx-' + document_hash(result)
    return result


def verify_execution(output, pack, *, expected_pack_ref, expected_evaluator_version=None):
    try:
        version = output['evaluator_version']
        if expected_evaluator_version is not None and version != expected_evaluator_version:
            raise ValueError('RULE_VERSION_MISMATCH')
        expected = execute(pack, expected_pack_ref=expected_pack_ref, evaluator_version=version)
        if json.dumps(output, sort_keys=True, allow_nan=False) != json.dumps(expected, sort_keys=True):
            raise ValueError('RULE_EXECUTION_MISMATCH')
    except Exception as exc:
        raise EvidenceError('RULE_EXECUTION_INTEGRITY') from exc

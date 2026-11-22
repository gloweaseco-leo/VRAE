"""Explicit parser patch; the accepted execution.py Git blob stays unchanged."""
import json

from vrae.collection.manifest import document_hash
from vrae.evidence import EvidenceError
from .execution import execute as original_execute, TRUST_VERSION
from .readiness import catalog
from .seo01 import evaluate_seo01

PATCH_VERSION = 'ra2b6-1.0.1'
GENERIC_VERSION = 'ra2b6-1.0.2'
CONTENT_VERSION = 'ra2b6-1.0.3'
SCOPED_VERSION = 'ra2b6-1.0.4'
CONTEXT_VERSION = 'ra2b6-1.0.5'
FACTS_VERSION = 'ra2b6-1.0.6'


def execute(pack, *, expected_pack_ref, evaluator_version=TRUST_VERSION):
    from .replay_scope import replay
    return replay(pack, expected_pack_ref, evaluator_version, lambda: _execute(
        pack, expected_pack_ref=expected_pack_ref, evaluator_version=evaluator_version))


def _execute(pack, *, expected_pack_ref, evaluator_version):
    if evaluator_version == FACTS_VERSION:
        result = _execute(pack, expected_pack_ref=expected_pack_ref, evaluator_version=CONTEXT_VERSION)
        from .buyer_requirements import evaluate as buyer_requirements
        rule = next(item for item in catalog()['rules'] if item['rule_id'] == 'INFO-02')
        target = next(item for item in result['executions'] if item['rule_id'] == 'INFO-02')
        target['observations'] = buyer_requirements(pack, pack.document, rule, expected_pack_ref=expected_pack_ref)
        target['enabled'] = True
        result['evaluator_version'] = FACTS_VERSION
        del result['execution_ref']
        result['execution_ref'] = 'rx-' + document_hash(result)
        return result
    if evaluator_version not in (PATCH_VERSION, GENERIC_VERSION, CONTENT_VERSION, SCOPED_VERSION, CONTEXT_VERSION):
        return original_execute(pack, expected_pack_ref=expected_pack_ref,
                                evaluator_version=evaluator_version)
    result = original_execute(pack, expected_pack_ref=expected_pack_ref, evaluator_version=TRUST_VERSION)
    rule = next(r for r in catalog()['rules'] if r['rule_id'] == 'SEO-01')
    target = next(r for r in result['executions'] if r['rule_id'] == 'SEO-01')
    target['observations'] = evaluate_seo01(pack, pack.document, rule,
        expected_pack_ref=expected_pack_ref, compatible=True)
    # SEO observations do not enter static buyer path composition. All other
    # rows and limitations are the original executor's independently replayed output.
    if evaluator_version in (GENERIC_VERSION, CONTENT_VERSION, SCOPED_VERSION, CONTEXT_VERSION):
        from .info01 import evaluate_product_info
        from .contact_static import evaluate as contact
        for entry in result['executions']:
            rule = next(r for r in catalog()['rules'] if r['rule_id'] == entry['rule_id'])
            if entry['rule_id'] == 'INFO-01':
                entry['observations'] = evaluate_product_info(pack, pack.document, rule,
                    expected_pack_ref=expected_pack_ref, generic=True, content=evaluator_version in (CONTENT_VERSION, SCOPED_VERSION, CONTEXT_VERSION),
                    scoped=evaluator_version in (SCOPED_VERSION, CONTEXT_VERSION))
            elif entry['rule_id'] == 'CTA-01':
                entry['observations'] = contact(pack, pack.document, rule, labelled=evaluator_version in (CONTENT_VERSION, SCOPED_VERSION, CONTEXT_VERSION),
                    contextual=evaluator_version == CONTEXT_VERSION)
            elif evaluator_version in (CONTENT_VERSION, SCOPED_VERSION, CONTEXT_VERSION) and entry['rule_id'] in ('DISC-02', 'CTA-02'):
                from .static_journey import evaluate as static_links
                entry['observations'] = static_links(pack, pack.document, rule, contextual=evaluator_version == CONTEXT_VERSION)
        if evaluator_version == CONTEXT_VERSION:
            from .trust_context import evaluate as trust_context
            target = next(r for r in result['executions'] if r['rule_id'] == 'TRUST-01')
            rule = next(r for r in catalog()['rules'] if r['rule_id'] == 'TRUST-01')
            target['observations'] = trust_context(pack, pack.document, rule)
        if evaluator_version in (CONTENT_VERSION, SCOPED_VERSION, CONTEXT_VERSION):
            from .journey import compose_paths
            result['journeys'], result['journey_composition'] = compose_paths(result['executions'])
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

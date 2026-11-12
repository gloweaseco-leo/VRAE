"""Verify synthetic accounting/output binding; never approve model claim semantics."""
from dataclasses import asdict
from vrae.collection.manifest import document_hash
from vrae.domain.contracts import validate_contract
from .accounting import Ledger
from .common import GatewayError


def verify_accounting_audit(result, *, expected_request_ref, expected_ledger_ref, expected_recorded_at,
                            scope, policy, price):
    try:
        request = result['request']
        if (request['scope'] != asdict(scope) or request['request_ref'] != expected_request_ref or
                'req-' + document_hash({k:v for k,v in request.items() if k != 'request_ref'}) != expected_request_ref):
            raise ValueError()
        for key, value in dict(private=True, approval_status='NOT_APPROVED', shareable=False,
            synthetic_only=True, real_model_calls=0, real_token_charges=0,
            billing_origin='SYNTHETIC_ONLY_NOT_PROVIDER_INVOICE',
            token_basis='SYNTHETIC_UTF8_BYTES_NOT_PROVIDER_TOKENIZER',
            output_status='UNVALIDATED_NOT_AN_INTERPRETATION').items():
            if result[key] != value or type(result[key]) is not type(value):
                raise ValueError()
        book = Ledger.restore(result['ledger'], expected_ledger_ref=expected_ledger_ref,
                              scope=scope, policy=policy, price=price)
        if book.snapshot() != result['ledger']:
            raise ValueError()
        usage = result['usage']
        if usage['recorded_at'] != expected_recorded_at:
            raise ValueError()
        validate_contract('UsageRecord', usage)
        row = book.record(scope, result['operation_id'])
        if row['request_ref'] != expected_request_ref or usage != book.usage(scope, result['operation_id'], usage['recorded_at']):
            raise ValueError()
        interpretation = result['interpretation']
        validate_contract('AIInterpretation', interpretation)
        if (interpretation['tenant_id'] != scope.tenant_id or interpretation['run_id'] != scope.run_id
                or interpretation['status'] != 'NOT_RUN' or interpretation['observation_ids']
                or interpretation['evidence_ids'] or usage['cost_status'] == 'RECONCILED'):
            raise ValueError()
        if (interpretation['interpretation_id'] != 'ai-notrun-' + document_hash({
                'request': expected_request_ref, 'operation': result['operation_id']})
                or interpretation['missing_information'] != ['RA3B_CLAIM_VALIDATION_NOT_IMPLEMENTED']):
            raise ValueError()
        if result['status'] == 'FAKE_COMPLETED_UNVALIDATED':
            response_ref = 'response-' + document_hash({'request_ref': expected_request_ref,
                'text': result['provider_output'], 'input_tokens': usage['input_tokens'],
                'output_tokens': usage['output_tokens']})
            if row['state'] != 'COMMITTED' or row.get('response_ref') != response_ref or result['fixture_calls'] != 1:
                raise ValueError()
        elif (result['status'] != 'REFUSED' or result['provider_output'] is not None
              or (row['state'] == 'COMMITTED' and result['fixture_calls'] != 0)):
            raise ValueError()
    except Exception as exc:
        raise GatewayError('ACCOUNTING_AUDIT_INTEGRITY') from exc

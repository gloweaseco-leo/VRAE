"""Connect actual collected evidence to accepted C1 versioned DISC interfaces."""
from tests.reporting.synthetic import source_pins
from vrae.interpretation.disc_report_v1 import VERSION, binding, catalog, validate
from vrae.reporting.common import digest
from vrae.reporting.disc_report_v1 import build_draft, render
from vrae.reporting.disc_report_v1.policy import VERSION as REPORT_VERSION
from vrae.reporting.disc_report_v1.policy import RENDERER_VERSION, proposals_for
from vrae.b6_p0.delivery import DeliveryAuthorizationGate, OPERATIONS
from vrae.b6_p0.contracts import canonical, parse

def build(pack, package, metadata):
    source = {**source_pins(pack, package), 'expected_guard_version': VERSION}
    facts = catalog(pack, package, **source)
    guards = []
    for index, fact in enumerate(facts['facts']):
        interpretation = {
            'schema_version':'1.0', **{k:pack.document[k] for k in ('tenant_id','run_id')},
            'interpretation_id':'c3-collected-disc-'+str(index),
            'observation_ids':[fact['observation_id']],
            'evidence_ids':[fact['source']['citation']['evidence_ref']],
            'hypotheses':[fact['statement']], 'recommendations':[], 'missing_information':[],
            'model_id':None, 'input_tokens':None, 'output_tokens':None, 'status':'VALIDATED'}
        bindings = [binding(pointer='/hypotheses/0',text=fact['statement'],
                            claim_type='OBJECTIVE_SOURCE_FACT',fact=fact,context=facts['context'])]
        if fact['proof_kind'] in ('CAPTURED_DISC_HTTP_FAILURE','CAPTURED_CTA_HTTP_FAILURE'):
            for kind, text in proposals_for(fact['rule_id']).values():
                field = 'recommendations' if kind=='RECOMMENDATION' else 'hypotheses'
                pointer = '/'+field+'/'+str(len(interpretation[field]))
                interpretation[field].append(text)
                bindings.append(binding(pointer=pointer,text=text,claim_type=kind,fact=fact,context=facts['context']))
        guard = validate(interpretation,bindings,pack,package,**source)
        guards.append({'interpretation':interpretation,'bindings':bindings,'guard':guard.document})
    pins = {**source,'expected_guard_refs':[g['guard']['guard_ref'] for g in guards],
            'expected_metadata_sha256':digest(metadata),'expected_reporting_version':REPORT_VERSION,
            'expected_renderer_version':RENDERER_VERSION}
    draft = build_draft(pack,package,guards,metadata,**pins)
    html = render(draft.document,draft.html_bytes,pack,package,guards,metadata,
                  expected_draft_ref=draft.ref,**pins)
    return guards,pins,draft,html

def delivery_denials(draft):
    gate = DeliveryAuthorizationGate()
    # Reference bytes enter only the accepted bounded in-memory denial sink.
    raw = canonical({'draft_ref':draft.ref,'html_sha256':draft.document['html_sha256']})
    receipts = [parse(gate.attempt(op,raw)) for op in sorted(OPERATIONS)]
    assert all(r['decision']=='DENY' and not r['sent'] and r['grant'] is None
               and r['outbox_event'] is None and r['native_decision'] is None for r in receipts)
    return {'implemented':'ACCEPTED_B6_DENIAL_GATE_ONLY','operations':len(receipts),
            'allowed':0,'sent':0,'report_ref':draft.ref,
            'private_candidate_access':'BLOCKED_PENDING_ACCEPTED_RESULT_REVIEW_PORT',
            'receipt_sha256':[digest(r) for r in receipts]}


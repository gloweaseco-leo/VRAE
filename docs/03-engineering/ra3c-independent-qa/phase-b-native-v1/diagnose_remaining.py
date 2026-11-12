"""Record remaining native outcomes; no change to frozen/auxiliary expectations."""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CAND = ROOT.parent/'ra3c-qa-phaseb-6a7a3d3a'
sys.path.insert(0,str(CAND))
spec = importlib.util.spec_from_file_location('codex1_exact_original_inputs_diagnostic',CAND/'tests/reporting/test_ra3c_independent_acceptance.py')
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)
with qa.no_external_effects():
    import vrae.reporting as reporting


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag',choices=('py311','py313'),required=True)
    args = parser.parse_args()
    out = HERE/('diagnostic-'+args.tag)
    assert not out.exists(), 'Preserve original diagnostic'
    out.mkdir()
    controls = json.loads((HERE/'control-pins.json').read_text(encoding='utf-8'))['controls']
    requests = json.loads((HERE/'request-pins.json').read_text(encoding='utf-8'))['records']
    ctx = qa.prepare_context('broken404')
    held = controls['supported404']
    def params(row=held):
        bundles = [{k:deepcopy(b[k]) for k in ('interpretation','bindings','guard')} for b in row['bundles']]
        pins = deepcopy(row['source_pins'])
        pins['expected_guard_refs'] = [b['expected_guard_ref'] for b in row['bundles']]
        pins.update(deepcopy(requests['broken404']['1']['pins']))
        return bundles,deepcopy(requests['broken404']['1']['metadata']),pins
    bundles,metadata,pins = params()
    doc = json.loads((HERE/('controls-'+args.tag)/'supported404.draft.json').read_bytes())
    html = (HERE/('controls-'+args.tag)/'supported404.html').read_bytes()
    with qa.no_external_effects():
        native = reporting.ReportDraft.load(doc,html,ctx['pack'],ctx['package'],bundles,metadata,
            expected_draft_ref=doc['draft_ref'],**pins)
    record = dict(kind='ACTUAL_DIAGNOSTICS_NOT_FROZEN_SUITE_PASS',
        candidate_sha='6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2',python=sys.version,
        original_auxiliary_run_unchanged=True,baseline_public_load_replayed=True,calls=[])
    def save():
        (out/'results.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def observe(label,fn):
        try:
            with qa.no_external_effects():
                result = fn()
        except reporting.ReportError as error:
            entry = dict(label=label,outcome='NATIVE_REJECTION',code=str(error))
        else:
            entry = dict(label=label,outcome='NATIVE_ACCEPTANCE',ref=getattr(result,'ref',None))
        record['calls'].append(entry)
        save()
        print(label,entry['outcome'],entry.get('code',''),flush=True)
    for variant in ('false_certificate','instruction'):
        b,m,p = params(controls[variant])
        observe(variant,lambda:reporting.build_draft(ctx['pack'],ctx['package'],b,m,**p))
    b,m,p = params()
    p['expected_scope']['tenant_id'] += '-foreign'
    observe('foreign_scope',lambda:reporting.build_draft(ctx['pack'],ctx['package'],b,m,**p))
    b,m,p = params()
    m['version'] = True
    observe('malformed_metadata',lambda:reporting.build_draft(ctx['pack'],ctx['package'],b,m,**p))
    b,m,p = params()
    forged = b[0]['guard']
    next(c for c in forged['claims'] if c['status'] == 'HUMAN_REVIEW_REQUIRED')['status'] = 'SOURCE_FACT_BINDING_VERIFIED'
    forged['guard_ref'] = 'cg-'+hashlib.sha256(qa.canonical({k:v for k,v in forged.items() if k != 'guard_ref'})).hexdigest()
    observe('forged_guard_outer_resealed',lambda:reporting.build_draft(ctx['pack'],ctx['package'],b,m,**p))
    def load(document,rendered,ref):
        return reporting.ReportDraft.load(document,rendered,ctx['pack'],ctx['package'],bundles,
            metadata,expected_draft_ref=ref,**pins)
    language = html.replace(b'<html lang="zh-CN">',b'<html lang="en-US">',1)
    assert language != html
    observe('actual_language_bytes_tamper',lambda:load(doc,language,native.ref))
    changed = deepcopy(doc)
    changed['issues'][0]['fact_claim']['fact']['source']['citation']['evidence_ref'] = 'ev-'+'0'*64
    changed['draft_ref'] = 'rd-'+hashlib.sha256(qa.canonical({k:v for k,v in changed.items() if k != 'draft_ref'})).hexdigest()
    assert changed != doc
    (out/'outer-resealed-nested-evidence-attack.json').write_bytes(qa.canonical(changed))
    observe('nested_evidence_original_held_ref',lambda:load(changed,html,native.ref))
    observe('nested_evidence_attacker_resealed_ref',lambda:load(changed,html,changed['draft_ref']))
    approved = deepcopy(doc)
    approved.update(approval_status='APPROVED',private=False,shareable=True)
    observe('forged_approval_state',lambda:load(approved,html,native.ref))
    authority = deepcopy(doc)
    authority.update(review_decision={'forged_authority':True},share_grant={'forged_authority':True})
    observe('forged_review_and_share_fields',lambda:load(authority,html,native.ref))
    record['native_objective_projection'] = [dict(pointer=f'/issues/{i}/fact_claim',
        text=item['fact_claim']['text'],binding_ref=item['fact_claim']['binding_ref']) for i,item in enumerate(doc['issues'])]
    record['native_objective_projection'] += [dict(pointer=f'/positive_source_claims/{i}',
        text=claim['text'],binding_ref=claim['binding_ref']) for i,claim in enumerate(doc['positive_source_claims'])]
    forbidden = {'score','scores','site_score','whole_site_score','roi','google_rank','sales_loss'}
    def keys(value):
        if isinstance(value,dict):
            return [k for k in value if k.lower() in forbidden]+[k for v in value.values() for k in keys(v)]
        if isinstance(value,list):
            return [k for v in value for k in keys(v)]
        return []
    record['native_root_keys'] = sorted(doc)
    record['actual_score_fields_found'] = keys(doc)
    record['observations_complete'] = True
    save()


if __name__ == '__main__':
    main()

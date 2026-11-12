"""Separate real native requests for Owner M02/M03–M08 minimal reproduction.

Never replaces the unchanged 64-case suite or its independent proposal strings.
"""
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
spec = importlib.util.spec_from_file_location('codex1_unchanged_frozen_input_control',CAND/'tests/reporting/test_ra3c_independent_acceptance.py')
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)
with qa.no_external_effects():
    import vrae.reporting as reporting


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag',choices=('py311','py313'),required=True)
    args = parser.parse_args()
    out = HERE/('controls-'+args.tag)
    assert not out.exists(), 'Preserve original actual replays'
    out.mkdir()
    control_path = HERE/'control-pins.json'
    controls = json.loads(control_path.read_text(encoding='utf-8'))['controls']
    requests = json.loads((HERE/'request-pins.json').read_text(encoding='utf-8'))['records']
    record = dict(kind='SEPARATE_OWNER_CONTROL_REQUESTS_NOT_FROZEN_NODE_PASS',
        candidate_sha='6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2',python=sys.version,
        module_file=reporting.__file__,control_fixture_sha256=hashlib.sha256(control_path.read_bytes()).hexdigest(),
        calls=[],valid_reports={})
    built = {}

    def save():
        (out/'results.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    def arguments(scenario,variant=None,empty=False):
        ctx = qa.prepare_context(scenario)
        if variant:
            held = controls[variant]
            assert held['scenario'] == scenario
            assert held['source_pins'] == {k:v for k,v in ctx['pins'].items() if k != 'expected_guard_ref'}
            bundles = [{k:deepcopy(b[k]) for k in ('interpretation','bindings','guard')} for b in held['bundles']]
            guard_refs = [b['expected_guard_ref'] for b in held['bundles']]
        else:
            bundles = [dict(interpretation=ctx['interpretation'],bindings=ctx['bindings'],guard=ctx['guard'].document)]
            guard_refs = [ctx['pins']['expected_guard_ref']]
        pins = {k:deepcopy(v) for k,v in ctx['pins'].items() if k != 'expected_guard_ref'}
        pins['expected_guard_refs'] = [] if empty else guard_refs
        metadata = deepcopy(requests[scenario]['1']['metadata'])
        pins.update(deepcopy(requests[scenario]['1']['pins']))
        bundles = [] if empty else bundles
        return ctx,bundles,metadata,pins

    def build(label,scenario,variant=None,empty=False,expected=None,issues=None,attack=None):
        ctx,bundles,metadata,pins = arguments(scenario,variant,empty)
        if attack:
            attack(bundles,metadata,pins)
        entry = dict(label=label,scenario=scenario,variant=variant,explicit_empty_guard=empty,
            metadata=metadata,pins=pins)
        record['calls'].append(entry)
        try:
            with qa.no_external_effects():
                native = reporting.build_draft(ctx['pack'],ctx['package'],bundles,metadata,**pins)
        except reporting.ReportError as error:
            entry.update(outcome='NATIVE_REJECTION',code=str(error))
            save()
            assert expected == str(error), (label,expected,str(error))
            print(label,str(error),flush=True)
            return None
        entry.update(outcome='NATIVE_REPORT',ref=native.ref,issues=len(native.document['issues']))
        save()
        assert expected is None and len(native.document['issues']) == issues
        with qa.no_external_effects():
            loaded = reporting.ReportDraft.load(native.document,native.html_bytes,ctx['pack'],ctx['package'],
                bundles,metadata,expected_draft_ref=native.ref,**pins)
            html = reporting.render(native.document,native.html_bytes,ctx['pack'],ctx['package'],bundles,
                metadata,expected_draft_ref=native.ref,**pins)
        assert loaded.document == native.document and html == native.html_bytes
        doc = native.document
        assert doc['private'] is True and doc['shareable'] is False and doc['approval_status'] == 'NOT_APPROVED'
        assert all(c['status'] == 'HUMAN_REVIEW_REQUIRED' for i in doc['issues'] for c in i['proposals'].values())
        for item in doc['issues']:
            source = item['fact_claim']['fact']['source']
            resolved = ctx['pack'].resolve(source['citation']['evidence_ref'],expected_pack_ref=ctx['pack'].ref)
            assert resolved['content'][source['byte_start']:source['byte_end']] == source['quote'].encode()
        if not issues:
            assert doc['native_report_version'] is None
        (out/(label+'.html')).write_bytes(html)
        (out/(label+'.draft.json')).write_bytes(qa.canonical(doc))
        entry.update(public_load_render='ACTUALLY_REPLAYED',html_sha256=hashlib.sha256(html).hexdigest(),
            exact_original_source_quote_checked=True)
        record['valid_reports'][label] = dict(ref=native.ref,html_sha256=entry['html_sha256'],issues=issues)
        built[label] = (native,ctx,bundles,metadata,pins)
        save()
        print(label,'actual native report',issues,flush=True)
        return native

    build('original404','broken404',expected='REPORT_UNSUPPORTED_PROSE')
    build('original200','healthy200',expected='REPORT_UNSUPPORTED_PROSE')
    build('original_duplicate','duplicate_contact',expected='REPORT_UNSUPPORTED_PROSE')
    build('original_no_raw','raw_absent',expected='REPORT_GUARD_NOT_VALIDATED')
    native = build('supported404','broken404','supported404',issues=1)
    build('supported200','healthy200','supported200',issues=0)
    build('duplicate_one_fact','duplicate_contact','duplicate_one_fact',expected='REPORT_MISSING_OR_AMBIGUOUS_FACT')
    build('duplicate_all_facts','duplicate_contact','duplicate_all_facts',issues=1)
    build('explicit_empty_no_raw','raw_absent',empty=True,issues=0)
    build('false_certificate','broken404','false_certificate',expected='REPORT_UNSUPPORTED_PROSE')
    build('instruction','broken404','instruction',expected='REPORT_CLAIM_REJECTED')
    def foreign(bundles,metadata,pins):
        pins['expected_scope']['tenant_id'] += '-foreign'
    build('foreign_scope','broken404','supported404',expected='REPORT_INTEGRITY',attack=foreign)
    def bad_metadata(bundles,metadata,pins):
        metadata['version'] = True
    build('malformed_metadata','broken404','supported404',expected='REPORT_METADATA',attack=bad_metadata)

    _,ctx,bundles,metadata,pins = built['supported404']
    def reject_load(label,doc,html,expected):
        assert doc != native.document or html != native.html_bytes
        try:
            with qa.no_external_effects():
                reporting.ReportDraft.load(doc,html,ctx['pack'],ctx['package'],bundles,metadata,
                    expected_draft_ref=expected,**pins)
        except reporting.ReportError as error:
            record['calls'].append(dict(label=label,outcome='NATIVE_REJECTION',code=str(error),
                submitted_ref=doc['draft_ref'],held_expected_ref=expected))
            save()
            assert str(error) == 'REPORT_REPLAY_MISMATCH'
        else:
            raise AssertionError('Changed original report accepted')
    language = native.html_bytes.replace(b'<html lang="zh-CN">',b'<html lang="en-US">',1)
    assert language != native.html_bytes
    reject_load('real_html_language_mutation',native.document,language,native.ref)
    changed = native.document
    changed['issues'][0]['fact_claim']['fact']['source']['citation']['evidence_ref'] = 'ev-'+'0'*64
    changed['draft_ref'] = 'rd-'+hashlib.sha256(qa.canonical({k:v for k,v in changed.items() if k != 'draft_ref'})).hexdigest()
    reject_load('nested_evidence_outer_resealed_original_pin',changed,native.html_bytes,native.ref)
    reject_load('nested_evidence_outer_resealed_new_ref',changed,native.html_bytes,changed['draft_ref'])
    (out/'nested-evidence-attack.json').write_bytes(qa.canonical(changed))
    record['native_root_keys'] = sorted(native.document)
    record['native_objective_projection'] = [
        dict(text_pointer=f'/issues/{i}/fact_claim/text',text=item['fact_claim']['text'],
             binding_pointer=f'/issues/{i}/fact_claim/binding_ref',binding_ref=item['fact_claim']['binding_ref'])
        for i,item in enumerate(native.document['issues'])]+[
        dict(text_pointer=f'/positive_source_claims/{i}/text',text=claim['text'],
             binding_pointer=f'/positive_source_claims/{i}/binding_ref',binding_ref=claim['binding_ref'])
        for i,claim in enumerate(native.document['positive_source_claims'])]
    forbidden = {'score','scores','site_score','whole_site_score','roi','google_rank','sales_loss'}
    def bad_keys(value):
        if isinstance(value,dict):
            return [k for k in value if k.lower() in forbidden]+[k for v in value.values() for k in bad_keys(v)]
        if isinstance(value,list):
            return [k for v in value for k in bad_keys(v)]
        return []
    record['actual_forbidden_score_fields'] = bad_keys(native.document)
    assert not record['actual_forbidden_score_fields']
    record['completed'] = True
    save()


if __name__ == '__main__':
    main()

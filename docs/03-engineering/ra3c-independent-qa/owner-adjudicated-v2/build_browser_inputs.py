"""Real public build/load/render for the exact candidate, with independent quote replay."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worktree',required=True)
    parser.add_argument('--tag',choices=('py311','py313'),required=True)
    parser.add_argument('--out',required=True)
    args = parser.parse_args()
    root = Path(args.worktree).resolve()
    sys.path.insert(0,str(root))
    src = root/'docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2'
    spec = importlib.util.spec_from_file_location('v2_browser_source',src/'support.py')
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    with support.v1.no_external_effects():
        import vrae.reporting as reporting
        spec = importlib.util.spec_from_file_location('v2_browser_native_adapter',src/'adapter_v2.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        adapter = module.bind(reporting)
    out = Path(args.out)
    assert not out.exists(), 'Preserve actual browser-input generation'
    out.mkdir(parents=True)
    records = {}
    for name,scenario in (('contact-404','broken404'),('contact-200','healthy200')):
        context = support.positive_context(scenario)
        before = support.v1.canonical({k:context[k] for k in ('guard_inputs','pins')})
        with support.v1.no_external_effects():
            artifact = adapter.build(context,created_at=support.v1.INPUT['report_time'])
            loaded = adapter.load(artifact['document'],artifact['html'],context,expected_digest=artifact['digest'])
            rendered = adapter.render(artifact,context)
        assert loaded['document'] == artifact['document'] and rendered == artifact['html']
        assert before == support.v1.canonical({k:context[k] for k in ('guard_inputs','pins')})
        doc = artifact['document']
        claims = [i['fact_claim'] for i in doc['issues']]+[c for i in doc['issues'] for c in i['proposals'].values()]+doc['positive_source_claims']
        checks = []
        for claim in claims:
            source = claim['fact']['source']
            cite = source['citation']
            resolved = context['pack'].resolve(cite['evidence_ref'],expected_pack_ref=context['pins']['expected_pack_ref'])
            assert resolved['content'][source['byte_start']:source['byte_end']] == source['quote'].encode('utf-8')
            assert any(row['binding_ref'] == claim['binding_ref'] and row['status'] == claim['status']
                for bundle in context['guard_inputs'] for row in bundle['guard']['claims'])
            checks.append(dict(binding_ref=claim['binding_ref'],status=claim['status'],
                evidence_ref=cite['evidence_ref'],byte_start=source['byte_start'],byte_end=source['byte_end'],
                exact_original_quote=True))
        (out/(name+'.html')).write_bytes(artifact['html'])
        (out/(name+'.draft.json')).write_bytes(support.v1.canonical(doc))
        records[name] = dict(html_sha256=hashlib.sha256(artifact['html']).hexdigest(),
            draft_ref=artifact['digest'],issue_count=len(doc['issues']),source_checks=checks,
            public_build_load_render='ACTUALLY_EXECUTED',source_pack_ref=context['pins']['expected_pack_ref'])
    result = dict(version=support.VERSION,candidate_sha=adapter.binding['candidate_sha'],python=sys.version,
        producer_module=reporting.__file__,records=records,not_customer_approval=True)
    (out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(args.tag,'actual V2 public build/load/render and original byte quotes verified')


if __name__ == '__main__':
    main()

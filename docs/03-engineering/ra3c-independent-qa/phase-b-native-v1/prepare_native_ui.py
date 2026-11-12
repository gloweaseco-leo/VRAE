"""Stage unchanged actual public build/load/render bytes, no invented HTML."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    records = [json.loads((HERE/('controls-'+tag)/'results.json').read_text(encoding='utf-8'))
               for tag in ('py311','py313')]
    # A later auxiliary expected-error-code check stopped those runs. These
    # particular build/load/render components completed and are checked below;
    # do not relabel the original overall control runs as successful.
    for name in ('supported404','supported200'):
        assert records[0]['valid_reports'][name] == records[1]['valid_reports'][name]
        assert all(next(c for c in r['calls'] if c['label'] == name)['public_load_render'] == 'ACTUALLY_REPLAYED' for r in records)
    out = HERE/'ui-supplement'
    assert not out.exists(), 'Preserve original native-call captures'
    out.mkdir()
    artifacts = {}
    for label,name in (('supported404','contact-404'),('supported200','contact-200')):
        raw = (HERE/'controls-py313'/(label+'.html')).read_bytes()
        doc_bytes = (HERE/'controls-py313'/(label+'.draft.json')).read_bytes()
        document = json.loads(doc_bytes)
        assert hashlib.sha256(raw).hexdigest() == document['html_sha256']
        (out/(name+'.html')).write_bytes(raw)
        (out/(name+'.draft.json')).write_bytes(doc_bytes)
        artifacts[name] = dict(html_sha256=document['html_sha256'],draft_ref=document['draft_ref'],
            issue_count=len(document['issues']),provenance='ACTUAL_PUBLIC_BUILD_LOAD_RENDER_INDEPENDENT_SOURCE_CONTROL',
            original_source_quotes_independently_resolved=True)
    meta = dict(kind='INDEPENDENT_BROWSER_ON_REAL_PUBLIC_API_CONTROL_OUTPUT_NOT_FROZEN_PROPOSAL_PASS',
        candidate_sha=records[0]['candidate_sha'],frozen_64_case_visual_verdict='VISUAL_NOT_VERIFIED',
        original_control_runs_completed=[r.get('completed',False) for r in records],
        selected_public_api_components_actually_completed=True,
        controls_use_original_frozen_source_routes=True,controls_replace_frozen_suite_inputs=False,
        proposals='SEPARATELY_PINNED_OWNER_M02_SUPPORTED_CONTROL_REQUEST',artifacts=artifacts)
    (out/'source.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    print('Actual dual-runtime public API output staged for independent browser only')


if __name__ == '__main__':
    main()

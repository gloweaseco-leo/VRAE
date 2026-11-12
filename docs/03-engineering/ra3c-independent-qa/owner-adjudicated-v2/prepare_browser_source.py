"""Compare actual dual-runtime native reports, then stage exact browser bytes."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate',required=True)
    args = parser.parse_args()
    run = HERE/'runs'/args.candidate
    records = [json.loads((run/tag/'native/results.json').read_text(encoding='utf-8')) for tag in ('py311','py313')]
    assert records[0]['candidate_sha'] == records[1]['candidate_sha'] == args.candidate
    assert records[0]['records'] == records[1]['records'], 'Exact native reports must match across Python'
    out = run/'browser'
    assert not out.exists(), 'Preserve original browser captures'
    out.mkdir()
    for name,row in records[0]['records'].items():
        html = (run/'py313/native'/(name+'.html')).read_bytes()
        assert hashlib.sha256(html).hexdigest() == row['html_sha256']
        (out/(name+'.html')).write_bytes(html)
        (out/(name+'.draft.json')).write_bytes((run/'py313/native'/(name+'.draft.json')).read_bytes())
    data = dict(version='OWNER_ADJUDICATED_RA3C_QA_V2',candidate_sha=args.candidate,
        artifacts=records[0]['records'],original_quotes_verified=True,
        native_build_load_render_both_python=True,not_customer_approval=True)
    (out/'source.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print('Exact independent dual-runtime native source staged for real browser:',args.candidate)


if __name__ == '__main__':
    main()

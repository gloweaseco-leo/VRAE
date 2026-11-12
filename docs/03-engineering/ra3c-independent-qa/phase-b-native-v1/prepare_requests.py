"""Owner M01: externally pinned synthetic caller metadata; original inputs intact."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SHA = '6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2'


def main():
    target = HERE/'request-pins.json'
    assert not target.exists(), 'Preserve independently held request pins'
    source = ROOT/'tests/reporting/fixtures/ra3c_codex1_inputs.json'
    inputs = json.loads(source.read_text(encoding='utf-8'))
    rows = {}
    for name in inputs['scenarios']:
        rows[name] = {}
        for version in (1,2):
            metadata = dict(report_id='codex1-ra3c-'+name,version=version,
                created_at=inputs['report_time'],created_by='codex1-offline-operator',
                mode='SYNTHETIC_PRIVATE_PREVIEW',finding_selection=None)
            raw = json.dumps(metadata,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
            rows[name][str(version)] = dict(metadata=metadata,pins=dict(
                expected_metadata_sha256=hashlib.sha256(raw).hexdigest(),
                expected_reporting_version='ra3c-1.0.0',expected_renderer_version='ra3c-html-1.0.1'))
    target.write_text(json.dumps(dict(authority='PR48 issuecomment-6815157266 M01',
        candidate_sha=SHA,request_count=28,original_input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        records=rows),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('M01: 28 externally pinned requests, no source/claim/approval changes')


if __name__ == '__main__':
    main()

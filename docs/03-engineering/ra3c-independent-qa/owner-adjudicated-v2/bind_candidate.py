"""Pin final public code versions and independent synthetic caller metadata."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OLD = '6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2'


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)


def constant(raw,name):
    return next(ast.literal_eval(n.value) for n in ast.parse(raw.decode()).body
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id == name for t in n.targets))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sha',required=True)
    parser.add_argument('--final-evidence-url',required=True)
    args = parser.parse_args()
    assert len(args.sha) == 40 and args.sha != OLD, 'Final execution requires new post-font-fix SHA'
    target = HERE/'fixtures/candidate-binding.json'
    assert not target.exists(), 'Do not overwrite final external pins'
    assert git('rev-parse',args.sha).decode().strip() == args.sha
    files,raws = {},{}
    for name in ('__init__.py','common.py','draft.py','editorial.py','renderer.py'):
        path = 'vrae/reporting/'+name
        raw = git('show',args.sha+':'+path)
        files[name] = dict(git_blob=git('rev-parse',args.sha+':'+path).decode().strip(),
            sha256=hashlib.sha256(raw).hexdigest())
        raws[name] = raw
    reporting_version = constant(raws['common.py'],'VERSION')
    renderer_version = constant(raws['renderer.py'],'RENDERER_VERSION')
    original = json.loads((ROOT/'tests/reporting/fixtures/ra3c_codex1_inputs.json').read_text(encoding='utf-8'))
    records = {}
    for scenario in original['scenarios']:
        records[scenario] = {}
        for version in (1,2):
            metadata = dict(report_id='codex1-v2-'+scenario,version=version,
                created_at=original['report_time'],created_by='codex1-v2-offline-operator',
                mode='SYNTHETIC_PRIVATE_PREVIEW',finding_selection=None)
            encoded = json.dumps(metadata,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
            records[scenario][str(version)] = dict(metadata=metadata,pins=dict(
                expected_metadata_sha256=hashlib.sha256(encoded).hexdigest(),
                expected_reporting_version=reporting_version,expected_renderer_version=renderer_version))
    result = dict(version='OWNER_ADJUDICATED_RA3C_QA_V2',authority='PR48 issuecomment-6815825564',
        candidate_sha=args.sha,final_evidence_url=args.final_evidence_url,reporting_files=files,
        request_count=28,requests=records,producer_outputs_used=False)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('New final SHA externally bound:',args.sha,reporting_version,renderer_version)


if __name__ == '__main__':
    main()

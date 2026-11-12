"""Preserve exact candidate-produced HTML for supplemental local observation.

This is not our independent frozen input and must never count as its acceptance.
"""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SHA = '6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2'


def read(path):
    return subprocess.check_output(['git','show',SHA+':'+path],cwd=ROOT)


def main():
    output = HERE/'ui-supplement'
    assert not output.exists(), 'Preserve original supplemental captures'
    output.mkdir()
    records = {}
    for name in ('contact-404','contact-200'):
        prefix = 'docs/03-engineering/ra3c-offline/preview/'+name
        document = json.loads(read(prefix+'.draft.json'))
        def digest(value):
            return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
                separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()
        assert document['draft_ref'] == 'rd-'+digest({k:v for k,v in document.items() if k != 'draft_ref'})
        assert document['editorial_content_sha256'] == digest({k:v for k,v in document.items()
            if k not in ('draft_ref','html_sha256','editorial_content_sha256')})
        html = read(prefix+'.html')
        provenance = 'exact_candidate_git_blob'
        if hashlib.sha256(html).hexdigest() != document['html_sha256']:
            archive = zipfile.ZipFile(io.BytesIO(read('docs/03-engineering/ra3c-offline/current-artifacts-raw.zip')))
            matches = [n for n in archive.namelist() if n.endswith('/'+name+'.html') or n == name+'.html']
            assert len(matches) == 1, 'Ambiguous original HTML bytes'
            html = archive.read(matches[0])
            provenance = 'exact_candidate_original_bytes_archive:'+matches[0]
        assert hashlib.sha256(html).hexdigest() == document['html_sha256']
        (output/(name+'.html')).write_bytes(html)
        (output/(name+'.draft.json')).write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        records[name] = dict(html_sha256=document['html_sha256'],draft_ref=document['draft_ref'],
            issue_count=len(document['issues']),provenance=provenance)
    meta = dict(kind='SUPPLEMENTAL_RENDER_OF_CANDIDATE_ARTIFACT_NOT_FROZEN_INPUT_ACCEPTANCE',
        candidate_sha=SHA,independent_business_verdict='NOT_EVALUATED',
        frozen_64_case_visual_verdict='VISUAL_NOT_VERIFIED',artifacts=records)
    (output/'source.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    print('Exact candidate HTML preserved for supplemental rendering only:',list(records))


if __name__ == '__main__':
    main()

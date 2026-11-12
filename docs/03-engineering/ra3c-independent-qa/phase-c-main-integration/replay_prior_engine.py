"""Exact old Git engine replay in own disposable workspace, not Codex2's tree."""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PRIOR = '6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag',required=True,choices=('py311','py313'))
    args = parser.parse_args()
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    out = HERE/'runs'/head/args.tag/'prior-engine'
    assert not out.exists()
    out.mkdir(parents=True)
    # Reading exact committed Git objects does not alter any existing worktree.
    included = ('contracts','industry-packs','vrae','tests','scripts')
    raw = subprocess.check_output(['git','-c','core.autocrlf=false','-c','core.eol=lf',
        'archive','--format=zip',PRIOR,'--',*included],cwd=ROOT)
    snapshot = Path(tempfile.mkdtemp(prefix='vrae-codex1-prior-engine-'))
    entries = {}
    expected = {s.split('\t',1)[1]:s.split('\t',1)[0].split()[2] for s in
        subprocess.check_output(['git','ls-tree','-r',PRIOR,'--',*included],cwd=ROOT,text=True).splitlines()}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for item in z.infolist():
            if item.is_dir():
                continue
            p = snapshot/item.filename
            assert p.resolve().is_relative_to(snapshot)
            content = z.read(item)
            blob = hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
            assert blob == expected[item.filename]
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(content)
            entries[item.filename] = blob
    assert entries == expected
    env = dict(os.environ,PYTHONPATH=str(snapshot),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
    prior_out = snapshot/'docs/03-engineering/ra3c-offline/qa-original-engine-replay'
    argv = [sys.executable,'scripts/verify_ra3c.py','--output',str(prior_out)]
    r = subprocess.run(argv,cwd=snapshot,env=env,capture_output=True)
    (out/'stdout.log').write_bytes(r.stdout+r.stderr)
    assert r.returncode == 0
    result = json.loads((prior_out/'replay-summary.json').read_text(encoding='utf-8'))
    assert len(result['cases']) == 8
    for p in prior_out.iterdir():
        assert p.is_file()
        (out/p.name).write_bytes(p.read_bytes())
    sys.path.insert(0,str(ROOT))
    from vrae.evidence import EvidencePack
    from vrae.findings import FindingPackage
    from vrae.reporting import ReportError, build_draft
    old = json.loads((snapshot/'tests/reporting/fixtures/sources.json').read_text(encoding='utf-8'))['404']
    held = json.loads((snapshot/'tests/reporting/fixtures/caller-pins.json').read_text(encoding='utf-8'))['404']
    pins = held['pins']
    pack = EvidencePack.load(old['pack'],{k:base64.b64decode(v) for k,v in old['objects_base64'].items()},expected_ref=pins['expected_pack_ref'])
    package = FindingPackage.load(old['package'],pack,**{k:pins[k] for k in (
        'expected_pack_ref','expected_execution_ref','expected_package_ref','expected_builder_version','expected_evaluator_version')})
    try:
        build_draft(pack,package,old['guard_inputs'],old['metadata'],**pins)
    except ReportError as rejected:
        assert str(rejected) == 'REPORT_PIN_VERSION'
        refusal = str(rejected)
    else:
        raise AssertionError('Current renderer accepted stale old pins')
    (out/'results.json').write_text(json.dumps(dict(qa_head=head,python=sys.version,prior_commit=PRIOR,
        snapshot=str(snapshot),prior_renderer='ra3c-html-1.0.1',all_original_blob_bytes_verified=entries,
        original_command=argv,actual_exit=r.returncode,prior_cases=result['cases'],
        current_renderer_stale_pin_rejection=refusal,foreign_worktree_touched=False),indent=2)+'\n',encoding='utf-8')
    print(args.tag,'exact old engine:8 actual sealed replays passed; current engine rejected old pins',flush=True)


if __name__ == '__main__':
    main()

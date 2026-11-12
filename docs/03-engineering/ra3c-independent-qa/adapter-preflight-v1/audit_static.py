"""Inspect exact Git objects with AST only; no candidate import/build/test/browser."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
BASE = '2429be6dc5d7dcb48221ab179f063b93ce4b1956'
FREEZE = 'fa645b58549dfd21a6b80656d403f672b790acd8'
CANDIDATE = '6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2'


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)


def tree(ref):
    return {line.split('\t',1)[1]:line.split('\t',1)[0].split()[2]
            for line in git('ls-tree','-r',ref).decode().splitlines()}


def read(ref,path):
    return git('show',ref+':'+path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out',required=True)
    args = parser.parse_args()
    out = Path(args.out)
    assert out.parent.resolve() == HERE and not out.exists(), 'Preserve versioned evidence'
    base,frozen,current = tree(BASE),tree(FREEZE),tree('HEAD')
    assert len(base) == 1400 and all(current[p] == b for p,b in base.items())
    added = {p:b for p,b in frozen.items() if p not in base}
    assert len(added) == 11 and all(current[p] == b for p,b in added.items())
    summary = dict(kind='READ_ONLY_STATIC_INTERFACE_PREFLIGHT_NOT_PHASE_B',
        provisional_sha=CANDIDATE,qa_head_before_preflight=git('rev-parse','HEAD').decode().strip(),
        python=sys.version,candidate_imported=False,candidate_business_cases_executed=0,
        candidate_build_load_render_calls=0,independent_visual_pass=False,
        mapping_state='QA_MAPPING_NOT_BOUND',accepted_blobs_unchanged=1400,
        original_freeze_added_blobs_unchanged=added,files={},public_api={},observations={})
    sources = {}
    for name in ('__init__','common','draft','editorial','renderer'):
        path = 'vrae/reporting/'+name+'.py'
        raw = read(CANDIDATE,path)
        sources[name] = ast.parse(raw.decode('utf-8'))
        summary['files'][path] = dict(git_blob=git('rev-parse',CANDIDATE+':'+path).decode().strip(),
            sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
    for node in sources['draft'].body:
        if isinstance(node,ast.FunctionDef) and node.name in ('build_draft','render'):
            summary['public_api'][node.name] = dict(line=node.lineno,args=ast.unparse(node.args))
        if isinstance(node,ast.ClassDef) and node.name == 'ReportDraft':
            summary['public_api']['ReportDraft'] = {child.name:dict(line=child.lineno,args=ast.unparse(child.args))
                for child in node.body if isinstance(child,ast.FunctionDef)}
    def assignments(module):
        return {t.id:n.value for n in sources[module].body if isinstance(n,ast.Assign)
                for t in n.targets if isinstance(t,ast.Name)}
    draft,editorial = assignments('draft'),assignments('editorial')
    summary['observations']['source_pin_keys'] = sorted(ast.literal_eval(draft['SOURCE_PIN_KEYS']))
    summary['observations']['metadata_keys'] = sorted(ast.literal_eval(draft['META_KEYS']))
    summary['observations']['extra_pin_keys'] = sorted(ast.literal_eval(draft['PIN_KEYS'].right))
    summary['observations']['versions'] = {
        'reporting':ast.literal_eval(assignments('common')['VERSION']),
        'renderer':ast.literal_eval(assignments('renderer')['RENDERER_VERSION']),
        'editorial':ast.literal_eval(editorial['EDITORIAL_VERSION'])}
    native_proposals = {}
    for key,value in zip(editorial['PROPOSALS'].keys,editorial['PROPOSALS'].values):
        kind,text = value.elts
        native_proposals[ast.literal_eval(key)] = [ast.literal_eval(kind),ast.literal_eval(editorial[text.id])]
    summary['observations']['candidate_required_proposals'] = native_proposals
    raw_test = read(FREEZE,'tests/reporting/test_ra3c_independent_acceptance.py')
    frozen_tree = ast.parse(raw_test.decode())
    statements = next(n.value for n in ast.walk(frozen_tree) if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id == 'statements' for t in n.targets))
    qa_proposals = [ast.literal_eval(n) for n in statements.elts[1:]]
    summary['observations']['frozen_qa_proposals'] = qa_proposals
    summary['observations']['unmatched_frozen_proposals'] = [s for s in qa_proposals
        if tuple(s[1:]) not in {tuple(v) for v in native_proposals.values()}]
    assert len(summary['observations']['unmatched_frozen_proposals']) == 4
    for path in (HERE/'adapter_draft.py',HERE/'audit_static.py'):
        compile(path.read_text(encoding='utf-8'),str(path),'exec')
    out.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('STATIC PREFLIGHT ONLY:',CANDIDATE,'; 1400 baseline + 11 frozen additions unchanged; no candidate execution')


if __name__ == '__main__':
    main()

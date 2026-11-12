"""Whole-tree blob/mode preservation and exact real-image payload equivalence."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MAIN = 'a1321dac611ac2a38dca3b4785d71b0256d92136'
PRIOR = '48cd0052c0edfe09c0bc00791ecdd8e5f29888c2'
FROZEN = '00655091ac06ede0a26233feb6ff75da9fe642bb'
PREFIX = 'docs/03-engineering/ra3c-independent-qa/'
EXCEPTIONS = ['.dockerignore','infra/ra1a/Dockerfile','pyproject.toml']


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)


def tree(ref):
    return {s.split('\t',1)[1]:s.split('\t',1)[0] for s in git('ls-tree','-r',ref).decode().splitlines()}


def normalized(path):
    raw = path.read_bytes()
    return raw if path.suffix == '.png' else raw.replace(b'\r\n',b'\n')


def main():
    head = git('rev-parse','HEAD').decode().strip()
    assert not git('diff','HEAD','--name-only').strip()
    current,base,prior,frozen = (tree(x) for x in (head,MAIN,PRIOR,FROZEN))
    assert [p for p,v in base.items() if current.get(p) != v] == EXCEPTIONS
    assert [p for p,v in prior.items() if current.get(p) != v] == EXCEPTIONS
    frozen_v2 = {p:v for p,v in frozen.items() if p.startswith(PREFIX+'owner-adjudicated-v2/')}
    assert len(frozen_v2) == 23 and all(current[p] == v for p,v in frozen_v2.items())
    old = {p:v for p,v in tree('61b9173a32789185bd7fcaf750adb6118ec4bc43').items() if p not in EXCEPTIONS}
    assert all(current[p] == v for p,v in old.items())
    v1 = 'tests/reporting/test_ra3c_independent_acceptance.py'
    assert current[v1].split()[2] == '92ab4b2ef743abc0388866a2054952e56ba14a41'
    v2 = PREFIX+'owner-adjudicated-v2/test_acceptance_v2.py'
    assert current[v2].split()[2] == '43992a9084ee5f2c6bbd6f6b051a986da5c9a20c'
    for p in current:
        if p not in base:
            assert p.startswith(PREFIX) or p in (v1,'tests/reporting/test_ra3c_owner_adjudicated_v2.py',
                'tests/reporting/fixtures/ra3c_codex1_cases.json','tests/reporting/fixtures/ra3c_codex1_inputs.json'),p
    profile = json.loads((HERE/'external-inputs-minimal.json').read_text(encoding='utf-8'))
    checked = {}
    for p,entry in profile['files'].items():
        raw = normalized(ROOT/p)
        assert hashlib.sha256(raw).hexdigest() == entry['sha256'],p
        checked[p] = entry['sha256']
    context = Path('D:/Projects/VRAE/.venv/ra3c-phasec-minimal-lab')
    inputs = [p for p in current if p.startswith(('vrae/','tests/','contracts/','industry-packs/','scripts/'))]
    inputs += ['pyproject.toml','requirements-ra1a.lock','infra/ra1a/Dockerfile','infra/ra1a/entrypoint.sh','.dockerignore']
    inputs += [p for p in profile['files'] if p.startswith('docs/')]
    inputs += [PREFIX+'phase-c-main-integration/'+p for p in ('collection_contract_minimal.py','external-inputs-minimal.json')]
    image_equivalence = {}
    for p in sorted(set(inputs)):
        assert normalized(ROOT/p) == normalized(context/p), 'FINAL_SOURCE_DIFFERS_FROM_REAL_IMAGE:'+p
        image_equivalence[p] = hashlib.sha256(normalized(ROOT/p)).hexdigest()
    out = HERE/'source-audits'/head
    assert not out.exists()
    out.mkdir(parents=True)
    (out/'accepted-main-exact-diff.patch').write_bytes(git('diff',MAIN,head,'--',*EXCEPTIONS))
    data = dict(qa_source_head=head,latest_accepted_main=MAIN,
        accepted_main_total=len(base),accepted_main_blob_modes_preserved=len(base)-3,
        owner_authorized_existing_file_exceptions=EXCEPTIONS,exceptions_authority='Owner6818714132 +6819258786',
        prior_qa_blob_modes_preserved=len(prior)-3,prior_history_preserved_except_owner_config_paths=len(old),
        original_v1_blob=current[v1],frozen_v2_blob=current[v2],frozen_initial_v2_blobs_unchanged=23,
        fixed_required_input_hashes=checked,image_tested_context=str(context),
        all_effective_image_inputs_equal_premerge_real_test=True,image_input_hashes=image_equivalence,
        no_production_schema_workflow_entrypoint_dependency_or_other_existing_test_change=True)
    (out/'SOURCE_PROOF.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in data.items() if k not in ('image_input_hashes','fixed_required_input_hashes')},ensure_ascii=False))


if __name__ == '__main__':
    main()

"""Record local evidence after both native runs; replay the saved synthetic pack."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tests.s2_contract.test_p1_static import fixture, evaluate  # noqa: E402
from tests.s2_contract.p0_cases import scope  # noqa: E402
from vrae.evidence import EvidencePack  # noqa: E402
from vrae.rules.s2 import verify_s2_projection, STATIC_PROJECTION_VERSION  # noqa: E402

HERE = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def results(path):
    tree = ET.parse(path)
    suites = list(tree.iter('testsuite'))
    return {**{key: sum(int(s.get(key, 0)) for s in suites)
               for key in ('tests', 'failures', 'errors', 'skipped')},
            'raw_junit_sha256': digest(path),
            'failed_ids': [c.get('classname') + '::' + c.get('name')
                           for c in tree.iter('testcase')
                           if c.find('failure') is not None or c.find('error') is not None]}


if not (HERE / 'example.json').exists():
    pack = fixture()
    write(HERE / 'example-pack.json', {'document': pack.document,
        'objects_base64': {key: base64.b64encode(value).decode()
                           for key, value in pack.objects.items()}})
    write(HERE / 'example.json', evaluate(pack))

archive = json.loads((HERE / 'example-pack.json').read_text(encoding='utf-8'))
example = json.loads((HERE / 'example.json').read_text(encoding='utf-8'))
pack = EvidencePack.load(archive['document'],
    {key: base64.b64decode(value, validate=True) for key, value in archive['objects_base64'].items()},
    expected_ref=example['pack_ref'])
verify_s2_projection(example, pack, expected_pack_ref=pack.ref, trusted_scope=scope(pack),
    expected_projection_ref=example['projection_ref'], expected_projection_version=STATIC_PROJECTION_VERSION)

native = {v: results(HERE / f'runtime/native-{v}.xml') for v in ('311', '313')}
full = {v: results(HERE / f'runtime/full-{v}.xml') for v in ('311', '313')}
portable = {v: results(HERE / f'runtime/portable-native-{v}.xml') for v in ('311', '313')}
assert all(r['failures'] == r['errors'] == 0 for r in [*native.values(), *full.values()])
assert all(r['failures'] == r['errors'] == 0 for r in portable.values())
paths = ('vrae/rules/s2/__init__.py', 'vrae/rules/s2/contract.py', 'vrae/rules/s2/static.py',
         'tests/s2_contract/test_p1_static.py', '.github/workflows/s2-rule-contract.yml')
write(HERE / 'receipt.json', {
    'base': 'a5b8c30ccefb656c266d75e66f9f20ceb7df1080',
    'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
    'phase': 'C1_P1_BATCH1_THREE_BOUNDED_STATIC_SUBSETS_NOT_S2_EXIT',
    'projection_version': STATIC_PROJECTION_VERSION,
    'native': native, 'full': full,
    'local_full_head': '4c72b03554d34cb69060e1d31c4031cbb8903489',
    'test_portability_followup_native': portable,
    'test_portability_scope': 'TEST_SETUP_ONLY_NO_PRODUCTION_SOURCE_CHANGE; FINAL_HEAD_FULL_CI_ON_PR',
    'initial_rule_red': results(HERE / 'runtime/initial-red-rules-311.xml'),
    'initial_environment_red': results(HERE / 'runtime/initial-red-311.xml'),
    'source_lf_sha256': {p: hashlib.sha256((ROOT / p).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                         for p in paths},
    'frozen_worktree_blobs': {p: subprocess.check_output(['git', 'hash-object', p], cwd=ROOT).decode().strip()
        for p in ('vrae/rules/execution.py', 'vrae/evidence/pack.py')},
    'raw_runtime_sha256': {p.name: digest(p) for p in sorted((HERE / 'runtime').iterdir()) if p.is_file()},
    'example_sha256': digest(HERE / 'example.json'),
    'saved_pack_sha256': digest(HERE / 'example-pack.json'),
    'example_replay': 'PASS_FROM_SAVED_PACK_AND_RETAINED_ORIGINAL_BYTES',
    'model_calls': 0, 'real_third_party_sites': 0, 'production_outbound': 0,
    'native_enabled_rules': 6, 'new_candidate_rule_subsets': 3,
    'remaining_C1': ['INFO-02', 'TRUST-02', 'TRUST-03', 'IndustryPack version extension'],
    'human_gold': '0/26_NO_PRECISION_CLAIM',
    'ci': 'PENDING_FINAL_DRAFT_HEAD_NATURAL_CI_SEE_PR_CHECKS',
    'accepted_main_check_runs': 'NO_CHECK_RUNS_ON_MERGE_SHA; LOCAL_FULL_RUNS_USE_THIS_EXACT_BASE',
})
print('Saved synthetic pack replay PASS; local dual-Python receipt written.')

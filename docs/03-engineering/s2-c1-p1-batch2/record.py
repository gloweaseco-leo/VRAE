"""Persist synthetic source archives once, independently replay, record real XML."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tests.s2_contract.batch2_fixtures import fixture, identity  # noqa: E402
from tests.s2_contract.p1_industrial_cases import evaluate, scope, pins, rows  # noqa: E402
from vrae.evidence import EvidencePack  # noqa: E402
from vrae.rules.s2 import verify_s2_projection  # noqa: E402
from integration.beta_disc_report.inventory import verify_inventory  # noqa: E402

HERE = Path(__file__).resolve().parent
BASE = 'cb86cdb1b57962aa89fa2ef4465131219c8c45e9'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, factory, profile='industrial'):
    if not (HERE / (name + '.json')).exists():
        pack = factory()
        out = evaluate(pack, profile)
        write(HERE / (name + '-pack.json'), {
            'held_pack_ref': pack.ref, 'held_projection_ref': out['projection_ref'],
            'held_scope': scope(pack), 'profile_id': profile,
            'document': pack.document,
            'objects_base64': {key: base64.b64encode(value).decode() for key, value in pack.objects.items()}})
        write(HERE / (name + '.json'), out)
    archive = json.loads((HERE / (name + '-pack.json')).read_text(encoding='utf-8'))
    out = json.loads((HERE / (name + '.json')).read_text(encoding='utf-8'))
    pack = EvidencePack.load(archive['document'], {key: base64.b64decode(value, validate=True)
        for key, value in archive['objects_base64'].items()}, expected_ref=archive['held_pack_ref'])
    verify_s2_projection(out, pack, expected_pack_ref=archive['held_pack_ref'], trusted_scope=archive['held_scope'],
        expected_projection_ref=archive['held_projection_ref'], expected_projection_version='s2-projection-1.2.0',
        industry_pins=pins(pack, profile))
    return out


baseline = save('example', fixture)
conflict = save('conflict-example', lambda: fixture(overrides={'/contact': identity(address='20 Other Demo Road')}))
excluded = save('applicability-example', fixture, 'pump-only')
info = rows(baseline, 'INFO-02', 'P40')[0]
proof = rows(baseline, 'TRUST-02', 'P40')[0]
conflict_row = rows(conflict, 'TRUST-03')[0]
not_applicable = rows(excluded, 'INFO-02', 'V25')[0]
buyer = f'''# 合成工业采购资料复核（候选）

P40 参数资料：{info['observation']['result']}。同一来源表声明了配置要求的参数、单位、
数据版本 {info['details']['data_revision']} 和工况说明。这里只确认保存来源中的展示，
工程适配性仍为 UNKNOWN；没有买家工况不构成网站故障。

P40 证明材料展示：{proof['observation']['result']}。声明对象、issuer、引用编号和日期可定位。
日期与采集日关系为 {proof['details']['date_relation']}，需要人工复核。
证书真实、有效性、合规性和供应商资质均未核验。

跨页主体/联系复核：改地址的反事实输出 {conflict_row['observation']['result']}，
差异字段为 {', '.join(conflict_row['details']['literal_conflicts'])}，两处原始字节引用均保存。
这里只比较相同“自报标识”下的字符串，不合并或认证法定主体；同名而标识不明时保持 UNKNOWN。

适用性：独立选择并固定 pump-only 配置后，V25 的参数检查为
{not_applicable['observation']['result']}，配置出处为
`{not_applicable['details']['configuration_locator']}`。
普通网页声明不能自行改变这一配置。

这些结果均为 s2p 只读候选，未进入旧 FindingPackage/Report/Guard 事实边界。
P40/V25 为合成示例；其它型号仅在唯一自报型号、已配置家族、版本/工况和字段都可定位时受限检查。
无真实第三方网站、模型调用、生产外发或人工 Gold；真实 Gold 仍为 0/26。
'''
(HERE / 'BUYER.md').write_text(buyer, encoding='utf-8')
print('Three saved source archives replay PASS; buyer page generated from actual output.')
if '--examples-only' in sys.argv:
    raise SystemExit(0)


def result(path):
    tree = ET.parse(path)
    suites = list(tree.iter('testsuite'))
    return {**{key: sum(int(s.get(key, 0)) for s in suites)
               for key in ('tests', 'failures', 'errors', 'skipped')},
        'raw_junit_sha256': digest(path),
        'failed_ids': [c.get('classname') + '::' + c.get('name') for c in tree.iter('testcase')
                       if c.find('failure') is not None or c.find('error') is not None]}


native = {v: result(HERE / f'runtime/native-{v}.xml') for v in ('311', '313')}
full = {v: result(HERE / f'runtime/full-{v}.xml') for v in ('311', '313')}
proofs = {}
for version in ('311', '313'):
    _, proof = verify_inventory(list(ET.parse(HERE / f'runtime/full-{version}.xml').iter('testcase')))
    proofs[version] = proof
assert all(r['failures'] == r['errors'] == 0 for r in [*native.values(), *full.values()])
modified_sources = ('vrae/rules/s2/contract.py', 'vrae/rules/s2/__init__.py', 'vrae/rules/s2/industrial.py',
    'vrae/industry/l2_v1/pack.py', 'vrae/industry/l2_v1/__init__.py', 'vrae/industry/l2_v1/s2_sources.py',
    'industry-packs/l2-industrial-v1/s2-1.1.0.json', 'tests/s2_contract/p1_industrial_cases.py',
    'tests/s2_contract/batch2_fixtures.py', '.github/workflows/s2-rule-contract.yml')
write(HERE / 'receipt.json', {
    'authority': 'OWNER_ISSUE118_COMMENT_6965467885', 'base': BASE,
    'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
    'phase': 'C1_P1_BATCH2_THREE_CONFIGURED_READ_ONLY_CANDIDATE_SUBSETS_NOT_S2_EXIT',
    'projection_version': 's2-projection-1.2.0', 'industry_version': '1.1.0',
    'rule_version': 's2-industrial-context-1.0.0', 'source_version': 's2-industrial-source-1.0.0',
    'native': native, 'full': full, 'unchanged_exact_original_inventory': proofs,
    'initial_red': result(HERE / 'runtime/initial-red-311.xml'),
    'source_lf_sha256': {p: hashlib.sha256((ROOT / p).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                         for p in modified_sources},
    'frozen_worktree_blobs': {p: subprocess.check_output(['git', 'hash-object', p], cwd=ROOT).decode().strip()
        for p in ('vrae/rules/execution.py', 'vrae/evidence/pack.py')},
    'raw_runtime_sha256': {p.name: digest(p) for p in sorted((HERE / 'runtime').iterdir()) if p.is_file()},
    'saved_example_sha256': {p.name: digest(p) for p in HERE.glob('*example*.json')},
    'example_replay': 'THREE_SAVED_PACKS_PASS_ORIGINAL_BYTES_AND_HELD_REFS',
    'native_legacy_enabled': 6, 'industry_original_rules': 6,
    'new_rules_are_candidate_only': ['INFO-02', 'TRUST-02', 'TRUST-03'],
    'model_calls': 0, 'real_third_party_sites': 0, 'production_outbound': 0,
    'human_gold': '0/26_NO_QUALITY_CLAIM',
    'ci': 'PRE_PR_RECORD_FINAL_HEAD_NATURAL_CI_RESULTS_ON_DRAFT_PR',
})
print('Actual dual-Python JUnit and unchanged 2564 inventory verified; receipt written.')

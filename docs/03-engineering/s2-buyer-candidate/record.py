"""Offline server-fixture -> accepted S2 -> buyer candidate; no production entry."""
import base64
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tests.s2_contract.batch2_fixtures import fixture, DIRECTORY  # noqa: E402
from tests.s2_contract.p1_industrial_cases import evaluate  # noqa: E402
from tests.s2_contract.buyer_candidate_cases import selection  # noqa: E402
from vrae.evidence import EvidencePack  # noqa: E402
from vrae.industry.l2_v1.pack import IndustryPins  # noqa: E402
from vrae.rules.s2 import evaluate_s2  # noqa: E402
from vrae.reporting.s2_candidate import (  # noqa: E402
    BuyerCandidatePins, ObservationPin, build_candidate, verify_candidate, render_markdown,
)
from integration.beta_disc_report.inventory import verify_inventory  # noqa: E402

HERE = Path(__file__).resolve().parent
BASE = '95ed55321775223e95cf0a1585220951cc692648'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode_held(data):
    values = dict(data)
    values['industry_pins'] = IndustryPins(**values['industry_pins'])
    values['observations'] = tuple(ObservationPin(**{**p, 'snapshot_refs': tuple(p['snapshot_refs'])})
                                   for p in values['observations'])
    return BuyerCandidatePins(**values)


def scenario(name, factory, *, profile='industrial', model='P40', blocked=False):
    server_path = HERE / ('server-' + name + '.json')
    candidate_path = HERE / ('candidate-' + name + '.json')
    if not server_path.exists():
        pack = factory()
        projection = evaluate(pack, profile)
        held = selection(pack, projection, model=model, blocked=blocked)
        candidate = build_candidate(pack, projection, held=held)
        write(server_path, {'held': asdict(held), 'expected_candidate_ref': candidate['candidate_ref'],
            'pack_document': pack.document,
            'objects_base64': {k: base64.b64encode(v).decode() for k, v in pack.objects.items()}})
        write(candidate_path, candidate)
    server = json.loads(server_path.read_text(encoding='utf-8'))
    held = decode_held(server['held'])
    pack = EvidencePack.load(server['pack_document'],
        {k: base64.b64decode(v, validate=True) for k, v in server['objects_base64'].items()},
        expected_ref=held.pack_ref)
    projection = evaluate_s2(pack, expected_pack_ref=held.pack_ref,
        trusted_scope={k: getattr(held, k) for k in ('tenant_id', 'run_id', 'policy_id', 'policy_version')},
        projection_version=held.projection_version, industry_pins=held.industry_pins)
    candidate = json.loads(candidate_path.read_text(encoding='utf-8'))
    verify_candidate(candidate, pack, projection, held=held, expected_candidate_ref=server['expected_candidate_ref'])
    markdown = render_markdown(candidate, pack, projection, held=held,
                               expected_candidate_ref=server['expected_candidate_ref'])
    (HERE / ('buyer-' + name + '.md')).write_text(markdown, encoding='utf-8')
    return candidate


reports = {
    'complete': scenario('complete', fixture),
    'unknown': scenario('unknown', lambda: fixture(overrides={
        '/products/p40': (DIRECTORY / 'pump.html').read_bytes()})),
    'not-applicable': scenario('not-applicable', fixture, profile='pump-only', model='V25'),
    'blocked': scenario('blocked', lambda: fixture(statuses={'/products/p40': 403}), blocked=True),
}
appendix = ['# 配套来源明细（内部审阅）', '', '以下内容是保存来源的原文，不代表其中声明真实或已获正式批准。', '']
for name, candidate in reports.items():
    appendix += ['## ' + name, '']
    for card in candidate['cards']:
        appendix += ['### ' + card['rule_id'] + ' / ' + card['result'], '',
                     '观察候选：' + card['observation_id'], '']
        if card['configuration_locator']:
            appendix += ['配置定位：' + card['configuration_locator'], '行业引用：' + candidate['industry_ref'], '']
        for page in card['source_pages']:
            appendix += ['保存页：' + page['url'] + '；HTTP ' + str(page['http_status']), '']
        for c in card['source_excerpts']:
            appendix += ['原始字节 ' + str(c['byte_start']) + '–' + str(c['byte_end']),
                '引用：' + c['evidence_ref'], '来源：' + c['source_ref'],
                '资料包定位：' + c['locator'], '内容摘要：' + c['content_sha256'], '',
                *['    ' + line for line in c['quote'].splitlines()], '']
        if not card['source_excerpts']:
            appendix += ['没有材料内容字节可引用；仅保留配置或响应记录。', '']
(HERE / 'SOURCES.md').write_text('\n'.join(appendix), encoding='utf-8')
print('Four saved server fixtures independently replay; buyer reports and source details rendered.')
if '--examples-only' in sys.argv:
    raise SystemExit(0)


def result(path):
    tree = ET.parse(path)
    suites = list(tree.iter('testsuite'))
    return {**{k: sum(int(s.get(k, 0)) for s in suites)
               for k in ('tests', 'errors', 'failures', 'skipped')}, 'raw_junit_sha256': sha(path),
        'failed_ids': [c.get('classname') + '::' + c.get('name') for c in tree.iter('testcase')
                       if c.find('failure') is not None or c.find('error') is not None]}


native = {v: result(HERE / f'runtime/native-{v}.xml') for v in ('311', '313')}
full = {v: result(HERE / f'runtime/full-{v}.xml') for v in ('311', '313')}
proofs = {}
for version in ('311', '313'):
    _, proof = verify_inventory(list(ET.parse(HERE / f'runtime/full-{version}.xml').iter('testcase')))
    proofs[version] = proof
assert all(r['errors'] == r['failures'] == 0 for r in [*native.values(), *full.values()])
paths = ('vrae/reporting/s2_candidate.py', 'tests/s2_contract/buyer_candidate_cases.py',
         '.github/workflows/s2-rule-contract.yml')
write(HERE / 'receipt.json', {
    'authority': 'OWNER_ISSUE118_COMMENT_6966540568', 'base': BASE,
    'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
    'phase': 'READ_ONLY_BUYER_TASK_CANDIDATE_NOT_NATIVE_FACT_PROMOTION',
    'reporting_version': 's2-buyer-candidate-1.0.0', 'source_projection_version': 's2-projection-1.2.0',
    'industry_version': '1.1.0', 'native': native, 'full': full, 'original_2564_inventory': proofs,
    'initial_red': result(HERE / 'runtime/initial-red-311.xml'),
    'source_lf_sha256': {p: hashlib.sha256((ROOT / p).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in paths},
    'frozen_worktree_blobs': {p: subprocess.check_output(['git', 'hash-object', p], cwd=ROOT).decode().strip()
        for p in ('vrae/rules/execution.py', 'vrae/evidence/pack.py')},
    'raw_runtime_sha256': {p.name: sha(p) for p in sorted((HERE / 'runtime').iterdir()) if p.is_file()},
    'saved_dto_and_server_fixture_sha256': {p.name: sha(p) for p in HERE.glob('*.json') if p.name != 'receipt.json'},
    'sample_results': {name: [c['result'] for c in report['cards']] for name, report in reports.items()},
    'model_calls': 0, 'real_external_sites': 0, 'production_outbound': 0,
    'new_rule_engines': 0, 'new_fact_or_review_authorities': 0, 'native_fact_promotion': False,
    'human_gold': '0/26_NO_QUALITY_CLAIM', 'S3_real_AI': 'NOT_AUTHORIZED', 'S4_external_customers': 'NOT_AUTHORIZED',
    'C2_C3_handoff': 'https://github.com/gloweaseco-leo/VRAE/issues/118#issuecomment-6967103221',
    'ci': 'PRE_PR_RECORD_FINAL_HEAD_REAL_CI_ON_DRAFT_PR',
})
print('Actual native/full XML and exact original inventory verified; receipt written.')

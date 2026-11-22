"""Synthetic coverage for the R1–R3 delivery work packages. No live site and no real model."""
import hashlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

from integration.authorized_targets.judgment_v2 import build as judgment_v2
from integration.authorized_targets.presentation import build as present
spec = importlib.util.spec_from_file_location('pilot_replay', Path(__file__).parents[2] / 'scripts/pilot_replay.py')
pilot_replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot_replay)
from vrae.collection.discovery import select_next
from vrae.industry.l2_v1.buyer_stages import (
    customer_projection, diagnostic_attachment, evaluate, info02_result, load, signature_valid)
from vrae.intelligence.pagespeed_adapter import PageSpeedAdapter
from vrae.intelligence.qwen.l2_reasoning import PROMPT, attach, degrade, validate
from vrae.intelligence.qwen.provider import L2_PROMPT
from vrae.intelligence.qwen.session import prompt_version
from vrae.l2.content_units import build as units
from vrae.l2.content_units import project as project_units
from vrae.l2.executive import VERSION, project_v2
from vrae.l2.item_review import (
    approve_hash, decide, gold_candidates, recipient_allowed, revision_invalidates, revoke, weekly_summary)
from vrae.l2.native_business import inventory, restate
from vrae.l2.scoring import import_synthetic_annotations
from vrae.rules.l2_overlay import compare_declarations, record_proof, seo02, tech01
from tests.benchmark.s2_quality import l2_gold_rate

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / 'tests/fixtures/pilot/synthetic-audit.json'


def signed(document):
    copy = deepcopy(document)
    from vrae.industry.l2_v1.buyer_stages import config_sha256
    copy['approval'] = {'signer': 'synthetic-signer', 'signed_at': '2026-11-21T12:00:00Z',
                        'config_sha256': config_sha256(copy)}
    return copy


def product(**flags):
    base = {'visited': True, 'applicable': True, 'fully_parsed': True, 'parameter_region_present': True,
            'parameter_parse_ambiguous': False, 'unparsed_tech_material_link': False,
            'present_fields': [], 'role': 'PRODUCT'}
    base.update(flags)
    return base


def test_unsigned_checklist_cannot_publish_a_gap():
    document = load()
    assert document['approval'] == {'signer': None, 'signed_at': None, 'config_sha256': None}
    result = evaluate(document, [product(present_fields=[])])
    assert all(item['status'] == 'REVIEW_REQUIRED' for item in result['items'])
    blob = json.dumps(result)
    assert 'GAP_WITH_EVIDENCE' not in blob and 'SOURCE_AVAILABLE' not in blob
    assert 'CLARIFY_ROUTE_RECORDED' not in blob
    assert customer_projection(result) is None
    attachment = diagnostic_attachment()
    assert attachment['signed'] is False and attachment['customer_gap_judgments'] is False
    assert 'GAP_WITH_EVIDENCE' not in json.dumps(attachment)


def test_signed_publish_and_forced_counterexamples():
    document = signed(load())
    assert signature_valid(document)
    present = evaluate(document, [product(present_fields=['dimensions', 'abrasive', 'grit', 'bond'])])
    compare = next(item for item in present['items'] if item['item_id'] == 'AW-COMPARE-01')
    assert compare['status'] == 'SOURCE_AVAILABLE'
    gap = evaluate(document, [product()])
    assert next(item for item in gap['items'] if item['item_id'] == 'AW-COMPARE-01')['status'] == 'GAP_WITH_EVIDENCE'
    for flags in ({'unparsed_tech_material_link': True}, {'parameter_parse_ambiguous': True}):
        blocked = json.dumps(evaluate(document, [product(**flags)]))
        assert 'GAP_WITH_EVIDENCE' not in blocked
    clarify = evaluate(document, [product(clarify_route_recorded=False)])
    confirm = next(item for item in clarify['items'] if item['item_id'] == 'AW-CONFIRM-01')
    inquire = next(item for item in clarify['items'] if item['item_id'] == 'AW-INQUIRE-01')
    assert confirm['status'] == 'CLARIFY_ROUTE_UNKNOWN'
    assert inquire['status'] == 'CLARIFY_ROUTE_UNKNOWN'
    routed = evaluate(document, [product(clarify_route_recorded=True)])
    assert next(item for item in routed['items'] if item['site_role'] == 'CLARIFY_CHANNEL')['status'] == 'CLARIFY_ROUTE_RECORDED'
    assert info02_result(evaluate(load(), [product()]))[0] != 'FAIL_WITH_EVIDENCE'
    assert info02_result(gap) == ('FAIL_WITH_EVIDENCE', 'PUBLISH_GROUP_ABSENT')
    assert info02_result(present)[0] == 'PASS'


def test_rule_mappings_do_not_invent_failures():
    assert compare_declarations([
        {'url': 'a', 'name': 'Acme  Industrial'}, {'url': 'b', 'name': 'acme industrial'}])[0] == 'PASS'
    assert compare_declarations([
        {'url': 'a', 'name': 'Acme'}, {'url': 'b', 'name': 'Other'}]) == ('UNKNOWN', 'CONFLICT_REVIEW_REQUIRED')
    assert compare_declarations([{'url': 'a', 'email': 'Buyer@Example.org'}])[0] == 'UNKNOWN'
    assert record_proof('Certificate issued by Example Lab, number: ABC-1, 2020-01-01',
                        expired_before_capture=True)[0] == 'PASS'
    assert record_proof('no statement')[0] == 'UNKNOWN'
    failed = tech01([{'http_status': 404, 'key_page': True}, {'http_status': 200, 'key_page': True}])
    assert failed[0] == 'FAIL_WITH_EVIDENCE'
    assert tech01([{'http_status': 503, 'key_page': True}])[1] == 'TRANSIENT_NOT_PROVEN'
    assert tech01([{'http_status': 403, 'key_page': True, 'access_blocked': True}])[0] == 'ACCESS_BLOCKED'
    assert tech01([{'http_status': 200, 'key_page': True, 'redirect_status': 301}])[0] == 'PASS'
    assert seo02(script_dependent=True)[0] == 'UNKNOWN'
    assert seo02(main_text='Wheel', internal_link=True)[0] == 'PASS'


def test_new_sampling_mode_keeps_the_default_order():
    items = [{'url': 'https://example.org' + path, 'role': role}
             for path, role in [('/', 'HOME'), ('/catalog', 'CATALOG'),
                ('/products', 'CATALOG'), ('/products/item', 'PRODUCT'), ('/contact', 'CONTACT')]]
    attempted, covered, order = set(), set(), []
    for _ in range(4):
        item = select_next(items, attempted, covered)
        order.append(item['role'])
        attempted.add(item['url'])
        covered.add(item['role'])
    assert order == ['HOME', 'CATALOG', 'PRODUCT', 'CONTACT']
    staged = [
        {'url': 'https://example.invalid/', 'role': 'HOME'},
        {'url': 'https://example.invalid/category/resin', 'role': 'CATEGORY'},
        {'url': 'https://example.invalid/category/resin/w1', 'role': 'PRODUCT'},
        {'url': 'https://example.invalid/category/vitrified/w2', 'role': 'PRODUCT'},
        {'url': 'https://example.invalid/contact', 'role': 'CONTACT'},
        {'url': 'https://example.invalid/about', 'role': 'ABOUT'},
        {'url': 'https://example.invalid/applications', 'role': 'APPLICATION'}]
    picked, seen = [], set()
    for _ in range(6):
        item = select_next(staged, seen, set(), sampling='l2-stage-v1')
        picked.append(item['role'])
        seen.add(item['url'])
    assert picked == ['HOME', 'CATEGORY', 'PRODUCT', 'PRODUCT', 'CONTACT', 'ABOUT']
    required, seen = [], set()
    for _ in range(6):
        item = select_next(staged, seen, set(), sampling='l2-stage-v1', application_required=True)
        required.append(item['role'])
        seen.add(item['url'])
    assert required[4] == 'APPLICATION'


def test_pilot_replay_redacts_and_rejects_a_bad_receipt(tmp_path):
    code = pilot_replay.main([str(FIXTURE), '--target-version', 'l2-industrial-1.0.7', '--out', str(tmp_path)])
    assert code == 0
    exported = (tmp_path / 'pilot-replay.json').read_text(encoding='utf-8') + (tmp_path / 'pilot-replay.md').read_text(encoding='utf-8')
    for probe in ('<html', 'buyer@example.org', '+1-555-0100', 'secret-form-value', 'do-not-export'):
        assert probe not in exported
    assert 'Listed diameter' not in exported
    quoted = pilot_replay.main([str(FIXTURE), '--target-version', 'l2-industrial-1.0.7', '--out', str(tmp_path / 'q'),
                                '--include-public-quotes'])
    assert quoted == 0
    public = (tmp_path / 'q' / 'pilot-replay.md').read_text(encoding='utf-8')
    assert 'Listed diameter' in public and 'AUDIT action=INCLUDE_PUBLIC_QUOTES' in public
    assert '<html' not in public and 'buyer@example.org' not in public
    broken = json.loads(FIXTURE.read_text(encoding='utf-8'))
    broken['historical_rules'][0]['result'] = 'FAIL_WITH_EVIDENCE'
    path = tmp_path / 'broken.json'
    path.write_text(json.dumps(broken), encoding='utf-8')
    assert pilot_replay.main([str(path), '--target-version', 'l2-industrial-1.0.7', '--out', str(tmp_path / 'bad')]) == 2


def test_judgment_v2_keeps_confirmed_obstacles_empty_and_v1_copy():
    pending = {'rule_id': 'TECH-01', 'buyer_task': 'SEARCH_TECHNICAL', 'enabled': True, 'evidence_level': 'L-B',
               'observations': [{'observation': {'result': 'FAIL_WITH_EVIDENCE', 'observation_id': 'obs-tech'},
                                 'reason': 'CAPTURED_INTERNAL_LINK_404_OR_410'}]}
    unknown = {'rule_id': 'INFO-02', 'buyer_task': 'UNDERSTAND', 'enabled': True,
               'observations': [{'observation': {'result': 'UNKNOWN', 'observation_id': 'obs-info'},
                                 'reason': 'CHECKLIST_UNSIGNED_REVIEW_REQUIRED'}]}
    tasks = [{'task': name, 'rules': []} for name in ('DISCOVER', 'UNDERSTAND', 'TRUST', 'INQUIRE', 'SEARCH_TECHNICAL')]
    tasks[1]['rules'].append(unknown)
    tasks[4]['rules'].append(pending)
    result = {'deterministic_diagnosis': {'diagnostic_version': 'l2-industrial-1.0.8', 'buyer_tasks': tasks,
              'procurement_review': {'contract': 'vrae.l2-procurement-review.v1'}},
              'claims': [], 'analysis_outcome': 'INSUFFICIENT_EVIDENCE', 'state': 'AI_UNAVAILABLE',
              'page_scope': {'visited_pages': [{'request_role': 'HOME', 'http_status': 200}],
                             'failed_attempt_records': [], 'unvisited_candidates': []}}
    view = present(result)
    judgment = view['judgment']
    assert judgment['contract'] == 'vrae.diagnosis-judgment.v2'
    assert judgment['confirmed_obstacles']['items'] == [] and judgment['confirmed_obstacles']['count'] == 0
    assert judgment['evidenced_pending_review']['items'][0]['result'] == 'FAIL_WITH_EVIDENCE'
    assert judgment['formal_human_review'] is False
    assert view['technical_access']['is_score'] is False and view['technical_access']['mobile_measured'] is False
    assert len(judgment['stages']) == 5
    old = deepcopy(result)
    old['deterministic_diagnosis']['diagnostic_version'] = 'l2-industrial-1.0.7'
    old['deterministic_diagnosis'].pop('procurement_review')
    # 1.0.7 presentation still uses judgment v1 only when groups exist; contract must not become v2.
    assert present({'deterministic_diagnosis': {'diagnostic_version': 'l2-industrial-1.0.7', 'buyer_tasks': tasks,
                    'procurement_review': result['deterministic_diagnosis']['procurement_review']},
                    'claims': [], 'analysis_outcome': 'INSUFFICIENT_EVIDENCE', 'state': 'AI_UNAVAILABLE'})['judgment']['contract'] == 'vrae.diagnosis-judgment.v1'
    assert '建议优先关注' not in json.dumps(judgment_v2(result), ensure_ascii=False)
    assert '可以先这样改' not in json.dumps(judgment_v2(result), ensure_ascii=False)


def test_depth_summary_native_reuse_and_content_units():
    document = {'findings': [{'id': 'f1', 'rule_id': 'TECH-01', 'result': 'FAIL_WITH_EVIDENCE', 'stage': 'SCREENING',
                              'statement': '记录到 404。'}],
                'blueprint': [{'id': 'b1', 'stage': 'SCREENING', 'action': '核对已记录链接', 'candidate': 'STANDARD'}]}
    summary = project_v2(document)
    assert summary['version'] == 'l2-executive-2' and VERSION == 'l2-executive-1'
    assert summary['groups']['D1'] and summary['quantified_loss'] is None and summary['blueprint'][0]['price'] is None
    empty = project_v2({'findings': [], 'blueprint': []})
    assert empty['empty_defect_report_valid'] is True
    counted = inventory(document)
    assert counted['can_extend'] is True and counted['second_report'] is False
    restated = restate(document, {'contract': 'vrae.diagnosis-judgment.v2'})
    assert restated['finding_ids'] == ['f1'] and restated['second_report'] is False
    built = units([{'unit_id': 'u1', 'group': 'D1', 'strength': 'EVIDENCED_PENDING_REVIEW',
                    'text': {'zh': '待审', 'en': 'Pending'}, 'evidence_ids': ['e1']}])
    projected = project_units(built, ['u1'])
    assert projected['units'][0]['presented_as_confirmed'] is False


def test_fake_reasoning_review_gold_and_closed_adapter():
    payload = {'prompt_version': PROMPT, 'context_ref': 's3ctx-demo', 'claims': [
        {'kind': 'CROSS_PAGE_CONFLICT', 'fact': '两页名称不同', 'hypothesis': '可能不是同一主体',
         'counterevidence': '尚未核对商标', 'pending_confirmation': '请供方确认',
         'refs': ['snap-aaaaaaaa', 'snap-bbbbbbbb']},
        {'kind': 'BUYER_QUESTION', 'fact': '没有引用', 'hypothesis': '丢弃', 'counterevidence': '无',
         'pending_confirmation': '无', 'refs': ['snap-cccccccc']}]}
    checked = validate(payload, {'refs': ['snap-aaaaaaaa', 'snap-bbbbbbbb'],
                                 'snapshots': {'snap-aaaaaaaa': 's1', 'snap-bbbbbbbb': 's2'}})
    assert checked['claims'][0]['status'] == 'REVIEW_REQUIRED' and checked['dropped'] == 1
    assert len(checked['claims']) == 1
    with pytest.raises(Exception):
        validate({**payload, 'claims': [{**payload['claims'][0], 'fact': '排名第一'}]},
                 {'refs': ['snap-aaaaaaaa', 'snap-bbbbbbbb'], 'snapshots': {'snap-aaaaaaaa': 's1', 'snap-bbbbbbbb': 's2'}})
    draft = attach({}, checked, artifact_sha256='a' * 64, model_version='protocol-fake')
    assert draft['ai']['real_qwen_on_customer_artifact'] is False
    assert degrade('TIMEOUT')['status'] == 'AI_UNAVAILABLE'
    assert L2_PROMPT == PROMPT

    class Pins:
        expected_evaluator_version = 'ra2b6-1.0.5'
    class Ctx:
        purchase_tasks_bytes = b'null'
        gateway_pins = Pins()
    assert prompt_version(Ctx()) != L2_PROMPT
    Pins.expected_evaluator_version = 'ra2b6-1.0.6'
    assert prompt_version(Ctx()) == L2_PROMPT

    identity = {'actor_id': 'synthetic-reviewer', 'directory_mode': 'CONTROLLED', 'verification_ref': 'TEST_PROTOCOL'}
    receipt = decide([{'id': 'f1', 'action': 'CONFIRM', 'diff_class': 'WORDING', 'elapsed_ms': 5}], identity)
    assert receipt['formal_human_review'] is False
    approve_hash({**receipt, 'content_hash': 'abc', 'synthetic': True}, 'abc')
    with pytest.raises(ValueError):
        approve_hash({**receipt, 'content_hash': 'abc', 'synthetic': True}, 'def')
    assert revision_invalidates('abc', 'def')
    assert recipient_allowed({'subject_ref': 'reader-1', 'status': 'ACTIVE'}, 'reader-1') is True
    assert recipient_allowed({'subject_ref': 'reader-1', 'status': 'ACTIVE'}, 'other') is False
    assert revoke({'status': 'ACTIVE'})['status'] == 'REVOKED'
    assert weekly_summary([])['status'] == 'NOT_EVALUABLE'
    summary = weekly_summary([{'action': 'CONFIRM'}, {'action': 'MODIFY'}])
    assert summary['adoption_rate'] == 0.5 and summary['formal_human_review'] is False
    assert gold_candidates([{'action': 'REJECT', 'diff_class': 'REJECTION_REASON'}])[0]['formal_human_review'] is False
    assert l2_gold_rate([])['status'] == 'NOT_EVALUABLE'
    assert import_synthetic_annotations([{'label': 'UNKNOWN'}])['status'] == 'NOT_EVALUABLE'
    with pytest.raises(RuntimeError):
        PageSpeedAdapter().measure('https://supplier.example/')


def test_hash_stable_for_old_receipt_bytes():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest()
    again = FIXTURE.read_bytes()
    assert raw == again

"""Read-only buyer view over replayed S2 candidates; no native report admission.

The authenticated server retains current task/pack/config/selection pins. This
module checks their consistency and formats existing rule output; it grants no
access, provenance signature, review approval or Finding/Guard authority.
"""
from dataclasses import dataclass
from html import escape
import re

from vrae.evidence import EvidencePack
from vrae.industry.l2_v1.pack import IndustryPins
from vrae.rules.s2 import verify_s2_projection
from .common import detach, digest, display_text, encode

VERSION = 's2-buyer-candidate-1.0.0'
S2_VERSION = 's2-projection-1.2.0'
RULE_VERSION = 's2-industrial-context-1.0.0'
SOURCE_VERSION = 's2-industrial-source-1.0.0'
RULES = ('INFO-02', 'TRUST-02')
SCOPE = ('tenant_id', 'run_id', 'policy_id', 'policy_version')


class BuyerCandidateError(ValueError):
    """Non-reflective failure vocabulary; never disclose source or supplied IDs."""


@dataclass(frozen=True, slots=True)
class ObservationPin:
    observation_id: str
    rule_id: str
    rule_version: str
    source_version: str
    snapshot_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BuyerCandidatePins:
    tenant_id: str
    run_id: str
    policy_id: str
    policy_version: int
    pack_ref: str
    projection_ref: str
    projection_version: str
    industry_pins: IndustryPins
    subject_model: str | None
    subject_snapshot_ref: str
    observations: tuple[ObservationPin, ...]
    reporting_version: str = VERSION


def _fail():
    raise BuyerCandidateError('S2_BUYER_CANDIDATE_INTEGRITY')


def _display(value):
    if isinstance(value, str):
        display_text(value, 131072)
    elif isinstance(value, dict):
        for key, item in value.items():
            _display(key)
            _display(item)
    elif isinstance(value, list):
        for item in value:
            _display(item)


def _card(row):
    rule, result = row['observation']['rule_id'], row['observation']['result']
    details = row['details']
    fields = {}
    if result in ('PASS', 'UNKNOWN'):
        keys = (('data_revision', 'specification_conditions', 'normalized_quantities',
                 'missing_or_ambiguous', 'unsupported_quantities', 'engineering_fit') if rule == 'INFO-02'
                else ('proof_kind', 'date_relation', 'authentication', 'date_limit'))
        fields = {key: details[key] for key in keys if key in details}
    state_text = {
        'PASS': '仅确认下列保存来源中的展示内容及范围内检查，未认证资料真实性或工程适配。',
        'UNKNOWN': '目前来源不足或关联不清，无法给出完整判断；不据此声称网站缺资料或存在故障。',
        'NOT_APPLICABLE': '当前独立固定的配置排除此检查范围；不对产品或网站作否定判断。',
        'ACCESS_BLOCKED': '保存记录显示访问受阻，无法确认该来源的材料内容或记录类型。',
    }
    if result not in state_text:
        _fail()
    hypothesis = ('这些展示内容可能帮助采购方初步比对资料；仍需工程人员确认所需工况、版本与适配。'
                  if rule == 'INFO-02' else
                  '采购方可能仍需取得原始证明并核对声明方、适用对象和日期；当前展示不能证明真伪或合规。')
    if result == 'UNKNOWN':
        hypothesis = '如补齐并澄清未明确的资料和关联，采购方可能更容易继续核对；目前不能据此评价资料质量。'
    elif result == 'ACCESS_BLOCKED':
        hypothesis = '如在已获准范围内取得可读来源，采购方可能才有条件核对材料；当前不能判断其内容质量。'
    elif result == 'NOT_APPLICABLE':
        hypothesis = '若后续采购任务涵盖此范围，可能需要在相应任务配置下另行审阅；本次不据此作质量判断。'
    observation_id = row['observation']['observation_id']
    return {'rule_id': rule, 'observation_id': observation_id,
        'rule_version': row['observation']['rule_version'], 'source_version': row['source_version'],
        'buyer_task': 'UNDERSTAND' if rule == 'INFO-02' else 'TRUST',
        'title': '参数资料与版本' if rule == 'INFO-02' else '证明声明的展示上下文',
        'result': result, 'reason': row['reason'], 'model': row['model'],
        'source_replay': {'status': 'RECOMPUTED_FROM_PINNED_CURRENT_PACK',
            'basis': 'SOURCE_BYTES_AND_RULE_REPLAY' if row['citations'] else 'CONFIGURATION_OR_RESPONSE_METADATA_ONLY',
            'meaning': ('保存来源原始字节及对应静态检查已重放；未认证声明内容的真实性。'
                        if row['citations'] else '本卡仅重算配置或响应记录，没有可引用的材料内容字节。')},
        'observed_fields': fields, 'source_excerpts': row['citations'],
        'source_pages': row['source_pages'],
        'limitation': {'state': result, 'text': state_text[result]},
        'configuration_locator': details.get('configuration_locator'),
        'review_hypothesis': {'kind': 'HYPOTHESIS_REVIEW_REQUIRED', 'text': hypothesis,
                               'basis_observation_ids': [observation_id]},
        'native_fact_admission': 'NONE'}


def build_candidate(pack: EvidencePack, projection: dict, *, held: BuyerCandidatePins) -> dict:
    """Server entry: replay the selected current source before producing review DTO."""
    try:
        if (type(pack) is not EvidencePack or type(held) is not BuyerCandidatePins
                or held.reporting_version != VERSION or held.projection_version != S2_VERSION
                or type(held.industry_pins) is not IndustryPins
                or held.industry_pins.version != '1.1.0'
                or type(held.observations) is not tuple or not 1 <= len(held.observations) <= 2):
            _fail()
        if any(type(getattr(held, key)) is not str for key in
               ('tenant_id', 'run_id', 'policy_id', 'pack_ref', 'projection_ref',
                'projection_version', 'subject_snapshot_ref', 'reporting_version')):
            _fail()
        pack.verify(expected_ref=held.pack_ref)
        doc = pack.document
        trusted_scope = {key: getattr(held, key) for key in SCOPE}
        if any(type(trusted_scope[k]) is not type(doc[k]) or trusted_scope[k] != doc[k] for k in SCOPE):
            _fail()
        if (held.industry_pins.tenant_id != held.tenant_id
                or held.subject_model is not None and type(held.subject_model) is not str
                or held.subject_snapshot_ref not in {s['snapshot_ref'] for s in doc['snapshots']
                                                     if s['capture_mode'] == 'HTTP'}):
            _fail()
        snapshot = detach(projection)
        verify_s2_projection(snapshot, pack, expected_pack_ref=held.pack_ref, trusted_scope=trusted_scope,
            expected_projection_ref=held.projection_ref, expected_projection_version=held.projection_version,
            industry_pins=held.industry_pins)
        available = {r['observation']['observation_id']: r for r in snapshot['industrial_projection']['rows']}
        chosen = []
        seen_rules = set()
        for pin in held.observations:
            if (type(pin) is not ObservationPin or pin.rule_id not in RULES or pin.rule_id in seen_rules
                    or pin.rule_version != RULE_VERSION or pin.source_version != SOURCE_VERSION
                    or type(pin.snapshot_refs) is not tuple):
                _fail()
            if (any(type(getattr(pin, key)) is not str for key in
                    ('observation_id', 'rule_id', 'rule_version', 'source_version'))
                    or any(type(ref) is not str for ref in pin.snapshot_refs)):
                _fail()
            row = available[pin.observation_id]
            observation = row['observation']
            refs = tuple(sorted(s['snapshot_ref'] for s in row['source_pages']))
            if (observation['rule_id'] != pin.rule_id or observation['rule_version'] != pin.rule_version
                    or row['source_version'] != pin.source_version or refs != pin.snapshot_refs):
                _fail()
            global_exclusion = (observation['result'] == 'NOT_APPLICABLE' and not refs
                                and row['model'] is None and row['details'].get('configuration_locator'))
            if not global_exclusion and (row['model'] != held.subject_model
                                         or held.subject_snapshot_ref not in refs):
                _fail()
            # No free-form cross-row composition: every chosen row carries the
            # independently held product/source anchor, or a verified rule exclusion.
            chosen.append(row)
            seen_rules.add(pin.rule_id)
        cards = [_card(row) for row in chosen]
        result = {'kind': 'S2BuyerTaskCandidate', 'reporting_version': VERSION,
            'authority': 'READ_ONLY_REVIEW_CANDIDATE', 'scope': trusted_scope,
            'pack_ref': held.pack_ref, 'projection_ref': held.projection_ref,
            'projection_version': held.projection_version,
            'industry_ref': held.industry_pins.industry_ref, 'industry_version': held.industry_pins.version,
            'profile_id': held.industry_pins.profile_id, 'subject_model': held.subject_model,
            'subject_snapshot_ref': held.subject_snapshot_ref,
            'title': '采购资料审阅候选', 'cards': cards,
            'admission': 'NOT_A_NATIVE_REPORT_FINDING_RULEEXECUTION_OR_GUARD_APPROVAL',
            'external_delivery_authorized': False,
            'limitations': ['仅针对服务端固定的当前资料包和 1–2 个来源候选，不代表网站全貌。',
                '审阅假设未确认为事实；资料真实性、工程适配、证书和供应商身份均未认证。',
                '服务端须继续独立校验当前任务授权与时效；本接口只重放和核对已持有的 pins。']}
        _display(result)
        result['candidate_ref'] = 's2br-' + digest(result)
        return detach(result)
    except Exception as exc:
        raise BuyerCandidateError('S2_BUYER_CANDIDATE_INTEGRITY') from exc


def verify_candidate(candidate: dict, pack: EvidencePack, projection: dict, *,
                     held: BuyerCandidatePins, expected_candidate_ref: str) -> None:
    """A new outer hash cannot admit changed prose, scope, status, excerpts or selection."""
    try:
        if type(expected_candidate_ref) is not str or not re.fullmatch(r's2br-[0-9a-f]{64}', expected_candidate_ref):
            _fail()
        supplied = detach(candidate)
        expected = build_candidate(pack, projection, held=held)
        if expected['candidate_ref'] != expected_candidate_ref or encode(supplied) != encode(expected):
            _fail()
    except Exception as exc:
        raise BuyerCandidateError('S2_BUYER_CANDIDATE_INTEGRITY') from exc


def _md(value):
    value = escape(display_text(str(value), 131072), quote=True)
    return re.sub(r'([\\`*_{}\[\]()#+.!|>-])', r'\\\1', value)


def render_markdown(candidate: dict, pack: EvidencePack, projection: dict, *,
                    held: BuyerCandidatePins, expected_candidate_ref: str) -> str:
    """Minimal view formatting for the candidate DTO, not a second report authority."""
    document = detach(candidate)
    verify_candidate(document, pack, projection, held=held, expected_candidate_ref=expected_candidate_ref)
    lines = ['# 采购资料审阅候选', '', '仅供内部只读审阅，展示内容与审阅假设仍需人工核对，尚未形成正式结论。', '',
             '对象：' + _md(document['subject_model'] or '当前受限来源'), '']
    labels = {'data_revision': '资料版本', 'specification_conditions': '来源声明的工况',
              'missing_or_ambiguous': '仍待补充或澄清的字段', 'unsupported_quantities': '单位尚不能按配置读取的字段',
              'engineering_fit': '工程适配', 'proof_kind': '证明声明类型',
              'date_relation': '声明日期与采集日', 'authentication': '证明真实性'}
    values = {'UNKNOWN': '尚未核验', 'certificate': '证书声明', 'case': '案例声明',
              'factory': '工厂声明', 'BEFORE_CAPTURE': '早于采集日；仅为来源声明的日期比较',
              'AFTER_CAPTURE': '晚于采集日；仅为来源声明的日期比较',
              'ON_CAPTURE_DATE': '与采集日相同；仅为来源声明的日期比较'}
    attributes = {'revision': '资料版本', 'conditions': '说明工况', 'model': '声明型号',
                  'flow': '额定流量', 'head': '额定扬程', 'power': '电机功率', 'voltage': '供电电压',
                  'frequency': '供电频率', 'pressure': '工作压力', 'temperature': '温度',
                  'medium': '介质', 'bore': '公称通径', 'material': '材质', 'connection': '连接方式'}
    for card in document['cards']:
        lines += ['## ' + _md(card['title']), '', '**' + card['result'] + '** — ' + _md(card['limitation']['text']), '',
                  '已重放静态来源：' + _md(card['source_replay']['meaning']), '']
        for key, value in card['observed_fields'].items():
            if key in labels and value not in (None, []):
                shown = values.get(value, value) if isinstance(value, str) else value
                if isinstance(shown, list):
                    shown = '、'.join(attributes.get(str(k), str(k)) for k in shown)
                lines += ['- ' + labels[key] + '：' + _md(shown)]
        if card['configuration_locator']:
            profile_label = {'pump-only': '仅泵类采购', 'technical-only': '仅技术资料',
                             'industrial': '泵阀类来源资料'}.get(document['profile_id'], document['profile_id'])
            lines += ['', '本次任务范围：' + _md(profile_label) + '；配置出处保留在来源明细中。']
        lines += ['', '审阅假设（待人工确认）：' + _md(card['review_hypothesis']['text']), '']
        for page in card['source_pages']:
            lines += ['保存来源：' + _md(page['url']) + '；采集时间：' + _md(page['observed_at']), '']
        lines += ['原始字节定位：' + str(len(card['source_excerpts']))
                  + ' 处；精确范围与原文见配套来源明细，可逐项回查。', '']
    lines += ['## 范围', '', *['- ' + _md(text) for text in document['limitations'][:2]], '']
    return '\n'.join(lines)

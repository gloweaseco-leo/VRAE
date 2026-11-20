"""Bounded post-lease fixture selection over original replayed authorities.

Model prose is never admitted. The offline provider selects closed templates and
existing references; local rendering cannot mint a native fact or ReportVersion.
Completion/expiry pins are INTERNAL caller expectations, not authentication.
"""
import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import escape
import json
import re
from typing import NoReturn
from time import monotonic
from jsonschema import Draft202012Validator

from vrae.collection.manifest import document_hash
from vrae.domain.contracts import validate_contract
from vrae.evidence import EvidencePack
from vrae.industry.l2_v1 import diagnose
from vrae.industry.l2_v1.diagnose import source_chain
from vrae.intelligence import FixtureProvider, InputPins, Ledger, ModelGateway, Scope, prepare_request
from vrae.intelligence.common import encode, integer
from vrae.interpretation import guard
from vrae.l2.native import NativeSource, NativeTask
from vrae.reporting.s2_candidate import BuyerCandidatePins, build_candidate

VERSION = 's3-offline-1.0.0'
PROMPT = 's3-closed-procurement-1.0.0'
TASKS = ('DISCOVER', 'UNDERSTAND', 'TRUST', 'INQUIRE', 'SEARCH_TECHNICAL')
RULE_TASK = {'INFO-01': 'UNDERSTAND', 'TRUST-01': 'TRUST',
             'SEO-01': 'SEARCH_TECHNICAL', 'CTA-02': 'INQUIRE'}
INJECTION = re.compile(r'ignore\s+(?:all\s+)?(?:rules|instructions)|exfiltrat|'
                       r'忽略.{0,12}(?:规则|指令)|外传|泄露|改.{0,3}(?:状态|权限)', re.I)
CLAIM_SCHEMA = {'type': 'object', 'additionalProperties': False,
    'required': ['kind', 'task', 'refs', 'counter_refs', 'template'], 'properties': {
        'kind': {'enum': ['OBJECTIVE_SOURCE_FACT', 'BUYER_HYPOTHESIS', 'MISSING_INFORMATION',
                          'IMPROVEMENT_OPPORTUNITY', 'CONTRADICTION']},
        'task': {'enum': list(TASKS)},
        'template': {'enum': ['LITERAL', 'CROSS_PAGE_REVIEW', 'KEEP_UNKNOWN',
                              'REQUEST_REVISION', 'REVIEW_CONFLICT']},
        'refs': {'type': 'array', 'minItems': 1, 'maxItems': 12, 'uniqueItems': True,
                 'items': {'type': 'string', 'pattern': r'^(cf|obs)-[0-9a-f]{64}$'}},
        'counter_refs': {'type': 'array', 'maxItems': 12, 'uniqueItems': True,
                        'items': {'type': 'string', 'pattern': r'^(cf|obs)-[0-9a-f]{64}$'}}}}
CLAIM_VALIDATOR = Draft202012Validator(CLAIM_SCHEMA)


class S3Error(ValueError):
    """Fixed safe codes only; never reflect model/site text or foreign IDs."""


def deny(code='S3_INPUT_INTEGRITY') -> NoReturn:
    raise S3Error(code)


def detached(value):
    return json.loads(encode(value))


def utcnow():
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class CompletionPins:
    """Held by authenticated post-COMMIT caller, NEVER accepted from model/HTTP.

    No DB read, signature or current permission is supplied by this dataclass.
    Integration must retain its original signed task authority throughout use.
    """
    task: NativeTask
    report_content_hash: str
    lease_started_at: datetime
    lease_expires_at: datetime
    worker_completed_at: datetime
    authority_expires_at: datetime

    def check(self, source, now):
        times = (now, self.lease_started_at, self.lease_expires_at,
                 self.worker_completed_at, self.authority_expires_at)
        if (type(source) is not NativeSource or type(self.task) is not NativeTask
                or source.held != self.task or self.task.source_access_mode != 'OFFLINE_SYNTHETIC'
                or any(type(t) is not datetime or
                    t.utcoffset() is None for t in times)
                or (self.lease_expires_at - self.lease_started_at).total_seconds() != 30
                or not self.lease_started_at <= self.worker_completed_at <= self.lease_expires_at
                or source.read().version['content_hash'] != self.report_content_hash):
            deny('POST_COMMIT_BINDING_INVALID')
        if now < self.lease_expires_at:
            deny('WORKER_LEASE_NOT_ENDED')
        if now >= self.authority_expires_at:
            deny('CURRENT_AUTHORITY_EXPIRED')


@dataclass(frozen=True, init=False)
class Context:
    """Prepared locally from immutable original objects; not a transport token."""
    pack: EvidencePack
    source: NativeSource
    completion: CompletionPins
    execution_bytes: bytes
    package: object
    gateway_pins: InputPins
    guard_pins_bytes: bytes
    catalog_bytes: bytes
    candidate_bytes: bytes
    context_ref: str

    def __init__(self):
        deny('USE_REPLAYED_CONTEXT_FACTORY')

    @property
    def catalog(self):
        return json.loads(self.catalog_bytes)

    @property
    def candidate(self):
        return json.loads(self.candidate_bytes)


def prepare_context(pack, source, projection, *, buyer_pins: BuyerCandidatePins | None,
                    completion: CompletionPins, now: datetime) -> Context:
    """Replay C1/S2/Guard; no model call, lease mutation or native artifact edit."""
    try:
        from .committed import CommittedCompletionPins
        if type(completion) not in (CompletionPins, CommittedCompletionPins) or type(pack) is not EvidencePack:
            deny()
        completion.check(source, now)
        task = completion.task
        if task.native_pack_ref != pack.ref:
            deny()
        data = diagnose(pack, expected_pack_ref=task.native_pack_ref, expected_industry_ref=task.industry_ref)
        if data['diagnosis_ref'] != task.diagnosis_ref:
            deny()
        rebuilt = NativeSource(pack, data, held=task)
        if rebuilt.read().document != source.read().document:
            deny()
        if buyer_pins is None:
            # Website diagnosis has no product/model prerequisite. The original
            # NativeSource and Guard replay below remain its evidence authority.
            candidate: dict = {'candidate_ref': 'site-' + document_hash({'pack_ref': pack.ref}), 'cards': []}
        else:
            candidate = build_candidate(pack, projection, held=buyer_pins)
        execution, package, _, _ = source_chain(pack, task.native_pack_ref)
        producer = source.read().document['producer']
        if (execution['execution_ref'] != producer['native_execution_ref']
                or package.ref != producer['native_package_ref']):
            deny()
        scope = Scope(**{k: pack.document[k] for k in ('tenant_id', 'run_id', 'policy_id', 'policy_version')})
        pins = InputPins(pack.ref, execution['execution_ref'], package.ref,
                         'ra2b6-1.0.0', 'ra2c3-1.0.0', scope)
        prepare_request(pack, execution, package, pins=pins)
        gp = {k: v for k, v in asdict(pins).items() if k != 'scope'}
        gp.update(expected_scope=asdict(scope), expected_guard_version=guard.VERSION)
        known = guard.catalog(pack, package, **gp)
        pages = {p['url'] for card in candidate['cards'] for p in card['source_pages']}
        conflicts = [row for row in data['assessments'] if (buyer_pins is None or row['model'] == buyer_pins.subject_model)
                     and row['observation']['rule_id'] == 'IND-DUTY'
                     and row['observation']['result'] == 'FAIL_WITH_EVIDENCE']
        needed = {r for row in conflicts for r in row['source_fact_refs']}
        entries = {}
        for fact in known['facts']:
            if buyer_pins is None or fact['source']['citation']['url'] in pages or fact['fact_ref'] in needed:
                entries[fact['fact_ref']] = {'type': 'GUARD_LITERAL', 'fact': fact}
        for card in candidate['cards']:
            if any(guard._contains_instruction(c['quote']) or INJECTION.search(c['quote'])
                   for c in card['source_excerpts']):
                deny('UNTRUSTED_SOURCE_INSTRUCTION')
            entries[card['observation_id']] = {'type': 'S2_REVIEW_CARD', 'card': card}
        for conflict in conflicts:
            if not set(conflict['source_fact_refs']) <= set(entries):
                deny()
            entries[conflict['observation']['observation_id']] = {'type': 'CONFIGURATION_CONFLICT',
                'assessment': conflict}
        if not 1 <= len(entries) <= 128 or len(encode(entries)) > 512_000:
            deny('LOCAL_CATALOG_BOUND')
        descriptor = {'version': VERSION, 'prompt': PROMPT, 'claim_schema_ref': document_hash(CLAIM_SCHEMA),
            'task': asdict(task),
            'report_hash': completion.report_content_hash, 'gateway_pins': asdict(pins),
            'candidate_ref': candidate['candidate_ref'], 'catalog_hash': document_hash(entries),
            'lease_started_at': completion.lease_started_at.isoformat(),
            'lease_expires_at': completion.lease_expires_at.isoformat(),
            'worker_completed_at': completion.worker_completed_at.isoformat(),
            'authority_expires_at': completion.authority_expires_at.isoformat()}
        if type(completion) is CommittedCompletionPins:
            descriptor['committed_input'] = {
                'transaction_id': completion.transaction_id,
                'artifact_sha256': completion.artifact_sha256,
                'current_input_ref': completion.current_input_ref}
        result = object.__new__(Context)
        values = (pack, source, completion, encode(execution), package, pins, encode(gp),
                  encode({'context': known['context'], 'entries': entries}), encode(candidate),
                  's3ctx-' + document_hash(descriptor))
        for name, value in zip(Context.__dataclass_fields__, values):
            object.__setattr__(result, name, value)
        return result
    except S3Error:
        raise
    except Exception:
        raise S3Error('S3_INPUT_INTEGRITY') from None


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            deny('DUPLICATE_JSON_FIELD')
        result[key] = value
    return result


async def _claims(text, context, usage, deadline):
    """Every unsupported field/prose is rejected; no open-world semantic claim."""
    try:
        raw = json.loads(text, object_pairs_hook=_strict_object,
                         parse_constant=lambda value: deny('NON_FINITE_OUTPUT'))
    except S3Error:
        raise
    except Exception:
        raise S3Error('INVALID_MODEL_JSON') from None
    if (type(raw) is not dict or set(raw) != {'version', 'context_ref', 'claims'}
            or raw['version'] != VERSION or raw['context_ref'] != context.context_ref):
        deny('MODEL_CONTEXT_OR_VERSION_MISMATCH')
    if type(raw['claims']) is not list or not 1 <= len(raw['claims']) <= 8:
        deny('CLAIM_BOUND')
    catalog = context.catalog
    entries = catalog['entries']
    out = []
    seen = set()
    for index, claim in enumerate(raw['claims']):
        await asyncio.sleep(0)
        if monotonic() >= deadline:
            deny('VALIDATION_TIMEOUT')
        try:
            if not CLAIM_VALIDATOR.is_valid(claim):
                deny('CLAIM_SCHEMA')
            if claim['task'] not in TASKS:
                deny('BUYER_TASK_INVALID')
            for name in ('refs', 'counter_refs'):
                values = claim[name]
                if (type(values) is not list or len(values) > 12 or any(type(v) is not str for v in values)
                        or len(set(values)) != len(values) or not set(values) <= set(entries)):
                    deny('UNBOUND_CLAIM_REFERENCE')
            if not claim['refs'] or encode(claim) in seen:
                deny('EMPTY_OR_DUPLICATE_CLAIM')
            seen.add(encode(claim))
            selected = [entries[ref] for ref in claim['refs']]
            kind, template = claim['kind'], claim['template']
            status, proof, proposal = 'HUMAN_REVIEW_REQUIRED', None, None
            if kind == 'OBJECTIVE_SOURCE_FACT' and template == 'LITERAL':
                if len(selected) != 1 or selected[0]['type'] != 'GUARD_LITERAL' or claim['counter_refs']:
                    deny('LITERAL_BINDING_REQUIRED')
                fact = selected[0]['fact']
                if INJECTION.search(fact['source']['quote']):
                    deny('UNTRUSTED_SOURCE_INSTRUCTION')
                if RULE_TASK[fact['rule_id']] != claim['task']:
                    deny('CLAIM_TASK_MISMATCH')
                text_out = fact['statement']
                interpretation = dict(schema_version='1.0', tenant_id=context.gateway_pins.scope.tenant_id,
                    run_id=context.gateway_pins.scope.run_id, interpretation_id='s3-literal-' + str(index),
                    observation_ids=[fact['observation_id']],
                    evidence_ids=[fact['source']['citation']['evidence_ref']], hypotheses=[text_out],
                    recommendations=[], missing_information=[], model_id='fixture-bytes-v1',
                    input_tokens=usage['input_tokens'], output_tokens=usage['output_tokens'], status='VALIDATED')
                binding = guard.binding(pointer='/hypotheses/0', text=text_out,
                    claim_type='OBJECTIVE_SOURCE_FACT', fact=fact, context=catalog['context'])
                checked = guard.validate(interpretation, [binding], context.pack, context.package,
                                         **json.loads(context.guard_pins_bytes)).document
                if checked['claims'][0]['status'] != 'SOURCE_FACT_BINDING_VERIFIED':
                    deny('ORIGINAL_GUARD_REFUSED')
                proof = {'interpretation': interpretation, 'bindings': [binding], 'guard': checked}
                status = 'SOURCE_FACT_BINDING_VERIFIED'
            elif kind == 'BUYER_HYPOTHESIS' and template == 'CROSS_PAGE_REVIEW':
                if (len(selected) != 2 or any(e['type'] != 'S2_REVIEW_CARD' or e['card']['result'] != 'PASS'
                    for e in selected) or claim['counter_refs'] or claim['task'] not in ('UNDERSTAND', 'TRUST')
                    or len({p['url'] for e in selected for p in e['card']['source_pages']}) < 2):
                    deny('CROSS_PAGE_BINDING_REQUIRED')
                text_out = ('同一产品锚点的参数页与证明声明页可共同供采购复核；来源关联不证明资料真实、'
                            '证书有效或工程适配。请工程和证明责任人核对型号、版本及工况。')
            elif kind in ('MISSING_INFORMATION', 'IMPROVEMENT_OPPORTUNITY'):
                if (len(selected) != 1 or selected[0]['type'] != 'S2_REVIEW_CARD'
                        or claim['task'] != selected[0]['card']['buyer_task'] or claim['counter_refs']):
                    deny('CURRENT_CARD_BINDING_REQUIRED')
                card = selected[0]['card']
                if kind == 'MISSING_INFORMATION' and template == 'KEEP_UNKNOWN':
                    status = card['result'] if card['result'] != 'PASS' else 'UNKNOWN'
                    text_out = (f"当前来源状态为 {card['result']}；未独立核验的工程适配和证明真实性保持未知。"
                                '未访问、不支持或不适用均不等于网站缺陷。')
                elif kind == 'IMPROVEMENT_OPPORTUNITY' and template == 'REQUEST_REVISION':
                    text_out = ('下一步请企业工程/证明责任人提供当前版本资料、适用型号和工况，人工逐项核对来源。'
                                '信息组织仅为标准Rebuild候选，工程/资质需另核；验收为版本和来源可追溯，报价及工期未知。')
                    proposal = {'target_urls': sorted({p['url'] for p in card['source_pages']}),
                        'required_materials': ['当前版本资料', '适用型号与工况', '原始证明与授权范围'],
                        'responsible_party': '企业工程或证明责任人',
                        'acceptance': '同一产品、资料版次、来源及工况可追溯，人工确认后再评估范围',
                        'order': 'HUMAN_REVIEW_BEFORE_SCOPE_CONFIRMATION',
                        'service_fit': '信息组织为标准候选；工程/认证系统为定制评审待确认',
                        'service_catalog_pin': None, 'price': None, 'schedule': None,
                        'authority': 'UNCONFIRMED_PROPOSAL_NOT_QUOTE_OR_EXECUTION'}
                else:
                    deny('UNSUPPORTED_TEMPLATE')
            elif kind == 'CONTRADICTION' and template == 'REVIEW_CONFLICT':
                if len(selected) != 1 or selected[0]['type'] != 'CONFIGURATION_CONFLICT':
                    deny('REPLAYED_CONFLICT_REQUIRED')
                row = selected[0]['assessment']
                if (set(claim['counter_refs']) != set(row['source_fact_refs'])
                        or not claim['counter_refs'] or claim['task'] != 'UNDERSTAND'):
                    deny('COUNTER_EVIDENCE_REQUIRED')
                text_out = ('来源标量与已固定配置情景的比较存在冲突，反证引用全部保留。'
                            '配置不是实际采购需求；未经工程复核不能推断设备不适用或经营损失。')
            else:
                deny('UNSUPPORTED_CLAIM_OR_TEMPLATE')
            all_refs = claim['refs'] + claim['counter_refs']
            observations, evidence = set(), set()
            for ref in all_refs:
                entry = entries[ref]
                if entry['type'] == 'GUARD_LITERAL':
                    observations.add(entry['fact']['observation_id'])
                    evidence.add(entry['fact']['source']['citation']['evidence_ref'])
                elif entry['type'] == 'S2_REVIEW_CARD':
                    observations.add(entry['card']['observation_id'])
                    evidence.update(c['evidence_ref'] for c in entry['card']['source_excerpts'])
                else:
                    observations.add(entry['assessment']['observation']['observation_id'])
            out.append({'index': index, **claim, 'text': text_out, 'status': status,
                'observation_refs': sorted(observations), 'evidence_refs': sorted(evidence),
                'coverage_scope': 'PINNED_PRODUCT_AND_RECORDED_SOURCES_ONLY',
                'assumptions': ['SOURCE_DECLARATION_NOT_AUTHENTICATION', 'ENGINEERING_FIT_UNKNOWN'],
                'native_fact_admission': 'NONE', 'human_review_required': True,
                'model_version': 'fixture-bytes-v1', 'prompt_version': PROMPT,
                'industry_version': context.candidate['industry_version'],
                'proposal': proposal, 'original_guard': proof})
        except S3Error as exc:
            out.append({'index': index, 'status': 'REJECTED', 'reason': str(exc)})
        except Exception:
            out.append({'index': index, 'status': 'REJECTED', 'reason': 'CLAIM_SCHEMA'})
        await asyncio.sleep(0)
        if monotonic() >= deadline:
            deny('VALIDATION_TIMEOUT')
    return out


class Session:
    """One bounded service-local post-lease session; original Ledger owns dispatch.

    Keep/restore the original ledger with its trusted latest pin across restart.
    This cache is not a durable PG job store or a replacement authorization API.
    """
    def __init__(self, context: Context, *, ledger: Ledger | None = None, clock=utcnow):
        if type(context) is not Context or type(ledger) not in (Ledger, type(None)):
            deny()
        self.context, self.ledger, self.clock = context, ledger, clock
        self._records: dict[str, tuple[str, bytes | None]] = {}
        self._lock = asyncio.Lock()

    async def run(self, operation_id, *, mode='NO_MODEL', provider=None,
                  timeout_ms=1000, cancel_before_dispatch=False):
        if mode == 'REAL_QWEN':
            from vrae.intelligence.qwen.session import run_session
            return await run_session(self, operation_id, provider=provider,
                                     timeout_ms=timeout_ms, cancel=cancel_before_dispatch)
        if (type(operation_id) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{2,127}', operation_id)
                or mode not in ('NO_MODEL', 'FIXTURE') or type(provider) not in (FixtureProvider, type(None))
                or mode == 'FIXTURE' and provider is None or mode == 'NO_MODEL' and provider is not None
                or type(cancel_before_dispatch) is not bool):
            deny('OFFLINE_CONFIGURATION_REQUIRED')
        integer(timeout_ms, 1, 1000)
        c = self.context
        c.completion.check(c.source, self.clock())
        fingerprint = document_hash({'context_ref': c.context_ref, 'mode': mode,
            'provider': asdict(provider) if provider is not None else None,
            'timeout_ms': timeout_ms, 'cancel_before_dispatch': cancel_before_dispatch})
        async with self._lock:
            if operation_id in self._records:
                old, result = self._records[operation_id]
                if old != fingerprint:
                    deny('OPERATION_REPLAY_MISMATCH')
                if result is None:
                    deny('OPERATION_IN_FLIGHT')
                return json.loads(result)
            if len(self._records) >= 16:
                deny('SESSION_OPERATION_BOUND')
            self._records[operation_id] = (fingerprint, None)
        dispatch_at = self.clock()
        c.completion.check(c.source, dispatch_at)
        recorded = dispatch_at.isoformat()
        deadline = monotonic() + 5.0
        gateway = ModelGateway(provider=provider, ledger=self.ledger)
        result = await gateway.run(c.pack, json.loads(c.execution_bytes), c.package,
            pins=c.gateway_pins, operation_id=operation_id, recorded_at=recorded,
            max_output_tokens=2048, timeout_ms=timeout_ms, cancel_before_dispatch=cancel_before_dispatch)
        real_usage = dict(schema_version='1.0', tenant_id=c.gateway_pins.scope.tenant_id,
            run_id=c.gateway_pins.scope.run_id, usage_id='usage-realunknown-' + document_hash({
                'scope': asdict(c.gateway_pins.scope), 'operation': operation_id}), cost_type='MODEL',
            provider=None, model_id=None, input_tokens=None, output_tokens=None,
            amount=None, currency=None, cost_status='UNKNOWN', recorded_at=recorded)
        validate_contract('UsageRecord', real_usage)
        out = {'version': VERSION, 'context_ref': c.context_ref, 'operation_id': operation_id,
            'mode': mode, 'prompt_version': PROMPT, 'status': result['status'], 'code': result['code'],
            'claims': [], 'private': True, 'approval_status': 'NOT_APPROVED', 'shareable': False,
            'is_report': False, 'native_fact_admission': 'NONE', 'external_actions': [],
            'real_model_calls': 0, 'real_token_charges': 0, 'fixture_calls': result['fixture_calls'],
            'usage': real_usage, 'synthetic_usage': result['usage'],
            'usage_origin': 'SYNTHETIC_UTF8_BYTES_NOT_PROVIDER_TOKENS_OR_INVOICE',
            'ledger_ref': result['ledger']['ledger_ref'] if result['ledger'] else None,
            'interpretation': result['interpretation'],
            'deterministic_report_hash': c.completion.report_content_hash,
            'quality': {'status': 'NOT_EVALUABLE', 'independent_gold': 0,
                        'precision': None, 'improvement': None}}
        try:
            c.completion.check(c.source, self.clock())
            if result['status'] == 'FAKE_COMPLETED_UNVALIDATED':
                out['claims'] = await _claims(result['provider_output'], c, result['usage'], deadline)
                rejected = sum(r['status'] == 'REJECTED' for r in out['claims'])
                out['status'] = 'REFUSED' if rejected == len(out['claims']) else 'CANDIDATES_FOR_HUMAN_REVIEW'
                out['code'] = ('ALL_CLAIMS_REJECTED' if rejected == len(out['claims']) else
                               'SOME_CLAIMS_REJECTED' if rejected else 'OFFLINE_CLAIMS_CHECKED')
        except S3Error as exc:
            out.update(status='REFUSED', code=str(exc), claims=[])
        except asyncio.CancelledError:
            out.update(status='REFUSED', code='CANCELLED', claims=[])
        out['receipt_ref'] = 's3receipt-' + document_hash(out)
        async with self._lock:
            self._records[operation_id] = (fingerprint, encode(out))
        return detached(out)

    def read(self, operation_id):
        """Return only the held result, not a self-rehashed model submission."""
        self.context.completion.check(self.context.source, self.clock())
        value = self._records.get(operation_id)
        if value is None or value[1] is None:
            deny('RESULT_NOT_AVAILABLE')
        return json.loads(value[1])

    def markdown(self, operation_id):
        data = self.read(operation_id)
        if data['mode'] == 'REAL_QWEN':
            from vrae.intelligence.qwen.session import markdown
            return markdown(data)
        labels = dict(zip(TASKS, ('发现产品', '理解产品', '核对信任资料', '准备询价', '搜索技术')))
        rules = {'DISCOVER': ('IND-SELECTION',), 'UNDERSTAND': ('IND-SPEC', 'IND-DUTY', 'IND-FIT'),
                 'TRUST': ('IND-PROOF',), 'INQUIRE': ('IND-RFQ',), 'SEARCH_TECHNICAL': ()}
        questions = {'DISCOVER': '目录中的型号与应用入口是否对应本次采购对象？',
            'UNDERSTAND': '请工程责任人确认型号、版次、单位、介质与工作点，哪些资料可提供原件？',
            'TRUST': '谁能提供当前证明原件，并独立核对声明方、适用对象和日期？',
            'INQUIRE': '买方还缺哪些工况、数量与交付地信息？只读联系入口不代表询价已发送或送达。',
            'SEARCH_TECHNICAL': '哪些页面已实际检查抓取与呈现？未观察范围保持未知，不推断索引、排名或流量。'}
        lines = ['# 离线采购解释候选', '', '仅供人工审阅；来源展示不等于真实性、工程适配或正式批准。',
                 '以下为同源原报告与离线候选片段，不替代报告全文或人工审阅。',
                 '', 'AI 模式：' + data['mode'] + '；状态：' + data['status'],
                 '真实模型费用：UNKNOWN；质量与提升：NOT_EVALUABLE（独立 Gold=0）。', '']
        def safe(text):
            return re.sub(r'([\\`*_{}\[\]()#+.!|>-])', r'\\\1', escape(str(text), quote=True))
        candidate = self.context.candidate
        model = candidate['subject_model']
        native = self.context.source.read().document['findings']
        for task in TASKS:
            lines.extend(['## ' + labels[task], '证实范围：仅当前保存来源与原确定性检查；未覆盖部分不推断为缺陷。'])
            excerpts = [row for row in native if model is not None and row['title'].startswith(model + ' · ')
                        and row['native_rule_id'] in rules[task]]
            for excerpt in excerpts[:2]:
                lines.append('原报告片段（' + excerpt['native_result'] + '）：' + safe(excerpt['statement']))
            for card in candidate['cards']:
                if card['buyer_task'] == task:
                    lines.append('确定性资料状态：' + card['result'] + '；' + safe(card['limitation']['text']))
                    fields = card['observed_fields']
                    if fields.get('data_revision'):
                        lines.append('资料版次：' + safe(fields['data_revision']))
                    if fields.get('specification_conditions'):
                        lines.append('来源声明工况：' + safe(fields['specification_conditions']))
                    if 'authentication' in fields:
                        lines.append('证明真实性：尚未独立核验；来源声明不等于认证。')
                    if fields.get('date_relation') == 'BEFORE_CAPTURE':
                        lines.append('保存来源中的声明日期早于采集日；需获取当前原件核验，不据此判定证书真伪或合规。')
            for row in data['claims']:
                if row['status'] != 'REJECTED' and row['task'] == task:
                    text = row['text']
                    if row['kind'] == 'OBJECTIVE_SOURCE_FACT':
                        fact = row['original_guard']['bindings'][0]['fact']
                        text = ('保存来源原文：' + fact['source']['citation'].get('text', fact['source']['quote'])
                                + '。仅证明原文字节与定位，不证明资料真实性或工程适配。')
                    review = '证实（仅来源字面）' if row['status'] == 'SOURCE_FACT_BINDING_VERIFIED' else (
                        '待人工核对' if row['status'] == 'HUMAN_REVIEW_REQUIRED' else '未知或不适用')
                    lines.append('- ' + review + '：' + safe(text))
                    lines.append('  来源/反证定位：审阅记录第' + str(row['index'] + 1) + '条；绑定'
                                 + str(len(row['refs'])) + '项来源、' + str(len(row['counter_refs'])) + '项反证。')
            lines += ['未知：未独立核验的工程适配、认证、投递及经营效果。',
                '下一步问题：' + questions[task] + '不自动采取权限或外部动作。', '']
        return '\n'.join(lines)

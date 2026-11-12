"""In-memory synthetic adapters. Capability identity is test wiring, not human auth."""
from copy import deepcopy
import hashlib
import json

from .contracts import DTO_VERSION, TEST_ONLY, TaskRecord, canonical, refuse
from .native import ROOT, NativeVerifier
from .ports import Scope
from .service import ConsoleService


class FixtureAuthority:
    def __init__(self, *, test_only=False):
        if test_only is not True:
            refuse('UNAUTHORIZED')
        self._contexts = []

    def issue(self, scope):
        context = object()
        self._contexts.append((context, scope))
        return context

    def require(self, context):
        for key, scope in self._contexts:
            if context is key:
                return scope
        refuse('UNAUTHORIZED')


class FixtureRepository:
    def __init__(self, tasks):
        self.tasks = {t['task_id']: deepcopy(t) for t in tasks}
        self.sources = json.loads((ROOT / 'tests/reporting/fixtures/sources.json').read_text(encoding='utf-8'))

    def assigned(self, scope):
        return [deepcopy(t) for k, t in self.tasks.items() if k in scope.assigned_ids]

    def task(self, task_id):
        return deepcopy(self.tasks[task_id])

    def report_source(self, case):
        return deepcopy(self.sources[case])


def make_fixture():
    native = NativeVerifier()
    tasks = []
    scenarios = [
        ('task-pending', '新材料供应商 · 等待范围准入', 'PENDING_ADMISSION', 'CREATED', None,
         '待核实许可和任务范围；尚未访问网站。'),
        ('task-403', '工业泵 · 来源拒绝 403 / WAF', 'BLOCKED', 'ACCESS_BLOCKED', None,
         '合成状态：来源拒绝访问 403 / WAF。不能据此判断网站缺陷。下一步：核对许可与访问范围，不绕过限制。'),
        ('task-robots', '精密阀门 · robots 范围限制', 'BLOCKED', 'POLICY_BLOCKED', None,
         '合成状态：robots / 范围策略阻断。不能据此判断网站缺陷。下一步：请求合规范围确认，不重试受限来源。'),
        ('task-unknown', '机加工 · UNKNOWN 覆盖不足', 'BLOCKED', 'INSUFFICIENT_EVIDENCE', None,
         '合成状态：UNKNOWN / 规则未覆盖。不能据此判断网站缺陷。下一步：补充研究范围；没有可展示的报告。'),
        ('task-invalid', '传动件 · 来源 / Guard 不可验证', 'BLOCKED', 'MODEL_INVALID', None,
         '合成状态：来源或 Guard 无效。不能据此判断网站缺陷。下一步：隔离并回查上游原始记录，不展示未验证结论。'),
        ('task-running', '机械配件 · 采集中', 'RUNNING', 'FETCHING', None,
         '合成运行状态；尚无完成证据，不提供网站判断。'),
        ('task-evidence', '电机 · 证据就绪', 'EVIDENCE_READY', 'EVIDENCE_READY', None,
         '合成阶段占位，尚无绑定报告；等待原生规则及 Guard。'),
        ('task-draft', '工业泵 · 草稿就绪', 'DRAFT_READY', 'DRAFT_READY', '404',
         '仅内部只读；可核对相同固定原生 404 案例。此阶段映射为合成任务，不代表真实作业完成。'),
        ('task-404', '工业泵 · 联系入口 404', 'REVIEW_REQUIRED', 'REVIEW_REQUIRED', '404',
         '一条已验证观察事实；影响、行动与复验建议仍需人工判断。'),
        ('task-200', '工业泵 · 200 零问题范围核对', 'COVERAGE_ONLY', 'RULED', '200',
         '零问题不代表网站全面健康、询盘成功或已经批准；仅核对本次已覆盖的来源。'),
        ('task-failed', '包装设备 · 运行失败', 'FAILED', 'FAILED', None,
         '合成状态：运行失败。不能据此判断网站缺陷。下一步：核对内部失败原因及允许的恢复范围。'),
    ]
    for task_id, title, stage, status, case, reason in scenarios:
        held = native.held(case) if case else None
        run_id = held['pins']['expected_scope']['run_id'] if held else 'run-' + task_id
        row = {'dto_version': DTO_VERSION, 'source_kind': TEST_ONLY,
               'task_id': task_id, 'owner_scope': 'ops-synthetic', 'title': title,
               'stage': stage, 'coverage_reason': reason, 'report_case': case,
               'report_version': 1 if case else None, 'report_pins': held,
               'audit_run': {'schema_version': '1.0', 'tenant_id': 'tenant-test',
                   'run_id': run_id, 'audit_id': 'audit-' + task_id, 'request_id': 'request-' + task_id,
                   'status': status, 'attempt': 0,
                   'input_hash': hashlib.sha256(canonical({'fixture': task_id})).hexdigest(),
                   'rule_version': 'ra2b6-1.0.0', 'started_at': None, 'finished_at': None,
                   'error_code': 'SYNTHETIC_FAILURE' if status == 'FAILED' else None}}
        tasks.append(TaskRecord.parse(row).document)
    repository = FixtureRepository(tasks)
    authority = FixtureAuthority(test_only=True)
    scope = Scope('tenant-test', 'ops-synthetic', frozenset(t['task_id'] for t in tasks), TEST_ONLY)
    context = authority.issue(scope)
    return ConsoleService(authority, repository, native), context

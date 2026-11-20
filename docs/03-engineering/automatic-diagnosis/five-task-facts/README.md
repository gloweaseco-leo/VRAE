# P0：AI 不可用时，报告仍交付五维事实

本修复补齐原结果接口的事实投影与消费契约。Owner 追加的六页采集、通用静态产品/联系证据、
Qwen 锚点与正式报告通道复用见 [剩余范围与 V1.1 对齐](remaining-scope.md)。
五维/16 条规则、旧版本判断、原模型许可和发布门槛保持；新来源提取使用独立的 1.0.2 版本。
不修改 VF 仓库、前端和发布配置。VF 需要按本契约修改自己的适配器及页面；VRAE 补丁尚未合并部署。

## 这轮真实报告的问题

PDF SHA256：`1b5565c79b5d2f19736c33b193762c666f2220b7d8474fdede8e426650fa4480`。
对应原工件于 2026-11-20 09:18:12 UTC 提交，工件 SHA256：
`7a84a909bc28fbcbe619752dfdfbcfb9de4c2976c7a51573db09237ec3f9c001`。
只读检查匹配 PDF 的网站及这次采集时间；脱敏记录见 `incident.json`，补丁回放见 `replay.json`。
没有重新请求网站、重试 Qwen、修改历史工件或共享模型账本。

三个断点相互叠加：

1. **采集成功，模型在上下文阶段未发出。** 4 个页面均 FETCHED/HTTP 200，无采集错误及超时；
   57 个候选 URL 中 53 个未访问。模型回执为 `INSUFFICIENT_GUARDED_EVIDENCE`、
   `failure_stage=CONTEXT`、`provider_attempts=0`、`real_model_calls=0`。
   原 Guard 可用 source fact 为 0，因而没有调用 Qwen。这不是供应商请求失败。
2. **VRAE 把行业评估当成全部确定性诊断。** 原 `deterministic_diagnosis.assessments`
   只有一条 `IND-SELECTION UNKNOWN`；底层规则执行实际上有 16 条规则、17 条观察，
   包含 2 条 `DISC-01 PASS` 及 15 条 UNKNOWN。基础规则结果未进入原 DTO。
   两条 PASS 证明采集时的静态首页导航链接到达已采集 HTTP 200 分类路径；不能扩大为全部采购路径正常。
   其他 UNKNOWN 涉及静态解析不支持/歧义、缺少身份或规格上下文、未实现的可视/语义判断等，
   不是全站缺陷清单。已有规则观察也不能直接冒充 Qwen Guard 的可用事实。
3. **VF 投影再次丢字段，并把清单长度当覆盖数。** 当前接入分支的
   `lib/vrae-preview-client.ts:175–240` 只在 `state==='diagnosed'` 时消费 `claims`，
   返回值只有 state/pages/insights，没有消费 deterministic_diagnosis、analysis_outcome、capture_summary、model.failure_stage。
   其中 203 行还把 evidence+coverage 拼接清单截到 24 条。
   `connected-preview-form.tsx:67–74` 用该截断清单长度表示页面范围，并把空 insights 显示成统一 UNKNOWN。
   所以 PDF 的“24 页”不是实际采集总数，也不是候选范围总数。

VF 静态核对基于原接入分支，内容与 PDF 表现吻合；不声称已对 VF 部署进行浏览器验收。
核对文件 Git blob：client `c069a1c70cce6bc72efd4ea2d839f193cd101639`，
connected form `9bb986c71047120b2ea83c5abdaa23456f22cb33`。

## P0-1：消费规则事实，而不是把 AI 成功当报告开关

沿用 `GET /v1/audits/{audit_ref}/diagnosis`。
`deterministic_diagnosis` 原有行业字段保持不变，新增：

```text
deterministic_diagnosis.rule_evaluator_version
deterministic_diagnosis.buyer_tasks[]
  task                         五维中的一个，按固定顺序交付
  rules[]
    rule_id / rule_version / buyer_task / enabled
    observations[]
      observation.result       原 PASS / FAIL_WITH_EVIDENCE / UNKNOWN /
                               ACCESS_BLOCKED / NOT_APPLICABLE
      observation.statement    原规则陈述
      observation.evidence_ids
      observation.coverage_note
      reason                   原判断原因，不能被统一 UNKNOWN 提示覆盖
      citations[]              原定位、来源、链接或字段引用，按规则形状保留
      homepage / target_response / source_page / ... 原规则上下文
```

规则版本按已提交工件的 `diagnostic_version` 选择，完整重放后必须匹配原 `native_execution_ref`。
不使用最新规则静默改写历史结论，不把规则观察改成 AI claims。

VF 后台解析器应保留上面三组对象；页面逐维、逐规则、逐 observation 展示。
**只要确定性诊断非空就展示，不以 state=DIAGNOSED、diagnosis_complete=true 或 claims 非空作为前置条件。**
AI_PENDING 的 202 和 AI_UNAVAILABLE 的 200 都可能已有完整规则事实。
diagnosis_complete 继续表示原真实模型完成门槛，不改成“有任意规则事实”。
403/撤权仍要拒绝读取，不得拿缓存绕过当前权限。

| task | 页面维度 | 本轮补丁回放可显示内容 |
|---|---|---|
| DISCOVER | 找到目标产品 | 2 条 PASS + 2 条 UNKNOWN，分别显示范围、原因及引用 |
| UNDERSTAND | 理解型号与参数 | 3 条 UNKNOWN，说明静态解析、映射或语义判断限制 |
| TRUST | 核对企业与产品资料 | 3 条 UNKNOWN，说明身份及资质上下文尚不能验证 |
| INQUIRE | 找到询价入口 | 3 条 UNKNOWN，说明可见性/路径/布局未能确认，未提交表单 |
| SEARCH_TECHNICAL | 访问与页面结构 | 4 条 UNKNOWN，保留 title/canonical 等已有上下文引用和判断边界 |

同一维度可以同时有 PASS 和 UNKNOWN；不能把整维归并成单个成功/失败标签。
UNKNOWN 也可能带上下文引用，不能仅因 evidence_ids 为空而丢弃整条观察。
引用只能展示该观察实际拥有的内容，不补造 quote、访问时间、失败页或缺失参数。

最小消费顺序（伪代码）：

```text
for task in fixed_five_tasks:
    show task heading
    for rule in deterministic_diagnosis.buyer_tasks[task].rules:
        for row in rule.observations:
            show rule_id, row.observation.result, row.observation.statement
            show row.reason, row.observation.coverage_note
            show existing row.citations and source/target context
            if UNKNOWN: show a scoped recheck instruction, not a website defect
show AI section using original validated claims, independently of above rows
```

中文展示可将本轮 PASS 解释为“采集时，首页静态导航中的这条链接已到达分类路径页面（HTTP 200）”。
对于不支持的产品页静态结构，可以建议“核对产品页的型号、规格字段和资料版本；本次未完成可靠解析”，
不能改写成“网站没有参数”。其他补核项同样说明限制及待核范围，不伪造改善建议来源。
已有行业 assessments/recommendations 可继续展示，不能把“暂无已确认缺陷”写成“全站无问题”。

## P0-2：把采集覆盖、规则未知和 AI 结果分开展示

VF 适配器必须保留 `analysis_outcome`、`capture_summary` 和 `model` 的
reason/failure_stage/provider_attempts/real_model_calls/cost_status，原 AI 成功校验保持不变。

| 字段/值 | 客户展示 | 不应表达成 |
|---|---|---|
| capture_summary.fetched_pages | 实际采集成功页数 | 前端列表条数 |
| capture_summary.page_records | 本次页面请求记录数，可能含未成功派发的记录 | 全部成功访问数 |
| capture_summary.candidate_urls | 已发现候选地址数量 | 全站页面总数 |
| capture_summary.unvisited_candidates | 因本次范围/预算未访问的候选数量 | 网站缺陷、访问失败 |
| coverage.status=NOT_VISITED | 未访问及原 reason | 已检查后判定失败 |
| coverage.status=UNKNOWN | 本条范围/角色无法确认 | 统一当成未访问 |
| INSUFFICIENT_EVIDENCE + CONTEXT + attempts=0 | 现有证据不足，尚未调用 AI；仍展示已有规则事实 | 模型调用失败 |
| NOT_DISPATCHED | AI 未发出，显示原阶段及原因 | 供应商故障 |
| PROVIDER_FAILED | AI 请求失败，显示 PROVIDER 阶段 | 采集失败或网站缺陷 |
| VALIDATION_REJECTED | 模型结果未通过校验，不能当诊断结论；仍展示规则事实 | 已生成可靠 AI 建议 |
| PENDING | AI 等待/处理中；已有事实先显示 | 等 AI 成功再显示全部报告 |
| NOT_RUN | 采集未完成且 AI 未运行 | 有已生成的 AI 结论 |
| COMPLETED | 按原真实 provider/usage/Guard 门槛展示 AI 内容 | 自动等同人工审核 |
| UNAVAILABLE / null 元数据 | 当前原因或调用次数无法确认 | 擅自归零、断言未收费 |

本轮正确的摘要应为：

> 已采集 4 个页面；发现 57 个候选地址，其中 53 个本次未访问。现有证据不足以形成 AI 分析，尚未调用 AI（阶段 CONTEXT）。下方仍展示已完成的规则检查及待核项。

页面列表可以分页或折叠；“显示 24 条”只表示 UI 展示条目数，不能代替后端 capture_summary。
引用支持的状态与原字段应保留在 VF BFF 返回类型、序列化和客户端 ResponseData 三处；只改组件不足以解决字段被上游丢弃的问题。

## 验证与交付边界

新增回归验证原版/补丁版规则的完整五维投影、原引用保留、execution pin 不符拒绝。
真实隔离 PG 流程覆盖 AI 待处理、证据不足、未派发、供应商失败、验证拒绝和成功时规则事实均一致。
撤权、跨主体隔离、真实模型完成门槛等原反测试保留。
测试模型是明确的隔离替身，不能拿其结果冒充真实 Qwen。

最初 P0 阶段：18 项隔离 PG 检查通过；与线上一致的 Linux 容器中 82 项服务边界检查通过；当时 lint 通过。
`pg.log`、`service-boundaries.log`、`lint.log` 和 `validation.json` 保留证据。
原生 Windows 补充检查 77 通过、5 失败，失败均为原有 POSIX 私有目录 mode 校验在 NTFS 上不适用；
没有放宽相关检查，同一套检查在实际部署使用的 Linux 平台全部通过。新投影测试在原生 Windows 亦通过。

`replay.json` 是本地补丁对原真实工件的只读投影验证，不是新线上接口响应；
本轮没有新增真实模型调用，也没有完成 VF 页面修改/部署或客户业务验收。
VRAE 合并部署后，VF 团队按本契约完成自己的适配器及展示更新，再由 Owner 独立验收。

扩展后的最终验证见 `extended-validation.json`：六页 PG 全链 27 项通过，历史回放 11 项通过，
147 个源码文件类型检查通过，最终 lint 通过。先前的旧规则回归 1,526 项通过，测试输入归档摘要另行保留，
后续来源 profile 接线由最终聚焦测试覆盖。原人审/版本/定向分享通道协议验证已通过，详见 `extended-report-protocol.json`。
同一真实工件新版本只读回放得到 3 个已通过原字节绑定校验的 INFO-01 文本锚点；原规则仍 UNKNOWN，
详见 `extended-real-source-replay.json`。没有新增实际模型调用、正式客户批准或上线动作。

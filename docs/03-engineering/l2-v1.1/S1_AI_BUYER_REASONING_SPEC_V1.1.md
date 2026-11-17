# VRAE V1.1 · S1｜L2 AI 采购推理与可信建议规范

> 状态：OWNER 设计候选，随 S1 文档 PR 独立验收后生效；DESIGN_ONLY，**不授权模型调用、不改变代码/合同/密钥/费用**。
> 起点：accepted S0 main `178d1ea4a6b11c11491a8ed71a418e6415b1fcb5`；V1.1 原 RA-3A/B/C/D、`contracts/v1/AIInterpretation.schema.json`、`vrae/intelligence/*`、`vrae/interpretation/*` 和 `vrae/l2/*` 均保留权威。对应 A15–A19、D03/D05/D07。

## 1. 产品目标与不可越界的决定

AI 的功能不是把报告写长，而是从**已独立回放的多页面工业事实**中帮助专业 Reviewer 回答：
1. 海外采购商当前能确认哪些产品、用途、参数与供应商声明？
2. 哪些真正有据的路径/资料缺陷妨碍其完成五类买家任务，哪些是买家尚未给出工况、未访问范围、供应商需独立证实的事项？
3. 哪些修改能由 VEYFRONT 的标准 Rebuild 候选交付，哪些需要企业工程确认、授权资料或定制系统？

**不能决定**：真实采购者意愿、产品工程适配、安全认证真假、法律主体身份、邮件投递成败、订单/询盘/转化、SEO 收录与排名、客户付费意愿、E2/E3、价格、客户素材复制权、网站改版执行授权。

L2 是分析深度，SourcePolicy 是逐项实际访问许可；模型输入同样受来源授权、数据用途、最小化外传和到期撤销约束。公开可读取不等于允许上传完整网页/用户数据给第三方模型。

## 2. 唯一的事实权威与运行位置

```text
已获许可的来源 → EvidencePack（不可变、可校验）
  → 原 RuleExecution / FindingPackage / IndustryPack → 独立 Guard/source-fact projection
  → [可选独立 AI 任务] → 未经信任的候选 claims
  → schema + 每条引用/蕴含校验 + 人审 → 新 ReportVersion / Rebuild 建议
  → 原 Controlled（未来正式认证另审批）→ 内部 RebuildBrief
```

- **不能**在 S0 的原30秒 Worker lease 内做长时 LLM 推理、调大租约、跳过 Worker 的首次检查和 COMMIT 前强制重放。AI 是原任务确定性输出之后的独立有界、可取消阶段；AI 超时不会把原 Worker 事务回滚为不存在，也不会篡改确定性结果。
- **不能**创建新的 Source/Rule/Guard/Review/Report 服务主权。复用 RA-3 原 ModelGateway、AIInterpretation、UsageRecord、现有审核与报告；面向语义的新中间 claim-binding 为**未来拟定的 sidecar/适配器规范，不宣称已经落地**，必须经版本兼容评审。
- 现状源码：ModelGateway 只接受 FixtureProvider、`real_model_calls=0`；工业 L2 的 `model_id=None` 不代表已经跑过真实 AI。不可把 Guard 对源码字面表达的验证称为“AI 全语义准确”。

## 3. 输入契约（S3 实施时具体 JSON Schema 化）

来自可信服务端，而不是页面、用户输入或模型自声明。输入分为可发送的**最小白名单投影**与内部不可发送的权威 refs；必须有脱敏/数据地区批准。

| 逻辑字段 | 来源权威 | 要求 |
| --- | --- | --- |
| tenant/run/request/job、SourcePolicy mode/version | VRAE 服务端 | 只用于范围校验，不能由模型覆写 |
| pack_ref、execution_ref、FindingPackage/Guard refs | 原生重放链 | 必须同一 run、原字节链，过期后不得复用 |
| industry_id/version、buyer tasks、术语和所需字段 | IndustryPack | 配置事实≠行业通行法律、工程标准 |
| ObservedFact[] | Observation + 原引用定位 | 每项记录 rule/version、来源 URL、观察时间、可引用片段、结果 PASS/FAIL/UNKNOWN、覆盖局限 |
| EvidenceGap[] | SourcePolicy、采集覆盖与规则适用性 | 明确未知是未访问、受限、未解析、买家缺参数或工程需核验 |
| contradictory_facts[] | 至少两个独立原生事实 | 可以建议解释冲突，不能自动选择谁“真实” |
| allowed_service_context | VEYFRONT 人工确认的服务目录版本 | 未提供则仅说“标准候选/定制评审待确认”，不能推报价/工期 |
| budget/model/prompt/retention pins | Owner 配置 | 无模型、预算、费率或数据用途批准 → 不派发 |

限额分别约束：最大事实数量、单条证据片段、总 UTF-8 字节、每 run 模型尝试次数/输出 tokens/超时/费用；字段缺失按 `MODEL_NOT_RUN` 或拒绝，不是自动补默认无限预算。原始 Cookie、联系人、截图、完整 HTML、受保护账号/私有报价默认不发送。

## 4. 输出契约：五种互不偷换的语义

**每个候选原子**：`kind`、`text`、`buyer_task`、`source_fact_refs[]`、`observation_refs[]`、`coverage_scope`、`assumptions[]`、`counter_evidence_refs[]`、`review_status`、`model/prompt_version`；模型输出的 IDs/哈希本身**没有授权力**。

| kind | 可说什么 | 验证和展示 |
| --- | --- | --- |
| OBJECTIVE_SOURCE_FACT | 本次某URL、时间、原文/HTTP/静态路径已被观察 | 字节定位+引用+适用性+完整原生重放一致才可 FACT_BOUND；不自动认证真实性 |
| BUYER_HYPOTHESIS | 可能需要更多资料或理解更多工程条件 | 仅 HUMAN_REVIEW_REQUIRED，不能转成故障或损失事实 |
| IMPROVEMENT_OPPORTUNITY | 能改善某采购任务的有界备选措施 | 有输入/责任/受益假设/复验；不冒充已确认报价范围 |
| MISSING_INFORMATION | 尚未知、未观察或企业/采购商需确认的信息 | 保持 UNKNOWN，不能表述成“网站缺失” |
| CONTRADICTION | 两个以上来源事实或与配置工况存在不一致 | 分别列出证据+版本+单位/条件，未获工程确认不宣称具体设备不适用 |

**非事实的“置信分数”不能晋升为事实权威**。技术文本的同义复述、工业专有名词归一、工程单位转换、跨页面指代均需有可独立测试的本体/词表或人工核验，无法确定时弃判。AI 自称 `VALIDATED` 只能表示所提交形状/被执行的具体校验通过，不能作为整条自然语言语义正确性的证据。

## 5. 五类买家任务的 AI 支持边界

| 任务 | 允许的 AI 辅助 | 必须避免的越界 |
| --- | --- | --- |
| DISCOVER | 从已证据化导航/分类/应用页总结可能路径缺口及采购找货步骤 | 没抓到目录就宣称没有产品 |
| UNDERSTAND | 总结型号/技术参数/单位/资料版本；提出需要企业工程师解释的问题 | 标量满足自动推断完整工况、可靠性或安全性 |
| TRUST | 区分企业公开声明、证明材料和真正独立验真所需条件 | 声称证书真伪、工厂资质或法人已核验 |
| INQUIRE | 分析产品到联系页只读链路、RFQ所需字段与买方待补数据 | 把 Contact link 当成询盘已提交或送达 |
| SEARCH_TECHNICAL | 对已观察抓取/元数据/渲染证据提出技术复核清单 | 声称谷歌收录、排名、真实流量或转化增长 |

五维可由规则优先逐项展示，AI 不允许用一个整站分数覆盖未检查、ACCESS_BLOCKED 或 NOT_APPLICABLE。

## 6. 处置状态、模型安全与费用

- `NO_MODEL/NOT_RUN`：默认状态。确定性业务链可继续并显示 AI 未运行。
- `CANDIDATE_UNTRUSTED`：模型返回后先经结构、同源引用和逐 claim 语义强约束；不得直连报表批准、分享、VF销售或L2M。
- `REJECTED/AI_INVALID`：原证据不存在、非法引用、伪认证/虚构金额、命令注入、坏 JSON/非有限数值、超长/PII、未知价格、越权/到期等 → 拒绝，不静默“修补”为事实。
- `HUMAN_REVIEW_REQUIRED`：不能独立验证的假设/改造建议；Reviewer 原因与修改形成追加决策及新报告版本。
- 超时、取消、模型服务异常、token消耗无法核对、同operation重复派发：有界记录，费用不明不记零；不得按一次模型成功覆盖已存在的原生诊断证据。

必须保存 `provider/model/prompt_version/price_snapshot/usage/retention/operation_id`（仅获批准后），模型密钥不入页面、日志、报告或 Git；持久 ledger 的幂等/重放与人工审核账本分别验证。

## 7. S3 可证伪验收（S1 只冻结要求）

1. **事实闭环**：逐个客观输出的原生证据/定位可重放；指向不存在的引用、跨 run、坏单位和无来源损失事实均拒绝，严重事实虚构=0。
2. **模型与无模型对照**：同一合法来源/IndustryPack/Gold，规则-only 与 AI-assist 的版本、审阅工时、误报率、专业建议有用性、弃判率分别报真实分母；不承诺 AI 必然优于确定性规则。
3. **扰动/对抗**：网页内包含“忽略规则/发邮件/改审核状态/泄漏凭据/调用外网”等指令、版本污染、恶意 URL、长文本、矛盾字段、伪证书、不可观察后台。模型不能获得工具权限；所有高风险客观事实拒绝或需真人审核。
4. **费用/隐私/恢复**：未批真实供应商、数据地区、用途、价格或费用上限时实际外部模型调用=0；已准实验需预算停止、保留最小数据和审计；失败后无模型报告仍完整。
5. **业务**：AI 提议不能自行生成 E2/E3、正式报价、对外分享、自动建站或资产使用授权。

本次 **S1 验收只看以上规范是否清楚、与现有合同兼容及矩阵可追溯**。真实 AI Provider、跨页解释效果、Gold/费用实测分别属于 S3/A15–A19，不能因为本文件存在就标完成。

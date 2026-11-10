# VRAE 开发总计划 V1.1｜从架构到可验收商业产品

> **文档状态：开发计划候选，已整理入仓库；本轮不启动 RA-0，不表示任何任务已经实现。**
>
> 编制日期：2026-11-10 ｜ 仓库：gloweaseco-leo/VRAE ｜ 优先服务对象：VEYFRONT
>
> 上位文件：[产品纲领](../00-product/PRODUCT_CHARTER_V1.1.md) / [应用架构](../01-architecture/SYSTEM_AND_APPLICATION_V1.1.md) / [数据架构](../01-architecture/DATA_ARCHITECTURE_V1.1.md) / [接口契约](../01-architecture/INTEGRATION_CONTRACTS_V1.1.md) / [安全架构](../01-architecture/DEPLOYMENT_AND_SECURITY_V1.1.md) / [诊断规则](../02-domain/AUDIT_METHODOLOGY_AND_RULES_V1.1.md)

## 0. 先确定交付目标，而不是先写代码

**VRAE V1 的可用状态**：在合法许可和明确配额下，操作员可以创建 L0/L1 诊断任务；隔离 Worker 获得代表性网页证据，规则生成可追溯发现，可选 AI 给出受约束的商业解释；审核员逐项批准/退回并生成不可静默覆写的报告版本；VEYFRONT 仅在正确授权下读取已批准报告，将客户自愿的咨询交接给现有销售流程。

**首期北极星**：实际 E3 合格商机及其完全成本。**不把**“任务创建成功”“模型输出漂亮”“截图存在”“报告已分享”算作成功销售。

**第一阶段非目标**：全自动网站生成、通用 SaaS、广告和内容分发、自动陌生客户外发、完整 CRM、大规模爬虫、Agent 自由使用工具、客户未授权的私有数据检查。

**四条工程不变量**：
1. 不可信网址/页面不能影响内部网络、其它客户、生产密钥；
2. 没有可核验证据的结论永不成为客观事实；
3. 未经人工批准，报告不可对外分享；未有客户确认，报告不得被当成询盘或商机；
4. VRAE 不直接依赖 L2M 生成运行时或 Vey2GE 当前 Beta 运行时。

## 1. 交付组织与版本策略

- 一个 GitHub 仓库 VRAE，Python 模块化单体，领域/应用/基础设施分层；**API 与 Worker 分进程/容器**、不同凭据和网络规则。
- 内部 `main` 为可复现基线；每一个开发包独立 `feat/ra-NN-...` 分支与 PR，关联契约变更和证据清单。未经验收不把实验代码合并到主干。当前文档落库不代表批准代码开发。
- API 与数据契约优先：`contracts/v1`（OpenAPI + JSON Schema + 兼容性），`db/migrations`，`vrae/domain`，`vrae/application`，`vrae/infrastructure`，`worker`，`apps/api`，`tests`，`industry-packs`，`infra`。
- CI 从第一阶段建立 Python 格式/类型/依赖检查、pytest、安全测试、契约与文档链接检查；真实浏览器/DB 集成在后续阶段新增。任何 GITHUB_RUNNER_NOT_STARTED 单列 INFRA_BLOCKED，不冒充代码 PASS。
- 每个 RA 阶段结束给出：范围、变更文件、源提交 SHA、测试命令与计数、事实证据、未通过项、预算记录、风险、Go/No-Go 决策。
- 责任角色：项目 Owner（商业方向和费用）、首席架构师（合同与边界）、安全/后端负责人（执行隔离）、QA 负责人（独立负例）、商务审核人（对外报告）；同一自然人可兼任，但**审批动作和机器输出必须区分**。

## 2. 总体顺序和依赖

    架构评审（本轮，仅文档）
           |
      RA-0 契约与样本
           |
      RA-1 安全采集 + 浏览器隔离
           |
      RA-2 证据与确定性规则
           |
      RA-3 AI 辅助 + 审核报告
           |
      RA-4 持久任务、权限、内部 UI、VF API
           |
      RA-5 真实授权小样本 + 商业验证
           |
      RA-6 有限开放 + 运维与发布验收

**跨阶段依赖**：RA-1 必须使用 RA-0 SourcePolicy；RA-2 必须引用 RA-1 的不可变证据；RA-3 不得绕过 RA-2 的规则事实；RA-4 只能分享 RA-3 审核通过的精确版本；RA-5 需 RA-4 的权限与故障回归；RA-6 需 RA-5 商业批准。部分 UI 原型可提前并行，但不能提前宣称通过后续门禁。

## 3. 工作包详细说明

### RA-0｜合同、规则数据与安全合成样本（**尚未启动**）

**目标**：任何人能只凭合同、合成样本和规则知道引擎必须做什么，不依赖模型推断需求。

| 子包 | 主要开发项 | 预期文件/工件 | 退出门禁 |
| --- | --- | --- | --- |
| RA-0A | 冻结 AuditRequest、SourcePolicy、AuditRun、PageSnapshot、Evidence、Observation、Finding、ReportVersion、ReviewDecision、ShareGrant、UsageRecord | contracts/v1/*.schema.json；openapi.yaml | 全部 schema 通过格式及正反例校验 |
| RA-0B | 明确 L0/L1/L2 授权边界、URL/配额、终态、租户和角色矩阵 | vrae/domain/*、tests/contracts/* | 越权/失效授权/未知来源均拒绝；状态转移可测 |
| RA-0C | 设计合成站型和攻击输入；给 16 条候选规则制定适用性与 false positive 测例 | tests/fixtures/sites/*；tests/fixtures/security/*；industry-packs/* | 最少 20 项人工标注基线，含至少 10 项异常/拒绝场景 |
| RA-0D | 建立基础工程模板和基础 CI，不触碰生产连接 | pyproject.toml、GitHub Actions、Dockerfile 开发版 | 本地与 CI 命令一致，依赖可锁定 |

**硬门禁**：必须通过架构 Owner 签署的合同/权限/安全审阅后才能开发外部网站抓取。不可因为已有 L2M 函数就跳过。

### RA-1｜安全采集与受控页面观察

**前置**：RA-0 PASS。

| 子包 | 主要开发项 | 预期工件 | 退出门禁 |
| --- | --- | --- | --- |
| RA-1A | 审核 L2M 抓取模块的许可证、依赖、源 SHA；最小提取 url_fetch/discovery，不复制生成器 | vrae/collection/*、THIRD_PARTY_CODE_PROVENANCE.md | 来源可追踪；独立安全测试通过 |
| RA-1B | URL/DNS-IP 绑定、跳转/同域/资源策略、robots/礼貌抓取、限制和阻断列表 | SourcePolicy 执行器、出网防护配置 | SSRF/metadata/重绑定/IPv6/跨域/无权限 100% 阻断 |
| RA-1C | 代表页抽样：首页、目录、分类、产品、应用、About、Contact；HTTP 与页面角色归档 | CaptureManifest、PageSnapshot | 执行范围、时刻、状态、哈希和失败原因可重放 |
| RA-1D | 隔离 Playwright 浏览器：仅对允许页面采集 DOM/桌面手机截图；禁止提交/购买/登录 | worker/browser/*、截图证据 | 浏览器网络 egress、403、POST、WebSocket、下载、崩溃负例通过 |

**停止条件**：DNS 绑定无法证明或浏览器可访问内网 → SECURITY_NO_GO；不能靠“只在测试环境跑”降低门槛。只读 HTTP 与 Playwright 是分开验收的。

### RA-2｜证据仓与确定性诊断

**前置**：RA-1 PASS；允许先使用本地固定合成证据。

| 子包 | 开发项 | 预期工件 | 退出门禁 |
| --- | --- | --- | --- |
| RA-2A | Evidence Snapshot 不可变引用、定位符、哈希、采集覆盖率、UNKNOWN/ACCESS_BLOCKED 分类 | vrae/evidence/*、EvidencePack | 证据源可追踪且哈希可核实 |
| RA-2B | 实现 5 个买家任务、16 条规则的版本化接口；优先实现有可测证据的子集 | vrae/rules/*、rulepacks | 每条已启用规则具有正反例及适用性 |
| RA-2C | Observation → Finding 的可复核映射，区分客观缺陷、可改善机会与数据未知 | FindingBuilder | 没有证据不得输出事实；无法观察不自动 FAIL |
| RA-2D | 建立人工 gold-label 评估器，不仅是快照对比 | tests/benchmark/* | 至少 5 种不同站型；报告已检范围、错判和未知率 |

**质量目标（试点阈值，非现状）**：有许可的 5 类代表站型中，合理覆盖代表性页面；已标注问题的 precision 目标 ≥90%，客户可见严重虚构 = 0。阈值达不到不得交给陌生客户。

### RA-3｜证据约束 AI 与人工报告审核

**前置**：RA-2 可输出经规则验证的结构化 Evidence/Finding。

| 子包 | 开发项 | 预期工件 | 退出门禁 |
| --- | --- | --- | --- |
| RA-3A | 可替换的 ModelGateway，供应商配置、数据脱敏、预算预留、token/cost 账本 | vrae/intelligence/* | 超额/未知消耗拒绝；无密钥泄露 |
| RA-3B | 固定 JSON Schema，evidence_id 必须真实存在且语义支持 claim；prompt injection 防护 | model_output.schema.json、回归集 | 注入/虚构/无依据 claims 被拒绝，不被静默修复为事实 |
| RA-3C | L1 报告编辑与验证，最多 3 个问题；事实、推断和建议分层 | report renderer、version hash | 报告事实 100% 可点击追溯 |
| RA-3D | Reviewer/Owner 的 approve/revise/reject；审批绑定内容哈希和规则/模型版本 | ReviewDecision 和审批 UI/API 原型 | 未审核不得分享；旧版本批准失效 |

**预算默认建议**：L0 模型 0；L1 单站模型上限候选 ¥2，最多一轮生成和一轮有界修复；包括浏览器/人工的实际成本独立统计。尚未确认模型和费率不得标记已控制成本。

### RA-4｜持久运行时、权限、界面与 VEYFRONT API

**前置**：RA-3 报告可由内部真实身份审核、不可误分享。

| 子包 | 开发项 | 预期工件 | 退出门禁 |
| --- | --- | --- | --- |
| RA-4A | PostgreSQL 迁移、租户/角色/RLS、持久队列/租约、对象存储、备份恢复 | db/migrations、integration tests | 真实数据库跨租户访问拒绝；备份恢复一致 |
| RA-4B | FastAPI 审计请求/状态/审核/分享授权/取消，版本化错误与幂等 | apps/api、OpenAPI、contract tests | 202 仅在真实持久化后返回；重复任务防重 |
| RA-4C | 内部任务池、证据核对、审核报告、成本追踪工作台 | Internal Operator Console | 真实浏览器端到端流程通过 |
| RA-4D | VEYFRONT BFF → VRAE server-to-server 合同适配；本人报告认证、过期撤回 | vf-adapter 示例和集成测试 | 不向浏览器暴露服务密钥；无越权读取 |
| RA-4E | 失败恢复：重试幂等、Worker SIGKILL、队列死信、任务取消、Outbox 失败 | recovery tests、ops runbook | 生产候选环境实测，不能仅靠合成 mock |

**注意**：RA-4 仅受保护预览，不直接替换 VEYFRONT 官网。是否新增客户入口是后续产品审批；不承诺客户直接输入 URL 即自动得到公开报告。

### RA-5｜真实授权样本及商业价值验证

**前置**：RA-4 安全/存储/审核/访问保护达到允许真实数据的标准。

- 选择 10–15 个可合法检查的不同 B2B 站点，事先明确来源政策、访问节制与禁区。
- 生成并人工审阅至少 3–5 份 L1；记录每条问题的真实误报、证据质量、是否具有可执行性、平均审核耗时。
- 对自愿沟通或经审批的一对一商务联系，记录实际回应和业务反馈；未经批准不得自动外发详细报告。
- 在 VEYFRONT 中记录咨询 E2、经责任人确认的 E3；绝不把诊断完成冒充 E3。
- 建立模型/浏览器/人工/触达四本账，计算真实完成报告成本和合格商机成本；E3=0 时成本/商机为 null。
- **GO 判定**：产品能否促成具体有效沟通、是否具备可承受的综合成本和业务承接能力。工程 PASS 但商业无实效，标 COMMERCIAL_NO_GO。

### RA-6｜有限开放与运维闭环

**前置**：RA-5 商业验证通过且运营主体授权正式开放。

- 配置诊断申请额度、反滥用、许可与隐私文本、域名阻断/退出机制、任务总预算熔断。
- VEYFRONT 官网按分支预览 → 真机/微信内浏览器 → 受控发布；公开入口与内部诊断业务解耦。
- 生产 DB/存储隔离、备份恢复、告警/日志审计、审查值班与撤销流程；发布回滚经真实操作验收。
- 监测诊断可靠性、误报、成本、E2/E3、报价与成交，形成每周人工可审阅报表。
- **GO 判定**：安全、工程、商业、隐私、运营责任人五类签署同时成立；单个指标改善不可替代整体验收。

## 4. 三条关键开发链要并行、但不互相拖累

| 工作流 | 负责内容 | 不能抢先突破的边界 |
| --- | --- | --- |
| C1 Evidence & Audit Core | URL 采集、浏览器、证据、规则、模型校验 | 从 RA-0 开始，安全通过后才可实网 |
| C2 Product & Operation | 审核 UI、版本、授权、报告、商业交接 | 可先做合成 UX，但真实客户只在 RA-4+ |
| C3 Integration & Reliability | 数据库/队列/回放、VF Adapter、日志/预算/监控 | 必须遵循已冻结合同，不能提前连 Vey2GE 生产 |

Vey2GE 与 L2M 的生产 API 集成不作为 RA-1–RA-4 的关键路径；L2M 交付链路只在授权签约后运行。

## 5. 合成样本与测试矩阵（最低门槛）

- URL 安全：私网/回环、metadata、DNS 重绑定、重定向、IPv6、用户名口令 URL、伪装域名、恶意 HTML；
- 站型：静态英文工业站、WordPress、SPA、无产品目录、多 SKU、多语言、无 sitemap、不同产品询盘路径；
- 浏览器：受控桌面/移动截图、JS 请求限制、WAF 403、跨域 CDN、POST/下载被阻断；
- 规则：证据正常、证据不足、反证、误判、行业不适用、模型输出伪造；
- 审核：越权 Reviewer、同一版本反复批准、内容变更后旧审批、分享过期和撤销；
- 运行：并发 1、重复申请、成本预算熔断、Worker SIGKILL 恢复、对象存储部分写入、DB 回滚、跨租户；
- 商业：有诊断无回应不等于 E2，有 E2 未人工确认不等于 E3，报价必须真实审批。

## 6. 费用与阶段闸门

**资金使用顺序**：RA-0/RA-2 使用合成资料且不调用外部模型；RA-1 先沙盒环境；RA-3 真实付费探针须单独批准供应商和预算；RA-4 才为持久预览数据库/队列配置必要资源；RA-5 才允许经授权真实企业试点；RA-6 才考虑公网自助规模化。

不要将参考 ¥2 模型预算误作为整站成本，必须包含 CPU、Chromium、模型重试、审核人工、触达和失败任务。

## 7. Codex 执行任务单模板

每轮开工前复制以下字段到 PR 描述或任务单：

- 工作包 ID / 目标 / 当前冻结文档版本：
- 输入证据与前置 PR / 精确 commit SHA：
- 本轮明确可修改的路径和禁止路径：
- 实现接口与 JSON Schema 版本：
- 安全/权限/数据范围与允许的外部网络、模型和费用：
- 需要编写的合成正例、反例、真实集成测试：
- 必须提供的测试命令、日志、截图或数据库验证证据：
- 成功门槛 / 非成功状态 / 失败即停止条件：
- 是否允许合并 main / 是否允许部署、真实外联或费用：
- 验收负责人/审批动作及结果：

**默认值：不允许生产部署、不允许真实客户外发、不允许实际费用、不允许调用第三方未批准网站。** 任何本轮之外的修复需单独报告，不自行扩大范围。

## 8. 明确的阻断项与需批准的决定

| 决定 | 何时必须确认 | 未确认时如何处理 |
| --- | --- | --- |
| L2M 底层代码的许可证、固定源 SHA 与最小提取范围 | RA-1 前 | 不复制/不运行 |
| 实网采集合法来源、robots/条款、行业样本许可 | RA-1/RA-5 前 | 仅合成数据 |
| ModelGateway 提供商、实际报价、数据区域、费用上限 | RA-3 前 | 规则引擎独立运行 |
| PostgreSQL/Queue/Object Store 的供应商和区域 | RA-4 前 | 合成数据/本地数据库 |
| 站点所有者授权、隐私与保留、商业报告发布主体 | RA-5 前 | 不触达真实客户 |
| 官网入口、限额、运营 Owner、成本预算与回滚方案 | RA-6 前 | 不发布公开申请 |

## 9. 本轮完成与未完成

本轮仅提交开发计划 Markdown，不执行任何 RA 阶段、未开发 API/Worker/DB、未触达客户、未运行模型/浏览器、未部署。正式开始开发必须有用户批准和目标工作包定义。

详见 [阶段验收与发布门禁](ROADMAP_AND_ACCEPTANCE_V1.1.md)。

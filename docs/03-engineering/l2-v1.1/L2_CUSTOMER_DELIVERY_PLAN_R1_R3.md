# VRAE V1.1｜L2 客户交付实施计划（R1–R3）

> 状态：OWNER 方向已确认（2026-11-21），交开发团队实施。
> 性质：V1.1 增量执行计划。不修改产品纲领、五维、16 条规则、SourcePolicy、Evidence/Guard、报告与审核权威，也不修改 B5A 精确 pin 的上位文件。
> 代码基线：`main@95d6df9`（PR #189 合并后）。
> 上位依据：[L2 纲领补充](L2_V1.1_CHARTER_SUPPLEMENT.md)、[A01–A27 验收矩阵](L2_V1.1_ACCEPTANCE_MATRIX.md)、[S1 规则/Gold/预算规范](S1_RULE_QUALITY_BUDGET_SPEC_V1.1.md)、[S1 AI 采购推理规范](S1_AI_BUYER_REASONING_SPEC_V1.1.md)、[S1 VF 交接规范](S1_VEYFRONT_REBUILD_HANDOFF_SPEC_V1.1.md)。

---

## 0. 目标与成功标准

### 0.1 唯一目标

在约 6 周内，向 3 个真实试点网站的企业，各交付一份**经真人审核的 L2 报告**，经现有正式通道（`report-authority`，`formal_human_review=true`，定向 ShareGrant）由 VF 呈现给客户。

L2 报告是三件套，来自同一份真实采集工件：

1. 执行摘要（1–2 页）；
2. 可回放到原证据的深度报告；
3. 改造蓝图（工作包）。

### 0.2 客户验收的六个问题

每一版报告都由首席客户体验负责人按以下六个问题通读验收。六个都答得出来才算可交付：

| # | 客户的问题 | 报告必须给出 |
| --- | --- | --- |
| Q1 | 买家在我网站上卡在哪？ | 按采购阶段组织的判断，而不是规则编号 |
| Q2 | 证据是什么？ | 每条判断可打开原页面、定位原文 |
| Q3 | 该改什么？ | 目标页面与具体动作 |
| Q4 | 需要我提供什么？ | 企业需补的资料清单 |
| Q5 | 改完怎么验证？ | 复验方法（哪条检查重跑、看什么结果） |
| Q6 | 这次没看到什么？ | 覆盖范围、未测项目、未知项，明确不算缺陷 |

### 0.3 衡量方式（替代规则数量与 CI 通过率）

- 3 个试点站的报告在 Q1–Q6 上的通读结论（每周一次）。
- 五个采购环节中，给出明确判断（通过 / 有据问题 / 写明原因的不判）的比例；目标是不再出现笼统的「仍需核实」。
- 审核成本：每份报告审核人耗时、AI 条目采纳率与修改率。
- 严重事实虚构：0。

---

## 1. 不变量（所有 PR 必须遵守）

1. **版本隔离**：任何改变输出的改动都使用新版本号；旧版本工件重放结果逐字节不变，须有回归测试证明。
2. **采集边界**：同源公开只读；6 页委托上限；30 秒 Worker 租约；24 秒采集预算；不提交表单；不登录；SSRF/DNS/TLS/robots 检查不变。
3. **未知语义**：UNKNOWN / ACCESS_BLOCKED / NOT_APPLICABLE / 未访问 / 未测试，永远不能变成缺陷或扣分；不给无依据总分。
4. **唯一权威链**：Evidence → Guard → 原生规则 → 诊断/报告投影 → C2 账本审核 → `report-authority`。不新增第二引擎、第二报告或第二审核权威。
5. **工业六条（IND-*）不替代通用 16 条**；IndustryPack 用版本化配置扩展，不按客户域名或单站硬编码。
6. **AI**：只在租约结束后的现有 Qwen 链路运行；输出是候选，客观断言须逐条引用验证；假设与建议保持 `REVIEW_REQUIRED`；失败降级到确定性结果。不新增供应商；超出现有额度的调用需 Owner 批准。
7. **商业边界**：VRAE 内容里不出现 VEYFRONT 服务价格、工期、销售承诺；报告、点击、审核不升级为 E2/E3。
8. **数据**：真实工件原文只留在运行主机；出主机的只有脱敏差异报告与 Gold 标注包。

---

## 2. 现状基线（代码事实，开工前必读）

| 项目 | 现状 | 位置 |
| --- | --- | --- |
| 自动诊断版本 | 新任务 `l2-industrial-1.0.7`；旧任务按原版本重放 | `integration/authorized_targets/worker.py`、`presentation.py` |
| 原生规则 | 仅 DISC-01/02、INFO-01、TRUST-01、CTA-02、SEO-01 出结果；CTA-01 只有「静态链接存在、可见性未知」 | `vrae/rules/execution.py`、`patch_execution.py`（最新 `ra2b6-1.0.5`） |
| 其余 10 条 | 有 S2 候选投影，`native_fact_admission: NONE`，不进原生结果 | `vrae/rules/s2/`、`integration/authorized_targets/buyer_review.py` |
| 工业候选提取 | INFO-02/TRUST-02/TRUST-03 依赖合成标签（`Data revision`、`Entity identifier` 等），真实站点基本全为 UNKNOWN | `industry-packs/l2-industrial-v1/s2-1.1.0.json` |
| 真实页面产品事实 | 通用产品事实提取 + 采购配置 `1.1.0`（含 `abrasive_wheel`） | `vrae/rules/product_facts.py`、`vrae/industry/l2_v1/procurement.py`、`procurement-1.1.0.json` |
| 信任子事实 | 声明名称、自述、静态联系链接等 | `vrae/rules/trust_facts.py`、`trust_context.py` |
| 表单静态事实 | 字段语义枚举，不提交 | `integration/authorized_targets/form_facts.py` |
| HTTP 量化 | 每页单次测量：connect / TLS / 首字节 / 整体耗时、字节数、跳转、状态码，已入证据链 | `CaptureManifest.pages[].http_measurement`、`fact_review.py` |
| 选页 | 按角色轮取 HOME→CATALOG→CATEGORY→PRODUCT→CONTACT→ABOUT→APPLICATION；自适应补查最多 2 页 | `vrae/collection/discovery.py::select_next` |
| AI | 真实 Qwen 已接入自动预诊断，提示词 `qwen-purchase-clarification-1.5.0`，最多 2 条澄清 | `vrae/intelligence/qwen/provider.py`、`session.py` |
| 原生 L2 文档 | 真实工件中已生成 `native_document.findings` 与 `blueprint` | `worker.py`、`vrae/l2/native.py`、`native_business.py` |
| 执行摘要 | 六类分组 D1–D6 投影已存在；D1 目前只接受 404/410 | `vrae/l2/executive.py` |
| 正式通道 | `report-authority` + C2 账本 + `VerifiedNativeSource`；仅合成身份演练过 | `integration/authorized_targets/report_authority.py`、`report_api.py`、`vrae/l2/ledger.py`、`checks/verified_report_drill.py` |
| 预诊断判断 | `judgment`（`vrae.diagnosis-judgment.v1`） | `docs/03-engineering/automatic-diagnosis/customer-judgment/README.md` |
| Gold | 0/26，评分工具已有 | `tests/benchmark/human_gold.py`、`s2_quality.py` |
| 浏览器 | 自动诊断路径无浏览器 | — |

---

## 3. 职责边界

| 角色 | 负责 | 不得 |
| --- | --- | --- |
| VRAE（本仓库） | 专业诊断内容权威：事实、问题类型、证据、买家影响假设、改善建议、限制条件、审核状态、经审核的正式报告正文（以内容单元交付） | 承诺 VF 的服务、价格、工期、销售结果 |
| VEYFRONT（VF 团队） | 客户沟通与商业体验权威：品牌表达、信息组织与排序、视觉、交互、咨询入口、服务范围解释、商务承接 | 强化或弱化诊断判断；改变问题类型；把待核实项并入已证实项；自写诊断结论句 |
| 审核人（Owner 指定） | 对每份正式报告逐条专业裁决：确认 / 修改 / 驳回；批准当前版本 | 替模型重做整份诊断（若发生，视为 AI 输出不合格，回到 R2 收紧） |
| 决策清单签字人（Owner 指定） | 签署各子行业的采购阶段信息需求清单 | — |
| Owner | 试点站点、审核人身份、AI 费用上限、第三方性能测量、委托页数 | — |

---

## 4. 版本与命名约定

- 每个改变输出的 PR 新增版本，不复用旧版本号。建议序列（实施时可按实际 PR 顺序递增，但必须单调、互不复用）：
  - 诊断版本：`l2-industrial-1.0.8` 起；
  - 原生执行器：`ra2b6-1.0.6` 起（沿用 `patch_execution.py` 的叠加方式）；
  - 采购配置：`procurement-1.2.0` 起；
  - 采购阶段清单：`buyer-stages-1.0.0` 起（新文件，见附录 A）；
  - AI 提示词：`qwen-l2-buyer-reasoning-1.0.0`（见附录 B）；
  - 内容单元契约：`vrae.report-content-units.v1`（见附录 C）；
  - 预诊断判断：`vrae.diagnosis-judgment.v2`。
- Worker 只对带 `automatic_result` 标记的新计划选择最新诊断版本；旧定向和受控任务保留原默认。
- 每个版本的变更写入 `docs/03-engineering/automatic-diagnosis/<topic>/README.md`，沿用现有目录惯例。

---

## 5. 规则准入级别（交付语义）

| 级别 | 条件 | 未审核预诊断（`/diagnosis`）中的呈现 | 正式报告中的呈现 |
| --- | --- | --- | --- |
| L-A 候选 | 现有 S2 投影 | 仅作「待复核线索」 | 审核人可采纳为条目 |
| L-B 原生启用 | 进入原生执行器；正例、反例、UNKNOWN/BLOCKED/NA 例、强制反例齐全；逐条可回放 | PASS 为正向事实；FAIL 显示为「有据待复核」，不进 `confirmed_obstacles` | 审核人确认后成为「已证实」 |
| L-C 可确认 | 该规则在对应站型分层上有独立人工 Gold：精确率 ≥ 90%，严重虚构 0 | FAIL 可进 `confirmed_obstacles` | 同上 |

本计划交付目标只要求新规则达到 L-B；正式报告的「已证实」由审核人逐条确认。L-C 在并行线 P1 中积累。

---

## 6. 工作包

估时为开发人日，含测试与文档，不含 Owner 审批等待。

### R1：五个环节都有判断（第 1–3 周）

#### WP-R1-0 试点重放与选页模拟工具（2–3 天）

**目的**：作为每个版本的测试手段，不是独立的基础设施阶段。

- 新增运维脚本 `scripts/pilot_replay.py`，只在运行主机执行，只读：
  - 输入：`audit_ref`、目标诊断版本；
  - 输出：脱敏差异 JSON 加一份 Markdown 摘要，内容包括每条规则的新旧结果与原因码、五环节判断分布、覆盖计数、报告条目数。
- 选页模拟：用工件中已保存的候选清单（inventory），离线模拟新选页策略会选哪些页面。只模拟，不发请求。
- 脱敏规则：不输出原始 HTML、联系方式、表单值；供方页面原文引用默认只输出哈希，带 `--include-public-quotes` 参数时才输出公开页面短引用，并记录导出审计行。
- 旧版本重放必须与历史回执逐字节一致，否则脚本以非零退出码失败。

**验收**：beherohome 工件在主机上完成新旧版本对比；导出文件无原始 HTML 和联系方式（用测试断言检查）。

#### WP-R1-1 采购阶段信息需求清单（核心资产，4–5 天）

**目的**：把「有没有」类检查变成「买家在当前阶段能否完成任务」的判断。

- 新增 `industry-packs/l2-industrial-v1/buyer-stages-1.0.0.json`，结构见附录 A。每项包括：采购阶段、买家问题、网站角色（`DISCOVERABLE` / `PUBLISH` / `CLARIFY_CHANNEL`）、适用条件、关联的采购配置字段组、缺口条件、明确不算缺口的情况、所需页面角色。
- 新增 `vrae/industry/l2_v1/buyer_stages.py`：加载、校验（JSON Schema 闭合）、计算配置哈希；每次诊断把清单版本和哈希写入结果。
- 签字：清单含 `approval` 块（签字人、时间、清单哈希）。没有有效签字时，所有条目只能输出 `REVIEW_REQUIRED`，不得产生缺口判断。
- 首个子行业：按 VF 线索分布确定。分布到位前，用砂轮起草（附录 A 示例），但不得发布到客户结果。
- 判断输出（每条清单项）：
  - `SOURCE_AVAILABLE`：已公开资料能支持该阶段任务；
  - `GAP_WITH_EVIDENCE`：仅限 `PUBLISH` 角色，且须同时满足：产品页完全解析、参数区存在、该项配置字段缺失、该页无指向未解析技术资料（PDF / Datasheet）的链接、清单适用；
  - `CLARIFY_ROUTE_RECORDED`：`CLARIFY_CHANNEL` 角色，已记录从产品页到咨询入口的静态路径（复用 CTA-02 和表单静态事实），并说明可带入的产品字段；
  - `CLARIFY_ROUTE_UNKNOWN`；
  - `UNKNOWN`（附原因码）；
  - `NOT_APPLICABLE`。
- `CLARIFY_CHANNEL` 项永远不得输出 `GAP_WITH_EVIDENCE`。「需要供方确认的信息」不等于「网站必须公开的信息」。

**测试**：每个判断值都有正例和反例；强制反例覆盖以下情况，均不得出现 `GAP_WITH_EVIDENCE`：有 PDF 链接、参数表解析歧义、清单未签字、工况组合类问题。

**验收**：砂轮草案在 beherohome 工件上：「结合剂/粒度组合」落入 `CLARIFY_ROUTE_*`，不是缺口；尺寸、磨料、粒度、结合剂的公开项为 `SOURCE_AVAILABLE`。

#### WP-R1-2 INFO-02 原生启用（3–4 天）

- 在新执行器版本中，以 WP-R1-1 的清单判断为依据启用 INFO-02，替代 S2 合成标签路径（S2 路径保留，不删除）。
- 映射：`GAP_WITH_EVIDENCE` → `FAIL_WITH_EVIDENCE`；全部适用的 `PUBLISH` 项为 `SOURCE_AVAILABLE` → `PASS`；其他 → `UNKNOWN` / `NOT_APPLICABLE`，并附原因码。
- 观察的 `coverage_note` 写明：只覆盖本次打开的产品页、不判断工程适配、不判断全站。

**验收**：3 个试点工件重放差异；旧版本逐字节不变。

#### WP-R1-3 TRUST-03 与 TRUST-02 通用化原生启用（4 天）

- **TRUST-03 主体与联系一致性**：基于 `trust_facts` 已提取的声明公司名、邮箱、电话，比较 About、Contact、页脚之间是否一致（规范化后精确比较，不做模糊合并）。
  - 两页及以上一致 → `PASS`；
  - 存在冲突 → `UNKNOWN`，原因码 `CONFLICT_REVIEW_REQUIRED`，列出冲突两处的引用；
  - 不足两页 → `UNKNOWN`。
  - 不做法人核验；同名不同主体不合并；不输出 FAIL。
- **TRUST-02 证明资料上下文**：在 About、证书、案例页主内容区，记录供方声明的证书或案例，以及能读到的发证方、编号、日期；接入自适应补查的 `PROOF_CONTEXT` 页面。
  - 记录到声明 → `PASS`（含义仅为「声明上下文已记录」）；
  - 否则 → `UNKNOWN`。
  - 真伪一律为 UNKNOWN；证书过期日早于观察日只记录比较事实，不判「无资质」；不输出 FAIL。

**验收**：beherohome「核对企业资料」环节从「仍需核实」变为具体的一致性事实与声明清单。

#### WP-R1-4 技术访问事实：TECH-01、SEO-02 原生启用与报告章节（4 天）

- **TECH-01**：先补证据引用缺口（readiness 记录的「非 200 页面没有可引用证据」）。新增元数据引用：`source_ref` + `/pages/{i}` + 清单哈希，用独立闭合扩展契约 `collection/extensions/MetadataCitation.schema.json`，参照 `AdaptiveInvestigation` / `HttpMeasurement` 的做法，不改冻结基础契约。
  - 关键页最终 200 → `PASS`；
  - 已采集页面上的站内链接指向 404/410 → `FAIL_WITH_EVIDENCE`；
  - 5xx 为单次样本 → `UNKNOWN`，原因码 `TRANSIENT_NOT_PROVEN`；
  - 401/403/429/WAF → `ACCESS_BLOCKED`；
  - 跳转链长度只记录事实，不判失败。
- **SEO-02**：晋升 `vrae/rules/s2/static.py` 逻辑：产品名称或描述出现在静态 HTML 主内容区，且有站内静态链接指向该产品页 → `PASS`；内容依赖脚本渲染 → `UNKNOWN`，不判 FAIL。
- **报告章节「技术访问事实」**（预诊断投影与 L2 报告共用的数据）：
  - 每个关键页：状态码、跳转、HTML 字节数、首字节耗时、整体耗时；
  - 固定说明：从 VRAE 测量点进行的单次测量，包含调度开销、不含 DNS，不是用户真实体验，不是评分；
  - 固定说明：「渲染性能（如 LCP）与移动端体验本次未测试，技术健康评价尚未完成」，除非 P2 已提供测量。

#### WP-R1-5 按买家任务选页（3 天，含试点验证）

- `select_next` 增加新模式参数，旧行为保持默认。新模式在 6 页内的优先顺序：HOME → 产品分类 → **2 个不同分类的产品页** → CONTACT → ABOUT/证书页；APPLICATION 仅在清单要求时优先。
- 先用 WP-R1-0 的离线模拟，在 3 个试点工件上证明新策略会选到更有用的页面，再在新计划/授权中启用。
- 真实验证需要新的授权采集（客户经现有入口提交网址并勾选）。不重抓未授权站点。
- 若试点证明 6 页不足，由 Owner 决定是否签发 8 页委托（方法论 L1 硬上限为 8）。代码不自行提高上限。

#### WP-R1-6 覆盖说明与判断 v2（3 天）

- 在现有 `page_scope` 上补齐：
  - 选中角色与理由；
  - 已观察角色；
  - 未覆盖角色及原因码：`UNSELECTED` / `LIMIT_REACHED` / `ACCESS_BLOCKED` / `UNSUPPORTED_FORMAT` / `EVIDENCE_INSUFFICIENT` / `NOT_APPLICABLE`；
  - 每条规则覆盖的分子与分母。分母为事先确定的应检查角色，不按抓到的页数倒推。
- `vrae.diagnosis-judgment.v2`：
  - `unjudged` 改为按启用规则集计算；
  - 新增 `evidenced_pending_review`，收 L-B 规则的 `FAIL_WITH_EVIDENCE`；
  - `confirmed_obstacles` 只收 L-C 规则；
  - 五环节按采购阶段输出。
- 更新 `api_contract.py` 与参考消费端（`consumer/reference.mjs` 等），同步测试。

**R1 退出**：3 个试点站的预诊断，五个环节都有明确判断；Q1、Q2、Q6 通读通过；全部旧版本重放不变；双 Python（3.11 / 3.13）回归通过。

### R2：L2 三件套、AI 深度推理、内容单元（第 3–5 周）

#### WP-R2-1 真实工件原生文档盘点（2 天，先做）

- 用 WP-R1-0 在 3 个试点工件上导出 `native_document.findings` 与 `blueprint` 的结构与条目统计（脱敏）。
- 结论二选一：
  1. 现有结构可直接承载 R1 的新判断 → 增量扩展；
  2. 不成形 → 在 `vrae/l2/native_business.py` 中以 R1 判断为输入重组，仍走同一账本与 `VerifiedNativeSource`。
- 禁止另起报告对象。

#### WP-R2-2 三件套组装（5 天）

- **执行摘要**：扩展 `vrae/l2/executive.py`（新版本，`l2-executive-2`），六类映射：

  | 分组 | 来源 |
  | --- | --- |
  | D1 已证路径阻碍 | TECH-01 404/410；DISC/CTA 有据失败 |
  | D2 资料组织改善 | INFO-02 `GAP_WITH_EVIDENCE`；清单 `PUBLISH` 缺口 |
  | D3 工程与资质待核 | TRUST-02 声明；`CLARIFY_CHANNEL` 项；TRUST-03 冲突 |
  | D4 买方 / 企业待补输入 | 清单要求但页面未见、需企业提供的资料 |
  | D5 未观察与访问受限 | 覆盖说明；技术未测项；ACCESS_BLOCKED |
  | D6 商业影响假设 | AI 假设与审核人校准，不量化损失 |

- **深度报告**：按采购阶段组织（筛选 → 比较 → 确认 → 询价），每条按附录 D 的六段结构；附「技术访问事实」与「覆盖说明」章节。
- **改造蓝图**：每个工作包包含影响的采购阶段、绑定的判断与证据、目标页面、页面或资料动作、企业需补资料、责任方（企业 / 待 VF 确认）、前置依赖、复验方法（重跑哪条检查、期望结果）、标准或需定制评估候选。不含价格和工期。
- **没有缺陷的报告**同样成立：走得通的环节、本次未看到的范围、建议企业先准备的资料。

#### WP-R2-3 AI 跨页买家推理（6 天）

- 在现有 `vrae/intelligence/qwen/provider.py` / `session.py` 中新增提示词 `qwen-l2-buyer-reasoning-1.0.0`，不新增供应商或编排器；仍在租约结束后运行。
- 输入：脱敏结构化事实、清单判断、规则观察、引用 ID；不发送原始 HTML、URL、联系方式。
- 输出四种类型，结构见附录 B：
  1. `CROSS_PAGE_CONFLICT`：必须引用两处原证据；
  2. `MATERIAL_RELATION`：资料之间的关系或不一致，例如列表页与详情页参数；
  3. `BUYER_QUESTION`：有价值的采购问题；
  4. `IMPROVEMENT_BASIS`：改善依据。

  每条分开写出已确认事实、推理假设、反证、需人工确认事项。
- 送审前机器筛选：Guard 逐条引用核验；去重；无证据支撑的丢弃；按证据强度排序，截断到上限 K（配置项，试点初值 8）。
- 调用预算：目标每份报告 1 次调用，使用现有共享额度。需要多次调用时，必须先有 Owner 批准的单份费用上限，否则不启用。
- 失败、超时、费用未知 → 降级到确定性报告，状态 `AI_UNAVAILABLE`，不伪装完成。

#### WP-R2-4 AI 接入 L2 链路与真实模型端到端验证（3 天）

- 把通过校验的 AI 输出，作为待审候选（AIInterpretation 候选，`REVIEW_REQUIRED`）接入 L2 报告草稿，与确定性事实分层存放，绑定同一工件哈希、提示词版本、模型版本和用量回执。
- **明确验收项**：在一个试点工件上，用真实 Qwen 跑通「采集 → 预诊断 AI → L2 草稿候选 → 审核界面可见」。真实用量记入现有账本。做到之前，文档和报告不得宣称 L2 AI 已完成（对应 A15、A16）。

#### WP-R2-5 内容单元契约与 VF 接口（4 天）

- 新契约 `vrae.report-content-units.v1`（附录 C）：每个单元有 `unit_id`、分组（D1–D6）、判断强度、中英文本、证据绑定、限制条件、审核状态、`content_hash`。
- 判断强度枚举：`CONFIRMED_BY_REVIEW` / `EVIDENCED_PENDING_REVIEW` / `HYPOTHESIS` / `UNKNOWN`。
- 参考消费端扩展校验：VF 按 `unit_id` + `content_hash` 引用；可以重排和分组；不得改变强度、分组或文本语义，不得把非 `CONFIRMED_BY_REVIEW` 单元呈现为已证实。延续现有禁用语与优先改造标记校验。
- 商务区（服务范围、价格）由 VF 单独标识，不与内容单元混排为诊断结论。

**R2 退出**：3 个试点站各有完整三件套草稿；Q1–Q6 通读通过；AI 条目在内部预审中有明确的采纳或驳回分布；WP-R2-4 真实模型端到端通过。

### R3：真人审核与正式交付（第 5–6 周）

#### WP-R3-1 真实报告审核流程（4 天）

- 在现有 C2 账本受控审核上处理真实工件：逐条确认、修改或驳回；修改生成新版本；批准当前 `content_hash` / `display_hash`；置 `formal_human_review=true`；定向 ShareGrant；VF 经 `GET /v1/report-authority/audits/{audit_ref}/report` 读取。
- 审核人身份按 `report_authority.py` 的根签名身份配置接入（A22）。具体人员由 Owner 确定后再配置，代码不内置任何人员。
- 以 `checks/verified_report_drill.py` 为基础，增加真实工件的演练清单：撤权、修订后旧批准失效、错误接收者拒绝。

#### WP-R3-2 审核成本记录与修改回流（3 天）

- 每条审核记录：决定、耗时、修改前后差异分类（措辞 / 强度 / 证据 / 驳回原因）。
- 每周汇总：AI 条目采纳率与修改率；同类修改重复出现时，提出文案模板修订（新版本）。
- 审核记录同时作为 Gold 候选，进入并行线 P1。

#### WP-R3-3 VF 移交（2 天）

- 编写 `docs/03-engineering/automatic-diagnosis/l2-delivery/VF_HANDOFF.md`：内容单元字段、强度呈现规则、禁止的转换、预诊断与正式报告的区别、商务区边界、打印要求。
- 在 VF 排期不及时的情况下，VRAE 提供可直接打印的参考渲染作为兜底，不替代 VF 页面。

**R3 退出**：至少 1 份真实 L2 报告经真人批准并经 VF 交付客户；3 份为目标。

---

## 7. 并行线（不挡交付）

### P1 人工 Gold

- 来源：R3 审核记录（第一标注）加第二名同事独立标注；冲突由 Owner 裁决。不采用多数票。
- 单元：规则 × 证据（页面、时刻、适用条件）；用 `tests/benchmark/human_gold.py` 导入，用 `s2_quality.py` 按站型 × 规则 × 来源类型计分，输出 TP / FP / FN / TN、precision、recall、弃判、覆盖、严重虚构。
- 标注包在主机生成，按第 1 节第 8 条脱敏后导出。
- 某规则在对应分层达到精确率 ≥ 90%、严重虚构 0 → 该规则升 L-C。分母为 0 → `NOT_EVALUABLE`。

### P2 关键页性能测量（需 Owner 批准）

- 对每个试点站的首页、产品页、联系页，用 Google PageSpeed Insights 接口做移动端测量；有真实用户数据（CrUX）时一并记录。
- 新增窄范围采集适配器：受 SourcePolicy 约束；原始 JSON、工具版本、时间、哈希作为独立来源存入 EvidencePack（新来源类型，闭合扩展契约）；API 密钥在私有配置中；失败 → UNKNOWN。
- 涉及把客户网址交给第三方处理：须 Owner 批准，并与 VF 协调授权说明文本的新版本；未批准时报告保持第一层说明。
- 不输出「网站慢 / 快」的结论性评分；只给测量值、测量条件与对买家体验的有限解释，并由审核人确认。

### P3 后置项（本计划不实施）

浏览器渲染代表页（CTA-01 可见性、CTA-03 移动端）、INFO-03、PDF 解析、DISC-03、自动报价、L-C 之前的自动对外发布。

---

## 8. 排期与里程碑

| 周 | 里程碑 | 内容 |
| --- | --- | --- |
| 1 | M1 | WP-R1-0 工具可用；WP-R1-1 清单草案提交签字人；试点站确定 |
| 2 | — | INFO-02、TRUST-02/03、TECH-01、SEO-02 PR 逐个合并 |
| 3 | M2 | 选页新模式试点验证；判断 v2；R1 退出评审 |
| 4 | — | WP-R2-1 盘点结论；三件套组装；AI 提示词 |
| 5 | M3 | AI 端到端；内容单元契约；R2 退出评审；审核人身份配置 |
| 6 | M4 | 首份真实 L2 报告人审交付；VF 移交 |

每周五：在 3 个试点工件上运行当周最新版本，首席客户体验负责人按 Q1–Q6 通读，结论记入 `docs/03-engineering/automatic-diagnosis/l2-delivery/PILOT_LOG.md`（脱敏）。

---

## 9. PR 纪律与完成定义

每个 PR 只做一件事，PR 描述必须包含：

1. 对应 WP 编号与验收矩阵编号（A05–A26）；
2. 新版本号与旧版本逐字节重放测试；
3. 正例、反例、UNKNOWN/BLOCKED/NA 例、强制反例清单；
4. `python -m compileall -q vrae`、`ruff check vrae tests --select E4,E7,E9,F`、`mypy vrae`、`python -m pytest -q`，在 Python 3.11 与 3.13 上通过；
5. 试点工件重放差异摘要（WP-R1-0 输出，脱敏）；
6. 若改变客户可见字段：参考消费端与契约同步更新，以及给 VF 的变更说明；
7. 主题 README（沿用 `docs/03-engineering/automatic-diagnosis/<topic>/` 惯例）。

未经 Owner 审阅不合并；不部署；不访问未授权站点；不新增付费调用。

### 9.1 返工硬性要求（PR #190 复盘，2026-11-21）

PR #190 一次实现全部工作包后被整体回滚（PR #192）。原因是规则没有读取真实页面、证据引用指错页面、AI 绕过 Guard，以及在没有审阅、CI 失败的情况下合并。返工的每个 PR 额外满足：

1. **接上真实数据**：
   - INFO-02 必须读取 `product_facts` 与采购配置给出的已解析字段；
   - TRUST-02、TRUST-03 必须使用 `trust_facts` 与 `trust_context` 的子事实，不在整页原始 HTML 上做正则；
   - TECH-01 必须读取 `CaptureManifest.pages[].http_measurement`；
   - SEO-02 必须读取已解析的主内容区与静态链接。

   以「空输入恒返回 UNKNOWN」的方式通过测试，视为未实现。
2. **证据引用指向事实所在处**：每条 PASS 或 FAIL 的引用必须是发现该事实的那一页的 `evidence_ref`，并带字节范围（元数据类结论用 `MetadataCitation`）。用「第一个页面的证据」充数，一律驳回。
3. **清单由配置驱动**：行业、条目编号、字段组都从 `buyer-stages-*.json` 读取；代码里不得写死某个行业或条目编号。
4. **AI 不绕过 Guard**：新提示词的客观断言必须经过现有 `source_guard` 的引用、字面和字节范围核验；`for_evaluator` 必须明确登记新的执行器版本。
5. **切换客户路径单独成 PR**：把 Worker 的自动诊断版本切到新版本，必须是最后一个独立 PR。前提是：VF 已完成新判断契约的消费；新版本已在至少一个试点工件上用 WP-R1-0 重放；真实模型链路已验证。
6. **不改质量门禁自己的文件**：`tests/benchmark/s2_quality.py`、`tests/s2_quality/`、`integration/l2_ops/s2_quality_*.py`、`integration/l2_ops/s2_acceptance_runtime.py` 由 Owner 管理。需要调整时单独提 PR，说明理由，由 Owner 重新确定基线。
7. **测试样本贴近真实页面**：每条规则至少有一个仿真实结构的夹具，包括导航和页脚里的干扰文本、图片文件名里的 `@`、多个页面重复出现的联系方式。用来证明规则不会被页面噪声误导。
8. **分支保护**：`main` 已要求必须走 PR，36 项稳定检查必须通过，管理员同样受约束。不得以任何方式绕过。

---

## 10. 风险与对策

| 风险 | 对策 |
| --- | --- |
| 清单「网站角色」划分不准，造成新一轮误报 | 签字前不得产生缺口；`CLARIFY_CHANNEL` 永不判缺口；试点审核驳回率高的条目回到清单修订 |
| 6 页样本不够 | 先改选页策略；用试点证据申请 8 页委托；报告如实写明覆盖 |
| AI 输出变长、审核变贵 | 上限 K、证据强度排序、采纳率指标；采纳率低则收紧 |
| 预诊断 AI 与 L2 链路被误认为等价 | WP-R2-4 端到端是 R2 退出硬条件 |
| 真实工件在主机上，开发难调试 | WP-R1-0 脱敏差异与选页模拟；合成夹具覆盖同类结构 |
| VF 渲染排期滞后 | R2 结束即移交契约；VRAE 参考渲染兜底 |
| 审核人身份迟迟未定 | M3 前必须确定，否则 M4 顺延，不用 Controlled 审核冒充正式审核 |

---

## 11. Owner 决策状态

| 事项 | 状态 |
| --- | --- |
| 真实工件仅在主机重放，脱敏后用于 Gold | 已决定：同意 |
| Gold 标注人 | 已决定：内部两名同事独立标注，Owner 裁决 |
| 浏览器代表页 | 已决定：列入计划，R1–R2 后再批 |
| 首个子行业 | 已决定：按 VF 线索分布选 1–2 个（需 VF 提供分布） |
| 另外 2 个试点站 | **待定**（M1 前） |
| 审核人身份（A22） | **待定**（M3 前） |
| AI 单份报告费用上限 | **待定**（WP-R2-3 前；未定则仅单次调用） |
| 决策清单签字人 | **待定**（M1 前） |
| PageSpeed Insights 第三方测量 | **待定**（P2 前） |

---

## 附录 A：采购阶段信息需求清单结构（`buyer-stages-*.json`）

```json
{
  "version": "1.0.0",
  "profile": "abrasive_wheel",
  "procurement_config": "1.2.0",
  "approval": {"signer": null, "signed_at": null, "config_sha256": null},
  "items": [
    {
      "item_id": "AW-SCREEN-01",
      "stage": "SCREENING",
      "buyer_question": {"zh": "是否有符合我加工对象的产品？", "en": "Is there a product for my workpiece?"},
      "site_role": "DISCOVERABLE",
      "applies_when": {"profile": "abrasive_wheel"},
      "field_groups": ["usage"],
      "evidence_roles": ["CATEGORY", "PRODUCT"],
      "gap_condition": null,
      "not_a_gap": ["用途写在未解析的 PDF 中", "本次未打开的分类"]
    },
    {
      "item_id": "AW-COMPARE-01",
      "stage": "COMPARISON",
      "buyer_question": {"zh": "能否看到尺寸、磨料、粒度、结合剂以做初步比较？", "en": "Are size, abrasive, grit and bond published for comparison?"},
      "site_role": "PUBLISH",
      "applies_when": {"profile": "abrasive_wheel"},
      "field_groups": ["dimensions", "abrasive", "grit", "bond"],
      "evidence_roles": ["PRODUCT"],
      "gap_condition": "PRODUCT_FULLY_PARSED_AND_PARAMETER_REGION_PRESENT_AND_GROUP_ABSENT_AND_NO_UNPARSED_TECH_MATERIAL_LINK",
      "not_a_gap": ["参数区解析歧义", "页面链接到 Datasheet/PDF", "以图片展示参数"]
    },
    {
      "item_id": "AW-CONFIRM-01",
      "stage": "TECH_CONFIRMATION",
      "buyer_question": {"zh": "哪种组合适合我的具体工况？", "en": "Which combination fits my duty?"},
      "site_role": "CLARIFY_CHANNEL",
      "applies_when": {"profile": "abrasive_wheel"},
      "field_groups": ["grit", "bond", "usage"],
      "evidence_roles": ["PRODUCT", "CONTACT"],
      "gap_condition": null,
      "not_a_gap": ["网站未公开全部组合", "选项与尺寸编码对应关系未列出"]
    },
    {
      "item_id": "AW-INQUIRE-01",
      "stage": "INQUIRY",
      "buyer_question": {"zh": "能否顺利找到咨询入口并说明型号与需求？", "en": "Can I reach inquiry and state model and needs?"},
      "site_role": "CLARIFY_CHANNEL",
      "applies_when": {"profile": "abrasive_wheel"},
      "field_groups": ["model", "dimensions"],
      "evidence_roles": ["PRODUCT", "CONTACT"],
      "gap_condition": null,
      "not_a_gap": ["表单未提交", "送达未验证"]
    }
  ]
}
```

`site_role` 语义：

- `DISCOVERABLE`：应能被找到；
- `PUBLISH`：该阶段应公开，唯一可能产生 `GAP_WITH_EVIDENCE` 的角色；
- `CLARIFY_CHANNEL`：不要求公开，只判断澄清渠道。

## 附录 B：AI 输出结构（`qwen-l2-buyer-reasoning-1.0.0`）

```json
{
  "items": [
    {
      "type": "CROSS_PAGE_CONFLICT | MATERIAL_RELATION | BUYER_QUESTION | IMPROVEMENT_BASIS",
      "stage": "SCREENING | COMPARISON | TECH_CONFIRMATION | INQUIRY",
      "confirmed_facts": [{"text": "...", "citation_ids": ["..."]}],
      "hypothesis": "...",
      "counter_evidence": [{"text": "...", "citation_ids": ["..."]}],
      "needs_human_confirmation": "...",
      "evidence_strength": "TWO_SOURCES | ONE_SOURCE | INFERRED"
    }
  ],
  "no_items_reason": null
}
```

约束：

- `CROSS_PAGE_CONFLICT` 至少引用两个不同快照；
- `confirmed_facts` 每条须通过 Guard 引用与字面核验；
- `hypothesis` 永远是 `REVIEW_REQUIRED`；
- 禁止出现价格、排名、流失额、证书真伪、工程适配结论；
- 允许零条，`no_items_reason` 必填。

## 附录 C：内容单元（`vrae.report-content-units.v1`）

```json
{
  "contract": "vrae.report-content-units.v1",
  "report_version": "...",
  "content_hash": "...",
  "units": [
    {
      "unit_id": "cu-...",
      "group": "D1 | D2 | D3 | D4 | D5 | D6",
      "stage": "SCREENING | COMPARISON | TECH_CONFIRMATION | INQUIRY | null",
      "strength": "CONFIRMED_BY_REVIEW | EVIDENCED_PENDING_REVIEW | HYPOTHESIS | UNKNOWN",
      "text": {"zh": "...", "en": "..."},
      "evidence": [{"evidence_ref": "...", "snapshot_ref": "...", "byte_start": 0, "byte_end": 0}],
      "limits": [{"zh": "...", "en": "..."}],
      "review_state": "PENDING | CONFIRMED | EDITED | REJECTED",
      "unit_hash": "..."
    }
  ]
}
```

VF 可以：排序、分组、折叠、品牌化、在独立商务区解释服务。
VF 不可以：改写 `text` 语义、提升 `strength`、改变 `group`、合并单元、呈现 `REJECTED` 单元。

## 附录 D：单条判断的客户表达（六段）

1. **买家想做什么**：采购阶段与买家问题。
2. **在你的网站上看到了什么**：事实与证据链接。
3. **影响**：对买家完成该阶段任务的影响（假设须标明）。
4. **建议改什么**：目标页面与动作。
5. **需要你提供什么**：企业资料。
6. **改完怎么验收**：重跑哪项检查、期望看到什么。

禁用语沿用 `customer-judgment/README.md`。不出现评分、排名、流失金额、服务价格与工期。

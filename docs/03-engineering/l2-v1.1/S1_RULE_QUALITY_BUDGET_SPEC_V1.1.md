# VRAE V1.1 · S1｜五维规则、行业能力、人工 Gold 与 L2 预算验收规范

> 状态：OWNER 设计候选，DESIGN_ONLY。对应 D02/D04/D07、A05–A14/A19/A25/A27；以 V1.1 原16候选规则和既有 IndustryPack/Gold/SourcePolicy 为准。
> 工程现状起点：S0 accepted main `178d1ea4a6b11c11491a8ed71a418e6415b1fcb5`；通用规则引擎 `vrae/rules/execution.py`、catalog `industry-packs/rule_catalog.v1.json`、工业 `industry-packs/l2-industrial-v1/profile.json`、人工候选 `tests/benchmark/human_gold.py`。本文件不声称增加规则实现、真人Gold或可部署限额。

## 1. 六个必分开的质量判据

| 判据 | 分母/意义 | 不能使用的替代 |
| --- | --- | --- |
| 规则实现覆盖 | 16个已冻结规则中实际启用且有正反例者；需明示 evaluator_version/站型 | 规则在 JSON 中就算实现，工业6条当作通用16条 |
| 采集与任务覆盖 | 被选择的合法代表页面角色中获得可复核证据的项／事先确定的应检查角色 | 抓取 HTTP200 的页面数或站点总页数直接当覆盖 |
| 事实精确率 | 经独立人工Gold判定的 TP/(TP+FP)；仅针对有明确定义的正类 | 候选夹具一致率、模型自评、UNKNOWN当TN |
| 召回/弃判 | TP/(TP+FN)；unknown/blocked/unobserved独立计数并报告样本组成 | 将“不知道”误算PASS或缺陷 |
| 严重事实虚构 | 无证据却认定违法/无资质/安全不合格/实际排名收入/询盘等高风险断言的条数 | “有 evidence_id”就等于真实认证 |
| 买家/商业可用性 | 实际可理解、可复验、可由企业决定下一步的工作包/证据及人工反馈 | 更长报告、更大模型、更多截图/测试用例 |

原 V1.1 的 **Gold precision ≥90%（试点目标）和严重事实虚构0** 继续有效；没有真实且足够覆盖的人工Gold时结论 `QUALITY_NOT_EVALUABLE`，不能宣告≥90%已实现。

## 2. 通用16条规则逐项执行状态与S2交付定位

**以下状态是 S0 main 的源码审计状态；不是未来S2完成结果。** 当前 `execute(..., evaluator_version=ra2b6-1.0.0)` 对6条启用，其余规则仍会被留在目录并输出 UNKNOWN/未启用。`vrae/rules/readiness.py` 的旧 GAPS 文本是历史设计提示，不得盖过实际执行器启用分支/原生测试。

| 五维 | 规则 | 当前执行 | S2补齐的可证伪关键负例 |
| --- | --- | --- | --- |
| DISCOVER | DISC-01 首页导航→类别 | 启用/静态路径范围 | 隐藏导航/未捕获目标不能误判没有目录 |
| DISCOVER | DISC-02 类别→产品 | 启用/静态路径范围 | 同名SKU、SPA无静态路径保持UNKNOWN |
| DISCOVER | DISC-03 应用/方案入口 | 未启用 | 不适用行业不判FAIL；观察到应用页但没链接的范围区分 |
| UNDERSTAND | INFO-01 产品基础规格 | 启用/严格标签来源 | 页面声明不证明真实性、全部规格完备或工程适配 |
| UNDERSTAND | INFO-02 行业关键资料 | 通用未启用，工业包另有 IND-SPEC | 行业包未配置/有PDF未解析不能判缺参数 |
| UNDERSTAND | INFO-03 英文技术可理解性 | 未启用 | 多语言混用、同义术语与人工语义冲突需复核 |
| TRUST | TRUST-01 企业公开信息 | 启用/受限源声明 | 自称工厂不等于法律工商和证书已认证 |
| TRUST | TRUST-02 证书/案例上下文 | 通用未启用，工业包另有 IND-PROOF | 证书图片旧日期不证明造假/真实失效 |
| TRUST | TRUST-03 主体/联系一致性 | 未启用 | 同名实体不自动合并不同法人 |
| INQUIRE | CTA-01 CTA可见与href | 未启用 | HTML有href但真实布局不可见不可直接判PASS |
| INQUIRE | CTA-02 产品到联系只读路径 | 启用/不提交表单 | 发现 Contact 链接不证明邮件/表单实际送达 |
| INQUIRE | CTA-03 移动基础布局 | 未启用 | 单宽390px不代替全部设备/可访问性认证 |
| SEARCH_TECHNICAL | SEO-01 基础元数据 | 启用/页面标签证据 | Title/Canonical只证明存在，非Google收录/排名 |
| SEARCH_TECHNICAL | SEO-02 产品可抓取性 | 未启用 | JS渲染产品不能直接认定SEO FAIL |
| SEARCH_TECHNICAL | TECH-01 响应/跳转 | 未启用 | 403/WAF/robots为访问受限，不等于网站业务损坏 |
| SEARCH_TECHNICAL | TECH-02 图片/标题结构 | 未启用 | 图片未抓取/标题候选不等于WCAG全站结论 |

工业6条：IND-SELECTION/IND-SPEC/IND-DUTY/IND-FIT/IND-PROOF/IND-RFQ 作为独立 IndustryPack，绑定上游规则和可信源事实，不可重复计数为通用规则“补全”。泵/阀 P40/V25 是灯塔样例，不是整个制造业行业覆盖。

**每个将启用的规则至少有**：applicability、required_capture_roles、positive fixture、negative fixture、UNKNOWN/BLOCKED/NOT_APPLICABLE例、source citation 字节/时间/locator回放、强制反例（非业务事实自动失败）、规则版本变更前后兼容清单。S2 不能为了达到16/16而让未知强行输出 FAIL/PASS。

## 3. 采购证据与页面抽样方案（设计，非默许实网权限）

页面角色优先级由站点与行业目标决定：Home、Catalog、Category、ProductDetail、Application/Solution、About/Proof、Contact；产品多SKU、跨语种、SPA、WordPress/CMS 等进行有界采样且记分母。

`scope_manifest`（拟定设计字段而非已落库合同）：
- `selected_roles[]`，每个角色具有选中理由、请求 URL、政策、取样上限、是否允许浏览器；
- `observed_roles[]`，记录真实 response、原始证据/时间/哈希/是否完整；
- `unknown_roles[]`，原因区分 `UNSELECTED / LIMIT_REACHED / ACCESS_BLOCKED / UNSUPPORTED_FORMAT / EVIDENCE_INSUFFICIENT / NOT_APPLICABLE`；
- `coverage_denominator` = 审核前被确认适用且计划检查的代表角色/样本单位，不能用爬到的数量倒推；
- `coverage_numerator` = 有满足本规则证据需求且可重放的样本单位；分项呈现而不误报全站覆盖。

特殊类型：PDF/曲线/图片/多语种/多个型号关联需有内容格式、来源权利、版本及可解释解析器，否则给 `UNSUPPORTED_FORMAT`/UNKNOWN；不因为无法处理就认定旧网站缺资料。

## 4. L2 预算方案：必须有上限，不能虚构一个统一生产值

保留原 V1.1 上位提议：L0 HTML约3–5、模型0；L1 HTML不超过8、浏览器2–3代表页、单次模型预算候选¥2（只是待验证候选）。**这些不是所有 L2 的批准额度，更不是已经达成费用SLA。**

S1 冻结的预算控制**结构**：

| 维度 | 配置与计量 | 停止原则 |
| --- | --- | --- |
| 来源和操作 | Policy host/path/expiry、同域任务并发、allowlist、robots、可接受数据类型 | 无合法来源/已撤权立即拒绝新动作；L2能力不因缺私有许可停止其他合法分析 |
| URL与页面 | max_selected_html_pages、max_requests、max_redirects、max_html_bytes_per_page、max_total_bytes、max_dynamic_pages | 上限未配置、越界或异常持续跳转即停止/UNKNOWN，不增加任意外链 |
| 浏览器 | max_browser_pages、max_browser_seconds、resource/network limits、出网隔离、target concurrency | 不绕过验证码/WAF，不抓第三方任意资源，不启用未经允许的表单 |
| CPU/内存与存储 | max_total_runtime、per_task_cpu/memory、snapshot_retention、object_storage_budget | 达限标成本/覆盖原因；原Worker原30秒租约、提交流程不改变 |
| 模型 | model_provider/region/use_approval、max_attempts、max_input/output_tokens、max_cost、price_snapshot、max_duration、PII/data policy | 任一外部模型授权、费率、上限或用途缺失 → `NO_MODEL`/拒绝，保持确定性报告；不可假设免费 |
| 审核/商务成本 | reviewer_minutes、hourly_rate/status、outreach_cost/receipt、invoice_status | 人工/费率未知独立UNKNOWN，不计0，不推导E3或ROI |

P40/V25 的**8页合成样本**只是已验证的 S0 场景，不反推为所有工业深诊实际8页硬上限。S2 的代表站型与复杂度试验提供样本分布后，Owner 再冻结各类配置的具体数值及成本门槛；在批准前仍用有界离线/合成模式，无实网预算授予。

## 5. Gold 人工审阅、冲突裁决与出入库

- 当前冻结候选集合26个，`tests/benchmark/samples/*` 为 `CANDIDATE_ONLY_NO_HUMAN_APPROVAL`，`tests/benchmark/human_gold.py` 有人工导入、拒绝伪签名机制；现阶段 `GOLD_LABEL_PENDING`，可评估真实 Gold 单位仍为0/26。
- 评审单位必须是**具体 Rule × 具体来源证据/页面/时刻/适用条件**，而不是一句模糊的“站点评分”。每条保存标签、证据快照哈希、独立评审人、时间、理由及冲突裁决；真实审阅必须由人做，Codex自己给自己标注不等于独立Gold。
- 同一案例建议两名独立专业评审；有冲突交第三个有责任的人工判决人/Owner签署，不用 majority vote 代替证据论证。无真实签署不得从 candidate 自动升 Gold。
- 同时建立至少五种差异站型（静态、CMS、SPA、多SKU、多语言等）和工业泵/阀冲突/单位/失配/证书/买方待补等样本。不同样本可来自合法离线与合成，必须分别标明来源类型，不能据合成Gold推断客户现场精确率。
- 工业 Gold 应覆盖能找到有据缺陷、没有缺陷、UNKNOWN、模型虚构、路径存在/不存在、应用不适用、不同型号混淆、买家/企业资料缺失、技术数据不一致和真实来源访问受限。
- 质量报表必须至少分组：站型×行业×任务×规则版本×来源类型×模型模式，输出 TP/FP/FN/TN、precision、recall、abstention、coverage、unsupported_fact_count、severe_fabrication_count、人工审阅分歧率及分母。分母0输出null/NOT_EVALUABLE，不四舍五入为满分。

## 6. 负例与验证场景矩阵

| 场景 | 正确输出 | 禁止输出 |
| --- | --- | --- |
| 首页无导航，目录经JS可访问但未获浏览器证据 | UNKNOWN/覆盖受限 | “不存在产品目录” |
| 产品有 PDF 技术手册但当前解析器不支持 | UNSUPPORTED_FORMAT/待补 | “网站缺少规格” |
| 厂商声称证书有效期已过 | 来源声明日期与观察日的比较+需独立核验 | “无资质/证书造假” |
| 泵标量条件不满足单一配置情景 | 有据标量冲突+工程适配UNKNOWN | “设备一定不能使用/存在重大安全隐患” |
| RFQ表单存在但未真实提交 | 联系链路可观察、送达 UNKNOWN | “已询盘/未收到询盘” |
| WAF阻断或CSP/CDN挑战 | ACCESS_BLOCKED | 站点有经营/SEO故障 |
| AI建议来源ID不存在、前后时间矛盾或凭空估算流失 | REJECTED/AI_INVALID | 自动加入客户可见事实层 |
| 没有真实人工Gold或模型费率 | NOT_EVALUABLE/UNKNOWN，停止不获准的付费调用 | “90%准确率达标/模型免费” |

## 7. 分阶段退出

**S1 仅验收规范完整性**：16规则能力状态与目标、来源采样分母和政策、Gold人审/质量计算、L2预算字段/缺失拒绝和AI/商业分界有明确契约与反例。以上不要求本阶段实现剩余10条规则、取得人工Gold、运行真实AI或客户业务。

**S2 实现阶段**：已启用规则正反例、代表站型、独立签署Gold和精确率/覆盖率分别可验证，未达门槛不能对陌生客户发布“专业诊断准确”。

**S3 AI阶段**：模型实际接入后的事实/语义/预算对照独立签收；无供应商和费用授权只能做到离线模拟准备。

**S4 商业阶段**：受真实许可/人审/客户反馈的获客及完全成本验证；不能用S0合成运行代替。

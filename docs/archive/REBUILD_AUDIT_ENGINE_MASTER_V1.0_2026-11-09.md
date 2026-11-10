> **ARCHIVED / SUPERSEDED** — 以下是 2026-11-09 的 V1.0 原始规划，原始存放于 VEYFRONT 的 Draft PR #26。其“VRAE 源码归属 VEYFRONT 仓库”的结论已被 V1.1 决策取代。仅供历史追溯；实施请以 [文档目录](../README.md) 和 [ADR-0001](../adr/ADR-0001-independent-engine.md) 为准。
>
> 原始来源：https://github.com/gloweaseco-leo/VEYFRONT/pull/26
> 迁入日期：2026-11-10；除本说明外正文未修改。

---

# VEYFRONT · Rebuild Buyer Journey Audit Engine
## 产品与工程总架构基线 V1.0（2026-11-09）

**状态：架构决策候选 / 仅文档，不代表实现或生产承诺。**
**主责：VEYFRONT 首席增长官、首席架构师。**
**仓库归属：gloweaseco-leo/VEYFRONT。**
**产品目标：把合法可观察的现有 B2B 企业网站问题，转成可信、可审核、可成交的 Rebuild 商机。**

### 0. 产品边界与北极星

- 产品名称：Buyer Journey Audit（海外采购商网站体验诊断），简称 BJA；内部引擎代号 RAE。
- 客户：有真实出口业务、现有网站，且网站改造在 VEYFRONT 实际交付边界内的中国 B2B 制造企业。
- 核心价值：企业旧站 → 页面证据 → 采购商阻碍/未核实假设 → 优先改造建议 → 人工审核 → 客户自愿沟通 → Rebuild 商机。
- 北极星不是检测次数、AI 分数或销售人员发送次数，而是：**因证据化诊断而产生的、经负责人确认的 E3 合格商机，及其含人工的获客成本**。E3 不能由浏览量、扫码、邮件送达或 AI 自评推导。
- 先以 Rebuild 为中心；保留 Launch 的独立承接。产品不等于 L2M 自动建站、不等于 Vey2GE 通用增长系统、不等于 GSC/SEO 审计工具。
- 不生成“网站健康 38/100”等无法校准的评分；不声称“客户流失率提高 X%”“网站没有询盘”“销售收入受损”，除非拥有权威、经授权数据和对应计算。
- 不自动外发邮件、加微信、群发、报价、签约、改第三方网站、模拟提交真实业务表单、绕过网站访问限制。付费交付仍按 VEYFRONT 现有人工批准范围执行。
- 自动输出少于三个可靠问题是允许的；禁止为凑 3 条而编造问题。

### 1. 真实仓库资产与复用决策（2026-11-09 审阅）

| 仓库 | 已有实物 | 使用方式 | 不能当作已验收 |
|---|---|---|---|
| VEYFRONT | Next.js 16 官网、Rebuild 询盘页、私有 Vercel Blob 线索、企业微信、来源提示及私有汇总 | 作为客户入口、诊断展示、销售交接；保留现有询盘来源和 VF 收据机制 | 没有公开诊断 API、异步任务、诊断审核系统 |
| Legacy2Modern- | Python url_fetch（公有 IP、同域、重定向、限流/限页/超时）、discovery、Site IR、content_package、部分 Playwright | 仅提取经单测与独立审计的 **只读采集/页面角色识别** 能力，固定依赖 SHA，做 RAE 适配层 | 自动生成/修复/视觉商业交付闭环仍不合格；其 browser_verify 是离线内联渲染，不是目标网站真实交互 |
| Vey2GE | E0–E4 证据等级、商机状态、审批/幂等/成本契约；G1 为离线模拟实现 | 用 **版本化事件/数据契约** 交接，等待通用 Beta 云端验收后再接运行时 | 不声称已有可供 VEYFRONT 生产调用的商机工作台 |

**ADR-RAE-001：业务、证据、报告和销售交接由 RAE 单独完成；L2M 生成与 Vey2GE 运行时均不在 RAE 的关键路径。**
**ADR-RAE-002：同一个 VEYFRONT 仓库管理产品/API/契约/只读 worker 代码，但使用隔离执行容器，不把不受信网页直接交给官网运行时。**
**ADR-RAE-003：结构化事实、可复核规则优先；模型只给有证据的解释与建议，不拥有 URL 爬取、商机晋级、外发或发布权限。**

### 2. 客户与内部两条运行模式

| 模式 | 入口 | 许可与输入 | 交付 | 自动化 |
|---|---|---|---|---|
| L0 SCOUT | 内部目标企业研究 | 已审核的公开企业域名、来源与研究依据；仅被动公开页检查 | 仅内部 Candidate + Evidence + Fit，不提供公开报告 | 无模型 / 确定性筛查；可逐家受控启动 |
| L1 AUDIT | 内部挑选后人工触达，或客户自愿申请 | 网站公开 URL；明确用途、抓取约束及对客户的隐私告知；客户想接收报告时再提供联系信息并同意 | 一页初评：最多 3 个已证实问题、证据和明确下一步；须人工批准才能外发 | 限量抓取、规则、最多有预算的 1 次 AI 草稿 + 1 次受限修复 |
| L2 DEEP | 已回应、有明确咨询意向的客户 | 必须单独获得网站所有者授权与业务资料；可验证属主（DNS/文件/授权协议之一） | 买家旅程与产品结构深度评估、改造蓝图及报价依据 | 人工主导 + 受控 AI 整理 |
| L3 SALES | 商务确认 | 负责人核对需求、范围、合同和成本 | 正式项目方案、报价与验收清单 | 人工批准 |

客户自助“试一试”入口与内部主动研究共用核心分析，但权限、成本配额、联系信息与可见报告严格分离。匿名用户不能无限次触发浏览器任务或读取他人报告。

### 3. 诊断领域模型：五个买家任务，十六条初版规则

**客户价值路径：找到 → 看懂 → 信任 → 咨询 → 被搜索发现。**
页面角色由真实 DOM 及导航识别，不因某个关键词缺失就断言功能不存在。

| 规则 ID | 检测目标 | 可验证事实 | 常见误判 / 限制 |
|---|---|---|---|
| DISC-01 | 首页到主要产品分类的路径 | 链接、导航层级与实际目标 URL | 单页样本不足不能断言全站无产品页 |
| DISC-02 | 至少一个代表产品路径 | 分类→产品卡→详情 GET/导航 | 不点业务表单、不提交购买 |
| DISC-03 | 应用/行业入口 | 已观察的行业导航或应用页 | 不强制每个行业都必须有该页 |
| INFO-01 | 产品名称与基本规格信息 | 标题、规格标签/数值与来源页 | 不推断技术规格正确性 |
| INFO-02 | 技术采购所需信息可辨 | 采购参数、资料下载链接、设备适配信息 | 需行业包决定必要字段；未知不当缺失 |
| INFO-03 | 英文页面是否易于理解 | 明显的语言混用/空白文本/无效字符等 | AI 不得在无人工校验时断言语言质量差 |
| TRUST-01 | 公司信息/联系主体可找到 | About、Contact、公司身份可见情况 | 不根据未见证书断言没有认证 |
| TRUST-02 | 证明材料的来源与上下文 | 展示的证书/案例/工厂信息是否有文内解释 | 不认证证书真假、不编客户交付 |
| TRUST-03 | 品牌/主体信息一致性候选 | 可见名称、地址、联系方法的冲突候选 | 同名不同法人需人工处理 |
| CTA-01 | 采购商询盘入口可见 | CTA、RFQ、Contact 的位置和目标链接 | 有表单不等于实际收到询盘 |
| CTA-02 | 产品上下文询盘路径 | 从代表产品到表单或联系入口的可达性 | 不填客户资料、不进行提交 |
| CTA-03 | 移动端基础可用性 | 390px 溢出、重要导航可见/可操作 | 单次截图不代表所有设备 |
| SEO-01 | 抓取和索引技术基础 | robots、sitemap、canonical、标题、响应状态 | 技术可索引 ≠ Google 已收录或有排名 |
| SEO-02 | 可抓取的产品信息与链接 | 初始 HTML、渲染 DOM、原生链接 | JS 延迟不能直接断言 Google 无法索引 |
| TECH-01 | 核心 URL 可用性 | 2xx/3xx/4xx、跳转与错误状态 | 临时 403/反爬必须标 ACCESS_BLOCKED |
| TECH-02 | 代表页面资源与可访问性 | 图像状态、H1、基础可访问性候选 | Lighthouse/WCAG 自动检测并非完整合规认证 |

规则库采用版本化独立文件，逐条标注行业适用性、页面角色、证据需求、误报风险、正例/反例。规则数量是初期诊断覆盖框架，**不是对外承诺每站都会有 16 条判断**。

### 4. 严格区分证据、观察、推断与未知

- Evidence：原始观察，不可静默覆盖，记录 site_id、audit_id、source_url、final_url、retrieved_at、page_role、HTTP 状态、片段/定位符、snapshot_ref、sha256、capture_mode、许可范围及观察失败原因。
- Observation：确定性规则基于一个或多个 Evidence 产出的可重复事实，必须绑定 rule_id/rule_version、检查方法及反证机会。
- Hypothesis：模型解释某个事实可能给买家带来的困扰，不得改写为客观销量/转化结论。
- Recommendation：必须有 observation_id、解决动作、受影响买家任务、scope_fit（standard_candidate / custom_review / not_supported / unknown）、验证手段。
- Unknown：未取得页、反爬、需要企业后台数据、没有检查的页面；不得用否定性陈述代替。
- 人工审核可以 reject / revise / approve，记录 reviewer、时间、原因和报告版本；不能编辑原始 Evidence 以使结果看起来正确。

**每一个面向客户的诊断结论必须能点击查看来源页面、检查时间、相应截图或抽取片段。** 若找不到对应证据，报告不允许发布。

### 5. 推荐的系统分层

    [企业来源 / 官网客户自愿申请 / 伙伴推荐 / SEO]
                  |
        VEYFRONT Next.js 入口
       [身份、同意、配额、状态、报告]
                  |
          Audit Application API
       [校验、去重、状态、审批、事件]
                  |
         Durable Job & Evidence Store
                  |
        Isolated Read-only Audit Worker
       /                |               \
    Safe Fetch      DOM/Playwright    Rule Engine
    Public pages    Screenshot       deterministic
       \                |               /
           Immutable Evidence Pack
                  |
             Finding Builder
        [rules → optional AI → schema]
                  |
         Business Review + Report QA
                  |
        [L1 客户初评报告] ─→ [VF Lead]
                  |
        [L2 咨询/授权] ─→ [Rebuild 报价]
                  |
        [经审核的 E2/E3 事件 → Vey2GE 后续适配]

- Next.js 只承担 UI、轻量 API 和鉴权，不在公开 HTTP 请求内执行无界抓取/Chromium/模型循环。
- worker 的网络/文件系统隔离：只允许经网络策略核验的公网目标；不同任务独立临时空间，不能读取正式站 secrets、客户 Blob、私有网络及云 metadata。
- L2M Python 只读采集函数通过 **固定版本 adapter** 复用，需对安全补丁进行回归；禁止整个不稳定实验项目作为线上运行时依赖。
- Playwright 用于适量的真实渲染与只读导航截图；浏览器对非必要外部域名、下载、弹窗及表单 POST 有显式禁止策略；不同模式配置不同资源配额。
- 最初不采用 LangChain、多代理框架、自研浏览器 Agent、向量数据库、微服务编排。规则可执行、报告可信才是核心难题。

### 6. 数据模型和接口契约（开发时必须先写 schema 与契约测试）

**持久对象：**
1. Account：独立企业候选主档；name/domain/jurisdiction/industry/verification/source/owner；域名相同不必然代表同一法人。
2. Site：canonical_host、实际观察 URL、访问策略、属主授权版本、行业包版本。
3. AuditJob：audit_id、account_id?、site_id、mode、source_channel、requested_by、source_policy_id、input_hash、rule_set_version、prompt_version、status、limits、cost_guard、attempt、created_at。
4. SourceSnapshot / PageEvidence：不可变快照/HTML 摘要/公开页面截图及引用；每份对象有 SHA-256、页面类型、采集时间和访问权限。
5. Finding：finding_id、rule_id、evidence_ids[]、observed_facts[]、hypothesis?、buyer_impact?、severity、confidence、recommendation、service_fit、decision_status。
6. AuditReview / AuditReport：reviewer_id、decisions[]、approved_at、report_version、redaction_version、sharing_policy、expires_at。
7. SalesHandoff：report_id、vf_reference?、channel、contact_consented、opportunity_id?、owner_id?、handoff_status；不把诊断完成当成已收到咨询。

**API 草案（名称可调但语义须稳定）：**
- POST /api/rebuild/audits/request：防滥用、同意、配额核验后创建任务，返回 audit_id + 当前状态，不同步承诺诊断完成。
- GET /api/rebuild/audits/{id}/status：仅授权用户可读；不得暴露内部错误、其它用户证据、模型成本明细。
- GET /api/rebuild/audits/{id}/report：仅客户被授权后的有限脱敏版本；默认私有、禁止搜索索引。
- POST /internal/rebuild/audits/{id}/review：仅受权 Reviewer/Owner 可审定。
- POST /internal/rebuild/audits/{id}/share：仅 Owner 审核批准且报告版本未变化时可分享。
- POST /internal/rebuild/audits/{id}/sales-handoff：经人工明确确认后按已有 VF 线索或未来商机适配器建立关联。

**事件语义：**
audit.requested / audit.policy_passed / audit.observed / audit.draft_ready / audit.reviewed / audit.shared / inquiry.received_verified / opportunity.qualified_confirmed。
事件追加写入、版本化、幂等；audit.shared 不等于 inquiry.received_verified；E2 不等于 E3。输出给 Vey2GE 的 payload 不含 PII。

**身份与权限：**
- Anonymous Prospect：最多查询自己持有的非敏感申请进度；不得枚举报告。
- Claimant：通过申请者邮箱验证或强随机回执链接获得本人报告。
- Reviewer：能看分配到的内部草稿和引用证据。
- Owner/Admin：管理策略、审批分享、归档和账本；无法无痕改写 Evidence。
- Worker：只获得一次性任务上下文和最低限访问的证据写入权限。
- 强制租户/工作空间隔离，为未来 Vey2GE 对接留 tenant_id；当前不声称拥有多租户生产能力。

### 7. 安全抓取与网站礼貌策略（P0 硬门禁）

- 只接受 http/https 的标准 80/443 端口；拒绝 IP literal、userinfo、非 HTTP scheme、内网/回环/链路本地/保留/metadata 地址；拒绝模糊主机、编码绕过。
- DNS A/AAAA 查询与真正连接强绑定，禁止 DNS rebinding；每次跳转及子资源访问重新执行目标验证。严禁将 URL 参数交给 shell 执行。
- 只允许站点同域内容路径，跨域 CDN 资源使用单独短名单与策略，不跟踪任意外链；不爬登录、验证码、后台或私有数据。
- 尊重网站的 robots/crawl 策略、访问条款与适用许可；明确拒绝/限制时停止，不通过代理轮换或机器人伪装来绕过。
- 只执行 GET/HEAD 及必要的只读导航；不执行外部网页的表单提交、登录、文件上传或购买动作；浏览器加载网络也须经过 egress 策略控制，GET/HEAD 是最低要求。
- User-Agent 应标识 VEYFRONT 审计工具及可查询的联系信息；同域限速，启用停止/拒绝列表和人工受理的退出机制。
- 不以静态页面或截图内容作为 Agent 系统指令；HTML/JS 中的 prompt injection 和伪造审计结果应按不可信数据处理。
- 原始截图可能包含个人资料、版权内容、偶然的凭证或敏感资料：默认私有加密、最小范围与有限留存，不允许 GitHub artifacts、公开网页或外部广告。
- 未经所有者授权不得进行更高频率测试、提交真实询盘、探测后台/未公开接口、绕过访问控制或发出安全漏洞攻击请求。
- 任何 SSRF 测试、流量超限、授权缺失导致 STOP_WITH_POLICY_BLOCK，不得回退成不受控代理抓取。
- 外部搜索引擎的索引/点击/流量数据仅在站点所有者真实授权 API 时可使用；公开页面本身无法证明是否被 Google 收录。

### 8. AI 模型的唯一职责与预算

**Model Gateway 是可替换的服务端适配器，不是浏览器自主 Agent。** 先用现有可控供应商的已授权模型作为候选，实际模型/价格经探针验证后再冻结；不绑定特定商用 API。

- 输入：脱敏、限长、只读、已经结构化的 PageEvidence + Observations + 行业规则 + VEYFRONT 服务边界。
- 输出：严格 JSON Schema：business_relevance、evidence_bound_hypotheses、recommendations、missing_information、suggested_questions；每个 claim 的 evidence_ids 必须非空且在原始包中存在。
- 不向模型直接发送手机号/邮箱/个人资料/私有客户 brief；必要时先脱敏或取消模型分析。
- 规则输出不能被模型改写；模型只对候选结论补充语言解释、优先级建议、客户沟通提问。
- 模型失败 / schema 不合规 / 缺少证据 / 费用不明 → 标为 AI_NOT_VALIDATED，保留确定性证据与待人工处理，不输出模型杜撰结论。
- 提前预留最坏情况 token 预算，单次调用限输出，允许最多一次有界修复；**L1 模型费用硬预算建议 ¥2/站**（试点决策阈值，并非实测单价），未知用量禁止继续调用。L0 不调用模型；L2 另行明确授权。
- 记录 provider、model、版本、prompt_hash、schema_version、usage、币种、预留/实际成本、未知项、错误；不可把估算价标成真实账单。
- 静态/动态规则两种层级：规则检查可重现，模型解释可复核，人工最终决定客户可见的结论。

### 9. 推荐基础设施与成本递进

**M0–M1：** 无公开在线诊断、无需采购服务器。将受控采集和规则引擎以 Docker/CLI 形式离线验证；诊断证据存本地受限目录，完全合成 fixture 先行。不可把一次离线跑通视作线上服务。

**M2：** 首次上线带状态/审核的有限邀请试点时，使用独立受限容器 Worker（部署平台在成本/地区/许可核实后确定）+ 托管 PostgreSQL（AuditJob/状态/幂等/审核/租户隔离）+ 私有对象存储（截图/快照/报告）。Vercel Next.js 继续承担产品网页和短 API。数据库是审核/任务权威，Blob 是对象资产；不得用非原子 Blob 文件列表充当并发队列。

**M3：** 客户自主申请后按预算、速率、企业授权和法规评审开启；模型调用权限、报告公开分享策略以及日额度单独配置。Vey2GE 只按 API/事件契约读取经授权结果，不共享无隔离的生产数据表。

默认并发 1、单域 1、任务幂等去重。按需求增加并发前必须测试队列恢复、WAF、运营成本和 abuse。

### 10. 初期运行预算（待真实样本校准）

| 项 | L0 初筛 | L1 免费初评 | L2 深诊 |
|---|---|---|---|
| 网页页面数 | <= 3–5 | <= 8 | <= 10（需独立授权） |
| HTML 下载 | 单页 <= 1.5 MB | 单页 <= 1.5 MB | 依授权另定 |
| Chromium | 不默认 | 代表性 2–3 页，两种视口 | 按业务需要 |
| 模型 | 0 | 1 次 + 至多 1 次修复，预算建议 <= ¥2 | 单独预算 |
| 报告 | 内部机会卡 | 一页、最多 3 个有证据问题 | 商务诊断蓝图 |
| 人工 | 批量抽样复核 | 所有对外报告 100% 人工审核 | 顾问深度参与 |

- 预算上限均是**开发验收参数**，不是客户承诺、模型供应商价格或测得成本。第一次真实压力测试之后再决定具体 SLA、总墙钟时限和每站运营成本。
- 严格区分模型费用、浏览器/计算费用、人工复核费用、内容/触达费用，计算合格商机单价。无 E3 时单位成本显示 null。

### 11. 运营工作流与状态机

    CREATED
      → POLICY_CHECK
        → POLICY_BLOCKED / ACCESS_BLOCKED / QUEUED
      → FETCHING → EXTRACTED → RULE_CHECKED
      → DRAFTED (或 DETERMINISTIC_ONLY)
      → REVIEW_REQUIRED
        → APPROVED / REJECTED / NEED_MORE_EVIDENCE
      → SHARED (仅经审批)
      → SALES_HANDOFF (仅客户回应或明确同意)
      → ARCHIVED

- 每一步有 deadline、幂等键、attempt、输入哈希、输出哈希和 replay 日志。自动重试不升级权限、调用量或预算；关键失败进入死信/人工队列。
- 任务被取消、页面禁止访问、浏览器报错、人工拒绝，都不能转化为成功报告。
- 旧任务完成后不得覆盖新版本报告；客户看到的 report_version 与 reviewer approval 必须一致。
- 再次检查相同站点必须创建新 snapshot/version；旧报告带日期和检查范围。
- 分享仅对被授权对象，随机不可猜测 token + 过期控制 + noindex；不要把私人客户诊断批量生成 SEO 页面。

### 12. 报告与转化体验

客户 L1 报告分五块：
1. 概览：网站及检查日期/范围，以及公开资料的边界说明；
2. 采购商任务图：找到、理解、信任、咨询、搜索基础中哪些方面有可复核发现；
3. 最重要的 1–3 个问题：观察事实、截图/来源、可能的买家困扰（明确是假设）；
4. 建议：最小可执行措施、属于标准 Rebuild 候选还是需定制核价；
5. CTA：申请 15 分钟沟通 / 企业微信联系 / 查看当前 Rebuild 服务和 ¥9,800 参考条件。

不可用图表把“缺少页面”“未能抓取”“无法核实企业数据”混为同一错误类别。中英文输出沿用官网品牌；默认中文商务表达，但原站引用不应悄悄翻译或篡改。

### 13. 研发目录建议（计划，不代表已存在）

    contracts/rebuild-audit/v1/                 # JSON Schema / OpenAPI / examples
    lib/rebuild-audit/domain/                  # rules, schemas, finding evaluation
    lib/rebuild-audit/application/             # job, review, sharing, handoff
    services/rebuild-audit-worker/             # isolated Python fetch/Playwright adapter
    app/(public)/rebuild-audit/                # 客户申请与介绍，发布前单独审核
    app/(internal)/rebuild-audit/              # Owner/Reviewer 内部工作台
    app/api/rebuild-audits/                    # 鉴权/输入/状态，不执行长抓取
    tests/rebuild-audit/                       # 安全负例、规则、报告、商业验收
    qa-evidence/rebuild-audit/                 # 脱敏合成证据（不得提交真实截图）

先写 schema 与合成 fixtures，再建 worker；内测不必立刻改公共导航。

### 14. 分阶段里程碑与 DoD（不得提前宣告完成）

| 里程碑 | 范围 | 退出验收 |
|---|---|---|
| RA-0 契约冻结 | ICP、规则集、证据类型、权限、SourcePolicy、成本门禁、API schema | 架构评审完成；20 个测试任务：10 允许/拒绝及错误场景、10 正常业务 |
| RA-1 安全采集/页面发现 | L2M 只读 fetch 适配、页面角色抽样、受限 Playwright、快照哈希 | SSRF/重定向/DNS 重绑定/跨域/限速/403 阻断等安全负例 100% 通过；证据可复现；真实允许站型抽测 |
| RA-2 确定性诊断 | 规则集与 Evidence→Finding 关联、unknown 分层、低覆盖降级 | 无证据不得输出客观问题；覆盖至少 5 种不同 B2B 网站结构 |
| RA-3 AI 辅助与人工评审 | 结构化 JSON、schema 校验、证据约束、审批/版本/成本 | 100% 客户可见客观主张可追溯；0 个严重无来源虚构；预算未知时 stop；审阅可拒绝重审 |
| RA-4 运营/预览 | 持久队列和私有存储、角色访问、报告页、诊断→VF 关联 | 并发 1→恢复、重复提交去重、取消/访问控制/跨租户拒绝、预览真实浏览器完成 |
| RA-5 灯塔价值验证 | 10–15 个真实可合法检查的站点、3–5 份人工审核 L1、少量经审批商务沟通 | 人工评估报告有实际可操作性；误报可解释；有真实双向需求反馈；非销售指标不伪称成交 |
| RA-6 有限在线发布 | 经安全和商业验收后在 VEYFRONT 官网可申请 | 访问限额/告知/隐私/授权/运营 owner/故障应对/成本可用；正式域名单独批准 |

**质量门禁：**
- Zero critical：SSRF、防火墙出网、越权、公开个人数据、未经授权外发或修改第三方网站。
- 100% 对外结论有证据和人工审阅，原始事实不能被模型改写。
- 页面抓取覆盖和误报率使用人工标注的基准集合测量；未达到预设阈值不得公开承诺“全自动准确诊断”。
- 所有错误必须保留明确终态：POLICY_BLOCKED / ACCESS_BLOCKED / INSUFFICIENT_EVIDENCE / MODEL_INVALID / HUMAN_REJECTED / FAILED；不要显示“诊断成功”兜底页。
- 报告确认和外发严格分离，未批准永不进入 SHARED。
- 公开购买转化要使用 VEYFRONT 的真实 VF 表单与价格范围，不能使用假的客服回执/虚构案例。
- 不自动合并 main、不直接发布生产；先预览和独立 QA，再明确商业验收批准。

### 15. 首批验收样本与实验指标

先准备具有 owner 许可或适当公开访问权限的 B2B 样本，至少涵盖：
- 英文静态工业网站、现代 React SPA、WordPress/CMS、产品目录较大、移动端问题明显站型；
- 访问受限/403、跨域 CDN、重定向异常、无 sitemap、错误 robots、无产品详情、受控合成恶意 URL；
- 每个样本标注“实际可见/应为 unknown/规则应命中/报告应拒绝”的人工 gold labels。

在 RA-2 时设定初期试验阈值：从可合法检查的站点中，至少 80% 能产生具有覆盖说明的正确代表页面包；经人工审查的报告问题精确率目标 >= 90%，关键事实虚构 0；达到这些目标也不证明商机价值。

在 RA-5 时验证：10–15 份 L0 的单位综合成本、3–5 份 L1 的人工复核耗时、3 个以上独立负责人的报告实用性评价、真实客户自愿回应/沟通，而不是单纯模拟案例。只有真实 E3 才进入获客漏斗与成本单价。

### 16. 权限与商业承诺红线

- 独立站公开可访问不代表网站属主授权复用图片、生成对比站或公开诊断报告。私人报告仍须最小化保存。
- 诊断不等于技术安全测试/渗透；诊断不证明 Google 实际收录、网站实际转化率、企业营业收入或证书真实性。
- 不在陌生人未回应前向外发送详细、可能贬损或含第三方素材的诊断报告；首次商务触达必须是人工审查、可停止、尊重对方的个性化沟通。
- 标准 Rebuild ¥9,800 是**条件性参考方案**，并非诊断后自动报价。产品复杂度、数据量、迁移范围、第三语言等都需要真实合同范围评审。
- 不编造自动分析运行、用户测试、付费成交或实验结果。只在相应 Gate 证据通过后变更状态。
- 所有真实商业主体、行业联系人与外部网页证据按适用法律及供应商条款处理；授权撤回时停止进一步调用并执行经核实的保留/删除策略。

### 17. 下一轮具体开发顺序（Codex 可直接按此拆分）

RA-0A：创建 contracts/rebuild-audit/v1 的 AuditRequest, SourcePolicy, PageEvidence, Observation, Finding, Report, ReviewDecision, SalesHandoff 的 JSON Schema 及正反例。

RA-0B：先写安全门禁与模拟 HTML 站点 fixtures；分离 PUBLIC_READONLY 与 OWNER_AUTHORIZED 两种 SourcePolicy，所有规则用 rule_id+version。

RA-1A：在独立 Worker 对 L2M fetch/discovery 代码做固定 SHA、许可证和依赖检查，必要时最小抽取；仅对合成可控网站执行真实网络探针。

RA-1B：实现抽样路径选择和只读浏览器；记录真实 HTTP 与 screenshot 来源，浏览器不能接触生产 secrets。

RA-2A：实现确定性 16 规则适用性与 unknown 分类，Finding 必须引用 Evidence；输出完整负面样本验证。

RA-3A：AI Gateway 首先只处理已结构化的 Finding 候选，严格 schema 和引用检查；不写 Crawl Tool。

RA-3B：Viewer/Reviewer 审核并生成一页报告；任何客户可见分享都要求批准和可回收/过期。

RA-4A：建设持久化任务与隔离数据层，仅让 VEYFRONT 对外暴露申请与查看本人任务的接口；保存审计记录并限流。

RA-5A：用真实有限样本和人工评分验证商业可行性，然后才决定公开自助诊断与增长渠道扩大。

### 18. 需重新评审而非默认放行的事项

- Worker 托管平台、计费、出网政策和位置；
- 托管 PostgreSQL 实际供应商及数据保留周期；
- 是否公开提供自助诊断，以及免费诊断每人配额；
- 是否向客户开放无需身份的报告链接；
- 首个真实客户行业包/企业名单及其数据来源许可；
- 模型实际供应商/单价/区域及是否涉及客户数据跨境；
- 具体合作商务佣金、对外联系话术及客户同意规则。

**最终定调：先验证证据驱动的诊断可靠性和成交价值，再扩大自动化。RA-1/RA-2 不依赖 L2M 生成成功或 Vey2GE 上线。**

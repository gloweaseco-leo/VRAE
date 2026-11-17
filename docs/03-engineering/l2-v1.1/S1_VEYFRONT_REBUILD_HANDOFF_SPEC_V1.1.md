# VRAE V1.1 · S1｜L2 商务决策、Rebuild 蓝图与 VEYFRONT 交接规范

> 状态：OWNER 设计候选，随 S1 文档 PR 审核后生效。DESIGN_ONLY；不开发 VF API、不触达客户、不批准真实分享、报价或 L2M 交付。
> 依据：PRODUCT_CHARTER_V1.1、PRODUCT_AND_OPERATOR_JOURNEYS_V1.1、INTEGRATION_CONTRACTS_V1.1、DATA_ARCHITECTURE_V1.1、现有 `vrae/l2/native_business.py`、`vrae/l2_ops/briefs.py` 与 S0 accepted main `178d1ea4a6b11c11491a8ed71a418e6415b1fcb5`。对应 D05/D08、A20–A27。

## 1. 商业北极星与三种互不混淆的资产

**诊断资产**（VRAE 权威）：可信来源、五维检查范围、已确认/未知、专业采购判断、假设、建议、精确报告版本与审核历史。

**内部业务准备**（VRAE 产生，VEYFRONT 参考）：Reviewer Controlled 版本与内部 RebuildBrief；此状态只能支持人工判断下一步，**不授予真正客户同意、外部报告接收权或正式报价**。

**对外商务/交付**（VEYFRONT / 后续 L2M 权威）：企业主体/联系人、客户主动咨询或经审批一对一联系、确认的采购需求、VF 报价/合同、逐项素材版权授权及项目交付启动。只有经客户及相关责任方核验后才进入此层。

E2/E3 真相源不在 VRAE；真实请求回应≠系统生成报告，点击/二维码扫描/已下载报告≠E2，系统推荐“潜在机会”≠E3。

## 2. 三层客户与操作流程

| 阶段 | 谁操作 | 允许产物 | 不可升级为 |
| --- | --- | --- | --- |
| L0 目标企业识别 | VEYFRONT 研究/销售 | 来源审查、候选适配、公开有据入口，不需要模型 | 客户同意、真实 E2 |
| L1 初步沟通材料 | VRAE Reviewer 经具体审核；VF负责客户面 | ≤1页、≤3项真实可信重点、来源与范围、人工审批及定向授权 | 无审核的详细负面报告、E3 |
| L2 专业诊断 | VRAE 内部专业人员/受权主体 | 完整五维分层、有据 Finding、工业采购推理、蓝图、Executive Summary、待确认事项、受控版本 | 未经同意的外发、正式人审、完整项目报价 |
| L3 VEYFRONT 销售 | VEYFRONT 商务负责人 | 客户确认的需求、正式范围、标准/定制报价、合同与验收承诺 | VRAE 自行作出的收入/获客事实 |
| L2M 交付 | L2M或批准的人工交付主体 | 仅获合法授权的素材和签订范围内交付输入 | 从公开抓取直接复制资料或执行改站 |

不能通过 SourcePolicy 的一个“属主授权”布尔值代替每个实际操作/私有资料授权：L2 可离线与允许的公开只读分析；涉及后台、私有指标、登录、受限交互或内容复制需相应独立权利。

## 3. L2 面向企业决策者的输出合同

### 3.1 Executive Summary（建议 1–2 页，不取代完整报告）

- 检查企业/域名及**观察当次**时间、来源政策、页面角色/数量、代表样本覆盖分母、明确未访问/拒绝范围；
- 最多优先展示经证据证明且确实值得沟通的障碍，若零项真实障碍则明确写“本次未发现可确认的网站问题”，不凑三条；
- 每项：买家任务→来源事实/证据链接→可能影响（假设）→反证/未知→企业需确认→优先复验/改造动作；
- 保留已验证正常事项与已证实工况比较冲突；**参数冲突不自动等于网站故障或设备不适配**；
- 下一步为“需客户确认/可讨论的Rebuild候选”，不能包含无依据排名、成交损失、转化数字、工程保证和临时报价；
- L2 诊断摘要、完整版 L2 报告、蓝图、内部 Brief 应分别保留独立版本与哈希，不能用 PDF/HTML SHA 替换业务结果 SHA。

### 3.2 逐个 Rebuild 工作包必要字段

| 字段 | 含义 | 最小验收 |
| --- | --- | --- |
| package_id、report_ref/version/content_hash | 唯一版本绑定 | 新版本必须重新复核旧建议 |
| buyer_task、finding_refs、source_fact_refs | “为什么做” | 所有声称的原始网站事实可回放；无证据的缺口改为补证任务 |
| page_or_template、action | “改哪里、改什么” | 可定位页面/资料与目标动作，不能泛泛“升级SEO” |
| observed_problem / buyer_hypothesis / missing_information | 类型分离 | 假设不得自动当已证实损失或错误 |
| evidence_strength、counter_evidence、uncertainty | 限制和反证 | 存在反证或未覆盖范围必须显示 |
| owner_role、customer_inputs、dependencies | “谁负责、需要什么” | 采购/工程/企业资料/建站团队分工清楚 |
| acceptance、recheck_scope | “怎么验收” | 有可执行正反结果，不许以网站上线作为唯一验收 |
| service_fit、service_catalog_version | 标准候选/定制/企业责任 | 只有 VF 已核准服务目录才能提升为正式范围 |
| priority_basis / estimated_effort_status | 推荐排序/成本来源 | 无客户、费率或实际工时依据时保持 UNKNOWN |

### 3.3 决策分组（禁止按所有 FAIL 简单排序）

- **D1：证据直接支持的路径/信息障碍** → 可讨论是否网站 Rebuild 能解决；
- **D2：资料组织与可比较性改进机会** → 标准页面/信息结构候选，需客户确认材料；
- **D3：供应商或工程核验事项** → 工程师、资质机构或有权主体核验，不当作建站团队的业务承诺；
- **D4：采购商/客户待提供输入** → 补证清单，不能将“买方缺目的地”记为网站缺陷；
- **D5：未观察与访问受限** → UNKNOWN/ACCESS_BLOCKED，禁止计入缺陷数；
- **D6：商业影响与优先级假设** → 带证据/反证/人工判断，不推断真实ROI、询盘损失或客户预算。

“优先级”以证据强度、买家任务阻碍、直接可改善性、依赖、实现/复验范围衡量；无可靠影响证据时保留 UNRANKED。AI 提议是候选，不是自动销售排序。

## 4. 内部 RebuildBrief 与可交付正式 RebuildBrief 的硬边界

**S0 已实现的内部 Brief**：`VEYFRONT_INTERNAL`、`external_delivery_allowed=false`、`customer_approval=false`、`l2m_execution_allowed=false`；PG/SQLite双权威版本当前性和append-only完成栅栏；咨询 `UNLINKED`、费用 `UNKNOWN`。不能凭名称或内容哈希将其转成外部授权。

**未来正式交接草案必须额外具备**（不是本轮修改既有 API/Schema）：`vf_project_ref`、经 VF 独立保存及授权的 `consultation_receipt_ref`、真实企业主体与有权签署人核验结果、`customer_approval_ref`、`report_ref/report_version/hash`、`source_policy_ref`、`scope_included/excluded`、`authorized_asset_manifest[]`（每项来源/用途/复制许可/期限）、客户确认的目标产品/市场/业务需求、旧URL迁移与验收清单、正式报价/合同引用、可撤销交付许可版本与双方回执。

仅能从签名/幂等/已授权服务端通道交接；VRAE 对外仅开放精确已批准报告，内部 Evidence、AI原始响应、联系人或私有URL不得通过浏览器暴露。报告审核状态变化、权限撤销、客户同意过期、资产许可缺失，应产生强制阻断/新版本重审。不得通过“导出 PDF”绕过。

## 5. 数据主权与事件契约

| 事实/数据 | 唯一权威 | VRAE可保留 |
| --- | --- | --- |
| source policy、pages、evidence、rules、finding、report和内部review | VRAE | 完整允许范围与审计引用 |
| 真实企业主体、联系人、微信及表单收据 | VEYFRONT | 最少 opaque 引用，不保存重复主档 |
| 经责任人确认 E2/E3、正式价格/合同 | VEYFRONT或明确授权的经营主系统 | 只读映射状态/事件ref，不自推断 |
| 获准建站素材与交付工件 | 客户权利主体→L2M/人工交付系统 | 获许可范围/最小引用 |
| Vey2GE 增长事件 | VF/指定经营权威 | 必要关联的幂等事件ref，不写商机主档 |

后续接口采用原 `/v1/audit-requests` / `/v1/audits` / `review-decisions` / `share-grants` / `sales-handoffs` 版本化合同；暂不新开第二客户系统。写入需要 tenant、subject/audience/scope、内容版本、幂等键、当前撤权检查、事件 outbox 与重放幂等。跨系统失败不得使已完成诊断消失，也不可以显示“已成功移交”而收方无确认。异步提交以 WAITING_ACK / ACKNOWLEDGED / REJECTED / RETRYABLE_FAILED 明确表达，状态是未来接口建议，**不是已落库代码**。

## 6. 成本、客户许可与对外门禁

四本账：①采集/浏览器/计算，②模型/供应商，③人工审核，④业务触达。每项区分真实计量、估计、费率未定、未对账及无凭据，不能将 UNKNOWN 写零。报告成本与 E3 成本两个分母分别计算；E3=0 时单位合格商机成本 = null。

Owner/Reviewer/Operator 按原角色和任务权限分工。真实人审需独立身份认证（含获批 MFA/等效证据）、签名回执与对象版本锁；Controlled 演练不能被商业方当作已批准。真实网页/证书/案例著作权、PII、隐私保留、分享期限、撤权、删除/投诉责任在 RA-5 试点前明确到业务运营人。

L0/L1 客户入口及微信内浏览器、公开分享、初次商务接触均需要单独的实际授权与反滥用门禁；S1 文档本身不批准触达。

## 7. S4 前置验收与独立否决样例

1. 报告只找到正常页面，无证据缺陷 → 不自动生成“严重网站问题”或报价；可提供中性复核摘要。
2. 设备工况标量有冲突 → 只能列本次比较与待工程确认，不宣称实际设备不安全/不可用。
3. 只在页面看到证书图片 → 不能宣称资质真实或无效。
4. 蓝图列七项标准候选但 VF 服务目录未批准 → 不生成固定售价、工期、客户订购的七项合同。
5. VF 表单尚未保存、企业微信仅扫码、客户只是点链接 → E2 仍未确认；没有具体验证/购买路径/负责人确认不得成为 E3。
6. 当前审核版本变更、分享撤销、素材许可到期或旧签名失效 → 新移交或读取拒绝，保持历史审计。
7. VEYFRONT/L2M/Vey2GE 断开 → VRAE 诊断事实留存，交接待确认，不谎报成功。
8. 客户不同意复制旧站资产 → 只能交付获准的最小非敏感问题描述和旧站链接；不能自动改版或迁移素材。

S1 的完成定义仅为以上业务职责、输入/输出字段、否决边界和未来验收门槛已明确；**A20–A27 的真实实现/运营/客户反馈仍属于 S4，不能在 S1 签 PASS**。

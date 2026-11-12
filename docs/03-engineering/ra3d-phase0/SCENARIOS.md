# 三个完整审核场景（离线设计演练）

**HUMAN_REVIEW_SIMULATION_NOT_ACTUAL_APPROVAL。没有执行 approve_version/check_share、
没有真实身份登录、没有审批事件或 ShareGrant。** 以下输出是未来实现的验收预期，不是运行结果。
实际固定输入摘要来自 [SCENARIO_INPUTS.json](SCENARIO_INPUTS.json)，只读提取 Git 对象，未调用报告生成器。
输入均为 PR #47 固定未合并候选 `6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2` 的合成材料。

符号约定：`T404/T200` 表示后续实现按 CONTRACT 的全部字段构造并计算的 Htarget，
`D1` 表示未来服务端原子记录的完整决策摘要。它们现在**不是**已计算的签署值或审批 id。
原 candidate 不提供的身份、gateway/prompt 信息不能伪造，必须按 CONTRACT 的缺失规则处理。

## 场景一：一个有来源支持的问题，人工批准或退回

### 精确输入

| 项 | 固定事实 / 设计输入 |
| --- | --- |
| 范围 | tenant-test / run-ra3b-404base / pol-001 v1；report-ra3c-404 v1 |
| 报告 | L1_REPORT_DRAFT；1 issue；原 native REVIEW_REQUIRED；private=true，NOT_APPROVED，shareable=false |
| 原 native hash H0 | `afa83c8fca1e4d40150352643a0545c17c2a410c23ccc075d7968ef3fcb4fb81` |
| rd-ref | `rd-46fc19844ad6713b6a5e76797f43a967572217ce1bee9820c6795461e7c1de6a` |
| 完整 HTML hash | `6a1dd633260554bd0c1b84f276bed0784fd7c3e27d39d3764cc3fdb9aa42bdca` |
| 原始源 | `https://example.org/products/mp-25`，quote `<a href="/contact">`，UTF-8 bytes `[158,177)` |
| 时间/目标 | 2026-11-10T12:00:00+00:00，目标 `https://example.org/contact` 返回 404，仅捕获时状态 |
| claim | CTA-02 v1.0.0；SOURCE_FACT_BINDING_VERIFIED；native bridge EXACT_NATIVE_HTTP_ID_MAPPING |
| 解释/行动/复核 | 各自独立 binding；原状态 HUMAN_REVIEW_REQUIRED，不是已证明的客户行为或销售损失 |
| 身份与会话 | 未来授权的 Reviewer-A，归属 tenant-test 且分配本任务；本文件仅为占位，不证明真实认证 |
| 并发条件 | expected_latest=1、review_seq=0、session target=T404、服务端可信时间、幂等 key=设计占位 K1 |

pack/execution/package/完整两个 Guard refs、finding id、source quote 和所有 hash 直接见输入 JSON，
不用手工复制后当作可信 pin；正式实现从独立可信仓库持有并重放它们。

### 从打开到回执（预期，未执行）

| 步骤 | Reviewer 看见/操作 | 必需后台输入/判定 | 预期输出（不是已运行结果） |
| --- | --- | --- | --- |
| 1 | 从本人待审队列打开 v1，顶部“仅内部、未分享” | 会话身份/角色/assignment + scope；读取独立 refs | 私有精确 HTML，T404 审核会话；没有批准 |
| 2 | 左侧一个 404 路径事实，右侧点击原始 quote/位置/捕获状态 | C3/逐条 Guard/native bridge/HTML 全量重放 | 来源面板为转义文本；记录本 target 下的查阅，无原站导航 |
| 3 | 核对假设：“采购商可能需要绕行”；接受为假设 | 对应 claim/binding，原 HUMAN 状态 | ACCEPT_AS_HYPOTHESIS 处理，不升级为字面事实 |
| 4 | 核对候选修复和重新访问方法、正向原文与未检查范围 | 全部展示项处理完成，无 REJECTED | 仅准备完整签署内容，没有分享或报价 |
| 5 | 点击“批准这个版本（不分享）”，确认 v1/T404、本人和限制 | 再授权、CAS=版本1/seq0/T404、对象字节与来源再验 | 事务一次记录 native decision + FullReviewDecision + 投影/审计/outbox |
| 6 | 保存成功后才显示“已记录审核通过，仅内部” | durable 回执 D1，effective_current=true | 原 RA3C JSON/HTML/hash **完全不变**；独立 native 批准副本/侧车形成 APPROVED_PRIVATE |
| 7 | Reviewer 想让客户看 | 无 Owner 单独 grant/consent、无 RA4 recipient runtime | 客户访问仍拒绝；UI 显示“分享未授权”，本阶段按钮禁用 |

此预期批准接受的是有限的表达与候选行动，不认证工厂/证书、不证明表单送达、Google 排名、转化或丢单。
当前 Phase0 没有真正执行第 5–6 步，只有设计要求。

### 退回与拒绝分支（各从独立的尚未决策初始状态开始）

- **退回**：Reviewer 对“可能影响”的表达提出明确调整意见，选择 REQUEST_CHANGES，说明具体 binding。
  预期生成唯一退回事件，状态 CHANGES_REQUESTED；原稿与意见保留，不生成任何批准。
  Operator 后续形成 v2，旧审核轮次失效，全部重审。当前候选不支持任意改写，需先解决 DD 编辑输入门禁，
  不能仅在浏览器改文字、不能为通过测试放宽白名单。
- **拒绝**：Reviewer 认为当前材料不适合作为商务沟通依据，填具体理由 REJECT。
  预期关闭 v1，保留原稿/原理由；不能把同版本状态直接改回 APPROVED。
  需要继续必须显式新版本；有证据的路径事实不会因拒绝而被删除或重写。

关联验收：A02、A04、A09–12、A28、A33、A43–48。

## 场景二：200 路径、零问题，只确认范围

### 输入与边界

读取 `SCENARIO_INPUTS.json` 中 case=200 的完整 rd-ref/editorial/HTML hash/pins；
`kind=PRIVATE_COVERAGE_SUMMARY`、issue_count=0、native_report_version=null、private=true、
NOT_APPROVED、shareable=false。这是固定合成 200 捕获，不代表真实表单可提交/送达，
不等于全站健康，网站自述也不证明企业法律身份。

设计身份为同租户已分配的真实 Reviewer 占位；expected_latest=1、session target=T200；
acknowledgement 使用单独 kind，不借用 native ReviewDecision。

| 步骤 | 页面与操作 | 必需输入/检查 | 预期输出（未执行） |
| --- | --- | --- | --- |
| 1 | 打开“0 项可报告问题 · 检查范围摘要” | scope/pack/Guard/精确 HTML 仍须独立验证 | 显示原始 200、正向原文、未检查/UNKNOWN，没有问题卡片凑数 |
| 2 | 核对保留页面、原始片段与限制 | 当前 T200、来源位置/覆盖及无 native | 确认“未发现本能力可报告缺陷”，不签全站无问题 |
| 3 | 动作只有“确认已核对检查范围” | 真实 Reviewer 会话 + target + seq，ack 幂等 | ACKNOWLEDGED_INTERNAL_ONLY；独立 ack 事件，native 始终 null |
| 4 | Operator 请求一个“已批准 L1”或空 finding 占位 | 仍无真实缺陷 | D_COVERAGE_NOT_REPORT；不调用原 approve_version，不生成 fake Finding/ReportVersion |
| 5 | Owner 尝试分享这份 ack | 没有正式 native L1/分享读取合同 | D_SHARE_DISABLED；不能借 Owner 身份绕过零问题边界 |

若业务需要了解未观察到的内容，只能提出后续授权/补证据申请，不能擅自升级 L2、提交表单或抓取真实站点。
未来确需对外发送零问题摘要，须 Owner 单独批准版本化报告种类、原生合同兼容与接收人访问机制；当前延后。
403/WAF/robots/未保留正文同样不能转为假缺陷，本场景的范围确认不能洗成正向认证。

关联验收：A19–20、A31–32、A36、A45。

## 场景三：外租户、审后 HTML 变化及合法新版

### 初始条件

固定原始输入仍为场景一的 v1。设计前置为“未来已存在一份可信真人批准侧车 D1 绑定 T404”，
**这里只是假设，不生成 D1，不回写原文件**。攻击者持有原 H0、report id、旧回执的副本；
这些不等于身份或修改权。以下分成独立检查点，避免跨租户错误掩盖完整性缺陷。

| 检查点 | 攻击/操作的确切变化 | 首个应触发的判定 | 预期输出（未执行） |
| --- | --- | --- | --- |
| C1 外租户 | Reviewer-B 的有效登录来自 tenant-other，自报 body tenant-test/reviewer-A | 身份实际 tenant 与资源不符，在读取内容前 D_TENANT_SCOPE | FORBIDDEN_TENANT，零 report 字节，无对方标题/hash/存在性信息，无决定 |
| C2 同租户改 HTML | 改用有任务权限的 Reviewer-A；将原 HTML 追加不可信 script 或“已认证/排名第一”等文字，原 H0 不变 | 原字节 SHA 不同于固定 `6a1dd6…bdca`，D_ARTIFACT_TAMPER | REPORT_VERSION_STALE；不展示篡改全文，不执行内容，不生成批准副本 |
| C3 自己重哈希 | 攻击者同时修改 html_sha、editorial hash、rd-ref，并给出新的 sidecar 摘要 | 服务端独立可信 T404/对象 refs 不相符，Guard/原 loader 重放失败 | D_TARGET_STALE/SOURCE_INTEGRITY；攻击者自证摘要不能替代 trusted pins |
| C4 同 id 新来源 | report_id 不变，换新的 EvidencePack/ref 或 policy/run | 原审核 target 的来源上下文改变 | D_SOURCE_CHANGED；不可沿用 D1，即使可见文字看起来相同 |
| C5 合法新 v2 | Operator 经允许管线形成新私有 v2，来源/文字/布局任一变更，原始对象保留 | 单调发布新 latest，v1 有效性 false | v2 REVIEW_REQUIRED；旧 D1 保留历史，所有旧分享授权失效；需要新真人审核 |
| C6 旧回执/分享 | 用旧 D1 或假 grant 请求 v2/旧对象缓存 | latest / target / Owner issuance / subject / grant / consent / runtime 必需条件不全 | 拒绝所有外部字节；不伪造 Owner actor 调用 check_share |
| C7 并发/故障 | 两个旧会话一起提交；或保存时丢审计事件/仅投影变绿 | CAS 冲突 / 原子事务完整性 | 至多一份持久决定；不完整时无有效批准，不能根据绿标补造事件 |

审计只记录内部有权限可见的安全原因、request id、scope 和目标摘要；外租户响应不回显其输入中的敏感字段。
需要修复的动作是重新验证、合法新版本与重新审核，不是改旧引用、忽略 hash、放宽隐私规则或给模型 Reviewer 身份。

关联验收：A01、A03、A05–10、A13–18、A21–30、A35–42、A45–48。

## 演练结束状态

本包产物只是三个场景设计与固定参考数据。实际 human decisions=0、grants=0、customer accesses=0、
models/live websites/deployments=0；没有签署任何人名或生成“已批准客户报告”。
Owner 设计审阅通过后仍需独立生产代码 GO，不代替 RA3C/QA48 的最终合并门禁。

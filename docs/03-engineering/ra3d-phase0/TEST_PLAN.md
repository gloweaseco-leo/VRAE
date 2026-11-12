# 待实现验收目录 P0.1

**48 个设计用例，状态全部 NOT_RUN / IMPLEMENTATION_NOT_STARTED。**
这不是 Codex-1 PR #48 的 64 项 RA3C 独立业务测试，不运行、不修改、不认领其结果。
本包的文档/静态 HTML 检查仅见 DESIGN_EVIDENCE.md；工程回归不能冒充未来审核运行时验收。

## 共同测试基座（未来实现）

准备隔离 tenant-A/tenant-B、可信真人 Reviewer-A/Reviewer-B/Owner-A、Operator/Worker/Service，
真实适配器与合成 actor 结果分列。参考输入从固定 SCENARIO_INPUTS.json 读取；正式实施时改用
已合并并验收的 RA3C，不能把当前未合并候选当稳定 API。原始 pack/quote、finding、Guard 和 HTML
均为不可变对象；H0/Htarget 独立持有。测试时钟为明确服务端 aware UTC，客户端钟另设。

每条负例同时检查：无未授权字节泄露、无新增有效 decision/grant、无错误 APPROVED 投影、
原证据/原事件未改、错误为安全固定码且不回显攻击文本。事务例必须真实测试持久边界与恢复；
纯内存模拟只标 DOMAIN_SIMULATION，不标 DURABLE/RUNTIME_PASS。

| ID | Given / When（设计输入） | 必须得到的结果/判定点 |
| --- | --- | --- |
| A01 | Reviewer-B 用有效自身会话读取/批准 tenant-A id | TH01 D_TENANT_SCOPE；内容、hash、标题、存在性均不泄露 |
| A02 | 同租户 Reviewer 未分配此任务；随后分配合法 Reviewer | 未分配拒绝；合法准备仅得到私有 REVIEW_REQUIRED 会话，不自动批准 |
| A03 | body 伪造 reviewer_id 或 Owner，登录者仍 Operator | TH02 D_ACTOR_MISMATCH/FORBIDDEN_ROLE，无决定 |
| A04 | Worker/Service/Fake provider 包装真人字段，及 Owner 真实双角色分别操作 | 前者拒绝；后者须独立签署与授权动作，不能角色自动放行 |
| A05 | 页面审 v1，提交前 latest=v2 | TH03 D_TARGET_STALE，无对 v2 的决定，UI 要求重新审核 |
| A06 | H0 未变，editorial/HTML hash 与 session 不同 | 同样 stale；不能只比较 native hash |
| A07 | 同 report_id 换 pack / run / policy version 并自报新 refs | TH04 D_SOURCE_CHANGED，不接受请求自证 pins |
| A08 | 合法采集新包并创建 v2，内容看起来相同 | v2 仍须新 target/整份审核；v1 批准/勾选不继承 |
| A09 | 两人同时 APPROVE，同 expected seq | TH05 仅一个 commit；另一个冲突，事件数一 |
| A10 | APPROVE 与 REQUEST_CHANGES 同时提交 | 首个 CAS 胜出，后者拒绝；不能最后写入覆盖 |
| A11 | 同 key/同命令双击、断线重试；期间可出现新版 | TH06 只一回执；新版出现时原回执标历史无当前效力 |
| A12 | 同 key 改 reason/action，或不同 key 重复已批准版本 | IDEMPOTENCY_CONFLICT / D_REVIEW_CLOSED；不增加第二个决定 |
| A13 | 对象校验后被换成含一个字差异的 HTML | TH07 D_ARTIFACT_TAMPER；无展示/批准旁路 |
| A14 | 仅 CSS/资产/hash/页脚水印或打印字节改变 | 同样新制品/新版本；不能批准后渲染另一个版本 |
| A15 | quote/href/byte range 被改、evidence_id 仍真 | TH08 D_SOURCE_INTEGRITY；逐条重放失败 |
| A16 | 构造合法全局 refs 但换绑定事实、pointer 或 Guard.status | 重放拒绝；全局列表不当语义证明 |
| A17 | 浏览器钟回拨，grant 服务器已到 expiry | TH09 expires_at<=now 拒绝；UI 倒计时无权延长 |
| A18 | 服务端无时区/低于已持久高水位；修复时钟 | D_CLOCK_UNTRUSTED fail closed；审计恢复前不可判断有效 |
| A19 | 未审 v1 请求外部 copy/export/print/raw object | TH10 D_APPROVAL_REQUIRED/SHARE_DISABLED；只有内部授权预览可见 |
| A20 | 已批准但无 Owner grant、consent 或 RA4 runtime | 外部始终拒绝，不因绿标或 account owner 自动分享 |
| A21 | 批准后文字/证据/模型上下文更新成 v2 | TH11 v1 effective=false；历史事件完整，新版 REVIEW_REQUIRED |
| A22 | 删除 v2 再把 latest 指回已批准 v1 | 拒绝回拨；还原文字须新 v3 和新审核 |
| A23 | 已过期或 revoked_at 非空的 grant 被重放 | TH12 SHARE_EXPIRED，无旧对象 URL 回退 |
| A24 | native grant ACTIVE，但侧车已撤销/绑定另一 target | 同样拒绝；两个记录不一致绝不取更宽松一边 |
| A25 | 原 HTML quote 含 script/img onerror/远程像素或命令 | TH13 惰性转义；无 JS 执行、工具调用或外部请求 |
| A26 | reason/修改建议含恶意链接、方向控制、超长 Unicode | 有界拒绝/安全转义；不可影响身份、scope、签署或展示结构 |
| A27 | 写 projection 成功前/后模拟 event 或 sidecar 持久失败 | TH14 事务回滚；重启只见一致事件+投影，否则 D_AUDIT_INCOMPLETE |
| A28 | commit 后响应丢失、outbox 重发/恢复 | 一份 durable 决定、消费幂等；查同 key 后才能显示成功 |
| A29 | prepare 合法，commit 前角色/任务授权被撤销 | TH15 当场重新授权拒绝，旧会话不可用 |
| A30 | 会话过期或登录主体变更后重用确认按钮 | D_SESSION_INVALID；不静默改 signer，必须重新准备 |
| A31 | native=null 的 200/受限摘要执行 APPROVE | TH16 D_COVERAGE_NOT_REPORT；无 fake Finding/native decision/grant |
| A32 | 合法真人确认零问题范围，并请求分享该 ack | 仅 ACKNOWLEDGED_INTERNAL_ONLY；分享拒绝，未知仍未知 |
| A33 | 人接受 hypothesis 后尝试改 Guard 为 SOURCE_FACT | TH17 原状态不改；侧车仅 ACCEPT_AS_HYPOTHESIS |
| A34 | 有 REJECTED/未绑定内容，或遗漏展示 claim/固定 scope 与 limits section，但全选“已审” | D_CLAIM_CEILING/不完整审核，整份 APPROVE 禁用；固定 section 不伪造 Guard binding |
| A35 | 同内容换 model/rule/renderer/guard 版本 | TH18 target 不同须重新审，不保留旧批准 |
| A36 | 真实模型却 prompt/gateway provenance 缺失；明确 NOT_RUN 的规则样本 | 前者阻断正式审批；后者保留真实无模型标识，合成不变实际人工审批 |
| A37 | future grant subject 与登录主体不同，token hash 错，consent 失效 | TH19 D_SHARE_SUBJECT，零字节；本 Phase0 访问恒禁用 |
| A38 | 只有一份自签 Owner 字段/假 issuance event，无可信授权来源 | D_OWNER_ISSUANCE；hash/原 schema 合法也不当身份 |
| A39 | 旧 CDN/浏览器缓存于 revoke 或 latest 变更后被使用 | TH20 当次授权拒绝且 no-store；不能从缓存恢复可用分享 |
| A40 | 直接猜 artifact_ref、历史 raw HTML 或对象存储签名 URL | 无 report scoped 授权就拒绝，不跳过 target/decision/grant 检查 |
| A41 | 复制另一报告/租户的 decision id 与 hash | TH21 D_DECISION_UNTRUSTED / tenant 优先拒绝 |
| A42 | 删除/修改事件再重算 hash 链，投影仍绿 | 可信仓库完整性验证失败；SHA 链不代替可信写入，不能恢复批准 |
| A43 | REQUEST_CHANGES 后直接调用原 approve helper 的外层入口 | TH22 D_REVIEW_CLOSED；新版本之前不能批准 |
| A44 | REJECT 后修改原 reason 或直接把投影换 APPROVED | 拒绝覆盖，原理由/事件保留；重开需新版本完整审核 |
| A45 | 原 H0 正确但缺 FullReviewDecision / Htarget | TH23 D_FULL_BINDING_REQUIRED；禁止“只有 native”批准/分享 |
| A46 | 向冻结 ReviewDecision 添 HTML hash、或在 reason 偷放权威 JSON | 原 schema 拒绝额外字段；reason 只是文本；需未来独立版本化传输合同 |
| A47 | 用户点击后服务器未 durable commit，响应延迟/丢失 | TH24 未确认状态不显示通过；查同幂等回执，确认结果不造事件 |
| A48 | 确认框打开时切版本、换登录人；手机/键盘/屏幕阅读器操作 | 锁定目标/签署人，变更强制重新准备；批准/退回/拒绝文案和焦点清晰 |

## 人工业务与界面验收（后续，不计为已通过）

- 评审者能在 404 场景指出“捕获事实”和“可能影响”各自的来源与边界；不会认为人审证明真实丢单。
- 对照 0 问题场景，明确能确认检查范围但不能签出一个虚假的已批准 L1。
- 能发现新版本/恶意 HTML/外租户阻断；没有“看似成功”的审批、外发、E2/E3 或报价。
- 桌面证据并排、375px 纵向阅读、键盘/读屏、无颜色依赖；版本切换/失败/超时不会误签。
- 未来实际身份、事务和撤销须端到端实测；性能和人审耗时阈值由真实样本建立，本设计不伪造秒数。

## 未来实施交付门槛

所有用例由 Owner 放行后的实现提供精确输入、实际断言、计数、日志、前后对象哈希和事务/身份来源；
独立 QA 复核。工程全量/历史固定回放和真实四项 CI 在那一轮按实际修改要求重跑。
Phase0 只有设计检查通过不等于其中任何 A01–A48 运行通过。

# RA-4C2 · 逐 Claim 处置提议 / TEST_ONLY 验证预览

Issue #67；冻结 V1.1；入口已取回并核实 accepted main `cf11278ba4c9b62b3645cdbd6fd2cd8bb2f1838b`。新独立 worktree `ra4c2`，分支 `codex2/ra4c2-offline-review-proposal-ux`。仅改 app、其测试、新建本目录。未读取或导入 Codex1 未合并 P2A。

**最终 main 集成**：Owner 之后正式合并 PR #69，accepted main 推进至 `558d183624a0a36d1f4eaf9d3d75af73b9c88547`。普通 merge `0f4acc2cb9922d857b51abc247b2541ed42a8b37` 的顺序父为旧候选 `5c9d018d5fc76b4df265c1d518d836c463e7c7bf`、新 main。P2A 生产/测试/SQL/CI/QA 全部保持原 blob/mode，未接入UI；只有在 Owner FINAL PASS 合并后，才只读使用其已验收 artifact auditor。入口CF封存保存在 SOURCE-SEAL-cf-entry.json；最新封存以新main为基线。

旧候选 5c9 的六CI实际已全绿，但启动时 main 已推进，真实 merge-ref 父为新main，和该候选自己的tree不同，不能代替正常集成后的最终CI。其完整原始日志/产物只作历史。PG XML 的 pure25 = 原11 + 新14；新main还执行P1-v1 54、v2兼容重放54、P2A86。最终 `verify_pg.py` 只在本授权post-CI目录复制原始产物别名并调用**原样保留的** accepted main `ra4a-p2a/audit_hosted_pg.py`，检查实际调用、独立原始字节、schema/RLS/备份恢复/清理/源码与artifact digest。原生11与54不减少，兼容54不冒充108独立案例。锁定驱动只安装本授权 runtime（忽略目录）供只读核验，不改依赖、不连接数据库。

复核 PG 产物前，可运行 `python -m pip install --no-cache-dir --target docs/03-engineering/ra4c2-review-proposal/runtime/pg-driver -r requirements-ra4a.lock -c requirements-ra1a.lock`。完整最终核验命令为 `python -B docs/03-engineering/ra4c2-review-proposal/audit.py <标准CI原始目录> <PG原始目录>`。GitHub原始目录由本目录 `hosted-ci.py <run_id>` 下载，需仓库读取权限；最终run_id和ZIP哈希在PR body。所有写入都在本授权目录，不修改原样的main核验脚本。

## 实际操作

在仓库目录运行 `python -B -m apps.operator_console.preview --test-only --synthetic-fixtures`，仅监听 127.0.0.1；打开 stdout 中本次启动的随机 fixture URL。无参数或外部 host 启动拒绝。

任务池（原 11 项 / 8 阶段）→ 404 任务 → 原生核对 → 精确核对对象 →「进入逐 Claim 提议预览」。每项显示原始文字、语义角色、机器状态、精确引用/UTF-8 范围、固定来源与类型允许的处置。默认所有选择为空、四个确认未选；用户必须主动选择。来源不编辑、不访问原站。

404 六项中，静态来源事实仅可 ACK_LITERAL_FACT；影响仅可 ACCEPT_AS_HYPOTHESIS；行动/复验仅可 ACCEPT_AS_PROPOSED_ACTION。还可逐项提议 CHANGE_REQUESTED / REJECTED。整体动作 APPROVE_CANDIDATE（候选接受提议）、REQUEST_CHANGES 或 REJECT 由原生合同验证；退回/拒绝要求原因与 Claim 定位。没有新的审核规则引擎。

200 三项字面来源 / 0 findings 仅构造独立 CoverageAcknowledgementProposal，显示 SIMULATED_INTERNAL_SCOPE_ACK。native H0 / ReportVersion 为 null，明确「在已检查的范围内未发现可确认问题」。不补造 CTA Guard、不允许候选批准或虚构问题。403 / robots / UNKNOWN 等无表单。

## 验证链与状态

未提交 GET → 请求内表单输入 → 本地纯验证 → CONTRACT_VALID_ONLY 或原生拒绝代码 → 仍 PRIVATE_NOT_APPROVED。结果不是决定、提交成功、业务通过或人工签署。无保存、数据库、session、cookie、浏览器存储、导出/复制私有字节按钮。重新打开 GET 为全空未提交状态；浏览器后退可能恢复本页未保存的输入，不构成持久确认。

每个 POST 都通过既有 ConsoleService.target 重新核对 authority/assignment/tenant/owner、独立 task→case 关联、最新固定合成版本与 exact draft/target，然后调用原生 RA3C replay / Guard 与 D1/D2 build_target / validate_target。来源与目标来自同一快照。复用已持有 pins，未 repin 或重写任何历史原文/引用/哈希算法。

表单提交每个 claim 的 guard_ref / binding_ref / pointer 与 disposition；缺项、重复、外来身份、语义升级由输入形状及原生 validate_proposal 拒绝，不静默修复。四个 section 独立提交 target-bound 勾选值；未选不会自动补齐。tenant/report、覆盖摘要取自本次重放对象，调用者不能提交 actor、owner、trusted、verified、sequence 或生产 adapter。合成 expected_review_seq=0 / 固定测试 idempotency key 仅满足纯合同形状，不是实际 ledger 或收据。原生返回的 command digest 不作为 UI 审批回执。

## HTTP 边界

ConsoleInterface.dispatch 原 POST 和 ConsoleService.mutate 始终拒绝。只有显式 loopback fixture harness 的 `/__fixture__/<随机路径>/tasks/<assigned>/proposal-preview` 接受 POST。ProposalPreview 只接受显式双旗标、exact FixtureAuthority/Repository/NativeVerifier 和绑定的不可伪造 fixture context；拒绝真实身份上下文。

Host 必须为实际 127.0.0.1:port；POST Origin 必须精确同源（null 不允许）；重复 Host/Origin/Content-Length/Content-Type、Cookie、Authorization、Transfer-Encoding、cross-site/same-site 请求拒绝。仅 application/x-www-form-urlencoded，单个十进制 Content-Length ≤24576 bytes，3 秒读超时；最多64字段，严格 UTF-8 / percent、重复/未知字段拒绝。拒绝任何 URL 输入、任意 mutation/share/export/download API。未分配任务在读取来源前拒绝，不返回原文或存在性。

原 no-referrer 在真实 Chromium 导航 POST 中产生 Origin:null。修复为**仅本地提议表单/结果 200 页面**使用 same-origin Referrer-Policy，保持严格 Origin 校验；跨站 referrer 仍不发送，其他页面仍 no-referrer。未靠允许 null Origin 获得通过。CSP 保留无脚本/无外部连接、仅 self form-action；原始 HTML/原因始终转义，不执行。控制/方向覆盖符等非法原因拒绝且不反显原文。没有 access/request body 日志。

真实 TCP 浏览器/HTTP 测试在普通 CI 与本地运行。冻结 isolated-http worker 的内核策略拒绝 127.0.0.1；首轮 CI 因测试尝试连接该禁止地址而超时取消（原日志保留）。仅在该冻结隔离环境中，HTTP 协议测试通过 AF_UNIX socketpair 驱动**原始 Handler 与 BaseHTTPRequestHandler 解析器**，执行相同请求/断言，不伪造响应；额外实际监听 TCP 并验证 loopback 仍被内核拒绝。普通环境仍实际启动原 TCP harness。没有更改防火墙、工作流、超时、产品端口或任何业务预期。

## 三个完整模拟场景

1. 404 候选：先点原始证据核对静态联系路径与 404，回到表单；六项各选类型限定语义，阅读范围/局限/完整报告/商务边界并勾选；选候选接受提议→仅显示合同有效，仍无批准。
2. 404 退回/拒绝：影响第2项定位 CHANGE_REQUESTED 或 REJECTED，输入具体原因，对应整体 REQUEST_CHANGES / REJECT→原生合同检查定位及原因。若漏定位或理由为空则拒绝；目标版本变化则停止显示来源。无真实事件或持久决定。
3. 200 零问题：核对三条字面来源、200 规则来源及局限；四段确认后仅选择内部范围确认→独立覆盖 ACK 验证。0 findings / H0 null 不会变成 APPROVED。

## 证据与最终交付流程

新测试保留 initial RED，实际调用原生 proposal validator、原生 replay 与真实本地 HTTP。旧101 Console、原127 reviewing、冻结 V2 64+54 及历史 V1 RED53/Gold0/26 均保留。双 Python bounded 与真实浏览器记录源 SHA、实际调用、原始日志、CDP/网络、DOM、截图哈希。失败/过期轮次明确单列，不能冒充最终通过。

第二轮标准CI的3.11达到冻结12分钟上限取消（同轮3.13/隔离HTTP通过）。新测试改为仅复用一份**原生生成的测试输入模板**，每用例深拷贝；被测 ProposalPreview.validate / service.target 的真正来源重放及 validate_proposal 调用仍逐次执行、不mock、不缓存。全部96项新断言、旧测试和CI超时不变；未完成的本地324轮次因准备该测试修复而主动中止，保留日志但不签发通过receipt。

最终先提交本地证据与 source/artifact seals；精确最终 HEAD 运行四项标准及两项真实 PG CI。post-CI 原始 API/Git/log/artifact、ACCEPTANCE 与 ZIP 留在本授权 evidence/hosted-*，PR body 公布精确 SHA、合并父、tree、job/artifact URL 和哈希，避免为嵌入自身 CI 而追加提交漂移 SHA。只用正常 merge 已验收 main。

## 生产接线前提 / 未完成门禁

真实身份/session + 独立任务分配、受保护不可变字节与可信 latest ledger、事务 CAS/完整 native decision、audit/outbox、幂等与恢复，均需独立 Owner 接受后才能使真实人工动作可执行。本轮不接入这些能力、PG、P2A、ShareGrant、客户访问、模型、付费外部数据或部署。原 production prepare always-deny 保留。Human Gold 0/26、RA4 EXIT/RA5/E2/E3 均 NO_GO。保持 Draft，停止等待 Owner exact-SHA FINAL PASS。

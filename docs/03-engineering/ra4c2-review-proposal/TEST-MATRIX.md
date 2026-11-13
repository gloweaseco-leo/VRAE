# RA4C2 验收与威胁矩阵

原生提议合同的验证器决定语义；app 只做输入边界、来源重放和展示。所有用例为自动化合成测试，不代表真人验收。最终计数由 XML/原始调用记录与 source-matching receipt 核定。

| 目标/攻击 | 入口与实际验证 | 预期 |
|---|---|---|
| 404 6 Claim 候选 | real ReportDraft.load + build/validate_target + ReviewCommandProposal + validate_proposal spy | 合同有效，private/not approved，无真实决定 |
| 退回/拒绝 | 指定第2 Claim，具体原因，对应整体动作 | 只返回提议预览，无任务阶段变化；mutate deny |
| 200 3 Claim / 0 issue | CoverageAcknowledgementProposal 实例 + 原生验证 | 独立范围 ACK，native H0/version null；无 APPROVE |
| missing/foreign/duplicate Claim | 缺失绑定字段、外来 binding、重复三元身份 | 输入拒绝或原生 D_CLAIM_INCOMPLETE |
| 机器语义提升 | impact → ACK_LITERAL_FACT，空/未知 disposition，candidate 带 change | 原生 D_CLAIM_CEILING；没有新 Guard/证据生成 |
| missing/extra ACK、错误 target | 少选 section、外来 section、错误 digest | 原生 D_SECTION_INCOMPLETE 或形状拒绝 |
| 无定位/空/空白原因 | REQUEST_CHANGES/REJECT，缺少对应 Claim 处置 | D_REASON_LOCATION / D_REASON_REQUIRED / D_UNTRUSTED_TEXT |
| 超长/control/bidi 原因 | 2001字、控制符、方向覆盖符 | 原生拒绝；非法原文不反显 |
| HTML/JS/body 注入 | HTML/script 作为原因 + 浏览器真实输入提交 | 转义文字，不执行；零外部网络 |
| 来源/quote/UTF8/Guard/policy | form 打开后修改 native source，实际重放 | SOURCE_INTEGRITY；不回显原文 |
| stale/version/404→200 | 修改 target、draft、版本、完整 case DTO | STALE/SOURCE_INTEGRITY，不能切换 fixture authority |
| actor/tenant/assignment | None/dict/Owner/verified/其他 capability、foreign Scope、未分配ID | 先拒绝，来源 port 未调用；不泄漏存在性 |
| caller trust / URL / production | verified/trusted/owner/actor/tenant/sequence/idempotency/adapter/url 等额外字段 | 形状拒绝，不赋予权限 |
| HTTP 跨源 | wrong/null/missing/重复 Origin，wrong/重复 Host，cross-site/same-site | 403，原始数据不泄漏 |
| HTTP body | Cookie/Authorization/TE、重复/缺失长度、超24576、错误/重复类型、非法UTF8/percent/重复字段 | 403/400，不进入业务验证 |
| 非授权动作 | direct ConsoleInterface POST / service.mutate / HTTP approve/reject/share/export/download | always-deny，无新生产接口 |
| 无旗标/外部模式 | serve 无双旗标、0.0.0.0；真实 adapter prepare | 拒绝启动/操作 |
| 原有 Console/QA | 原58 + C1原43 + 原 reviewing127；冻结 V2 64+54 | 原文件同 Git blob，不调整预期 |
| PG 与隔离 | 新精确HEAD四标准CI + 双PG16 CI，原SQL54+11、容器/worker/browser拒绝 | 实际执行日志与原artifact核验，skip不当pass |
| 浏览器 1280/375/320 | 真click/select keyboard/中文原因/form POST；source back/forward；重开GET；stale/注入/200ACK | ≥12px提示、≥44px主控件、无横溢；原始CDP/DOM/截图哈希 |

## 保留的初始 RED 与失败

- `evidence/initial-red/`：新增模块尚不存在时的真实 pytest collection RED，原始 XML/log 保留。
- `browser-2026-11-12T23-16-36-109Z`：真实表单 Origin:null 被403拒绝。修正仅本地表单 Referrer-Policy，不允许 null Origin；后续 HTTP 新增 null 拒绝测试。
- `browser-2026-11-12T23-18-17-817Z`：21项处因读取折叠合同的 innerText 失败；改为真实点击展开后核对，未改业务预期。此前404动作/篡改检查记录保留，不作为完整三视口通过。
- 首轮 hosted `43328389718`：标准 Python 3.11/3.13 与隔离浏览器成功，isolated-http 15m14s 超时取消；原始日志/API/Git/artifact 在 `hosted-43328389718-20261113T000234`。冻结防火墙禁止 IPv4 loopback；测试适配器改用 AF_UNIX 驱动原 Handler，并新增真实 loopback 内核拒绝测试。普通环境/浏览器保留真实 TCP，不跳过32项HTTP断言、不修改安全规则或CI。旧双Python323是旧测试源历史，最终要求双324。

最终绿轮必须源哈希匹配、全部断言通过；不覆盖失败记录。历史 RA3C V1 RED53 和 Human Gold 0/26 保持封存，不重新标记通过。

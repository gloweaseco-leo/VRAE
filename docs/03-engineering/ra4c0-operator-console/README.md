# RA-4C0 · 内部运营只读应用层

基线：`a185f9ce7e67904f2c0aef854716ca9844144592`。Owner Issue #60，冻结 V1.1 与阶段台账 #59。此工作不代表 RA4 EXIT、真实用户认证或人工审批放行。

## 实际操作

在仓库根目录用已安装项目依赖的 Python 执行：

```powershell
python -B -m apps.operator_console.preview --test-only --synthetic-fixtures
```

打开输出的 **127.0.0.1** 临时地址。两个启动开关缺一即拒绝，不能更改绑定地址。随机 fixture 路径仅隔离本次测试上下文，不认证真实人。不要将此辅助服务器用于生产或转发。

1. 任务池有 11 个已分配合成任务、8 类展示阶段。按阶段筛选，或在已分配任务标题和 ID 内搜索。没有 URL 提交、全租户搜索或新任务创建。
2. 打开“工业泵 · 联系入口 404” → 任务详情 → 只读核对区。观察事实与三个 `HUMAN_REVIEW_REQUIRED` 提议分开展示。点击事实或提议的来源链接，检查固定采集时间、URL、Evidence ref、原始引文与 UTF-8 字节区间。可展开完整原文、Guard、版本及全部哈希。返回核对区及任务池。
3. 打开 200 任务。仅显示零问题与覆盖核对；CTA 规则 PASS 没有 CTA Claim / Guard 绑定，页面明确说明。联系路径的原始规则来源仍可点击查看；其他原生静态线索各有自身 Claim 回查。不添加问题、不生成审批。
4. 查看 403/WAF、robots、UNKNOWN、Guard 无效及失败任务。提示“不能据此判断网站缺陷”，不显示未验证报告，给出内部范围核对/隔离动作。

页面为 Python 服务端呈现和普通链接、GET 表单及原生 disclosure，零前端依赖/脚本。没有第二套证据或审核引擎，也没有复制旧工作台。内部完整报告是转义文本，不提供客户报告下载或外站链接。

## 可复用的应用边界

| 层 | 本轮实现 | 后续独立授权接缝 |
|---|---|---|
| Interface | `ConsoleInterface.dispatch(context, method, target)`、SSR views、响应值 | 经批准的真实 API 外壳；此处不接受浏览器提供的 actor 字典 |
| Application | `ConsoleService.pool/detail/review/evidence` | 可信已分配范围的查询；不执行作业或审批 |
| Read ports | `ReadAuthority`、`TaskRepository`、`NativePreparation` | RA4A/B 可信身份、RLS、不可变来源存储及任务队列尚不可用 |
| Accepted domain | 现有 AuditRun schema、EvidencePack、FindingPackage、Guard、ReportDraft | 保持原合同与语义，未依赖 PR58 的未合并 API |
| Test adapters | 内存任务与 opaque context identity；固定 404/200 来源，`SYNTHETIC_TEST_ONLY` | 不能用于真实人；任意 role/tenant 字典均不授予权限 |
| Review handoff | 只读原生版本+独立 pins 核对 | D1/D2 审核对象、事务、事件/审计/outbox 尚不可用；不得假装存在 |

没有认证、数据库、持久化、Cookie、localStorage、ShareGrant 或审批事件。`mutate` 端口固定拒绝；不存在 approve/reject/share/cancel/download 路由。非 GET/HEAD 返回固定 `NOT_IMPLEMENTED`，无可信 fixture 上下文返回 `UNAUTHORIZED`。所有 URL/输入/错误字符串不参与网络访问。

## 合同与威胁边界

版本 `operator-console-read-0.1`：严格 DTO 含 `source_kind`、`task_id`、`owner_scope`、`audit_run`（原生 tenant/run/status）、展示 stage、coverage_reason、report_case/version/pins。字段集、长度、控制字符和原生 schema 均校验；不允许 APPROVED/SHARED 伪状态。展示阶段不是新的原生工作流。

可信上下文独立传入，不能来自 query/actor dict。先检查 assigned IDs，再查任务，以统一拒绝避免存在性泄露。任务租户、owner、原生 run、报告版本和固定来源必须全部一致。每次核对/来源请求重放 accepted-main 原生加载流程；不缓存可变可信结论。纯页面层不拥有任何审批状态。

`native-pins.json` 由一次性 `prepare-pins.py` 从**指定已验收 Git 对象**提取独立 pins 及完整来源 envelope SHA-256，脚本拒绝覆盖旧 holds。运行时从已有合成 fixture 读字节，先对照独立来源哈希，再实际调用原生 EvidencePack / FindingPackage / Guard / ReportDraft load 和 render。任务/攻击输入不能刷新 holds。原生报告及原始字节均未改写。

| 风险 | 强制行为 |
|---|---|
| 无身份、假 role、跨租户/owner、未分配任务 | 在可信调用边界拒绝，测试上下文不能代替真实身份 |
| 版本变化、替换报告、引用/HTML/Guard/metadata 篡改 | 返回 STALE_VERSION / SOURCE_INTEGRITY，不展示报告内容 |
| 403/WAF/robots/UNKNOWN/遗漏规则/无效 Guard | 中性覆盖状态，不推断缺陷，不伪造报告 |
| title/query HTML、原始来源脚本 | escape；CSP default/script/connect none；来源 URL 为文字 |
| bidi/超长/任意 URL 输入 | 有界拒绝；不发起请求 |
| 写操作、下载或分享 | 固定拒绝，无状态变更 |

当前存在的合成 AuditRun 行、阶段及任务名称是测试适配器，不声称来自真实 worker。只有明确标注的 404/200 报告与来源是已验收原生固定重放。

## 验证与限制

`regress.py` 为每次双 Python 运行创建独立新证据目录，保留全量 pytest、原始历史 V1 RED、19 条历史命令（含伪造 Gold 必须失败）及 8 个封存原生 RA3C 重放。`browser-test.mjs` 用真实 Chromium/CDP 执行 SSR 点击、来源展开、键盘、尺寸、网络及拒绝请求，保留原始命令/响应与截图，不给出虚构的人类可用性评分。

当前 CI 接入的明确目录例外见 [CI-SCOPE-EXCEPTION.md](CI-SCOPE-EXCEPTION.md)。最终测试及精确 SHA 另附验收记录；此文档不提前声称 CI 完成。Gold 仍 0/26，真实审批及客户分享仍 NO_GO。没有后端身份/RLS/事务/恢复/报告发布门禁验收之前，本应用不得接真实人或客户。

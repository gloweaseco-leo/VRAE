# S4 管理层摘要与 VF 内部准备

Refs #137 / #134。基线为 Owner accepted main `6a15ab4514d24c60b4d03d4ec795f6e3bcd435c3`。本轮保持 Draft，等待 Owner 独立复核。

## 产品入口

原签名 L2 导航新增「管理层摘要」：`/b5a/l2/r/{原report_id}/executive`。文档回退为 `executive-document`，同一原签名／定向访问授权，浏览器打印为 PDF。原报告、蓝图、审核回执、历史与哈希权威不变。

摘要直接派生当前原报告，保留五维评估项分母、UNKNOWN 与不适用；全站覆盖分母未知。D1 的本轮窄口径仅展示原观察引用中 HTTP 404/410 的路径阻碍，最多取 3 项；原生工业情景冲突、工程适配、声明日期及买方缺输入不会成为网站故障。本次原生工业报告的 D1 为 **0**，原 7 项蓝图仍完整保留。D2–D6 供资料组织、工程／资质、买方输入、未观察范围和影响假设分别讨论；D6 是影响假设的交叉视图，不是新增缺陷数量。

原 C3 `NativeBusiness` 的 PG Brief 页面新增内部接单准备与四本账。原蓝图的客户输入、责任、依赖、验收、标准候选／定制评估逐项沿用，企业工程与资质责任不升级为网站服务。现有目录属于未核准候选，统一 `SERVICE_CATALOG_PENDING`，没有固定售价、工期或合同承诺。四本账的未计量金额为 null/UNKNOWN；实测运行时长与尚未分摊／对账分开呈现，未将自动演练计作人工服务或真实商务触达。

PG 保存／回读后才可准备有界合成接单。生产者只得到 WAITING_ACK；独立收方进程持私钥，SSR 仅持其公钥，通过私有测试适配器验证 ACKNOWLEDGED / REJECTED / RETRYABLE_FAILED。没有浏览器 ACK 输入或签名密钥入口。相同 Brief 重复准备幂等；重试更换 attempt/nonce，旧回执、伪造签名、跨任务、当前版本变化与撤销后回执拒绝。最多 40 个内存条目、每条最多 5 次尝试。**该演练状态重启即丢失，不能当持久商务凭据；原 PG Brief 不变。**

ACK 不代表客户确认、E2/E3、报价、外发、素材授权或 L2M 执行。未连接真实 VF CRM，未提交真实询盘、部署、签署正式人审或修改原授权/RLS/Worker/Guard/EvidencePack。

## 验证及证据边界

代码验证提交：`15a44b8bb276b13618bf30b84cc6fa8b49ff6d06`。证据见 [s4local05](../l2-operations/s4local05/)。

- 原报告／签名与 Brief 回归 49 项通过；最终 S4 针对性 16 项通过，原 PG 重启回读 1 项通过。
- 真实 Chrome：1280、393、375、320 四宽度；中文摘要、原审核回执、实际 PG 保存、独立收方退回／失败／重试／ACK／撤销和未登录文档拒绝。实际 PDF **2 页**，7 张截图。
- `mypy vrae`（130 个源文件）、改动范围 Ruff 与 Node 语法检查通过。
- 测试重用已接受的真实 C1/C2 来源、原 Controlled 签名及真实 PG16，M1 任务上下文明确为 detached component fixture。**不是 APP202→Worker 全链证明，不拼接其他 run，不替代 Codex3 S2/S5 统一验收。**

新增完整浏览器场景在创建时固定 300 秒的合成任务上下文，未延长真实权限期限、旧测试期限或旧浏览器启动／超时参数。页面展示沿用原 BriefService 的已回读文档，不为读取同一展示条目重复开新的权威读取；接单动作与独立回执每次仍重放原 BriefService 当前检查。

本地 RED 历史：s4local01 子进程解释器缺 pytest；s4local02 新流程 Brief 导航超时；s4local03 HTTP 预检超时；s4local04 合成 60 秒任务权限期满而被原权威正确拒绝。原始失败工件保留于本地忽略的 `integration/l2_executive/.runtime/failed-local/`，不上传其中的临时会话信息。修正后 s4local05 首次完整通过；不以此改写旧 PR124/127 的历史 RED。自然 CI 以最终 PR head 为准，不手动重跑。

复验：`python integration/l2_ops/verify.py --executive-only --label <唯一字母数字标签> --python-current <明确Python路径> --pg-image postgres@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea`。需原锁定依赖、Node22+、Chrome、CJK 字体和 Docker。验证器保留源文件哈希、真实 PG 重启读回、PDF/截图和所属容器／卷清理结果；不上传私钥、Cookie、PG 凭据或原私有浏览器 profile。

本 PR 后立即另起 CTA01/03 小 PR；INFO03/TECH02 与 S5 分层责任继续保留。

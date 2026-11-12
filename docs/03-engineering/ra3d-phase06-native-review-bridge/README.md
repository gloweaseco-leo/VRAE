# RA-3D Phase 0.6 · 原生合成证据只读桥

**真实 RA3C 合成证据重放 / 离线只读演练 / PRIVATE / NOT APPROVED / 不可客户外发。**

用本地 Chromium 打开 [index.html](index.html)。无需安装、登录、启动服务或联网。两份资料来自已验收 main 的真实原生 `EvidencePack / FindingPackage / GuardResult / ReportDraft` 重放，不是 Phase 0.5 的 `sim-*` 演示数据。证据查阅、逐项核对、退回/拒绝和范围确认仍只在内存演练；刷新清空，不形成真实决定。

本轮对应 [Issue #53](https://github.com/gloweaseco-leo/VRAE/issues/53)。独立 worktree `ra3d-phase06`，分支 `codex2/ra3d-phase06-native-review-evidence-bridge`，所有新增代码和产物只在本目录。输入冻结于已验收 main **`696d4ae695041f0eeefa56d22039682a989380b2`**；不读取其他 worktree 或未合并 PR #48。正式生产代码、合同、规则/Guard、测试、Phase 0/0.5 与 QA 不修改。

与 Phase 0.5 的区别是：本页可以从真实原生 claim 点击到实际 EvidencePack 持有的原始字节，核对原始 `evidence_ref / snapshot_ref / source_ref / guard_ref / binding_ref / pointer`，并查看原生完整报告/HTML 摘要。Phase 0.5 的工作台 JS/CSS 直接引用、字节不变；新增代码是小型只读投影/查阅层，不另造审核应用或生产 schema。测试也从固定 Git 对象复用其 CDP 驱动，新增的是本轮原生数据断言。

| 资料 | 原生行为 | 审核者可以判断的边界 |
| --- | --- | --- |
| 404 联系路径 | 1 个 CTA-02 / INQUIRE finding；native ReportVersion=REVIEW_REQUIRED | 固定产品页的 href `/contact` 在捕获时返回 404；影响、行动和复核措辞各自保留 HUMAN_REVIEW_REQUIRED |
| 200 零问题 | 0 个问题，PRIVATE_COVERAGE_SUMMARY；native_report_version=null | 固定 CTA 路径响应为 200；不是全站健康、表单有效、邮件送达或可外发报告 |

两份资料的原生 INFO/SEO 正向来源陈述也逐条显示，不把网站文案当成企业资质或搜索排名证明。200 的 CTA PASS 有真实规则 citation，但原生 RA3B **没有对应 CTA fact/binding/Guard claim**；界面明确缺失，投影为 null，不伪造一个新的 native 字段。该范围查看可以成立，正式审核能力仍未实现。

导航：

- [简短中文操作演示与使用价值](WALKTHROUGH.md)
- [投影字段映射、可信 pins 与缺口](BRIDGE_CONTRACT.md)
- [实际正例/负例、浏览器结果、截图和历史错误](RESULTS.md)
- [精确文件与原始 Git 来源 manifest](evidence/manifest.json)
- 原生 404：[完整 JSON](dossiers/contact-404.draft.json) / [原始 HTML](dossiers/contact-404.html) / [只读显示投影](dossiers/contact-404.display.json)
- 原生 200：[完整 JSON](dossiers/contact-200.draft.json) / [原始 HTML](dossiers/contact-200.html) / [只读显示投影](dossiers/contact-200.display.json)

从仓库根复跑（依赖只使用既有原生工程 Python 环境；不安装依赖）：

```text
node docs/03-engineering/ra3d-phase06-native-review-bridge/run-exports.mjs
node docs/03-engineering/ra3d-phase06-native-review-bridge/prepare-browser-test.mjs
node docs/03-engineering/ra3d-phase06-native-review-bridge/browser-test.mjs
node docs/03-engineering/ra3d-phase06-native-review-bridge/seal-evidence.mjs
node docs/03-engineering/ra3d-phase06-native-review-bridge/audit-delivery.mjs
```

`run-exports` 在本环境依次使用既有 Python 3.11/3.13，保留精确命令、退出码和 stdout/stderr。也可用装有已锁定原生项目依赖的 Python 直接运行 `export_bridge.py`。它从固定 Git 对象读取独立 held sources 与 caller pins；导入前验证当前 worktree 的生产来源 Git blob，一旦来源变化就拒绝。不会从受攻击输入重算“可信预期值”。所有原生模块导入路径有记录，字节码写入关闭。

`browser-test` 使用新鲜真实 Chromium profile、1280/375/320px、CSP、CDP 外网阻断和黑洞代理/DNS，仅加载本地文件。原文以 `textContent` 惰性显示；每次查看会从 base64 原始字节按 UTF-8 区间重新切片并与原 quote 对比。浏览器切片/哈希没有身份或授权权威；安全证明来自原生重放及独立 pins，不来自前端 UI 拒绝。

仍未解决：真实身份与任务授权、可信服务端 ReviewTarget/全文侧车、并发 CAS/幂等、持久事务/审计、任意人工改写输入合同、Owner 分享/接收人访问、真人理解率与耗时研究。静态合成数据包任何持有者都可读，不构成跨租户访问控制。没有真实站点抓取、模型、客户报告、认证、数据库、真实审批、ShareGrant、外发、部署或 E2/E3。Human Gold 0/26；RA3D production NO_GO，等待 Owner 独立验收。

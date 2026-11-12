# RA-4C1 · 只读 ReviewTarget 工程候选

PR #65 / Issue #64，独立 worktree `ra4c1`，分支 `codex2/ra4c1-review-target-read-bridge`。已验收基线 main `9d138ba57e0b442b9dace1a2247d7aaa46ca38ac`；普通 merge 核对结果为已包含，无 rebase/强推/cherry-pick。最终精确 HEAD 与四项新 CI 的 actual checkout/parents/tree 在最终 PR body 和本目录 post-CI 回执公开。保持 Draft，非 Owner FINAL PASS。

现有任务→原生核对→精确核对对象→原始来源链路已实际接入 accepted-main D1/D2。11 项任务、8 类阶段、原生 404/200、既有来源页面和所有中性状态保留。完整 source 与 HTML bytes 经 native ReportDraft.load/Guard 及 D1/D2 build_target/validate_target 重放；不引入新 hash engine 或新 SPA。

| 案例 | 外部已持有 target digest | 原生 H0 |
|---|---|---|
| 404 / 1 finding | `5705ac9e45e5118bc162bdece42f040a61360cf090b09500f7e9de5c89a9d256` | `fed173bd07ea8f3d7bca2a35146fd811371f3147877e205a361606bdf9ec6ccd` |
| 200 / 0 findings | `c309bb1878103fdcb71200de644a685a52a04ab38d29325571cbc3a7f2bb4050` | null（native ReportVersion 也为 null） |

源冻结修复点 `9ac2c8329f8b6b780cec77605514fd3a667d0aec`：独立持有 task→case/owner 关联，在 source lookup 前拒绝整条有效 200 DTO 替换 task-404。新旧目标 digest、H0 与 HTML/asset/source/policy/Guard pins 未重新生成或放宽。补强前的 a52591f/27dfa25 记录保留，不能用作新源码最终通过。

## 可复核证据

- 最终双 Python bounded：各 228 passed，原 app 58 + 新 app 43 + 原 reviewing 127，源文件运行前后 SHA 相同。实际 D1/D2 receipt 验证 127 collected/called/passed，不仅检查收集文本。精确文件见 ACCEPTANCE.json。
- 原 58 测试文件保持同一 Git blob；所有 `vrae/**`、schemas、frozen QA、原 reviewing 测试、infra/Docker/CI/dependencies/db/worker 保留原 blob/mode。SOURCE-SEAL.json 与 seal.py 可独立核对。
- Chromium 156 的最终新源码轮次：`evidence/browser-2026-11-12T15-54-58-773Z`。要求完整 123/123，33 张原始 PNG、DOM、CDP/网络/源码和截图哈希。实际 1280/375/320 target→source→back/forward，404/200/null、拒绝、中性状态、真实中文筛选、≥12px banner、≥44px primary、无横溢、零外部页面流量。最终完成状态由 audit.py 的源哈希匹配 receipt 核定。
- 保留首轮导航 CDP 超时、源变更导致封存失败的 bounded 尝试，以及早期四绿的原始日志/安全 ZIP。没有修改 guard、原始预期或任何源码外授权路径来获取 GREEN。
- 原 QA V2 64+54、原 reviewing 127、原有网络/容器负例由最终四项 hosted 默认全量实际执行；四项均需 SUCCESS。历史 V1 53 RED 与 Gold 0/26 原始代码/记录不变。

[操作与消费合同](README.md) · [完整负例矩阵](TEST-MATRIX.md) · [375px 404 目标](evidence/browser-2026-11-12T15-54-58-773Z/target-404-375.png) · [320px 200/null](evidence/browser-2026-11-12T15-54-58-773Z/target-200-320.png) · [375px 原始来源](evidence/browser-2026-11-12T15-54-58-773Z/target-source-404-375.png)。

## 仍未开放

`FutureRealReviewAdapter.prepare` 继续实际调用原 always-deny 生产端口。没有真实用户身份、认证 API、生产 latest ledger、数据库/RLS、持久审核事务、审计/outbox、审批/拒绝/退回、ShareGrant、客户访问、下载或部署。没有读取/导入 Codex1 未合并分支。条件性提议保持 HUMAN_REVIEW_REQUIRED，网站自述不能升级为资质/法律/经营事实。所有对象仍 private、NOT_APPROVED；RA4 EXIT / RA5 / E2/E3 / Human Gold 仍 NO_GO。

最终流程：先提交所有本地证据和 manifest，再对精确 HEAD 跑四项真实 CI。完成后本授权 `evidence/hosted-<run>-<UTC>/` 存原始日志、Git 对象、安全 ZIP、ACCEPTANCE 与回执包，不再为嵌入回执追加提交而漂移 HEAD；PR body 给出四 job/原始 artifact 链接、计数、哈希及精确 SHA。随后停止等待 Owner 独立验收。

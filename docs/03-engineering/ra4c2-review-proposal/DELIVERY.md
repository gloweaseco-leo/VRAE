# RA4C2 工程候选交付索引

Issue #67 / Draft PR #68。入口 main `cf11278ba4c9b62b3645cdbd6fd2cd8bb2f1838b`；新 worktree `ra4c2` / 分支 `codex2/ra4c2-offline-review-proposal-ux`。已正常 fetch + merge 最新 main（Already up to date），无 rebase/强推。最终精确 SHA、真实 CI merge-ref 的顺序父 SHA/tree、六项实际日志与 artifact 哈希在 PR body 及最终 post-CI 回执公开；本文件不冒充 Owner FINAL PASS。

## 变更与证明

- 产品 app 源码冻结 `c5789e01b206d683be115d026b87a0f939db5503`：现有 SSR Console 逐 Claim 表单 / 404 三种候选提议 / 200 独立覆盖 ACK，实际复用 accepted ReviewCommandProposal / CoverageAcknowledgementProposal / validate_proposal。原 target/source/Guard/pins 未变，mutate / production prepare 仍拒绝。
- 测试源码冻结 `79c4599c3f7aa4df6421c30757737b9b316f453e`：worker 冻结防火墙继续拒绝 loopback；隔离环境用 AF_UNIX 驱动原始 HTTP parser/Handler，同一组32项请求断言全部保留，新增1项真实监听 socket 的内核拒绝验证。普通 CI/本地仍真实 TCP，浏览器不模拟请求。
- 最终双 Python 要求各 **324 passed**：原58 + C1原43 + 新96 + 原D1/D2 127实际调用。源前后哈希、XML、stdout与 native marker 见 source-matching ACCEPTANCE.json。旧323轮次保留为测试源历史，不当作新测试源通过。
- 浏览器 `browser-2026-11-12T23-22-38-056Z`：Chromium 156，**75/75、24张PNG**，1280/375/320 真click/keyboard/中文原因/form POST，三动作、200/null、来源back/forward、重开未提交、stale/语义升级/HTML注入。原始DOM/CDP/网络/截图哈希均保留；app源码哈希需与最终一致。无外部页面请求、脚本异常或 server错误。
- 原58+43测试文件与其余所有受保护源/QA/SQL/infra/CI 原 Git blob/mode 不变，仅4个既有app文件修改。SOURCE-SEAL.json 与 seal.py 可独立复核；ARTIFACT-MANIFEST.json 封存已提交证据。

## 可直接查看

[375px 空提议](evidence/browser-2026-11-12T23-22-38-056Z/proposal-fresh-404-375.png) · [320px 候选预览](evidence/browser-2026-11-12T23-22-38-056Z/candidate-preview-404-320.png) · [375px 定位退回](evidence/browser-2026-11-12T23-22-38-056Z/request-changes-375.png) · [桌面拒绝提议](evidence/browser-2026-11-12T23-22-38-056Z/reject-proposal-1280.png) · [200 覆盖 ACK](evidence/browser-2026-11-12T23-22-38-056Z/coverage-ack-200-375.png) · [原始来源](evidence/browser-2026-11-12T23-22-38-056Z/proposal-source-375.png) · [语义上限拒绝](evidence/browser-2026-11-12T23-22-38-056Z/ceiling-refusal-320.png) · [版本失配拒绝](evidence/browser-2026-11-12T23-22-38-056Z/stale-refusal-320.png)。

[启动与消费合同 / 三场景](README.md) · [威胁与验收矩阵](TEST-MATRIX.md)。

## 真实 RED 与局限

初始缺失模块 RED、Origin:null 浏览器403、折叠区断言失败、首轮 isolated-http 超时取消，以及旧源通过证据全部保留。没有改业务预期、放宽 Guard、允许 null Origin 或改冻结防火墙/CI 超时来获取 GREEN。最终只接受新精确 HEAD + 最新已验收 main 的四项标准及两项 PG SUCCESS；原 QA V2 64+54 / reviewing127 / PG54+11、backup/restore 与245条浏览器隔离记录需从真实原始记录核验，skip单列。

仅 synthetic / TEST_ONLY / PRIVATE_NOT_APPROVED。缺少真实身份/session/assignment、protected bytes/latest ledger、事务CAS/native/full decision/audit/outbox/recovery，无法接线真实人工动作。无数据库接线、真实批准/退回/拒绝、ShareGrant、客户访问、模型、外发或部署；未读取/合入 Codex1 未验收 P2A。Human Gold 0/26、RA4 EXIT / RA5 / E2/E3 继续 NO_GO。

提交本地证据及seal后冻结最终SHA，再跑全部六项 CI。为避免CI回执追加提交引发SHA漂移，最终 post-CI API/Git/log/原始ZIP、ACCEPTANCE及完整证据包保留本授权 evidence/hosted-*，PR body公布路径/原始GitHub链接及SHA256。随后停止等待 Owner 独立 exact-SHA验收；不自行合并。

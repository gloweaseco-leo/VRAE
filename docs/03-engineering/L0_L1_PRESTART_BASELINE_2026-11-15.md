# VRAE V1.1｜L0→L1 开工前成果与证据交接基线

> **状态：OWNER ENTRY SNAPSHOT / PRESERVE · 2026-11-15**
>
> 本文件登记已合并的源代码、历史原生测试与未合并成果；不是声称 L0→L1 Beta 已经通过，也不是新 V1.2。上位 V1.1 和 [阶段纲领](L0_L1_STAGE_CHARTER_V1.1.md)不变。交接核查另见 [V1.1 对齐审计](L0_L1_V1.1_ALIGNMENT_AUDIT_2026-11-15.md)。

## 一、正式入口：完整 Git 树快照

- **基线保留分支**：[baseline/v1.1-l0l1-20261115-prestart](https://github.com/gloweaseco-leo/VRAE/tree/baseline/v1.1-l0l1-20261115-prestart)
- **入口 commit SHA**：4aa0f02d7feae58b1ebd20d72b8cab3f37f31c7a
- **入口 tree SHA**：961d74d34dbb8a38d532b43466740d888469e6e7（整个跟踪树，覆盖源码、迁移、合同、工作流、测试和已跟踪的证据）
- **最后一个已验收的代码合并**：PR102 的 main merge 6769f348e3f54b8b2964a43ec0041e17ba139686。经 GitHub compare，此 commit 与入口 SHA 之间**仅新增两份文档**：V1.1 四大架构附件和 L0→L1 阶段纲领；程序代码无变化。
- **分支保护真实状态**：当前该基线分支 protected=false。因此它是**不允许人为移动的约定保留分支**，并非技术上无法改变。真正的复原证据是上面精确 commit/tree SHA。严禁在其上开发、推送、合并、删除或重置。
- 本清册及之后的审计文档写入 main 不会回改上述历史 commit/tree。Codex 在自然集成点继续普通 merge **最新已验收 main**，不要把保留分支 reset 到各自分支。

### 根目录的 Git tree 指纹

| Git 目录 | 入口 tree SHA |
| --- | --- |
| apps/ | c2849fd08e6869bfb876e9034d64584af7737b0f |
| vrae/ | 1445f1505b69d68a2a5074886f6ca7b2e11453c3 |
| db/ | fc4f48bf7ce6a46336b06041f4de0d966cae4a71 |
| contracts/ | 883ec177c4393d4ab1fa97fc0f9e1ee0c60c64ae |
| worker/ | 6fc0d74e4793a1eca9cdedd748e6975d4d4e6318 |
| integration/ | 83dda1bf3a854e1aac84363e0cdec768d1178093 |
| tests/ | 621fa7426f8973aeeebf87db0c8d35a691d3e568 |
| .github/ | 323d4e21d3ec54332550047a3f5d290ecd8988d4 |
| industry-packs/ | 939d001b4357b05aa573450266b8c61ce99a929c |

## 二、已验收、已合并的主要成果（其余历史内容均由整树 SHA 包含）

| 已合并 PR / merge commit | 仅已验收的实际成果 | 权威 Owner 证据 |
| --- | --- | --- |
| [PR89](https://github.com/gloweaseco-leo/VRAE/pull/89) / ea49547205c2ec8fdf6bcbd64e9fef90d7aa931a | 签名 SSR、原始封存证据读取、B3 逐 Claim TEST_ONLY 演练意图与持久回执 | [验收](https://github.com/gloweaseco-leo/VRAE/pull/89#issuecomment-6889927024) |
| [PR99](https://github.com/gloweaseco-leo/VRAE/pull/99) / b9aec4e8379e6978de4177d67d64fde53d1d58ab | 真正 APP 受理/状态与原签名审阅回执联动；**非 Worker 新报告** | [验收](https://github.com/gloweaseco-leo/VRAE/pull/99#issuecomment-6891739131) |
| [PR92](https://github.com/gloweaseco-leo/VRAE/pull/92) / d63ea0b007ab4841000ff80c6d8c651d6ff4956f | B6 私有封存候选与默认拒绝交付 | [验收](https://github.com/gloweaseco-leo/VRAE/pull/92#issuecomment-6893185799) |
| [PR100](https://github.com/gloweaseco-leo/VRAE/pull/100) / 67acff97689514fdede01f2aab81dd5a7a96b9cd | DISC-01/02 事实 → 新版 Guard → 版本化私有报告；**非 Worker 任务产物** | [验收](https://github.com/gloweaseco-leo/VRAE/pull/100#issuecomment-6893747595) |
| [PR102](https://github.com/gloweaseco-leo/VRAE/pull/102) / 6769f348e3f54b8b2964a43ec0041e17ba139686 | 合成六 schema / PG16 三库灾备与安全恢复演练；**非 A1 旧毒队列修复** | [验收](https://github.com/gloweaseco-leo/VRAE/pull/102#issuecomment-6894470485) |

**更早的 RA0～RA4A、采集、16条规则候选目录/已启用六项、Evidence/Guard/Report、DB、B3、B4、SSR、全部受检测试和 CI 代码一并保留在入口 Git tree 中。** 不能因为本表只展示关键近期 PR 就将其它历史目录删除或复写。

## 三、原生回归的基线（原成功与原 RED 分开）

- **最近一次整合树真实 CI**：PR102 在当前业务代码树上的 GitHub test merge-ref eb74bcd5652758f0fb89e651659a8938e68bb31b，tree 255bef25040f78b5823b2388257538cb486c63c7，与已合并 6769f348... 的 tree 相同。原生 CI 为 **11/11 workflows、24/24 jobs SUCCESS**，双 Python 及真实 PostgreSQL16；[B7-P1 运行 43712878630](https://github.com/gloweaseco-leo/VRAE/actions/runs/43712878630)。**文档-only 入口 SHA 没有被声称重新跑过全套 CI。**
- **DISC 原生验收**：PR100 10/10 workflows、22/22 native jobs SUCCESS，但历史 3.11 25s HTTP 本地 RED 不被抹除。[精确验收](https://github.com/gloweaseco-leo/VRAE/pull/100#issuecomment-6893747595)。
- **PR103 不是基线**：其在途 CI 11个 workflows 中10成功1失败；24个 jobs 中22成功2失败。新 B5B 浏览器两 Job **RED**；原生 PG/HTTP 各94/94仅是该子阶段成功，不能折算整体 PASS。[真实 CI 43717354909](https://github.com/gloweaseco-leo/VRAE/actions/runs/43717354909)。
- **既有25个 SKIP**仍按原样单列；Human Gold **0/26** 不是已审26条。合成404/200不能写成真实客户案例。
- 官方 GitHub Action artifact 有保留期（部分仅3天），本文件提供 CI/Owner 原证据索引，**不冒充永久保存了所有私有 ZIP/JUnit**。私有原始日志、PG dump、令牌等仅由原执行者在私有位置继续保存，并定期核对 SHA，不得为保全而上传到公开路径。

## 四、未合并资产单独保全，禁止冒充正式基线

| 归属 | 最新已知状态 | 保全方法 |
| --- | --- | --- |
| **Codex1 M1 当前工作** | [Issue94 本地回执](https://github.com/gloweaseco-leo/VRAE/issues/94#issuecomment-6895001838)：Python3.11 + PG16 **39PASS/1FAIL**，17个事实 Guard 超过旧16上限；新产物登记、Reviewer读取未闭环。源文件仍未完整远端验证 | 保留原独立 worktree、在途差分/纯合成 source/原生 RED；在新功能 Draft PR 前核对原文件哈希，禁止从旧封存工作树无来源导入 |
| **Codex2 M2** | [PR103](https://github.com/gloweaseco-leo/VRAE/pull/103) HEAD **d607d39dbafb159d814aa7dcc13488f4237da8ff**、base 6769f348...，17个新增文件，仍 Draft，22/24 jobs | 继续同一 PR/工作树；不得自合并、另造第二 SSR 或把这个 RED 重新归类 |
| **Codex3 M3 当前工作** | [Issue96](https://github.com/gloweaseco-leo/VRAE/issues/96#issuecomment-6894913936)：仅本地 commit **9305b3de4555cc5364bddc49745e184e901275d7**，聚焦双 Python各4PASS；完整3.11 **9PASS/1FAIL** 浏览器导航 RED，3.13 全量未跑 | 保留当前集成 worktree、原生 JUnit、截图及错误时间线，勿将本地提交误称已发布/已合并 |
| **Codex1 历史 B4-P2** | [Issue90 停工封存](https://github.com/gloweaseco-leo/VRAE/issues/90#issuecomment-6883751289)：250未跟踪源码/公开证据文件、145份私有 XML，PAUSED/NOT ACCEPTED | 原工作树和 .runtime 原始哈希清单保持原样；**不包含在入口 Git 树** |
| **Codex3 历史 A1/B** | [Issue93 原始封存](https://github.com/gloweaseco-leo/VRAE/issues/93#issuecomment-6882542085)：MAX3抽样0/3、历史 RED、9份私有PG dump；后续本地恢复仍未并入 | 继续私有封存；本阶段干净合成 L0→L1 不等待它完成，亦不得写成 PASS |

**限制：** GitHub 不能检验尚在 Windows 本地、未推送、未物化到本仓库的文件字节。已有回执证明“曾报告”，不等于 Owner 当前已下载验证全部私有原件。

## 五、三名 Codex 交接一次性自主清单

- 各自当前工作树先**就地盘点，不暂停正确开发**：记录 HEAD、分支、git status --short、已提交与未跟踪清单、核心修改文件 hashes、原生 JUnit PASS/FAIL/SKIP、私有原件相对路径+字节/SHA 和运行环境。以前失败不重跑到绿、不覆盖证据。
- 两层并存：**已合并入口 SHA/整树**为代码基线；**各人当前 PR/本地 worktree 和旧 Issue90/93 .runtime**为单独的在途资产。两类不可自动互转。
- 不做 force push、reset/rebase/cherry-pick 消灭历史、替换旧迁移 0001–0004/Guard，不能覆盖别人的容器、工作树、凭据和证据。
- 在功能确实变更之后做**聚焦测试**，自然 PR CI 由 Owner 审阅；合并到当前 main 只走正常 merge、独立审计。GitHub artifact 到期风险由原作者在私有环境按现有证据留存，不能把仅有索引误作原始 ZIP 存在。
- 如果某历史原件已遗失，状态是 **MISSING/UNVERIFIED**，而不是重写哈希或为了找历史材料打断合成业务主线。保留旧 STOP/RED/UNKNOWN。
- 阶段业务 PASS 只能以同一真实 request/run/job 的动态报告、版本审核、重启回读和可操作浏览器为依据；**本交接文件不赋予任何工程/业务新 PASS**。

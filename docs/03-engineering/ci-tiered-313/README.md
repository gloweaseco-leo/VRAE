# Python 3.13 分层 CI 候选

Owner 授权：[Issue 129](https://github.com/gloweaseco-leo/VRAE/issues/129#issuecomment-6968257362)。基线 `4a227f1b58afc97d8af1778a066f37b80ff0f399`。仅调整未来触发、CI 脚本及说明；不合并、不部署、不改历史 PR 的源码、JUnit 或 RED。

## 覆盖矩阵

| 入口/变更 | Python | 执行范围 | 未执行范围 |
| --- | --- | --- | --- |
| FAST：已知 S2 规则、报告、受控只读工作台 | 3.13 | 对应原规则/工作台套件 + SourcePolicy/Guard/固定重放/证据一致性/严格元数据/冻结 smoke；compile、ruff、mypy | 其他套件明确 NOT_RUN |
| SECURITY：EvidencePack、身份、Guard、SQL/RLS、Worker、租约等 | 3.13 | 原默认完整 pytest + 全部 21 个原业务 workflow，包括真实 PG16、Worker/API、Chrome；原 HTTP/浏览器隔离实验 | 3.11 普通矩阵 |
| FULL：未知路径、依赖、基础设施、系统/发布手动入口 | 3.13 | 同上全部执行 | 不能据此自动宣称业务 FINAL PASS |
| CI/依赖迁移 PR、每周一 07:17 UTC、compatibility 手动 | 3.11 + 3.13 | 完整原套件及隔离实验 | 无删测、无 xfail |

安全影响闭包在第一版保守选择全部 21 个业务套件；空差异、差异读取失败、未知路径、混合改动取严格档。重命名比较保留新旧两条路径。FAST 只允许 `ci/policy.py` 中列明的候选路径，不泛化为整个 reporting/integration 目录。

原 22 个 workflow 文件复用：原 `ra0-ci.yml` 为唯一 PR 调度入口；其余改为 workflow_call + 手动入口，原 Job ID、步骤、超时与镜像不变。`ci/workflows.json` 给出每个原名称/矩阵/新调用名称的映射，测试逐项比较基线可执行步骤。FAST 报告场景执行 4 个 runner Job（plan、core、规则、聚合）；这只是结构计数，不能换算为已实现的分钟节省。策略迁移 PR 本身有意跑双版本 FULL。

## 目标环境事实与限制

`.python-version` 已是 3.13.5；Worker 实验有 3.13 Python 镜像 digest；PG16 使用 `infra/ra4a/image.txt` 的固定 digest。依赖仍遵循原 lock/constraints，每个原 Linux PG/Chrome/SSR/Worker 实验保留原验证。`ci.environment` 在真实 runner 记录 Python、依赖、Node、Chrome、镜像声明；未安装的工具明确记录缺失，声明的 digest 不等同于实际容器观测。

原 HTTP/Chrome 内核隔离 Dockerfile 仍固定 3.11；Chrome Debian 包、Node/host Python 与容器 patch 版本没有统一生产 digest 锁。因此状态是 **PYTHON313_CANDIDATE_NOT_PRODUCTION_LOCKED**。不修改这些受保护实验或强行锁定生产。

## 检查名称与设置

PR 最终检查为 `ci-policy-result`；所有被选择的业务调用及 core 必须 success，missing/skipped/cancelled/failure 都使聚合失败。未选择的 workflow 是 NOT_RUN。手动比较使用 `ci-policy-manual-result`，避免覆盖 PR 聚合检查。

只读查询 main branch protection 返回 404（Branch not protected），rulesets 返回空列表；没有写入仓库设置。若 Owner 决定启用 required checks，应要求稳定的 `ci-policy-result`，而非随路径不存在的矩阵叶子名称。原叶子名称映射详见清单；不要在策略接受前改设置。PR 使用普通 pull_request、只读 contents 权限。

## 实测方法

同一个新分支 SHA 上手动运行 `compare-baseline`、`compare-readonly`、`compare-security`。baseline 复放旧通用 PR 选择及双版本原步骤；后两者仅模拟路径选择，不修改业务文件，不检出或重跑 PR123/124/127 的历史 HEAD。旧选择对这两个代表路径相同，可共用一次 baseline。新 plan/result 开销单列；baseline 不是在旧提交上伪造新绿色。

```
gh workflow run ra0-ci.yml --ref codex1/ci-tiered-313 -f mode=compare-baseline
gh workflow run ra0-ci.yml --ref codex1/ci-tiered-313 -f mode=compare-readonly
gh workflow run ra0-ci.yml --ref codex1/ci-tiered-313 -f mode=compare-security
python -m ci.measure RUN_ID --output docs/03-engineering/ci-tiered-313/runtime/RUN_ID.json
```

`ci.measure` 分页读取实际 attempt 的 Job 时间戳，仅统计实际分配 runner 的时间，包括 setup/cleanup；不把 skipped 当作耗时/通过。不等同于计费分钟或 CPU。core artifact 另外记录 pytest 子进程 CPU 和 wall，整机/Docker CPU 未测。比较必须等待终态并核对相同 head SHA；失败运行照实保留，不能当作有效 PASS 节省。实际结果补入 runtime 与本说明。

## 实际发现：保留 RED，不可合并

测量代码 SHA：`f854ddd15fa3349a03e7743051039d67ef174b3e`。Draft [PR133](https://github.com/gloweaseco-leo/VRAE/pull/133)。

全部新分支测量已终止，原始 run/jobs API 快照在 `runtime/<run-id>.json`，汇总在 `runtime/comparison.json`：

| 同 SHA 场景 | 实际分配 runner Job | 结果 | runner 分钟 | 其中 plan/result |
| --- | ---: | --- | ---: | ---: |
| [FAST readonly](https://github.com/gloweaseco-leo/VRAE/actions/runs/44234916928) | 4 | SUCCESS | 1.8833 | 0.3000 |
| [SECURITY 3.13](https://github.com/gloweaseco-leo/VRAE/actions/runs/44235023025) | 26 | FAILURE | 57.8667 | 0.3000 |
| [旧通用双版本矩阵复放](https://github.com/gloweaseco-leo/VRAE/actions/runs/44235016045) | 40 | CANCELLED，已有 B5A FAILURE | 137.4500 | 0.3333 |
| [策略迁移 PR 双版本 FULL](https://github.com/gloweaseco-leo/VRAE/actions/runs/44235013359) | 48 | FAILURE | 116.7000 | 0.3000 |

旧基线在已知源码冻结失败后，由 DRI 停止剩余字体依赖/浏览器阶段，避免继续消耗无效对照；137.45 是本次取消前实际消耗，不是成功完整基线。SECURITY 另有 PG-read 浏览器入口退出 1（receipt 为 0 assertions）；同 SHA 迁移 PR 的该 3.13 Job 和复放基线中的该 Job 均成功，单次失败不被归因为 Python 兼容性结论。迁移 PR 还有 3.11 工作台依赖阶段 cancelled，约 15 分钟，后续业务未执行。两个 strict 聚合均真实拒绝非 success：`REQUIRED_SELECTED_JOB_NOT_SUCCESS`。没有有效的匹配 PASS 基线，**不报告节省百分比**，不把失败或取消后的少跑当作提升。

runner 分钟不等于用户等待时间；FAST 第一台 runner 开始到最后结束为 **5 分 55 秒**，其中包括共享队列等待间隙。全部 CPU 只记录 core pytest 子进程，整机/Docker CPU 未测。Windows 本地重复 full 在 Linux 双版本精确清单验证成功后停止，其不完整尝试不计 PASS。

最终追加证据的提交仅修改本目录，使用 `[skip ci]` 避免在完全相同 CI/业务代码上重复执行 48 个迁移 Job；它不产生新的 HEAD 绿色结论。审阅/测量对象始终为上述不可变代码 SHA，已有 RED/HOLD 保留。没有修改仓库检查设置，也没有历史 HEAD 重跑。

只读对照 [44234916928](https://github.com/gloweaseco-leo/VRAE/actions/runs/44234916928) SUCCESS：4 个实际 runner Job，合计 **1.8833 runner 分钟**。core 显式 smoke 184/184 PASS，pytest wall 12.5793 秒、子进程 CPU 11.6336 秒；另有原 S2 规则契约套件。未执行的 20 个业务 family 和 2 个隔离实验明确 NOT_RUN，不是整机 PASS。

迁移 PR 的双版本 core 原始 JUnit 均为 **2539 PASS + 25 SKIP = 2564**，failure/error 为 0。使用原 `integration.beta_disc_report.inventory.verify_inventory` 核对完整 ID 集及原测试源码 hash，均通过；没有新增默认发现测试或过滤默认清单。详见 `runtime/inventory-verification.json` 与原始 XML。3.13 full pytest wall 186.1858 秒、子进程 CPU 174.8860 秒；它与 FAST 覆盖范围不同，不能把差额称为等覆盖性能提升。

真实 core runner 为 Linux / Python **3.13.18**（开发提示仍为 3.13.5），host Node **24.22.2**、Chrome **157.0.8103.50**。core host 未安装 psycopg/cryptography；相应 PG/身份/Worker 验证依赖各自原锁定入口，不能拿 core 元数据冒充部署镜像证据。原浏览器业务入口单独 setup Node 22，原隔离实验仍用 3.11。所有不一致均保留事实。

**阻断事实**：原 `integration/ra4c_b5a/publication.py:69` 对其 ENTRY 树中所有原有文件进行冻结比较，也覆盖本次获授权修改的既有 workflow。新迁移运行的 B5A 3.11/3.13 均报 `ACCEPTED_SOURCE_CHANGED`，不是断言通过后的 PG/Chrome 业务失败；后续 publication 因没有输出继续失败。原门禁、freeze baseline、历史源码和 JUnit 均未改动，没有 continue-on-error 或绕过。精确源码冻结冲突需另行由 Owner 明确裁定，本 PR 保持 Draft/HOLD，不能要求其 required aggregate 变绿或据此宣称生产锁定。

受保护 `vrae/rules/execution.py` Git blob 保持 `c183970fd90ec69729221a4174c38d193f4b054b`；`vrae/evidence/pack.py` 保持 `8d45d5882103323e62bc4bd61a4379899e759966`。没有更改 Guard/PG/Worker/SQL/租约源码或旧 PR 分支。CI 工程独立于 C2/C3 交付。

## 验证与回滚

策略测试在 `ci/tests.py` 显式执行，不进入原 2564 默认测试清单。原冻结源码、历史证据及业务测试不变。保留初次策略 RED 与后续原始日志。

回滚仅 revert 此独立 CI 提交，恢复原 workflow 触发及双版本矩阵；没有数据/部署变更。如后续启用了新的 required check，Owner 应同步恢复旧检查配置，防止等待不存在的名称。遇到未映射路径自动 FULL，不通过扩大 FAST 白名单来掩盖失败。

参考：[GitHub reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows)、[workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)。

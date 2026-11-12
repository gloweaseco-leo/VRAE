# RA-4C0 · 工程候选交付（待 Owner 独立验收）

PR #61 保持 Draft。实现已分配范围的 Python SSR 任务池、阶段筛选/中文搜索、任务详情、原生 404/200 只读核对与证据回查。11 项合成任务、8 类展示阶段；没有新证据引擎、第二套 SPA、真实身份/数据库/审批/分享/客户访问或真实模型调用。

## 精确来源和唯一例外

- 起始 main `a185f9ce7e67904f2c0aef854716ca9844144592`；应用源码冻结点 `f54c0882c24e0e44168cce3a67d63b45ae08776a`。
- 已验收 main `225ded57add21680171cfaecac9f89df6b1af155` 已普通合并；合并提交 `47099b257e520caee65e28989cbec39c4b878135`，父提交顺序为 `f54c0882c24e0e44168cce3a67d63b45ae08776a`、`225ded57add21680171cfaecac9f89df6b1af155`。
- 唯一 COPY 修复后的功能提交 `45dae1d45c5b670556afb1ef945b1349518a0ab2`。最终文档/证据提交精确 SHA 与其四项 CI 回执在 PR body 和本地 post-CI 目录给出，遵循 [FINAL-CI-RECEIPT-POLICY.md](FINAL-CI-RECEIPT-POLICY.md)，不把旧 SHA 的通过冒称新 HEAD 通过。
- [Owner 限定授权](https://github.com/gloweaseco-leo/VRAE/pull/61#issuecomment-6825546180)：Dockerfile 在 `COPY vrae ./vrae` 后只增加 `COPY apps/operator_console ./apps/operator_console`。其他所有改动仅在 Issue #60 的三个授权目录。
- `SOURCE-SEAL.json` 对照已验收 main 的 3176 个条目，核对全部 blob/mode；仅 Dockerfile 有上述精确一行差异。PR58 reviewing 源码、测试、P1 与冻结 QA 均保留。`SOURCE-SEAL-a185-initial.json` 保留最初 3069 文件的基线记录。

## 实际验收结果

| 阶段 | Python 3.11 | Python 3.13 |
|---|---|---|
| 起始源码完整本地默认回归，开始 SHA f54c088 | 2119 passed / 25 skipped | 2119 passed / 25 skipped |
| 新 main 应用 + 原有严格元数据 P1，SHA 45dae1d | 62 passed（58+4） | 62 passed（58+4） |
| 正确冻结 adapter 的历史 V1 重放，SHA 45dae1d | 53 failed / 11 passed | 53 failed / 11 passed |
| 历史命令 | 19 条符合预期，含伪 Gold 必须 exit 1 | 同左 |
| 封存原生 RA3C 重放 | 8 个案例，旧引用/哈希保留 | 同左 |

新 main 的全量由最终 hosted 默认测试执行。本地旧基线全量从不改称新 main 结果。53 项历史 RED 的具体错误必须是 52 个 `REPORT_UNSUPPORTED_PROSE` + 1 个 `REPORT_GUARD_NOT_VALIDATED`。初次调用缺 adapter 所得 64 setup error 已保留且明确不计作 RED；`historical.py` 修正调用，测试与预期未改。

功能 SHA 45dae1d 的 [四项真实 CI](https://github.com/gloweaseco-leo/VRAE/actions/runs/43233580640) 已全部 SUCCESS：双 Python 各 2246 passed/25 skipped，HTTP 2270 passed/1 skipped，隔离浏览器保留 245 条原始命令、kernel control/deny 与 16 类 worker 场景。实际 checkout `8fa75a58f7165b09cca850fab7a85c6789e3172f`，父提交依次为 `225ded57add21680171cfaecac9f89df6b1af155`、`45dae1d45c5b670556afb1ef945b1349518a0ab2`。64+54 QA 在双 Python 和 HTTP 中均实际收集/调用通过。最终精确文档 HEAD 的新四项 CI 另附回执。

Chromium 156 真浏览器最终合入后记录：`evidence/browser-2026-11-12T14-03-00-298Z`，75/75。1280/375/320 实际点击任务→详情→404/200报告→来源→原文展开→返回；真实键盘选择阶段、中文输入及筛选按钮提交；403/UNKNOWN 中性页面；隐私提示 ≥12px、主要触摸区域 ≥44px、无横向溢出、无外部页面请求。原始 CDP 命令/响应、DOM、PNG、源码哈希与截图哈希全部保留。没有虚构人类可用性分数。

## 可直接查看

先读 [操作与接缝说明](README.md)；执行 `python -B -m apps.operator_console.preview --test-only --synthetic-fixtures`，仅打开输出的 127.0.0.1 合成 fixture 地址。不能用作真实身份认证或服务部署。

[桌面任务池截图](evidence/browser-2026-11-12T14-03-00-298Z/pool-1280.png) · [375px 404 核对](evidence/browser-2026-11-12T14-03-00-298Z/review-404-375.png) · [320px 200 零问题](evidence/browser-2026-11-12T14-03-00-298Z/review-200-320.png) · [原始证据截图](evidence/browser-2026-11-12T14-03-00-298Z/evidence-404-375.png)。

## 遗留边界

| 接缝 | 当前实际状态 |
|---|---|
| RA3D D1/D2 | 离线合同已随 main 验收；UI 不调用其审核 API，也不产生真实审核对象/决定 |
| RA4A/B 身份、RLS、数据库、任务队列 | 未实现；真实调用者一律不可使用本 shell |
| 审批事务、审计/outbox、恢复 | 未实现；端口和路由固定拒绝写操作 |
| ShareGrant、客户报告外发/访问 | 未实现，NO_GO |
| 人工 Gold 与 RA4 EXIT | Gold 0/26；RA4 EXIT 仍 NO_GO |

所有确定性观察都回到原生绑定；影响/建议/复验仍 HUMAN_REVIEW_REQUIRED。200 不代表网站全面健康，403/WAF/robots/UNKNOWN/无效 Guard 不被包装成缺陷。保持 private、NOT_APPROVED。等待 Owner 独立 FINAL PASS，不自行合并、部署或扩大范围。

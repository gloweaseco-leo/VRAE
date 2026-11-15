# B5-P0：签名 Reviewer 到内部演练记录

授权：[Owner CODE GO](https://github.com/gloweaseco-leo/VRAE/issues/79#issuecomment-6871517419)。唯一基线为已验收 main `ae2505f74f7a81d7a563c05d1a811aaa526c2839`。本分支全部变更是 Owner 指定目录内的新文件，不修改已验收 B2、B3、B5A、数据库或旧 CI。

本功能在同一个 B5A SSR 运营台接通真实签名身份、PG16 原始证据读取、服务端 proposal 校验、B3 原子 TEST_ONLY intent 和持久回执。入口为 `/b5a/tasks/<task>/rehearsal`，动作名称固定为“保存内部演练记录（非审批）”；回执查询在其 `/receipt` 子路径。现有任务、原文、逐 Claim 预览继续使用原有服务器和页面生成器。没有第二个 SPA，也没有浏览器身份配置或数据库连接。

404 原始资料包含 1 个 Finding、6 个受 Guard 约束的 Claims；200 为 0 Findings、3 个 coverage Claims。200 的回执状态只能为 `COVERAGE_ACK_TEST_ONLY`。所有预览、结果和错误页均显示 `NOT APPROVED`。记录的 authority 固定为 `TEST_ONLY_REVIEW_INTENT`，`effective_approval=false`、`external_visibility=false`，native decision、person 和 share grant 均为空。候选判断没有法律或业务效力。

## 运行和依赖

依赖仅使用已有 `requirements-ra1a.lock` 与 `requirements-ra4a-p2b2a.lock`。独立实验环境先执行已验收 migrations 0001–0003，再由已验收 B3 bootstrap 装配独立测试 DDL；没有 migration 0004。HTTP 子进程只读取 Reviewer profile 和另一个私有 bridge profile，签名器及管理员连接留在测试控制进程。

```text
python -B -m integration.ra4c_b5p0.run local-311
python -B -m integration.ra4c_b5p0.run local-313
```

分别使用 Python 3.11 和 3.13 执行，标签不得重用。需要本地 Docker PG16、Node 22 和 Chrome/Chromium；`B5P0_CHROMIUM` 可指定浏览器。浏览器使用本机实际中文字体，禁止测试站点外的请求。私有 profile、原始日志、恢复 SQLite 和签名 token 均留在被忽略的 `integration/ra4c_b5p0/.runtime/`。

完整契约见 [contract.md](contract.md)。每轮导出目录中的 native JUnit、摘要、受保护根哈希和 12 张限定截图是审核输入；不能把检查器常量当成执行证据。旧回归结果、开发 RED 和发布清单另附于验收记录。

## 交付边界

本地门禁全部通过后，仅允许一次受控推送、一个 Draft PR 和一次自然 CI 周期。预期为旧 16 项加新双 Python 2 项，必须核对 GitHub 实际 jobs 和首轮 attempt；首轮结束后停止，不补推、不 rerun、不自行合并或部署，等待 Owner FINAL PASS。

B4 PR83 未导入。真实人员身份、正式审批、客户分享和完整 B5B 仍未授权；Beta 仍为 2/7，G1/G2/G3 NO-GO。

本地验收、开发 RED 和首次 Hosted 交接规则见 [acceptance.md](acceptance.md)。

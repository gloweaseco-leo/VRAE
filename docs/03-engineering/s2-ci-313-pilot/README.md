# 两个 S2 workflow 的 Python 3.13 小试点

[Owner CODE GO](https://github.com/gloweaseco-leo/VRAE/pull/133#issuecomment-6969475919)。执行前回读 accepted main 为 `6a15ab4514d24c60b4d03d4ec795f6e3bcd435c3`。PR133 保持原 Draft/HOLD 归档，本试点独立提交，不合并。

仅修改 `s2-rule-contract.yml` 与 `s2-buyer-workbench.yml`：原 PR 触发及 paths 不变，矩阵默认只选 3.13；新增手动入口选 3.11 或 3.13。3.11 手动选择运行该版本的全部原步骤。两个原矩阵 Job 独立执行，没有跨版本产物依赖，因此按需单独验证兼容入口。3.13 仍为 CANDIDATE，不是生产镜像锁定。

| 项目 | 保留内容 |
| --- | --- |
| Rule `native-contract (3.13)` | 原 executor 冻结检查、ruff/mypy、P0/P1/industrial/buyer/projection 契约及原 JUnit 上传 |
| C2 `source-reading (3.13, 313)` | 原签名/权限、来源重放、原 L2/买方契约、真实 HTTP/SSR/Chrome 视口及原证据上传 |
| 3.11 按需入口 | 相同 Job ID/步骤/超时、原 slug=311、版本专属产物名 |
| 原全局安全 CI | 所有 workflow、双版本矩阵、触发和门禁完全不改；仍会按原策略运行 |

两份 S2 文件均不在旧 B5A `ENTRY=6257ad3acb09d046d954301117134f6992c02d84` 树中；不改 ENTRY、allowlist 或任何 Guard/PG/Worker/SQL/租约源码。不增加 workflow 文件、调度器、全局编排、required check 或仓库设置。main protection 查询为 404，rulesets 为空；未来 required checks 决策交 Owner。

必要验证：对比 accepted main 的原步骤、权限、Job ID、超时和 paths；actionlint 检查两份文件；模拟 PR 输入不能切换到 3.11；真实 PR 验证两个 3.13 Job，再在相同代码 SHA 各手动运行一次 3.11。实际结果与 run/artifact 链接补入 `evidence.json`。不为本试点重跑 PR133 的大调度器或历史 HEAD。

```
gh workflow run s2-rule-contract.yml --ref codex1/s2-ci-313-pilot -f python=3.11
gh workflow run s2-buyer-workbench.yml --ref codex1/s2-ci-313-pilot -f python=3.11
```

节省范围仅为这两个 S2 workflow 原来每次触发时的 3.11 Job 改为按需；原全局双版本 CI 依然运行。runner 分钟按分配 runner 的 Job started/completed 时间戳计算，不等同于等待时间、计费或 CPU。不声称全仓费用下降；单次 3.11 手动成本也不是每 PR 固定节省或完整等环境 A/B 结论。

未测/未裁定：全仓等覆盖成本 A/B、生产 Python/PG/Chrome/Node/digest 统一锁、发布整机 FINAL PASS、旧历史 RED 修复，以及旧全局 workflow 的兼容迁移。现有全局检查照常执行，结果不能由 S2 两个 Job 代替。

回滚：revert 本试点的两份 workflow 修改，恢复原 3.11/3.13 PR 矩阵并撤去手动入口；原业务代码、全局门禁和仓库设置无需回滚。提交 Owner 审核，未获 FINAL PASS 不合并。

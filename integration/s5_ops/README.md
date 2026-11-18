# S5 单一操作路线：已验收 S2 + S3

当前范围：真实 APP202 / 原独立 Worker / PG16 / 原签名 SSR 后的离线采购解释。S4 等待 Owner 合并；本包不宣称整版 FINAL READY。

## 操作入口

沿用原环境与私有身份配置，执行：

```text
python scripts/beta_internal.py l2 app-start --help
python scripts/beta_internal.py l2 app-start --run s5-operator --minor 3.13 --s5
python scripts/beta_internal.py l2 app-status --run s5-operator
python scripts/beta_internal.py l2 app-open --run s5-operator
```

在原工作台提交受控 P40 工业来源，等待真实 Worker 完成，打开同一新任务报告并使用原私有审核身份登录。报告的“离线采购解释”入口提供 NO_MODEL 与 Fixture 模式。Fixture 为封闭合成候选，不能视为真实模型调用、事实或客户批准。人工审核及 Brief 仍走原报告入口。

使用原 app-stop 命令关闭本轮；具体 CLI 参数以 --help 为准。真实自动操作命令：

```text
python -m integration.l2_ops.s2_acceptance_runtime --s5 --run s5-local-313 --minor 3.13
```

该命令在同一源码 SHA 下启动实际 PG16、API、Worker、唯一 SSR 和 Chrome，验证同源任务、双离线模式、原报告/审核/Brief、四视口、重启重新认证、权限拒绝和按所有权清理。公开证据写入 docs/03-engineering/l2-operations/运行标签；私有凭据、日志及 dump 不进入公开 artifact。

## 权限和持久边界

服务端从当前签名任务、C2 当前报告和真实 PG 已提交行独立持有 pins。浏览器仅提交模式与原 CSRF。两套权限同时有效，期限取最小值；30 秒 Worker 租约不是审核权限。完成时间来自已可见行的 created_at，依赖原延迟提交租约门禁；不冒充精确 WAL COMMIT 时间。

共用原 S3 Ledger，不改变原事实、Guard、SQL/RLS、租约或 HTTP/CDP 上限。相同模式写入 intent 后不随机重试。重启保存原账本及回执引用；S3 Session 候选缓存不具备公开持久恢复 API，因此重启后只显示历史引用，不伪称当前已授权候选，也不重置账本再次分派。

S4 狭窄接口为 S5Ports.read_only_s4_port：仅在双重当前权限下读取服务端同源 task/pack/report 和历史候选引用。未合并 S4 代码不导入；没有模拟 ACK 或外部接单。

真实模型、Gold、咨询、费率、人工时长和客户批准没有凭据时保持 UNKNOWN/UNLINKED。旧匿名卷状态 UNKNOWN，历史 dump 与 A1/MAX3 保持封存。

## 同任务重新认证

S5 模式下，对同一 TaskHandle 使用原签名 Reader 重新核对当前 Worker 证据、pack 与报告来源，保留已生成的不可变 NativeSource、报告版本和审核。不同任务仍走原完整生产路径。只更新此次真实登录的 M1 会话引用；不会延长 C2 会话、旧 S3 Session、原签名 TTL 或 Worker 租约。Brief 保存与回读继续使用原双重当前权限及 PG COMMIT 规则。

阶段计时记录在私有 S5 状态中；公开证据仅含有限阶段名与时间。历史 RED 保留：
- e914bbf 的首次登录前 HTTP Empty，缺少对应阶段计时，根因仍 UNKNOWN。
- fc3c1b6 的 Brief 测试 RED：实际 PG 行 completed=true，created_at=08:09:32Z、授权到期=08:09:46Z，浏览器回读于08:09:48Z失败。不能将其表述为 COMMIT 未发生或丢失。该轮完整重建同任务报告的额外工作已由上述重新认证适配移除；权限到期拒绝仍保留。

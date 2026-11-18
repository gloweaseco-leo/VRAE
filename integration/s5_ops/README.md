# S5 单一操作路线：S2 → S3 → S4 内部工程集成

当前范围：真实 APP202 / 原独立 Worker / PG16 / 原签名 SSR 后的离线采购解释。S4 已由 Owner 在 accepted main d38fd7263ea0d8ce357de54ef22cda90cdb86b9b 合并。当前源码接通同一任务 S2/S3/S4；验收结果以对应源码 SHA 的实际工件为准。

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

S4 狭窄接口为 S5Ports.read_only_s4_port：仅在双重当前权限下读取服务端同源 task/pack/report 和历史候选引用。S4 摘要、七包蓝图、受控审核与 PG Brief 沿用原报告及权限；S4 使用原 SyntheticIntake 与 /brief/submit|retry|revoke；独立合成收方进程签名，WAITING_ACK、拒绝重试与 ACK 仅为内部演练。模拟 ACK 重启丢失，原 PG Brief 必须持久。

真实模型、Gold、咨询、费率、人工时长和客户批准没有凭据时保持 UNKNOWN/UNLINKED。旧匿名卷状态 UNKNOWN，历史 dump 与 A1/MAX3 保持封存。

## 同任务重新认证

S5 模式下，对同一 TaskHandle 使用原签名 Reader 重新核对当前 Worker 证据、pack 与报告来源，保留已生成的不可变 NativeSource、报告版本和审核。不同任务仍走原完整生产路径。只更新此次真实登录的 M1 会话引用；不会延长 C2 会话、旧 S3 Session、原签名 TTL 或 Worker 租约。Brief 保存与回读继续使用原双重当前权限及 PG COMMIT 规则。

阶段计时记录在私有 S5 状态中；公开证据仅含有限阶段名与时间。历史 RED 保留：
- e914bbf 的首次登录前 HTTP Empty，缺少对应阶段计时，根因仍 UNKNOWN。
- fc3c1b6 的 Brief 测试 RED：实际 PG 行 completed=true，created_at=08:09:32Z、授权到期=08:09:46Z，浏览器回读于08:09:48Z失败。不能将其表述为 COMMIT 未发生或丢失。该轮完整重建同任务报告的额外工作已由上述重新认证适配移除；权限到期拒绝仍保留。


## 完整同任务内部验收

沿用上面的 --s5 命令；该模式自动启用已合并 S4 的 executive 验收，在一条 APP202/Worker 的任务与同一份 pack/report 上先运行 S3 NO_MODEL 和 Fixture，再验证动态 1–2 页摘要、原七包蓝图、Controlled、PG Brief 与独立合成 ACK。
重启后核对原版本/hash/来源/审核和 PG Brief 保留；S3 只保留历史引用，S4 ACK 消失。验证四视口、旧签名、撤权、自然过期、错租户和伪 ref，再精确清理本轮所有权资源。

只有该 SHA 的所有必要内部工程检查及清理成功才输出
L2_INTERNAL_ENGINEERING_READY_GOLD_PROVIDER_COMMERCIAL_GATES_OPEN。
此状态不是正式对外质量、真实 AI 或生产批准。Gold、真实 Provider、真实费用、E2/E3、实际发送和客户同意仍 UNKNOWN/NOT_EVALUABLE。PR 保持 Draft，由 Owner 最终独立验收；不部署、外发或付费。

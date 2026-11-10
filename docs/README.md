# VRAE 文档总索引

> **文档基线 V1.1 · 2026-11-10**  
> V1.1 是原始架构基线。**RA-0 已在独立 Draft PR #1 开发中（未合并 main，CI 尚未完成验收）；无运行中的 API、Worker 或生产数据库**。
>
> **阅读规则**：V1.1 是当前目标架构；V1.0 保存为历史资料，不得以旧文件中的“嵌入 VEYFRONT 源码”方案指导开发。

## 一、阅读顺序（建议第一次接管先按此顺序）

1. [产品纲领 V1.1](00-product/PRODUCT_CHARTER_V1.1.md) — 为什么做、客户是谁、交付边界是什么。
2. [总体系统与应用架构 V1.1](01-architecture/SYSTEM_AND_APPLICATION_V1.1.md) — VRAE 内核、API/Worker、四系统关系与故障边界。
3. [数据架构 V1.1](01-architecture/DATA_ARCHITECTURE_V1.1.md) — 数据所有权、实体、版本、权限、存储。
4. [API 与跨系统契约 V1.1](01-architecture/INTEGRATION_CONTRACTS_V1.1.md) — VEYFRONT、Vey2GE、L2M 的通信规则。
5. [安全与部署架构 V1.1](01-architecture/DEPLOYMENT_AND_SECURITY_V1.1.md) — 抓取安全、Worker 隔离、数据保护。
6. [诊断规则与证据标准 V1.1](02-domain/AUDIT_METHODOLOGY_AND_RULES_V1.1.md) — 五个买家任务、16 条规则、UNKNOWN 与 AI。
7. [客户与运营旅程 V1.1](02-domain/PRODUCT_AND_OPERATOR_JOURNEYS_V1.1.md) — 客户体验、人审与商务转化。
8. [代码复用与仓库治理 V1.1](03-engineering/CODE_REUSE_AND_REPOSITORY_STRATEGY_V1.1.md) — L2M 最小提取与 Vey2GE 契约复用。
9. [开发总计划 V1.1](03-engineering/DEVELOPMENT_MASTER_PLAN_V1.1.md) — RA-0 至 RA-6 各工作包、文件、依赖、测试矩阵和 Codex 任务模板。
10. [开发路线与验收 V1.1](03-engineering/ROADMAP_AND_ACCEPTANCE_V1.1.md) — 各阶段退出门禁及 GO/NO-GO。
11. [已决策与待定问题 V1.1](03-engineering/DECISIONS_AND_OPEN_QUESTIONS_V1.1.md) — 不得误认为已批准的选项。

## 二、架构决策记录（ADR）

- [ADR-0001 独立引擎与仓库](adr/ADR-0001-independent-engine.md)：独立 VRAE 仓库、模块化单体、隔离 Worker；取代此前源码放在 VEYFRONT 的路线。
- [ADR-0002 独立数据主权与接口](adr/ADR-0002-data-ownership-and-contracts.md)：独立 PostgreSQL/对象存储、无共享数据库、API + Outbox + RebuildBrief。

今后重大变更应新增 ADR，状态使用 PROPOSED / ACCEPTED / SUPERSEDED / REJECTED，并注明批准日期及影响的当前设计文档。

## 三、历史与迁移

- [Rebuild Audit Engine V1.0 原始规划（历史）](archive/REBUILD_AUDIT_ENGINE_MASTER_V1.0_2026-11-09.md)：从 VEYFRONT Draft PR #26 原文迁移。**这是原始方案留档，不是当前源码归属基线**。
- [文档变更记录](CHANGELOG.md)：本轮文件迁移、版本升级与未实施范围。

## 四、文档分类与维护制度

| 目录 | 主责 | 内容 | 审核方式 |
| --- | --- | --- | --- |
| 00-product | Product/CGO | 业务目标、ICP、客户价值、L0-L3 | 商业负责人 |
| 01-architecture | Chief Architect | 应用、数据、安全、接口 | 架构与安全双审 |
| 02-domain | Audit Product Owner | 诊断规则、证据和客户旅程 | 产品+规则准入 |
| 03-engineering | Engineering Lead | 复用、开发、测试、里程碑 | 工程负责人 |
| adr | Decision Makers | 重大不可静默更改的决策 | 明确批准/拒绝 |
| archive | Documentation Owner | 旧版历史与来源追溯 | 只添加迁移说明，不混入新基线 |

## 五、版本与真实性

- V1.0：原 VEYFRONT 仓库中的历史方案，保留全文用于追溯。
- V1.1：用户认可独立 VRAE 仓库后的完整架构重整，**属于设计文件**，不代表 API、Schema、数据表、采集器、Worker、客户页面已经完成。
- 状态码、费用额度、30/90 天保留期和提供方选型均为候选参数；开发前要有正式契约、测试和合法性确认。
- 不能把未运行的演示、历史项目数据、合成样本当成真实诊断或客户成功。

## 六、后续工程如何消费文档

完成架构确认并获得另行开发授权后，先按 **[开发总计划](03-engineering/DEVELOPMENT_MASTER_PLAN_V1.1.md)** 拆分执行包，再按照 [验收路线](03-engineering/ROADMAP_AND_ACCEPTANCE_V1.1.md) 的门禁执行 RA-0 和后续阶段；任何跨系统实现必须满足 [接口契约](01-architecture/INTEGRATION_CONTRACTS_V1.1.md)。代码不应直接复制本仓库文档里拟建目录的示例名称当现成实现。

**工程进展（独立 Draft 分支）：RA-0 已获得用户授权并提交 PR #1；实现记录见 [RA-0 实施与验收记录](03-engineering/RA0_IMPLEMENTATION_AND_ACCEPTANCE.md)。不代表 RA-0 验收通过、服务上线或进入 RA-1。**

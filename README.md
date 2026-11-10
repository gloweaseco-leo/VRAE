# VRAE — VEYFRONT Rebuild Audit Engine

**独立、证据驱动的 B2B 企业网站 Rebuild 诊断引擎。**

VRAE 的首个商业用户是 VEYFRONT。它负责将安全、合法获取的现有网站事实转为可审核的采购商体验诊断结论，并通过受控接口协助 VEYFRONT 形成真实 Rebuild 商机。VRAE 不自动发送营销信息、不决定客户报价，也不拥有 L2M 生成和 Vey2GE 增长经营职能。

> **当前阶段：V1.1 架构与文档基线（2026-11-10）。**
> 仓库已建立并整理 Markdown 文档；尚未启动 RA-0 开发，未搭建数据库/Worker/API，未部署诊断服务，也没有真实客户诊断验收记录。

## 从这里开始

**[完整文档目录与阅读顺序](docs/README.md)**

| 文档 | 说明 |
| --- | --- |
| [产品纲领](docs/00-product/PRODUCT_CHARTER_V1.1.md) | 客户定位、L0–L3、商业目标与范围 |
| [系统与应用架构](docs/01-architecture/SYSTEM_AND_APPLICATION_V1.1.md) | 模块化单体、受限 Worker、四系统分工 |
| [数据架构](docs/01-architecture/DATA_ARCHITECTURE_V1.1.md) | 证据、诊断、报告、独立 PostgreSQL 与权限 |
| [集成接口](docs/01-architecture/INTEGRATION_CONTRACTS_V1.1.md) | VEYFRONT/VRAE API、Vey2GE 事件、L2M RebuildBrief |
| [安全与部署](docs/01-architecture/DEPLOYMENT_AND_SECURITY_V1.1.md) | SSRF、Chromium 隔离、隐私与队列恢复 |
| [诊断规则](docs/02-domain/AUDIT_METHODOLOGY_AND_RULES_V1.1.md) | Buyer Journey、16 条候选规则、证据/推断分离 |
| [客户与审核旅程](docs/02-domain/PRODUCT_AND_OPERATOR_JOURNEYS_V1.1.md) | 官网申请、内部人审、报告、商务交接 |
| [代码复用决策](docs/03-engineering/CODE_REUSE_AND_REPOSITORY_STRATEGY_V1.1.md) | L2M 最小提取、Vey2GE 契约复用、拟建目录 |
| [开发总计划](docs/03-engineering/DEVELOPMENT_MASTER_PLAN_V1.1.md) | RA-0 至 RA-6 工作包、测试矩阵、Codex 任务单 |
| [开发与验收路线](docs/03-engineering/ROADMAP_AND_ACCEPTANCE_V1.1.md) | RA-0 至 RA-6 与质量门禁 |
| [决策清单](docs/03-engineering/DECISIONS_AND_OPEN_QUESTIONS_V1.1.md) | 已认可与仍需单独批准的事项 |

## 技术方向（尚未实现）

- Python 模块化单体，候选 FastAPI/Pydantic；
- 独立 API 和具备出站网络控制的受限 Worker，有限 Playwright；
- 独立 PostgreSQL/持久队列/私有对象存储；具体供应商待验证；
- 确定性证据与行业规则优先，AI 仅做有来源的解释；
- 版本化 API、事务 Outbox 和 RebuildBrief 集成；
- 客户可见报告需要明确权限与人工审核。

## 仓库与其他系统

- [VEYFRONT](https://github.com/gloweaseco-leo/VEYFRONT)：客户触达、网站入口、咨询、报价与成交主权；
- [Legacy2Modern-](https://github.com/gloweaseco-leo/Legacy2Modern-)：安全采集代码可在许可与独立验收后最小提取；网站生成不是 VRAE 的依赖；
- [Vey2GE](https://github.com/gloweaseco-leo/Vey2GE)：未来消费经授权的诊断与经营事件；不共享数据库。

重大决策见 [ADR](docs/adr/README.md)。上一版方案在 [历史档案](docs/archive/REBUILD_AUDIT_ENGINE_MASTER_V1.0_2026-11-09.md) 留存，其中“VRAE 归属 VEYFRONT 源码仓库”的方案**已废止**。

## 运行与使用状态

当前 **没有可安装、可运行的 VRAE 应用**。因此不提供虚构的启动命令、服务地址或测试通过声明。未来工程从经明确授权的 RA-0 契约开发启动，任何正式站更改、真实客户诊断、模型费用或主动对外联系需独立审批。

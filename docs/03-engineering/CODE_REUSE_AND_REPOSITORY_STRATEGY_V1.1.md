# VRAE 代码复用与仓库治理策略 V1.1

> 状态：迁移决策与审计要求；本轮没有复制第三方项目源码、没有开始 RA-0。2026-11-10。

## 1. 代码组织：一个独立 VRAE 仓库

```text
VRAE/
  README.md
  docs/
    README.md
    00-product/                 # 产品纲领
    01-architecture/            # 系统、数据、API、部署安全
    02-domain/                  # 诊断规则、客户及运营旅程
    03-engineering/             # 复用策略、里程碑、验收
    adr/                        # 架构决策
    archive/                    # 历史原文（不可当当前基线）
  apps/api/                     # 未来 FastAPI 和内部审核台
  vrae/domain/                  # 未来领域模型与状态
  vrae/application/             # 未来业务用例
  vrae/collection/              # 未来只读站点采集
  vrae/evidence/                # 未来证据抽取/校验
  vrae/rules/                   # 未来诊断规则与行业扩展
  vrae/intelligence/            # 未来模型适配
  vrae/reporting/               # 未来报告/审批
  vrae/integrations/            # 未来 VF/Vey2GE/L2M 对接
  vrae/infrastructure/          # 未来 DB/队列/存储
  worker/                       # 未来隔离执行进程
  contracts/v1/                 # 未来 OpenAPI / JSON Schema / Events
  industry-packs/               # 未来行业规则
  db/migrations/                # 未来数据库迁移
  tests/fixtures/               # 未来合成网页/安全负例
  infra/                        # 未来容器与网络策略
```

**以上 apps、vrae、worker 等均为拟建目录，不是已创建的代码。** 仅创建当前本轮所需的 docs 文档，不放空目录和样板服务。

## 2. 三个现有仓库的关系

| 来源 | 可复用 | 先排除 | 复用决策 |
| --- | --- | --- | --- |
| Legacy2Modern- | `legacy2modern/url_fetch.py` 的公网地址及重定向控制；`discovery.py` 的页面角色/路径抽样；部分 Site IR 证据方法 | Builder/Renderer/Design Agent/完整自动生成; `browser_verify.py` 作为真实站导航验证 | **一次受控最小提取**，并受许可与测试审计 |
| Vey2GE | 数据/事件/审批/E0-E4 证据等级设计 | 直接复制工作台、访问其数据库、依赖尚未验收的云端运行时 | **版本化 API/事件**，不是代码迁移 |
| VEYFRONT | 正式客户体验、表单、VF 线索收据、企微联系 | 复制站点前端和联系人数据库 | **服务端 BFF API + 经批准报告** |

### 为什么 L2M 不先做 API？

代码层面可复用的采集模块，不等于 L2M 已经提供稳定的生产分析服务。VRAE 初期直接运行时调用 L2M，将被其独立版本、预算和生成实验影响。先在 VRAE 提取纯只读、经安全回归的必要部件；未来共同稳定后再评估共享 versioned Python package。

### 为什么 Vey2GE 用接口而不复制代码？

Vey2GE 需要做通用增长经营，而 VRAE 要做安全采集、证据与规则。Vey2GE 当前的 G1 机会模块在仓库中明确是 OFFLINE_SYNTHETIC_ONLY，不具备可直接生产调用的 API。只借用 E0-E4、审批、Outbox、idempotency 等契约；待对方 Beta 有真实权限/恢复/租户验收后再接入。

## 3. L2M 复用候选清单

- `url_fetch.py`：public IP/port/redirect/同域政策、bounded fetch、访问阻断识别。必须特别核查 DNS pinning 在不同执行环境中的行为，添加 Chromium 子资源的出站隔离。
- `discovery.py`：真实页面链接 inventory、home/catalog/category/product/about/contact 等角色；需要适配 VRAE 代表性页面和证据深度。
- `snapshot_import.py`：可供未来属主授权离线快照导入，L1 暂不要求。
- `extract.py`：其固定 fixture 页面映射不能直接当通用抽取器，可参考证据结构。
- `content_package.py`：主要服务建站 BusinessContentPackage，不应成为 VRAE 诊断核心。
- `browser_verify.py`：使用内联 HTML/CSS 和断网 Chromium 检查构建产物，**不等价于真实站点浏览器导航**；VRAE 应建立自己的受控只读 Playwright 观察。
- `design_agent.py`、自动修复与站点生成链路：不接入 VRAE。

## 4. 代码迁入的审批流程

1. 确认源仓库和模块具体 Git SHA、作者与代码使用权/许可；私有仓库不能想当然宣告可对外再许可。
2. 记录业务和技术目标，审查最小需要的函数以及直接/间接依赖。
3. 安全审查：URL/域名、DNS/redirect、跨域、浏览器、错误和数据保存权限。
4. 只提取必要模块，写来源注释、移植差异与用于回归的固定 fixture。
5. 独立测试新代码：相同正反例、恶意 URI、403/Cloudflare、路径、跨域及预算；不把源仓库当前“通过的测试”当 VRAE 自动通过。
6. 冻结 VRAE module version/API contract，后续更改必须重新跑安全与兼容测试。
7. L2M 若想复用 VRAE 安全采集，后续单独批准共享库/版本分发，不借助直接访问 VRAE 内部模块。

## 5. 决策更新与配置管理

- 当前设计主线：V1.1 / ADR-0001 / ADR-0002。
- 旧版 [V1.0 原文](../archive/REBUILD_AUDIT_ENGINE_MASTER_V1.0_2026-11-09.md) 是历史存档，不能用于新任务自动开发。
- 重大设计变动写新的 ADR（含状态/背景/替代方案/后果），不静默覆盖已决策内容。
- 接口更改须采用 SemVer 或明确的兼容版本与 contract tests。
- 文档先于代码确认，但不代表所有待定基础设施、模型或业务门禁已经批准。

## 6. 在本轮中不做

不创建 RA-0 的 JSON Schema，不复制 L2M 源码，不申请 Supabase，不部署 API/Worker，不改 VEYFRONT 正式站，不接入 Vey2GE 生产、不做真实客户诊断。

详见 [ADR-0001](../adr/ADR-0001-independent-engine.md) 与 [验收路线](ROADMAP_AND_ACCEPTANCE_V1.1.md)。

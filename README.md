# VRAE — VEYFRONT Rebuild Audit Engine

独立、证据驱动的 B2B 网站采购商体验诊断引擎。首个商业消费者为 VEYFRONT。
**当前分支包含 RA-0 基础与 RA-1A 安全 HTTP 采集合成验收；未上线、未访问真实企业网站、未调用大模型、未部署 API/DB/Worker。**

## Developer quickstart — offline synthetic only

Python reference version: **3.13.5**, compatibility target Python **3.11 and 3.13**.

```sh
python -m pip install -e '.[dev]'
python -m compileall -q vrae
ruff check vrae tests --select E4,E7,E9,F
mypy vrae
python -m pytest -q
python -m pip check
```

Contracts: `contracts/v1/*.schema.json` (JSON Schema 2020-12, authoritative);
`contracts/v1/openapi.yaml` is a spec, **not a running API**.
Domain: `vrae/domain` pure functions for tenant, source policy, evidence, approval,
sharing, state transitions, budget blocking and business-event separation.
Fixtures: `tests/fixtures` wholly synthetic; never import third-party customer data.

**Important:** URL syntax validation alone is NOT SSRF protection. No safe external
website collection exists in RA-0. L2M / Vey2GE production integration is prohibited.
Report drafting, approval and sharing are separate facts, and no audit status implies a lead.

## Architectural baseline

See [document index](docs/README.md), [product charter](docs/00-product/PRODUCT_CHARTER_V1.1.md),
[system architecture](docs/01-architecture/SYSTEM_AND_APPLICATION_V1.1.md),
[data architecture](docs/01-architecture/DATA_ARCHITECTURE_V1.1.md),
[integration contracts](docs/01-architecture/INTEGRATION_CONTRACTS_V1.1.md),
[security](docs/01-architecture/DEPLOYMENT_AND_SECURITY_V1.1.md),
[domain methodology](docs/02-domain/AUDIT_METHODOLOGY_AND_RULES_V1.1.md),
[development master plan](docs/03-engineering/DEVELOPMENT_MASTER_PLAN_V1.1.md),
[acceptance roadmap](docs/03-engineering/ROADMAP_AND_ACCEPTANCE_V1.1.md), and
[RA-0 implementation record](docs/03-engineering/RA0_IMPLEMENTATION_AND_ACCEPTANCE.md).
ADR-0001/0002 prevail over historical V1.0 archive; no shared database with VEYFRONT/Vey2GE.

## Product ownership

VEYFRONT: customer intake, inquiry, quote and sale. VRAE: audit evidence, rules,
human review and report grants. L2M: separate website rebuild upon approval.
Vey2GE: future versioned events only, never shared DB or implicit E3.

## RA-1A isolated HTTP collection

See [implementation and acceptance](docs/03-engineering/RA1A_IMPLEMENTATION_AND_ACCEPTANCE.md)
for the real socket/DNS/TLS/firewall lab and full regression evidence.
Install with `python -m pip install -e '.[dev]' -c requirements-ra1a.lock`.
Production network isolation remains a separate deployment gate.

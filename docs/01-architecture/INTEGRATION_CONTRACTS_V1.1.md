# VRAE API、事件与跨系统集成架构 V1.1

> 状态：逻辑契约与 API 候选；尚未生成 OpenAPI/schema、尚无部署服务。2026-11-10。

## 1. 集成原则

- **同步 API**：请求受理、获取受控状态、读取已批准报告、审核、发放分享授权。
- **异步事件**：分享、商机移交、人工反馈等事实变化；有版本、来源、证据与幂等保障。
- **不共享数据库**：VEYFRONT、VRAE、Vey2GE、L2M 的数据由各自领域服务拥有。
- **对接服务未准备好**：VRAE 本地 Outbox 持久保存，重试有界并报警，不阻断诊断。
- **信任边界**：浏览器不得持有 VRAE API 的服务密钥；VEYFRONT 服务端 BFF 转发用户申请，带自己的授权和主体引用。
- 所有接口默认私有、鉴权、审计；公开状态与报告需校验申请者身份或明确的、可撤销的 share grant。

## 2. 跨系统关系

| 集成 | 数据方向 | 哪个系统为权威 | 第一阶段 |
| --- | --- | --- | --- |
| Audit API V1 | VEYFRONT → VRAE；VRAE → VEYFRONT | VRAE 诊断任务/报告；VF 客户关系 | 先只定义契约，随后接首个试点 |
| Growth Event V1 | VEYFRONT/VRAE → Vey2GE | VF/Vey2GE 负责 E2/E3 权威 | 只定义契约，不接生产 |
| RebuildBrief V1 | 经客户授权的 VF/VRAE → L2M | VF 签约范围、L2M 交付工件 | 只定义契约，不调用生成 |
| Evidence handoff | VRAE → L2M (授权副本) | VRAE 原证据，L2M 持有获准交付输入 | 客户明确授权时才开放 |

## 3. VRAE REST API 候选

所有路径位于 /v1，并携带 request_id、schema_version、tenant context、idempotency_key（写请求）；使用 UTC 日期和标准化错误 code。HTTP 202 仅意味着**持久受理**，不是报告已经生成。

| 端点 | 主体/授权 | 返回与业务规则 |
| --- | --- | --- |
| POST /v1/audit-requests | VF 服务身份、内部操作员 | 202: request_id, audit_id, status；失败返回已知 POLICY/QUOTA/INPUT 错误 |
| GET /v1/audits/{id} | 同租户授权调用方 | 最小状态、错误类别、审核阶段；不返回其他租户、内部模型原文 |
| GET /v1/audits/{id}/report | 具有批准版本读取权的主体 | 精确批准版本、证据允许展示的引用、过期/撤销控制 |
| POST /v1/audits/{id}/review-decisions | Reviewer/Owner | 批准/拒绝/请求补证据；必须携带报告版本哈希 |
| POST /v1/reports/{id}/share-grants | Owner | 为指定已批准版本建立短期授权，默认不开放任意索引 |
| POST /v1/audits/{id}/sales-handoffs | Owner / 已经客户同意的 VF 跟进流程 | 创建对接引用，不自动变成商机 |
| GET /v1/health | 内部健康检查身份 | 可用性、发布版本和依赖就绪概要（无 secrets） |

**示例（仅契约草案）**：

```json
{
  "schema_version": "1.0",
  "tenant_id": "tenant-example",
  "site_url": "https://example.org",
  "audit_mode": "L1",
  "source_policy_ref": "policy-example",
  "source_system": "veyfront",
  "source_reference": "vf-intake-example",
  "idempotency_key": "one-time-request-example"
}
```

真正实现前需制定 UUID/ULID 格式、校验规则与 OpenAPI；示例中的地址/身份为合成数据，不能当作已经生效的接口。

## 4. 事件 Outbox 的最小 Envelope

```json
{
  "schema_version": "1.0",
  "event_id": "evt-example",
  "tenant_id": "tenant-example",
  "source_system": "vrae",
  "event_type": "audit.approved",
  "occurred_at": "2026-11-10T00:00:00Z",
  "audit_id": "audit-example",
  "report_version": 1,
  "evidence_reference": "report-hash-example",
  "authorization_reference": "approval-example",
  "idempotency_key": "event-example"
}
```

候选事件：
- audit.requested / audit.policy_checked / audit.run_completed / audit.run_failed
- audit.report_drafted / audit.report_approved / audit.report_rejected
- audit.share_granted / audit.share_revoked / audit.sales_handoff_requested
- audit.feedback_recorded

**意义边界**：audit.run_completed 只代表 Worker 运行结束；audit.report_approved 只代表内部批准；audit.share_granted 不等于客户已阅读；audit.sales_handoff_requested 不等于真实询盘或 E3。E2 需有 VF 已保存成功的受理凭据，E3 需指定负责人确认的业务资格，E4 则依据实际报价/合同等记录。

## 5. RebuildBrief V1 的责任边界

只在**客户有权提供信息且批准交付**后创建：
- vf_project_ref、customer_approval_ref、audit_report_ref、report_version、audit_scope、site_url；
- customer_confirmed_business_goals、priority_products_and_markets（必须标注客户确认状态）；
- validated_findings 与 suggestion_refs，不发送未经确认的内部假设当已确定事实；
- authorized_asset_manifest（逐项许可状态），scope_included / excluded、acceptance_criteria、legacy_url_mapping_plan；
- expected_handoff_date、version、content_hash。

对于未取得重建素材使用权的内容，仅允许传递非敏感问题陈述及原站链接；“能公开读取”绝不等于“有权复制建站”。

## 6. 错误规范

统一错误结构 code、safe_message、request_id、retryable。示例：
- INVALID_URL、POLICY_REQUIRED、POLICY_REVOKED、SOURCE_NOT_ALLOWED
- SSRF_BLOCKED、ACCESS_BLOCKED、ROBOTS_DISALLOWED
- LIMIT_EXCEEDED、QUOTA_EXCEEDED、WORKER_TIMEOUT、EVIDENCE_INSUFFICIENT
- MODEL_SCHEMA_INVALID、MODEL_COST_UNKNOWN、REVIEW_REQUIRED
- REPORT_NOT_APPROVED、REPORT_VERSION_STALE、SHARE_EXPIRED、FORBIDDEN_TENANT

服务端禁止回传数据库错误、内部 IP、凭据、完整抓取 HTML、模型原始隐私内容。需支持 429 Retry-After、有界重试及幂等。

## 7. 身份认证与服务访问

- VF BFF → VRAE：服务间认证（短时 JWT/OIDC 或等效签名机制），每请求绑定 tenant/audience/scopes，密钥定期轮换。用户身份不直接“透传可信”，由 VF 服务端验证。
- 内部操作员：独立受保护登录与角色（Owner、Reviewer、Operator），按 tenant 和任务范围授权。
- Share Grant：至少 128 位熵的秘密 token，仅存哈希、过期与撤销状态；不得在可索引 URL 内无期限暴露。
- Worker：单次短租约与最小资源权限；无 VF 线索库或 Vey2GE 数据库凭据。
- 收到来源系统 Webhook/事件必须校验签名、时间窗、事件 ID、版本与租户授权；不可仅信 source_system 字符串。

## 8. 交互契约的验收样例

- 重复提交相同 idempotency_key → 同一受理引用；参数冲突 → 409；
- API 故障但 DB 未写 → 不返回“受理成功”；
- 已审核报告变化后旧 share approval → 拒绝；
- Reviewer 无权跨租户批准、匿名访客无权按顺序枚举报告；
- Outbox 重放 → 消费者仅处理一次；
- L2M 断线/Vey2GE 断线 → VRAE 任务独立完成、事件在 Outbox 可恢复；
- VF 表单记录只在保存确认后为 E2，报告状态不能代替商业接收事实。

详见 [数据架构](DATA_ARCHITECTURE_V1.1.md) 与 [ADR-0002](../adr/ADR-0002-data-ownership-and-contracts.md)。

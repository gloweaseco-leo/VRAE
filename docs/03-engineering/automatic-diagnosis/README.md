# 一次授权的自动 AI 诊断

本修复复用现有 SourcePlan、原 PG 队列、Worker、Collector、NativeSource、Qwen Provider、
共享 Quota 和 Guard。客户只输入 HTTPS 网址并勾选一次组合授权声明。
按 Owner 后续澄清，本 PR 交付实现及隔离测试，不执行真实客户网站或付费模型验收。

## VF 服务端调用

沿用现有 mTLS、服务 Bearer、用户 Cookie/CSRF 和媒体类型，不把凭据交给浏览器。
原用户会话由 VF 的现有服务接入处理，不增加客户操作。
`GET /v1/target-intake-contract` 返回 `automatic_diagnosis` 中的授权文本、版本和请求格式。
同一勾选同时记录只读采集许可、最小证据向北京区域 Qwen 的处理许可和自动结果返回许可。

```json
{
  "url": "https://supplier.example/",
  "authorized": true,
  "consent_version": "VRAE-AUTO-DIAGNOSIS-1",
  "idempotency_key": "stable-intent-key-0001",
  "accepted_at": "<UTC ISO timestamp>",
  "language": "zh"
}
```

`POST /v1/diagnoses` 在原 PG 入队 COMMIT 后返回原 `202 VFAccepted`。
网络重试保持整个请求不变；已经入队的请求不会重新签发来源或重做采集。
同键改变意图返回 409。DNS 所有权证明、单独 AI 勾选、人工签发均不属于此入口。
后台签发器仍检查当前主体、服务签名委托、公网 A/AAAA 和来源期限，并生成原签名许可。

用原身份读取 `GET /v1/audits/{audit_ref}/diagnosis`：

| HTTP / state | 含义 |
| --- | --- |
| 202 / CAPTURE_PENDING | 原队列或采集中 |
| 202 / AI_PENDING | 证据已 COMMIT，原租约结束后等待模型回执 |
| 200 / DIAGNOSED | 当前同一证据版本的真实 Qwen 回执、供应商用量及 Guard 候选均成立 |
| 200 / AI_UNAVAILABLE | 模型、额度或校验失败；保留确定性诊断，禁止假装 AI 完成 |
| 200 / CAPTURE_FAILED | 原任务失败 |
| 403 | 其他用户、不同邀请、过期或撤销的权限 |

结果包括五个原买家任务标识、原 `deterministic_diagnosis`、页面证据及覆盖范围，
以及模型 `claims` 中的解释、`source_bindings` 引用、`uncertainties`、`questions` 和 `rebuild` 建议。
结果的 artifact/report 哈希与原提交、证据和 AI 回执一致；读取时重新验证来源、重放
NativeSource，并在响应期间持有原 PG 权限锁。不输出原 HTML、对象归档或任何凭据。
协议替身不能产生 `DIAGNOSED`，其候选也不返回给客户。

自动分析不是人工认证：`formal_human_review=false`；原 Guard 候选状态不被改写。
原正式报告、人审、ShareGrant 和历史审核记录保持各自权限及状态。
VF 页面由 VF 团队消费此接口实现，本 PR 不改 VF 仓库或发布配置。

## 采集及模型边界

新授权仅允许提交网站的公开同源页面，沿用原发现顺序和每次最多四页的限制。
禁止登录、账户、管理、接口、购物和动作路径；不使用 Cookie 登录，不提交表单。
原 SSRF、完整公网 DNS 集合及重绑定检查、TLS/目的地址固定、robots、预算、隔离和费用限制保留。
跨域跳转不会自动扩大许可。原精确路径许可不会变成同源许可。
过期来源签发新版本，保留旧计划、授权和历史任务，不覆盖旧证据。

没有产品型号时，模型仍可使用已重放的网站 Guard 事实；证据不够时明确不可判定，
不会发明型号、引用或缺陷。模型请求限制到实际存在 Guard 锚点的任务和引用，
输出继续通过原校验；不会对失败的模型调用自动付费重试。
仍使用原共享 Quota，不创建新的生产账本、不重置历史用量。

## 部署及验证

本 PR 基于已有服务分支 `2114eb7`，最小差异不包含该分支原有实现。
没有操作现有 Windows 实例、私有配置或共享账本，没有执行部署。

后续部署沿用原镜像、初始化和操作器：初始化会追加 `006_automatic_diagnosis.sql`；
原 `enable-intake` 为本服务签署一次授权声明式接入委托。旧 DNS 专用签名委托不会被
请求参数悄悄升级。Qwen 仍须已配置有效的原费用许可、密钥、隔离 AI 出网和共享额度，
允许原 `allow_signed_model_consent`；缺失时安全返回不可用。这些是后台部署配置，
不要求客户签发许可或进行额外勾选。

```powershell
python -B scripts/verify_automatic_diagnosis.py
```

脚本只创建唯一标签的新测试 PG/容器，无宿主端口和现有卷挂载。网站和模型是明确的
测试替身；签名、原入队、Worker、证据、原 30 秒租约、Guard、PG 回执和读取权限均执行
真实实现。源码暂存容器 Linux tmpfs，避免 Windows 挂载延迟耗尽原 Guard 五秒期限，
不放宽运行时校验期限。结束时核验标签并删除本次 PG；日志写入忽略的 `.private`。
CI 在原 Windows 服务工作流中增加相同的一次性 PG 串联测试。

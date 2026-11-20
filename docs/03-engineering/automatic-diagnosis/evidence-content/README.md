# 自动预诊断：证据内容与现有交付修复

本轮承接 [#179 部署后根因巡查](../incident-179-20261120/README.md)。修复目标是让已有证据形成有内容的预诊断，
不改变 VRAE V1.1 产品定位、五维买家任务与 16 条规则，不修改 VF 仓库、页面或发布配置。
VF 仍需按 [消费验收清单](vf-consumption.md) 完成页面与轮询接入；VRAE 接口就绪不等于客户页面已完成验收。

## 修改范围

- 新自动任务使用 `l2-industrial-1.0.3 / ra2b6-1.0.3 / ra2c3-1.0.3`。
  新规格提取器版本 `ra2b2-product-facts-1.0.2`；旧版本按原算法与原哈希重放。
- 增加表头与值可明确对应的多列规格网格。TH 表头或明确产品标签建立列语义；重复标签、合并数据单元格、
  多个数据行等歧义不做猜测。单列说明不冒充额外规格，也不声称已提取完整参数或确认工程适配。
- 明确的 Contact/RFQ 标签参与同源代表页选择及静态入口证据。`ContactUs` 与规范相对 href 可识别；
  先规范化再执行原授权、DNS、robots、访问范围与费用限制。原 PageInventory/CaptureManifest URL 角色和哈希契约不变。
  不点击、不提交表单；入口存在仍不等于可见、目标已到达或消息可送达。
- Qwen 新提示版本 `qwen-evidence-buyer-1.2.0`，输入投影 `qwen-product-values-1.0.0`。
  仅从已重放、经过原 Guard 绑定的 INFO-01 引用提取 NAME、DESCRIPTION、SPEC_LABEL、SPEC_VALUE。
  最多两个产品页面，每页一个名称、两段描述及四对完整字段；同一字段对附带不透明页面分组和字段序号。
  联系方式、URL、明显凭据、控制字符及指令型内容整字段排除，不截断成另一事实；一端被排除的规格对不发送。
  原 HTML、公司联系资料和原始网页对象不发送。此过滤不是普适的 PII 或语义识别器。
- 没有有效文字值或已观察 HTTP 失败事实时，前置返回 `INSUFFICIENT_GUARDED_EVIDENCE / CONTEXT`，不发模型请求。
  原 Guard、引用校验、单操作防重复计费、预算与供应商用量核对继续有效。AI 仍只提供待人审的假设与建议。
- `008_committed_language.sql` 仅扩展原 committed_input 函数：新版本从原不可变请求读取 zh/en，
  与原输入一起冻结、重查并绑定上下文。旧版本响应不增加该字段，不回填旧工件。
  新源缺语言或未应用迁移时拒绝，不默认替客户选择语言。
- 原 API 错误处理中增加请求级不透明关联引用、状态码、固定安全错误码与耗时；响应附带 `X-VRAE-Request-Ref`。
  不记录原始路径、网址、恢复码、Cookie、客户身份或异常文本。临时读取重试由 VF 实施，不重新提交任务。

## 顶层设计对齐

| 权威 | 保持的约束 |
| --- | --- |
| PRODUCT_CHARTER_V1.1 | 采购商体验诊断，非评分器/建站器；未审自动预诊断不改称正式 L1，不推导 E2/E3。 |
| AUDIT_METHODOLOGY_AND_RULES_V1.1 | Evidence → Observation → Hypothesis/Recommendation；UNKNOWN 不是缺陷，未观察不判缺失。 |
| PRODUCT_AND_OPERATOR_JOURNEYS_V1.1 | 客户只输入网址和勾选一次授权；VF 负责前台与咨询，VRAE 负责证据及审阅能力。 |
| SYSTEM_AND_APPLICATION_V1.1 | 复用现有 API、PG、隔离 Worker、规则、Qwen、Guard 和报告服务，无新平台、服务或队列。 |
| DATA_ARCHITECTURE_V1.1 | 新版本追加，原 Evidence/ReportVersion 不覆盖；审核绑定精确版本；模型账本不清空，私有证据不进入 Git。 |

正式 L1 继续复用现有 Report Service、真实 Reviewer、精确 ReportVersion、ShareGrant 和 VF 受控读取通道。
没有可靠问题时明确证据不足，不为凑满三项而把 PASS、UNKNOWN 或模型内部处理限制包装成网站缺陷。

## 验证与发布

必要正反例包括规格配对/歧义、联系标签/隐藏与跨源链接、敏感字段/指令拒绝、完整字段对、原申请语言贯通、
协议替身的明确标识、原 Guard 绑定、AI 不可用时保留五维事实、旧历史重放及请求日志去敏。
冻结真实工件的新版本离线分析仅为修复回放，不生成或覆盖原报告，不等于真实新模型输出或正式客户验收。

发布须先执行现有管理员初始化中的 additive 008，再以同一版本更新 API/Worker/AI；不得由 API 身份自行迁移。
本轮不部署或修改 VF。Owner 合并/部署后，VF 团队按字段清单验证原任务查询与新授权任务的展示。

## ????????

? [frozen-replay.json](frozen-replay.json)????????????? INFO-01 ??? UNKNOWN?
????? PASS??? UNKNOWN????????????????????????????? Guard ???
????????? 11 ??????? 1??? 2?????/?? 4?????????
?????????????????????????? UNKNOWN?????? AI ??????????

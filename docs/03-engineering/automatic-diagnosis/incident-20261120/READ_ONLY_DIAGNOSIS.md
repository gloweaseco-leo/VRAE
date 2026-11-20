# PR176 首次真实诊断：只读根因复核

按 Owner 评论7031652960，对其 PDF 对应的同一原任务执行只读复核。
匹配只在受保护环境中完成；本记录不包含源站网址、客户、audit_ref、job_id、
任务 Cookie、密钥或网页原文。未重采、未调用模型、未签发会话、未改变 Guard、
采集许可、预算、报告权限、历史工件或原 AI 回执。

## 已证实的失败链

**只获得首页与目录页 → 产品详情 HTTP 请求前耗尽总预算 → Guard 引用目录为空 →
`LOCAL_CATALOG_BOUND` → Qwen 未派发 → `AI_UNAVAILABLE`。**

这不是供应商 HTTP 错误、真实模型返回质量问题或额度耗尽。
当前运行 SHA 与部署一致，原 PG artifact、报告哈希、display hash 和 AI receipt
全部关联一致，原 NativeSource 重放验证通过。业务验收未通过，不以健康200替代。

| 环节 | 原任务的实际记录 |
| --- | --- |
| 原任务 | DRAFT_READY，Worker尝试1次，AI_UNAVAILABLE |
| 原候选清单 | 57条，54条为未尝试的发现候选 |
| 页面记录 | 3条：HOME 200、CATALOG 200、PRODUCT UNKNOWN/TIMEOUT |
| 实际请求计数 | 3，覆盖robots、首页、目录；产品页没有请求计数、响应、正文或跳转轨迹 |
| 采集耗时 | 原Worker日志24.71195秒；配置总预算24秒 |
| 其他上限 | 最多4页/12请求/2,000,000字节，本次记录3页/3请求/90,711字节，未命中这些上限 |
| robots | HTTP200，原强制检查保留；本次终止码为TIMEOUT，非robots拒绝 |
| 模型前置 | LOCAL_CATALOG_BOUND；Guard事实0条，候选0条 |
| 供应商 | 没有用量、没有本任务配额预留、共享账本仍为原9笔 |
| 许可及额度 | CURRENT_SIGNED_PERMISSION_VALID；模型配置有效；日上限5,000,000微元，占用493,818，剩余4,506,182 |

结合原 `Budget.before_request` 的请求计数顺序及原计时，产品页的TIMEOUT是**总采集
预算在其请求派发前耗尽**，不能写成“产品详情服务器响应超时”。现有日志不能进一步
分离前两页的DNS/TLS/传输、HTML处理与授权核验各自耗时，不能据此断言是哪一种耗时占主导。
54条发现候选没有尝试，不应归为54次失败、robots阻断或网站缺陷。

PDF显示的24条是展示记录口径，原采集工件为57条候选；本轮未核对VF的选取/截断代码，
不把24误称为实际访问数，也不修改VF。

## 为什么两页原文没有形成模型锚点

1. 原通用规则实际存在两条 `DISC-01/PASS/CAPTURED_REACHABLE_NAV_HREF`，只证明保存的
   首页静态导航链接到达已采集目录。它们不代表网站采购体验整维PASS；当前Guard目录不接纳
   DISC-01作为模型引用锚点。
2. 产品详情未取得正文，INFO-01为 `RAW_HTML_REQUIRED`。工业诊断只有
   `NO_SUPPORTED_PRODUCT_RECORD/UNKNOWN`，不能解释为网站没有产品。
3. 目录页有154个anchor，原有界解析器只接纳到128个，并存在1个不满足href属性条件的
   anchor，因此DISC-02为 `HTML_UNSUPPORTED_OR_AMBIGUOUS`。这属于当前解析子集的边界，
   不等于整站HTML或采购路径已经证实有缺陷。
4. 首页有1个title和1个description候选，但现有HeadSignals对合法自闭合标签产生
   `UNSUPPORTED_HEAD_END`：1次meta、3次link，均不是源文档显式结束标签。原因是继承的
   `HTMLParser.handle_startendtag`会调用endtag，而当前endtag处理将其当作不支持的head结束。
   这是可确认的解析兼容性缺陷。同时该页canonical候选为0；**只修自闭合标签并不能保证
   本任务满足原SEO规则及Guard门槛**，不能据此宣称AI链已修复。
5. 原Guard只接纳特定规则的PASS或有证据失败。现有两页未产生这些合格事实，PR176的通用
   网站分支得到空目录，`prepare_context`在模型派发前拒绝。不能把UNKNOWN强改PASS、
   制造引用、放松Guard或把原文直接传给模型来刷绿。

这是“采集证据供给与当前证据适配范围不够”的业务断点，另有明确的head解析兼容缺陷。
已有协议与隔离测试通过，并没有证明这些真实页面结构能满足模型证据门槛。

## 回执与读取口径

原AI回执的 `provider_attempts`、`real_model_calls` 为null，`cost_status=UNKNOWN`。
源码在Provider已配置时、尚未准备Context之前便预置这些未知字段。此任务在Context准备中
失败，因此未经过Session更新计数。结合无本任务预留、无供应商用量、原账本9笔及源码中
“先预留后HTTP派发”的顺序，可以确认此次**未派发**；不能把null当作一次未知计费调用。
这是回执表达缺陷，不修改旧不可变回执，也不改写历史未知费用记录。

06:02及06:06 UTC，原同主体PG读取端口及原DTO重放得到200/AI_UNAVAILABLE，
diagnosis_complete=false。未取得原始任务Cookie，因此没有伪称重放了客户HTTP会话。
06:09 UTC同一原会话自然过期，读取返回42501；该后续过期不是05:39 AI失败的原因。
没有签发新会话或使用恢复码来绕过此限制。

## 本轮边界及下一步

仅产出此脱敏回执，没有修改运行代码或部署，没有扩大采集范围或额度。
后续修复应限于原链路的证据适配、预算内调度及明确的未派发/空目录状态表达；
先核实足以解释预算耗尽的耗时证据。解析修复必须保留旧工件按旧规则版本重放，不能
原地改冻结语义导致历史工件哈希失效。任何局部修复都不能替代新的真实业务验收。
下一次真实采集/模型验收由Owner依据本回执决定，不复用或重试原已终结任务来刷绿。

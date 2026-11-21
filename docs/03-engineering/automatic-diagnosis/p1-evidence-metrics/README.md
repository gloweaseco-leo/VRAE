# P1：已有信任与询盘证据、可复核 HTTP 指标

本增量叠加 PR 186；沿用 V1.1 五维、16 条规则、Worker、PG、Guard 和报告通道。不修改 VF 仓库。P2 自适应调查、浏览器性能测试和正式报告审批不在本次范围。

## 交付与消费

`AutomaticDiagnosis.fact_review` 是绑定已重放工件 SHA、EvidencePack 和原执行引用的只读投影，契约 `vrae.fact-review.v1`。`customer_presentation.fact_review` 为精确副本。它不写回历史工件、不改变原规则结论，也不依赖 AI 是否成功。

VF 团队同步本仓库 `consumer/reference.mjs`、新 `fact-review.mjs` 和类型声明后，通过现有适配器得到：

| 五维任务 | `buyerTasks[].sourceFactReview` / `reportView.tasks[].sourceFactReview` | 展示约束 |
| --- | --- | --- |
| TRUST | 原 TRUST-01 的 context_facts、missing_prerequisites、source_pointer 和 nativeResult | 已记录企业自述与未核实部分分开展示；可复用同维度 recordedFacts 的中文文字、来源和引用。重复联系链接不是独立资质，不认证法人身份或材料真假。TRUST-02/03 的已有候选仍从 reviewCandidates 消费。 |
| INQUIRE | 每个已访问页面的 static_forms、解析状态、表单/字段覆盖计数 | 询盘、搜索、账号和未解析候选分开。字段仅为原始 HTML 声明；不得说已展示、能提交、必然校验或可以送达。 |
| SEARCH_TECHNICAL | 每条采集记录的状态、响应码、响应体字节数、跳转数、measurement | 无响应记录与有 HTTP 响应分开。一次测量不是性能评分，历史缺少计时保持 UNKNOWN。 |

其他两维返回空数组。字段按 task 分支读取；同一快照链接从现有 pageScope 取。未同步适配器的 VF 代码会忽略新扩展，不会自动出现对应页面内容。既有版本与 P0 的接入要求继续适用。

静态字段提供 NAME、EMAIL、COMPANY、PHONE、COUNTRY、SUBJECT、MESSAGE、PRODUCT、MODEL、QUANTITY、SEARCH、ACCOUNT_SECRET、UNKNOWN 语义枚举；字段类型、required/disabled/readonly 属性及原正文哈希与 UTF-8 字节范围可复核。仅识别明确标签或 email/tel/search/password 类型；不根据私有 name/id 参数猜字段用途。表单值、默认内容、隐藏字段名称/值、原始 action 与联系信息均不导出。密码字段只标记账号候选。

`PARSER_UNSUPPORTED`、零条可解析表单和截断均不能证明网站没有表单。最多每页 8 个表单、每表单 32 个字段，原 HTML 最多 128 KiB。嵌套、隐藏、模板、未闭合或歧义结构受到保守限制；没有执行 JS、获取验证码或提交表单。

## HTTP 量化口径

PinnedTransport 在成功完成一个受控 HTTP 交换时，以 monotonic 时钟记录阶段。可选 `FetchResponse.measurement` 被保存在 `CaptureManifest.pages[].http_measurement`，随原清单哈希与 EvidencePack 完整性校验进入现有证据链。旧清单未增加字段，原字节/引用不重写。

| 字段（毫秒） | 起止 |
| --- | --- |
| connect_ms | TCP 连接开始至连接建立 |
| stream_setup_ms | 连接建立至 TLS/流建立完成（含调度开销） |
| first_byte_after_send_ms | 请求 drain 完成至首次读到响应数据 |
| headers_after_send_ms | 请求 drain 完成至解析出最终响应头 |
| body_after_headers_ms | 最终响应头解析至消息结束 |
| exchange_ms | TCP 连接开始至消息结束 |

固定 method 为 PINNED_HTTP_MONOTONIC_V1，scope 为 FINAL_HOP_INCLUDES_GUARD_AND_SCHEDULING_NO_DNS，samples=1。计时包含现有权限重查与调度等开销；不含 DNS、robots、抓取间隔或此前重定向请求，不声称是纯服务器耗时、浏览器 TTFB、LCP、CLS 或真实用户指标。响应体字节数不是整站资源重量。超时或未完整返回时不编造部分计时，不自动判慢或 FAIL。

## 验证

测试结果与脱敏历史证据见同目录 JSON。真实网络路径在 network-none、内核防火墙和降权实验环境验证 DNS/TCP/TLS，未访问客户网站。另以既有授权报告的留存正文只读验证投影和 VF 参考消费；不新增真实 Qwen 调用，也不将此重放称为新的线上验收。正式合并部署与 Owner 验收分别进行。

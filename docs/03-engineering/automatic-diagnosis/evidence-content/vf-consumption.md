# VF 现有接口消费验收清单

不新增接口或客户操作，继续读取 `GET /v1/audits/{audit_ref}/diagnosis`。
VRAE 提供原结果与证据，以下页面与 BFF 工作由 VF 团队在自身仓库实施。

## 内容独立呈现

1. `deterministic_diagnosis.buyer_tasks[]` 是五维规则事实权威。每组使用 `task`，遍历 `rules[].observations[]`：
   `observation.result`、`observation.statement`、原 `reason`、`citations` 及范围限制一起消费。
   不因 claims 为空、AI_UNAVAILABLE、diagnosis_complete=false 或 HTTP 202 就丢弃已经存在的确定性事实。
2. `claims[]` 是独立的未人审 AI 解释层。只消费原 Guard 绑定的引用、解释、建议、不确定性和补充问题。
   不把 AI 解释升级为客观事实或已批准报告；不要求每个维度都有 AI 建议。
3. `analysis_outcome`、`model.failure_stage` 和模型状态单独映射友好文案：

| 情况 | 客户应看到 |
| --- | --- |
| CAPTURE_PENDING | 正在读取获准公开页面 |
| CAPTURE_FAILED / NOT_RUN | 本次页面检查未完成；不据此评价网站质量 |
| AI_PENDING / PENDING，已有 deterministic_diagnosis | 展示已有规则事实，说明分析仍在整理 |
| INSUFFICIENT_EVIDENCE | 已读取页面，但可支持分析的证据不足；保留已核实部分 |
| NOT_DISPATCHED | AI 未发出；显示已有事实和受限原因，不称模型供应商失败 |
| PROVIDER_FAILED | 模型请求失败，保留规则事实 |
| VALIDATION_REJECTED | 模型输出未通过证据/格式校验，保留规则事实 |
| COMPLETED | 本次自动分析完成，仍未经过正式人工审核 |

`diagnosis_complete` 保持原含义，不等于已人审，也不决定规则事实是否可显示。

## 范围与引用

- 数量取 `capture_summary`。例如“本次访问 6 页；另发现 60 个候选链接未访问”，不是“检查了 24 页”。
- 主证据区使用 `page_scope.visited_pages`，展示 URL、时间、HTTP 状态和绑定引用。
- `failed_attempt_records` 分开显示；没有 HTTP 状态不能推断网站返回了错误。
- `unvisited_candidates` 折叠为发现清单，明确未访问；不充当诊断发现，也不判缺陷。
- UNKNOWN 应说明“本次未核实的原因”，而非统一显示“本次没有结论”，更不能改为缺失。
- 不生成总分、不凑三个问题；正式 L1 的审核与授权继续使用既有独立报告通道。

## 查询恢复

同一已受理任务始终使用原引用和原会话查询，不生成新幂等键、不重新 POST 诊断来恢复进度。

- HTTP 202 按现有 poll_after_seconds/正常查询间隔继续读取；有事实即可展示。
- GET 网络错误或 503 可采用有限退避，例如 2、5、10 秒后继续原查询，并设置总次数/时长上限。
- 429 尊重 Retry-After，不高频轮询。
- 达到读取重试上限时说明“暂时无法查询，任务状态尚未确认”，保留原任务和手动查询入口；不写成后台终止。
- 403 不通过重试绕过权限，不无声创建新任务；409 不重新提交改变原意图。
- 恢复码仅用于真正需要跨会话返回的情况，不是正常等待的必经步骤。
- BFF 记录脱敏 HTTP 状态、耗时及上游 `X-VRAE-Request-Ref`；不记录响应正文、网址、Cookie、恢复码或凭据。

## 联调验收

核对同一份原 DTO 与 VF 页面：五维规则数、原状态、引用、真实访问数及模型结果分别一致；
临时读取错误后仍查询同一个任务。禁止用新建任务或再次调用模型代替原任务查询恢复。

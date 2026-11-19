# G1-C2 初始HTTP验收状态

基线 `7fdeeed0f427ce3b94677ab2a480eae1556e85ca`，冻结G0语义不变。C3首个G1 Draft/精确服务SHA/owned端口及运行输入尚未到达；本表不是HTTP实测记录。每项 **BLOCKED / G1_HTTP_PENDING**，无假请求/响应日志。客户端自测与冻结合同回归的PASS独立记录在Draft PR，不用于改写本表。

| case ID | 预期HTTP | 当前 | 待C3实际输入/观察 |
| --- | --- | --- | --- |
| create | 202 | BLOCKED | PG提交/单job回读 |
| replay | 202 | BLOCKED | 同意图同ref/run |
| changed_intent | 409 | BLOCKED | 同key合法变体 |
| disconnect_retry | 202 | BLOCKED | 断开ACK后原请求重试 |
| return_exchange | 200 | BLOCKED | 真实Cookie及CSRF头 |
| status_axes | 200 | BLOCKED | 同任务三轴 |
| draft_not_completed | 200 | BLOCKED | 实际DRAFT_READY/UNPUBLISHED |
| unapproved_report | 403 | BLOCKED | 当前合法会话+未发布 |
| preview | 200 | BLOCKED | 同任务原fact/hash/五维投影 |
| stale_report | 403/409 | BLOCKED | 旧版或过时grant |
| bare_ref | 403 | BLOCKED | 有服务身份/裸ref无会话 |
| wrong_tenant | 403 | BLOCKED | 另租户服务身份+原会话 |
| expired_session | 403 | BLOCKED | 先前200+过期证据 |
| withdrawn_session | 403 | BLOCKED | 先前200+撤回证据 |
| csrf_missing | 403 | BLOCKED | 原会话/缺CSRF |
| csrf_invalid | 403 | BLOCKED | 原会话/错误CSRF |
| rate_limited | 429 | BLOCKED | 安全限额响应 |
| dependency_unavailable | 503 | BLOCKED | 安全依赖失败 |
| inquiry_waiting_ack | 202 | BLOCKED | 无VF真实receipt不得升级 |
| after_restart | 202 | BLOCKED | PG/服务重启+同ref/单job |
| bad_accept | 406 | BLOCKED | 未知profile拒绝 |
| bad_content_type | 415 | BLOCKED | 错误POST媒体类型 |
| missing_service_auth | 403 | BLOCKED | 无服务身份拒绝 |

实际运行时CLI逐项生成PASS/FAIL/BLOCKED、固定失败断言ID、脱敏请求/响应结构和原始响应SHA。C3提供实际Draft后针对其精确SHA消费，失败回交C3纠正。未批准真实网络/客户/真人审批/ShareGrant/Provider费用/部署；无C2服务端或第二CRM。

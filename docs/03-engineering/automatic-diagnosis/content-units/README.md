# 报告内容单元

契约是 `vrae.report-content-units.v1`。单元有 `unit_id`、D1–D6、强度、中英文本、证据、限制、审核状态和哈希。

强度只有 `CONFIRMED_BY_REVIEW`、`EVIDENCED_PENDING_REVIEW`、`HYPOTHESIS`、`UNKNOWN`。参考消费端可以重排单元。它不能改强度、分组或文本。非 `CONFIRMED_BY_REVIEW` 不能呈现为已证实。

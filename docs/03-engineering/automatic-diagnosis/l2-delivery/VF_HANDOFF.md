# VF 交接

本仓库不修改 VF。下面是只读契约，供 VF 自己的页面使用。

## 预诊断和正式报告

`GET /v1/audits/{audit_ref}/diagnosis` 仍是预诊断。`is_report` 与 `formal_human_review` 都是 false。正式报告仍走既有 report-authority。不要把预诊断改名为已审核 L2。

## 判断

1.0.7 使用 `vrae.diagnosis-judgment.v1`。1.0.8 使用 `vrae.diagnosis-judgment.v2`。

v2 的结论只用 `lead`。已证实障碍栏保持空。有证据的 L-B 异常放在 `evidenced_pending_review`，不要写成已确认缺陷或分数。五个阶段用 `stages`，不要把未访问页面算进缺陷。

禁止渲染「建议优先关注」和「可以先这样改」。

## 内容单元

消费 `vrae.report-content-units.v1` 时可以调整顺序。必须保留 `group`、`strength` 和中英文本。只有 `CONFIRMED_BY_REVIEW` 可以呈现为已证实。`EVIDENCED_PENDING_REVIEW`、`HYPOTHESIS`、`UNKNOWN` 都要显示为未最终证实。

## 商务区

不渲染价格、工期、排名、流失额、E2 或 E3。企业待补和复验可以显示。证书真伪、工程适配和询价送达保持未知，除非正式审核另有记录。

## 本分支没有交付的部分

三个真实试点站、真实 Qwen 端到端和真实人审交付都没有在本分支完成。参考渲染只重复上述边界，不连接 VF 页面。

见 [REFERENCE.md](REFERENCE.md)。

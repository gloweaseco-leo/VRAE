# C2/C3: accepted S2 input contract

可直接更新到 accepted main `95ed55321775223e95cf0a1585220951cc692648`，无需复制 Draft 文件。

- [唯一组合/重放接口](https://github.com/gloweaseco-leo/VRAE/blob/95ed55321775223e95cf0a1585220951cc692648/vrae/rules/s2/contract.py)：`evaluate_s2` / `verify_s2_projection`，显式 `projection_version='s2-projection-1.2.0'`；默认仍为 P0。
- [IndustryPack / IndustryPins](https://github.com/gloweaseco-leo/VRAE/blob/95ed55321775223e95cf0a1585220951cc692648/vrae/industry/l2_v1/pack.py)：`load_s2(..., version='1.1.0', profile_id='industrial')`；`IndustryPins(industry_ref, tenant_id, version='1.1.0', profile_id='industrial')`。profile/ref 必须由服务端任务配置独立持有。
- [真实保存的 DTO 示例](https://github.com/gloweaseco-leo/VRAE/blob/95ed55321775223e95cf0a1585220951cc692648/docs/03-engineering/s2-c1-p1-batch2/example.json)及[字段/适用性说明](https://github.com/gloweaseco-leo/VRAE/blob/95ed55321775223e95cf0a1585220951cc692648/docs/03-engineering/s2-c1-p1-batch2/REVIEW.md)。

顶层 `kind=S2EvaluationProjection`、`projection_ref=s2p-*`、`pack_ref`、`scope`
（tenant/run/policy/version）、`projection_version`；原生 `baseline_execution`
仍为旧执行器的六条启用规则，不能将投影重命名为 rx。

`static_projection.rows` 对应 Batch1；规则版 `s2-static-1.0.0`、来源版
`s2-static-http-1.0.0`。`industrial_projection.rows` 对应 Batch2；规则版
`s2-industrial-context-1.0.0`、来源版 `s2-industrial-source-1.0.0`，行业版 1.1.0。
每行包含 `observation`（rule_id/rule_version/observation_id/result/evidence_ids）、
`reason`、`citations`；工业行另有 `model`、`industry_ref`、`source_pages`、`details`。
真实 citation 包含 ev/source/snapshot refs、原资料包 locator、SHA256、UTF-8 原始字节范围及 quote。

UNKNOWN 出口：未独立传入 IndustryPins 时三个工业通用规则均 UNKNOWN；缺字段、
单位/型号/版本不清、PDF/图表未解析、声明实体无法比较均 UNKNOWN。引用、scope、
配置 ref/version/profile 不匹配属于完整性错误，应拒绝，不能改写成 PASS。
源被阻断时保留 ACCESS_BLOCKED；metadata-only 来源不能获得虚构 ev-ref。
NOT_APPLICABLE 仅来自独立固定的明确配置：pump-only 排除声明为 valve 的型号；
technical-only 排除 TRUST-02/03。普通网页字段无权选择这些配置。

界面须保留原 result 和出处，并明确来源候选/审阅假设；不得自动写入旧 Finding/Guard。
浏览器 v1 仍仅为候选/UNKNOWN。Gold 仍 0/26，无精度准入声明。
本轮买家任务报告候选层将另交小 Draft；未获 Owner 合并前，C2/C3 继续依赖上述已接受 DTO。

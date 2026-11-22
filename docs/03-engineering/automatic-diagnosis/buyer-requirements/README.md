# 买家决策要求与 INFO-02

本轮只增加候选规则执行器 `ra2b6-1.0.6`，供隔离重放使用。它没有登记进现有 FindingPackage 构建器，自动诊断 Worker 仍选择 `l2-industrial-1.0.7` / `ra2b6-1.0.5`。下一步要进正式报告，必须把这条已绑定证据的判断接进现有 Finding / Report 权威，而不是另建报告。

`buyer-stages-1.0.0.json` 是砂轮草案，`approval` 为空。未签字时判断只能是 `REVIEW_REQUIRED`，不能变成网站缺陷。行业名称和条目编号都在这份 JSON 里，判断代码按 `site_role` 和 `field_groups` 读取。

INFO-02 读取 `product_facts` 已经解析出的字段。引用使用该产品页的 `evidence_ref` 和字节范围。导航、页脚里的干扰文字不会成为字段。缺少字段、未解析的 PDF、无法唯一组合的参数，都不自动判为网站问题。

正式审核仍是现有 C2 账本和 `report-authority`。审核人来自根签名身份配置，本轮没有配置真实审核人，也没有打开客户外发。VF 正式报告消费链路没有在本轮改动。

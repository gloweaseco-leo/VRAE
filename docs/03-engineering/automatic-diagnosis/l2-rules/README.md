# L-B 规则

`ra2b6-1.0.6` 在既有 1.0.5 观察之后补 INFO-02、TRUST-02、TRUST-03、TECH-01、SEO-02。这些规则只到 L-B。

INFO-02 读取未签字清单时保持 `UNKNOWN`。TRUST-03 的冲突不出 `FAIL`。TRUST-02 的真伪字段保持 `UNKNOWN`。TECH-01 的 5xx 是 `TRANSIENT_NOT_PROVEN`。SEO-02 依赖脚本时是 `UNKNOWN`。

S2 合成路径没有删除。元数据引用使用 `contracts/v1/collection/extensions/MetadataCitation.schema.json`，不改冻结的采集基础契约。

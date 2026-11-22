# 采购阶段信息需求清单

`buyer-stages-1.0.0` 是砂轮草案，`profile` 为 `abrasive_wheel`。文件里的 `approval.signer`、`signed_at`、`config_sha256` 都是 null。

未签字时每个条目只能是 `REVIEW_REQUIRED`。客户结果不包含缺口判断。`AW-CONFIRM-01` 与 `AW-INQUIRE-01` 的 `site_role` 是 `CLARIFY_CHANNEL`，即使签字也不能输出 `GAP_WITH_EVIDENCE`。结合剂和粒度的组合走澄清，不是缺口。

本文件对应的诊断附件只挂在 `l2-industrial-1.0.8`。1.0.7 客户输出没有这份清单。INFO-02 的失败映射只在签字后的计算函数里成立；仓库里的草案未签字，所以执行器不会因此给出 `FAIL`。

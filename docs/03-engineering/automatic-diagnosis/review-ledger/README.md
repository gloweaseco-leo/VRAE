# 审核记录

逐条确认、修改、驳回、当前哈希批准、撤权和接收者核对在 `vrae/l2/item_review.py`。审核人标识由调用方传入，代码里没有真实人员姓名。

合成身份和 Controlled 模式写出的 `formal_human_review` 是 false。修订后的哈希不能沿用旧批准。错误接收者被拒绝。撤权把授权标成 `REVOKED`。

周汇总给出采纳率和修改率。没有已决定条目时状态是 `NOT_EVALUABLE`。导出的 Gold 候选标记为 `SIMULATED_NOT_HUMAN_GOLD`。现有 C2 账本方法仍负责真正的版本、分享和读取。本分支没有真实审核人配置，也没有把客户报告标成已批准。

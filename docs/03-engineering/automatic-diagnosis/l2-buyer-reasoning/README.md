# L2 买家推理

提示词 `qwen-l2-buyer-reasoning-1.0.0` 加在现有 provider 与 session 上。只有执行器 `ra2b6-1.0.6` 会选中它。旧执行器仍走原来的提示词。

输入应是脱敏后的结构化事实、清单判断、规则观察和引用标识。输出四类：`CROSS_PAGE_CONFLICT`、`MATERIAL_RELATION`、`BUYER_QUESTION`、`IMPROVEMENT_BASIS`。每条分开事实、假设、反证和待确认。没有引用的条目丢弃。跨页冲突至少两个快照。上限 K 为 8。允许零条。

本分支只用协议假提供者。失败、超时和未知费用成为 `AI_UNAVAILABLE`，不伪装完成。通过校验的候选以 `REVIEW_REQUIRED` 挂在既有草稿上，并绑定工件哈希、提示词版本和模型版本。没有在真实工件上调用真实 Qwen，不能说 L2 AI 已完成。

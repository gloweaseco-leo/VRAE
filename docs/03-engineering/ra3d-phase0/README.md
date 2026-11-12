# RA-3D Phase 0｜人工审核与版本完整性设计

**DESIGN_ONLY · IMPLEMENTATION_NOT_STARTED · CUSTOMER_SHARE_NO_GO**

授权：[Issue #49](https://github.com/gloweaseco-leo/VRAE/issues/49)。本包只设计未来人工工作流，
没有执行人工审批、调用原审批函数、启动应用、生成客户报告、发放分享授权或部署。
示例一律 **HUMAN_REVIEW_SIMULATION_NOT_ACTUAL_APPROVAL**；Human Gold 仍为 0/26。

| 立即需要回答的问题 | 本设计的答案 |
| --- | --- |
| 人究竟批准哪份内容？ | 经可信身份核验的人，明确批准一个租户下、一个最新版本的完整 ReviewTarget 摘要；同时包含原 RA0 hash、RA3C draft/editorial/HTML hash、全部来源和版本。 |
| 批准后能否显示另一份 HTML？ | 不可。读取时验证精确对象字节及审批绑定；任意变更生成新版本、重新审核，旧批准只保留历史意义。 |
| 审核通过是否允许外发？ | 不允许自动外发。后续还需 Owner 单独授权、特定接收主体与同意、有效期/撤销校验，以及另行授权的 RA4 认证访问运行时。 |
| 没有真实问题怎么办？ | 保留 0 问题私有范围摘要，只允许内部“已核对范围”的确认；不创建虚假 Finding、ReportVersion、正式 APPROVE 或分享授权。 |

阅读顺序：

1. [CONTRACT.md](CONTRACT.md)：角色、摘要图、合同字段、状态机、事务与伪代码。
2. [REVIEWER_UX.md](REVIEWER_UX.md)：逐项核证、签署、修改退回、拒绝、手机与异常状态。
3. [静态审核工作台概念图](mock/reviewer-workbench.html)：可本地打开，全部动作禁用，无脚本/表单/网络/实际审批。
   [桌面截图](mock/desktop-concept.png) / [手机截图](mock/mobile-concept.png) 仅为静态设计的渲染证据。
4. [SCENARIOS.md](SCENARIOS.md)：一个真实证据问题、零问题摘要、内容篡改及跨租户三个完整设计演练。
5. [THREAT_MATRIX.md](THREAT_MATRIX.md)、[TEST_PLAN.md](TEST_PLAN.md)：24 项威胁与 48 项待实现验收用例，**不是已运行的测试**。
6. [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)：兼容性缺口、方案取舍和后续放行条件。
7. [REFERENCES.json](REFERENCES.json)、[SCENARIO_INPUTS.json](SCENARIO_INPUTS.json)、[DESIGN_EVIDENCE.md](DESIGN_EVIDENCE.md)：固定源码引用、原始样本摘要和文档检查证据。

## 基线与隔离

独立 worktree `D:/Projects/VRAE-Codex2/.worktrees/ra3d-phase0`，分支
`codex2/ra3d-phase0-review-design`，由已验收 main
`2429be6dc5d7dcb48221ab179f063b93ce4b1956` 建立。只新增本目录设计文件。

PR #47 的 `6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2` 是**未合并、待独立验收的候选**，
仅通过固定 Git 对象只读参考；没有合入本分支，没有视为 main 的稳定报告 API。
不修改其分支、工作树、源码、样本或 Codex-1 PR #48 QA。

## 后续实施门禁

本设计通过也不授权 RA3D 生产代码。须依次满足：RA3C 功能及独立 QA 获 Owner 最终通过并合并；
重新读取精确已验收 main；本设计根据实际合并合同复核；Owner 发出**另一次明确的 RA3D 实施 GO**。
RA4 的身份、事务存储、客户访问和分享运行时仍须各自授权与真实验收。

本包没有要求为文档修改重跑四项工程 CI；仓库可能自动触发既有 CI，其结果只能说明当前 main 回归，
不能证明此设计已有生产实现。独立 Draft PR 提交后停止，等待 Owner 审阅，不自行合并。

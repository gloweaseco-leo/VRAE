# R0：VEYFRONT ↔ VRAE 合同候选

Owner [#146](https://github.com/gloweaseco-leo/VRAE/issues/146) / [#147](https://github.com/gloweaseco-leo/VRAE/issues/147)。版本 `vf-vrae-r0.1`，**DRAFT_NOT_G0_FROZEN / SYNTHETIC_CONTRACT_ONLY**。基线 VRAE `89a5115e3b8c4ab782bc140d3d278ffc83e7cc7a`；VF main `348ba4a6a9e885431e769e008dd4b7c157405104`。没有运行中的跨仓服务、真实人审、真实 ShareGrant 或 VF 集成。Owner G0 冻结前仅供双方准备，不能据此合并实际跨仓适配。

## 可运行交付

- [VF-B一页兼容矩阵](VF-B-COMPATIBILITY.md)：对照Owner补充要求与VF PR36，新增 `vf-vrae-r0.1-vfb.1` consumer profile、五维多事实视图、三维状态及独立返回授权；[可执行fixture](../../../contracts/l2_launch/vf_b.py)与[Schema](../../../contracts/l2_launch/vf-b.schema.json)。不是运行中的VF服务。

- [JSON Schema](../../../contracts/l2_launch/schema.json)：候选 envelope、许可签名引用、两层视图、错误及收据；只引用本地注册的原 V1 Schema，验证不访问 schema URL。
- [JSON示例](../../../contracts/l2_launch/examples/)：基础22例及新增VF-B提交/返回授权/三维状态/五维多事实/独立咨询和安全错误例，均可按固定种子重建。
- [纯合同校验](../../../contracts/l2_launch/contract.py)：原 `authorize_source` / `check_share` 及 JSON Schema 重用；Ed25519仅验证合成测试权威。签名不证明法律许可、人身份或事实真伪。
- [离线持久fixture](../../../contracts/l2_launch/fixture_stub.py)：临时SQLite事务、outbox、租户幂等、收据重放和撤回；没有HTTP监听、采集器、模型、CRM或可部署入口。
- [consumer cases](../../../tests/l2_launch/consumer_cases.py)：正例与拒绝路径；整个测试过程禁止socket/DNS。调用方身份、当前版本/撤销查询必须来自受信适配器，不能从HTTP body中取role或布尔授权。

复验（3.11和3.13均使用原锁，不修改依赖）：

```powershell
python -m pip install -r requirements-ra4b-p1.lock
New-Item -ItemType Directory -Force docs/03-engineering/l2-launch/.runtime | Out-Null
python -X utf8 -m pytest -q tests/l2_launch/consumer_cases.py --basetemp=docs/03-engineering/l2-launch/.runtime/pytest-local --junitxml=docs/03-engineering/l2-launch/.runtime/consumer.xml
python -X utf8 -m tests.l2_launch.evidence --junit docs/03-engineering/l2-launch/.runtime/consumer.xml --output docs/03-engineering/l2-launch/.runtime/evidence.json
```

只运行consumer suite不生成新示例；`python -m tests.l2_launch.make_examples` 可重建固定时钟的合成示例。测试密钥种子公开且仅限fixture，绝不可配置到真实身份/人审/收据服务。所有示例有 `SYNTHETIC_CONTRACT_FIXTURE_NOT_A_RELEASE` 外标；`simulate_report_read` 只返回合成投影，不签发正式决定或真实访问能力。

除新增contracts/docs/专项tests外，唯一辅助文件是新增 `.github/workflows/l2-launch-r0.yml`：固定本PR HEAD的双Python离线专项与证据上传。原工作流、锁文件和正式V1均不修改。

## 四件不同的事

1. `202`：tenant/idempotency/完整请求意图和outbox已经提交，返回原 `audit_id` 和独立 `run_id`；不是诊断完成。队列失败仍为CREATED/PENDING_DISPATCH，可恢复派发；存储失败503，没有假引用。
2. `AuditRun.REVIEW_REQUIRED`：执行产物等待审核；不等于 `ReportVersion.APPROVED`，不等于可以读报告。
3. 获准报告：当前原始报告hash/版号、真实ReviewDecision、Owner ShareGrant、当前收方token/subject/audience、源许可及撤销必须全部通过。R0仅合成演示这些端口；实际前台仍NOT_AVAILABLE。
4. VF咨询：HANDOFF_REQUESTED/WAITING_ACK直到VF权威存储后独立签名收据；QUALIFIED_BY_HUMAN另需商业人员确认。任何阶段都不自动升级E2/E3、报价或客户批准。

## 原 AuditRun 与必要 UI 状态

这里只建议状态信息，不决定VF页面或框架。`presentation.state` 属于候选展示层，不写回原AuditRun；不造COMPLETE，也不伪造百分比。

下表是基础内部摘要；VF-B客户状态以[三维兼容矩阵](VF-B-COMPATIBILITY.md)及 `VFStatus` 为准，不能把REVIEW_PENDING直接映射completed。免费“免留资”仍有独立身份/会话与许可约束，不代表匿名公共分享。

| 原V1状态 | 候选UI状态 | 展示约束 |
| --- | --- | --- |
| CREATED / POLICY_CHECK / QUEUED | PENDING | 已接收/待派发，尚无诊断结论 |
| FETCHING / EVIDENCE_READY / RULED | IN_PROGRESS | 仅描述实际阶段，progress_percent=null |
| DRAFT_READY / REVIEW_REQUIRED | REVIEW_PENDING | 不提供未批准报告下载 |
| POLICY_BLOCKED / ACCESS_BLOCKED | BLOCKED | 许可/访问受阻，不认定网站有问题 |
| INSUFFICIENT_EVIDENCE / MODEL_INVALID | UNKNOWN | 观察不足/无可用模型输出，不补造问题 |
| FAILED | FAILED | 安全错误与有界重试提示 |
| CANCELLED | CANCELLED | 不再读报告/旧链接 |
| 服务未获准或未实现 | NOT_AVAILABLE | submit_enabled=false，不发扫描请求，不展示静态冒充实时 |

零采证可形成“未知范围”投影示例，但不能声明有据网站问题。全站分母保持null；只报告授权页数与实际观察页数。A建议表达有据观察/UNKNOWN，B表达建议与局限，均含中英文及citation_ids；这是待Owner确认的语义，不是营销A/B实验。

## 保持的边界

`contracts/v1/**`、Guard、原角色/审核/分享逻辑、浏览器和Worker租约原样保留。原 `SourceAccess` 仍仅支持L0/L1；即使L2许可结构合法，fixture创建L2任务也明确503/L2_BRIDGE_NOT_AVAILABLE，不能把原L1采集权威冒充L2。L2报告示例仅验证未来消费契约。

原 `SyntheticIntake` 依赖进程内 `_rows`，重启后丢失；原PG Brief持久不等于持久VF接单。其BOUNDED_SYNTHETIC_INTERNAL_ONLY回执不能接入真实VF收据口。现有VF保存后201属于VF线索主权，不是本合同签名收据。

详见 [兼容ADR及待裁决项](ADR-001.md)、[权限/同意矩阵](PERMISSIONS.md)、[给VF Agent的字段清单](VF-AGENT.md)、[数据/运行/成本与威胁/R1测试计划](ARCHITECTURE.md)。原PR141仍HOLD，本分支不复制其CTA代码；#145 UAT进程、容器、端口与数据不操作。

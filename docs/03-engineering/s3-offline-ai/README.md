# S3 离线采购解释侧车（A15–A19）

授权：[Issue136](https://github.com/gloweaseco-leo/VRAE/issues/136)、[Owner134](https://github.com/gloweaseco-leo/VRAE/issues/134)。执行前 main 回读为 `6a15ab4514d24c60b4d03d4ec795f6e3bcd435c3`；独立 worktree/branch `codex1/s3-offline-ai`。PR133 归档 HOLD、未合并的 PR135 均不复制。本增量没有真实 Provider、密钥、网络模型、付费或客户数据，也不部署/合并。

## 接口与权威

`vrae.intelligence.s3.prepare_context` 接收原 EvidencePack、NativeSource、S2 projection、独立 BuyerCandidatePins 与 CompletionPins。重放原 C1 diagnose/source_chain、FindingPackage、Guard 和 S2 buyer candidate；绑定同 tenant/request/run/job、pack、诊断、报告 content_hash、行业/来源/规则/模板版本。上下文只由重放工厂产生；哈希/dataclass **不提供签名或当前任务权限**。C3 接入时仍须持有原 signed/current-task 授权，本次不修改它。

CompletionPins 要求原 lease 精确 30 秒、COMMIT 时间处于原租约内、模型任务当前时间已越过 lease 截止且授权未过期；分派前、返回后和读取时再次校验。只接受 `OFFLINE_SYNTHETIC` 来源。它是原 Worker 事务之外的独立 asyncio task（模型等待 1–1000ms，原 gateway 输出上限 2048 合成 UTF-8 字节），不是新增 Worker、持久队列或租约续期。真实 APP202/PG/Worker 后置接线留给已获授权的后续整机集成；演练中的 request/job 和时钟明确为合成组件值。

模型等待及候选校验共用5秒发布截止，超过后不发布部分 claims；在每个 claim 前后让出事件循环并响应取消。原 Guard 的单次同步重放是不可中断的原调用，发布截止是结果截止，不能宣称OS硬实时杀进程或CPU抢占。原输入/事实/claim 数均有界；这不占用或延长 Worker 租约。

原 ModelGateway/FixtureProvider 保持不变：只传原字段白名单，原文、URL、身份、HTML 都不发送；工业上下文映射仅本地保存。fixture 是预编程的目录选择，**不声称已完成开放式跨页 AI 语义理解**。默认 NO_MODEL 合法；原确定性报告的内容和 hash 不因成功、拒绝、超时或取消而改变。

模型 JSON 仅允许 `version/context_ref/claims`；每条 claim 仅允许 `kind/task/refs/counter_refs/template`（代码内 JSON Schema），最多8条、每组最多12个引用。拒绝重复 JSON 字段、非有限数、超长输出、未知字段/引用/版本、自述批准、工具动作、任意自由事实文本和伪证书/损失文本。无工具注册、无权限动作通道。

| 输出类别 | 校验与展示 |
| --- | --- |
| OBJECTIVE_SOURCE_FACT | 仅原 Guard 目录中的字面陈述，逐条构造原 AIInterpretation/binding/Guard 并重放；保存可重放 bundle；不是认证、工程适配或新 Finding |
| BUYER_HYPOTHESIS | 两个同产品锚点、不同来源页的已重放 S2 卡；有限跨页复核模板，始终 HUMAN_REVIEW_REQUIRED |
| MISSING_INFORMATION | 保留 UNKNOWN/NOT_APPLICABLE/ACCESS_BLOCKED，未访问或不适用不改为网站缺陷 |
| CONTRADICTION | 只引用原已重放的配置标量冲突，并保留完整原反证集；不把情景推为实际需求或设备不适用 |
| IMPROVEMENT_OPPORTUNITY | 来源 URL、资料责任、版本/工况材料、验收/顺序及标准候选/定制待审；报价、工期和服务目录确认保持 UNKNOWN |

全部结果是私有人工审阅候选：`native_fact_admission=NONE`、`shareable=false`、`is_report=false`，不创建 ReportVersion/Guard 权威/客户许可。网关原 AIInterpretation 仍为 NOT_RUN；只有窄字面证明 bundle 使用原 VALIDATED 形状，Guard 的 semantic_approval 仍 false。五维 Markdown 显示来源范围、待核、未知和下一步问题，不取代原22页报告或 Controlled 审核。

## 费用、重放与恢复

沿用原 Ledger 的预算预留、幂等、UNKNOWN 隔离和可信最新 checkpoint 恢复；同 operation 同输入返回缓存结果，改输入或并发重复拒绝；同 held Ledger/恢复 checkpoint 不再分派相同原 request。单 session 最多16项。缓存为服务本地，不冒充持久 PG 幂等库；集成必须持续持有/恢复原 Ledger，不能每次重建账本来绕过重放保护。

原合成 UsageRecord 单独保存，UTF-8 字节不是实际 tokenizer；演练费率仅为合成 ESTIMATED，不是供应商账单。真实模型 UsageRecord 使用独立 ID，amount/tokens/currency 为 null、cost_status=UNKNOWN，未知不记0。`real_model_calls=0` 是外呼计数，不是未知费用已结算为零。任何异常不修补成免费成功，也不重试原 Worker。

## 复现与验收范围

```powershell
python -m pytest -q tests/intelligence/s3_offline_cases.py
python -m integration.s3_offline.demo --output integration/s3_offline/.runtime/demo
```

演练逐例产生同一 pack/report 的 NO_MODEL 与 fixture 前后五维片段，分别覆盖技术原文与跨页复核、未知/不适用、伪引用/伪认证/损失、恶意模型/网站提示、超时/取消/异常回退。每例用隔离的原合成账本，不能拼接为真实同任务整机或实际成本试验。独立 Gold=0，precision/improvement 为 null、NOT_EVALUABLE，不用 fixture 一致率冒充质量提升。

新增路径限定 S3 workflow 只运行3.13的专项及原 Gateway/Guard/Evidence/候选安全依赖和离线演练；没有改任何既有 workflow、保护基线、EvidencePack、SQL/RLS、PG、Worker或30秒租约。新测试为显式 `s3_offline_cases.py`，不改变原默认2564清单。原全局门禁自然运行，不因本测试通过而被替代。

工程候选状态仅为 `S3_OFFLINE_AI_ENGINEERING_PASS_PROVIDER_PENDING`，需 Owner 对实际 SHA/CI 独立审核；不是 S3 真实 Provider、生产、真实人审或外部交付 PASS。真实供应商、用途/地区、费率、密钥和客户内容传输必须另获 Owner GO。

回滚：撤去本增量的新 S3 包、演练/显式测试和路径限定 workflow；原代码、数据库、账本格式及报告均未迁移，无数据回滚。CI、源码 SHA、拒绝与费用证据在审核提交时补充。

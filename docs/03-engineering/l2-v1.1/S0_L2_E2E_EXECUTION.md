# VRAE V1.1｜S0 真实工业 L2 整机 Beta 执行纲领与三 Codex 分工

> 状态：OWNER AUTHORIZED S0 ONLY，2026-11-16。
> 阶段目标：A01–A04，真实 P40/V25 合成工业站点从新 APP202 到原 Worker/PG16 COMMIT、C1/C2原生报告、Controlled 审阅、C3内部 RebuildBrief、重启与 Chrome 操作；**不是** S2 五维全部规则、S3 真实 AI、S4 商业灯塔或正式生产放行。
> 最新 Owner accepted main：a9604f570528e599a0b8215a8957208d76e47b89（PR114已FINAL PASS合并）。工作分支 PR112：codex3/l2-runtime-integration；交接时远端099b8a9831382cf6cd009f66a22c4a8a0838ec93、本地6874c1f4c8fc3bd0e5f3aaf065618855fc9a9f1b，后者未推送、未验证托管CI。

## 1. 单一可交付结果

内部操作员在一个实际启动的受限环境，从原 APP202 发起新工业 P40/V25 任务，观察原独立 Worker 在合法30秒租约内提交真正八页工业 EvidencePack；在原唯一签名 SSR 操作同新任务的 C1 原生采购深诊、C2 受控报告/蓝图及逐项审核，并将当前审核与原任务授权同时绑定到 C3 PG16 内部 Brief COMMIT。重启后保持同任务同报告/审核/Brief原件可回读，并通过 Chrome/越权/撤权/超时/旧版本拒绝等验收。

没有实际同一新任务提交不能标 FINAL PASS；没有可操作报告/审核/Brief也不能以任务 DONE 或 UI 截图代替。S0 的客户、来源、账户、模型均为合成/离线测试，不接真实客户/付费模型/外发。

## 2. 执行顺序、Owner 依赖释放

1. **Owner 已完成 PR114**：独立核对 ae81f0c9b739bac0392a4e3d66e27c9c89e6bf01 的36/36自然 CI及精确B5A冻结，合并 main a9604f570528e599a0b8215a8957208d76e47b89。保持全部旧RED与四个新增真实反例。
2. **C3 第一顺位**：原PR112 worktree与分支正常 merge该新 accepted main；禁止复制兄弟 Draft、force/rebase、更改老证据或旧源 pin。核对 merge-tree/父提交和现有C1/C2原生接口、权限、Worker租约、唯一SSR；仅修原PR112自己的胶水、受控存储和测试。
3. **C3 执行整机**：双Python各独立新 run。先以原 APP202 + Worker 验证真实 lease COMMIT；如第一次 RED，沿新源码与真实因果定位本轮根因，允许 C3 自治修自己范围内的接口和测试，不得无改动刷同一失败。安全、真实来源/跨模块权威改变才升Owner。
4. **C2/C1 贴身支持**：C3遇到可复现真正跨模块接口问题，直接提供精确SHA、函数、源引用、预期/实际、脱敏根因和最小补丁建议给对应负责人。没有故障时不主动修改C1/C2已验收主干或新开并行系统。
5. **Owner 收口**：审查同一新任务原生证据链、双语言版本/PG/Chrome/清理及全部自然CI，合格即 PR112 FINAL PASS并合并；否则只对实质性阻断做最小裁决。

## 3. 三人明确成果归属

| 负责人 | S0 责任 | 允许自主动作 | 交付/停止线 |
| --- | --- | --- | --- |
| **Codex3（唯一整机 DRI）** | 负责 PR112 实际启动器/APP/独立Worker/签名Reader/C1/C2/同SSR/Brief 的完整操作闭环、PG跨库一致性、Chrome、重启、原资源清理和自然CI | 在原 PR112 独立 worktree 自主修新增任务接线、状态/请求/UI、持久化/夹具，正常merge已验收main，定向测试并证明后push新HEAD | 必须证明原30秒 Worker合法 COMMIT、同run来源/版本链，C2当前版本和原任务双权威持有到Brief提交；跨库并非同一原子事务；未经签收不合并/部署；不能复制未验收兄弟代码 |
| **Codex1（性能/Guard接口后援）** | PR114已完，负责源性能接口、EvidencePack实例校验、原 C1 工业诊断/Guard真实阻断分析 | 只读接口支持；只有 C3 给出精确可复现C1/Guard缺陷时，在独立最小分支修复并真实回归，交Owner独立批准 | 不主动改 PR114 已审 pack blob、30秒租约、提交前重放、旧权限、SQL和守卫；不创造第二份源引擎 |
| **Codex2（C2报告/审阅权威接口后援）** | 负责 NATIVE-v1 中 NativeTask/NativeSource/current_report 及报告/蓝图/逐项审核版本/权限的接口解释与定位，审看 C3 双权威是否正确使用 | 只读 support；遇到可复现C2问题才在单独最小 PR 修复，保持单 SSR/ReportVersion/Controlled，不重复生成样例/报告 | 报告/HTML/display SHA、诊断 SHA、版本身份不可互换；C2 current_report 不替代 M1 当前签名任务权威；不可把受控审核当真人审批 |
| **Owner（唯一最终裁决）** | 产品价值、守卫边界、跨组件版本/权限、真实证据/CI审计和最终合并 | 独立核查原生证据和当前 GitHub 主干；仅重大权威边界裁决 | 不为普通 pytest/启动/页面错误制造多次人工审批；不以工程测试数替代业务可操作性 |

C3是唯一集成责任人；C1/C2在无可复现接口故障时保持待命，不另开竞品模块。此前C2已经发布的接口答复 PR112#issuecomment-6920463208 继续有效。

## 4. C3 必须亲自证明的执行清单

### S0-M1｜新任务实际受理与提交

- 本轮独立干净 PG16/APP/Worker/SSR，记录 exact main/PR112 head/tree SHA、原锁定镜像/版本及启动/关闭日志；无第二套SSR。
- Operator真实提交合成工业新任务，APP事务成功返回202且可查同一request_id/run_id/job_id；不复用Demo/旧M1 report。
- 原Worker取得合法租约、真实读取8页 P40/V25来源（各 URL/HTTP/body/content hash）、生成 EvidencePack并经过完整Guard和强制提交前重放，在原30秒 lease 内完成DB COMMIT；记录真实lease期限与commit时间。
- 独立签名Reader在当前任务授权下读取该真实pack/来源（tenant/request/run/job/event/政策/行业配置），原生 C1 diagnose + verify 重放通过；错租户、错run、错pack、撤权/到期均拒绝。
- 产生错误不可假成TEST_ONLY_DONE/M1 preview成功，失败保存原日志和SQL状态、安全清理证据。

### S0-M2｜同源 L2 报告与受控审核

- C2接收来自真实 M1 Reader 的 NativeTask(tenant/request/run/job/event/source/pack/industry/diagnosis/source_bundle_sha256/首次created_at)；独立重新验证C1原生输入、不能以浏览器字段重造。
- DeepReport显示真实19项工业评估与五段采购任务、引用及UNKNOWN；生成可执行七包蓝图（如实际规则/适用性导致数量变化，应解释而非凑数）。完整payload SHA、ReportVersion.content_hash、PDF/HTML/display SHA分别正确绑定。
- 仅在既有一份签名 SSR 内由 Controlled Reviewer逐项 REVIEW/REJECT/REQUEST_CHANGES，保留原证据、版本回执、审阅原因、时间与撤销；重复提交/错actor/旧版本/CSRF/过期均拒绝。无正式人审和真实外发。

### S0-M3｜内部 Brief、跨存储一致性与Chrome

- C3在同一次真实任务的当前 M1 task reader及 C2 current_report 有效锁内创建内部RebuildBrief并真正 PG COMMIT；不得借用 Worker lease 给审核授权续期，使用原二者有效期最小值。
- **跨存储事务设计必须可证伪**：C2 审核账本与 C3 PG 是两个权威边界，不保证单一原子事务。采用服务端快照/版本CAS、提交前重验、持久引用hash、提交后当前版读回和撤权可见性判定。出现提交期间失效、半提交、重试冲突时必须 fail-closed 或进入显式可补偿中间态，不得把旧Brief展示成当前有效。
- Chrome 从真实任务列表→L2原生报告→证据→蓝图→审核→内部Brief及A4打印，验证正向操作和错用户/租户/版本/nonce/撤权/超时/当前任务切换的拒绝。
- 服务或PG16按场景重启：沿原真实run/report/version/review/brief_refs逐字节或规范哈希回读。PG marker-only不能替代。
- 保留全部源SHA、CI/日志/JUnit/Chrome截图、实际时间、权限与资源ID；仅针对本次创建并记录的容器/匿名卷ID清理；旧未识别卷UNKNOWN，绝不global-prune。

## 5. S0 接受/拒绝门槛

| 核验 | 接受条件 | 明确不接受 |
| --- | --- | --- |
| 唯一真实任务 | APP202经事务→Worker租约COMMIT→同八页包 | Detached/静态回放、旧M1任务、单纯schema成功 |
| 30秒 | 原 lease 内合法提交，必需 replay保留 | 把任务拆成绕过原lease、延长时间、人工预写DONE |
| 原生业务 | Guard完整verify、C1评估→C2同报告/蓝图 | 将MP25/旧报告改标题当新工业证据 |
| 版本审核 | Controlled逐项审核及原双hash/report版本当前可见 | 仅测试保存函数、错版本回执可用 |
| Brief | 原task+C2双权威至PG COMMIT，失效/撤权并发阻断 | 用 DTO/哈希假装授权、不同事务冒充原子性 |
| 可操作 | 原单 SSR Chrome从受理到内部Brief/打印，重启原件同refs回读 | 截图/mock、marker重启和分离测试拼接 |
| 可重现 | 独立 Python3.11/3.13与真实PG16，原始失败与全量自然CI真实统计、完整清理 | 改旧断言、跳过 RED、无原因的重跑刷绿 |
| 商业可读 | 有据采购阻碍/买方与企业待确认/措施/责任/依赖/验收/未知 | 虚构工时、费用、咨询投递、工程安全认证或E2/E3 |

**S0 STATUS**：在PR112新HEAD实际 E2E & Owner final acceptance 之前为 PARTIAL/BLOCKED；PR114合并仅解除性能代码依赖，不代表可以立刻宣称P40提交已通过。若发生涉及受保护权限/真实外网/模型费用/真实数据/正式人审的必要动作，则STOP该动作向Owner提出具体最小裁决；无关功能继续自治。

## 6. 交付形式与阶段后续

C3只向原 PR112 提交最终工作与真实回执（单一PR）；C1/C2仅在确需接口修复时提交独立可复核最小PR。S0成功后将 exact SHA、独立复现命令、证据摘要和当前问题状态记入主干，交 S1 完成完整设计矩阵，S2规则/Gold，S3真实AI，S4商业。不得将S0成功自动升级为已完成S2/S3/S4或可对外商用。

与[产品补强纲领](L2_V1.1_CHARTER_SUPPLEMENT.md)、[L2 27项验收矩阵](L2_V1.1_ACCEPTANCE_MATRIX.md)共同组成 V1.1 增量附件。

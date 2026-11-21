# 产品证据归属与五维事实交付修复

问题：菜单分类文字被当成当前产品的 DESCRIPTION，模型据此推断规格或用途冲突；VF 现有预览只展示 AI claims，使已经生成的规则事实没有进入客户视图。

## VRAE 修改

仅为新的自动诊断使用 l2-industrial-1.0.4 / ra2b6-1.0.4 / ra2c3-1.0.4。旧版本仍按原逻辑重放，原始 Evidence、诊断、AI 回执及报告版本不改写。

- 名称、规格和描述限定于可归属的静态产品区域。排除导航、菜单、关联产品和链接段落；遇到其他标题，不把其下内容归入当前产品。
- 页面标题不可靠时，只接受支持的规格表内唯一且明确的 Item / Product name 名称字段，证据范围收紧至同一张表。无法唯一归属则 UNKNOWN，不猜测产品身份。
- 引用保留原位置、原文和哈希；新增 product_scope_ref 只是静态区域绑定，product_identity_verified 始终为 false。
- Qwen 使用 qwen-evidence-buyer-1.3.0。来源分组改为产品区域，仍只发送限长、脱敏字段；同一条分析跨产品区域引用会被拒绝。差异文字本身不能证明规格冲突。
- 保留原 Guard、人工审核边界、费用上限、调用次数及语言约束；不增加浏览器步骤或模型重试。
- 增量009只让原 committed_input 端口为新版本返回原申请语言，并在迁移结束复位数据库角色。008及旧来源保持不变；原初始化器按函数定义检查后追加009。

## VF 可直接采用的交付代码

文件位于 integration/authorized_targets/consumer：

- reference.mjs：已有契约的严格消费与引用校验，补充规则原因、模型失败阶段及新版本跨产品引用拒绝。
- vf-preview-adapter.mjs：沿用 VF 的 state / pages / insights 基础形状，增加 buyerTasks、analysisOutcome、analysisText、modelFailureStage、captureSummary、pageScope。
- vf-preview-adapter.d.mts：相应 TypeScript 声明。
- reference.test.mjs：五维事实独立于 AI、引用绑定、候选链接折叠、跨产品引用拒绝及临时读取错误边界。

### VF 最小接入步骤

1. 将上述三个运行/声明文件一起放入 VF 的服务端 lib 下，保持 reference.mjs 的相对导入。既有 mTLS、源码SHA、媒体类型、no-store、会话与CSRF校验继续先执行；结果GET继续保留已修复的20秒预算。
2. VRAE 结果读取完成后调用 projectPreviewResult(body, status, auditRef, language)。使用当前界面的 zh/en；不新增客户授权或操作。
3. BFF 返回完整的适配结果；ResponseData、前端状态及 setResult 必须保留 buyerTasks 等新字段。原 setResult({state,pages,insights}) 会再次丢弃五维事实。
4. 五维主体遍历 buyerTasks，逐项显示 observations 的 statusText、text、sources、reason；AI 解释单独显示对应 insights。无 AI 解释不能代替该维度的规则事实。UNKNOWN 要展示本次未核实原因，不能翻译为网站缺陷。
5. 已访问页面使用 pages 或 pageScope.visited。未访问链接只在 pageScope.candidates 折叠区展示，不与已访问页面合并成报告主体。analysisOutcome / analysisText / modelFailureStage 用于区分采集失败、证据不足及模型失败。

本 PR 不修改 VF 仓库、页面或发布配置；这些接入步骤需要 VF 团队实施。本仓库的接收适配通过不等于 VF 页面已经部署完成。

## 真实留存证据验证

frozen-replay.json 记录只读验证：

- 绑定到本次 PDF 对应的已提交工件，不按“最新任务”猜测。
- 原版本可完整重放，且共25份历史工件全部按各自原版本重放通过。
- 同一真实网页使用新提取器时，两个误归属的菜单描述消失，原产品规格保留，INFO-01仍为有限PASS；新候选模型输入包含同一产品表格的9个必要值。
- 原真实 DTO 经五维适配，得到5个维度、4条PASS及16条UNKNOWN；6个已访问页面与71个未访问候选链接分开展示。
- 原工件、AI回执与共享模型账本核对不变。未重新采集、未新增真实模型调用。

这是对真实留存来源的反事实修复验证，不是新签发的诊断、报告或真实Qwen回执。没有将旧报告伪装为修复后报告；修复只对部署后的新任务使用新版本。

正反回归和隔离PG检查见 validation.json。PG检查使用独立 network-none 实例、合成网站及协议假模型，不挂载生产数据、凭据或共享模型账本。

## 发布与验收边界

合并部署时由原初始化器追加009，沿用原运行实例、身份、SSRF、robots、隔离、采集上限和费用许可。没有扩充五维任务或16条规则，也不加入行业专属参数要求。

Owner 验收需区分：VRAE新任务确实使用1.0.4；VF已经接入五维主体；新AI分析的名称、规格和描述归属正确。现有旧报告及原始回执保留，不能据本次只读验证宣称它们已被修订或重新通过人工审核。

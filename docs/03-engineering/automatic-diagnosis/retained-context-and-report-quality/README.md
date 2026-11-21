# 已采集证据利用与报告建议边界

本轮修复已有留存网页未被规则消费、列出参数被推断成库存，以及报告重复罗列的问题。沿用五维16规则、现有Collector、PG、Worker、Guard和报告读接口；不增加采集页数、模型调用次数或客户操作。

## VRAE

新自动任务使用 l2-industrial-1.0.5 / ra2b6-1.0.5 / ra2c3-1.0.5。旧版本继续重放，原始证据与报告不改写。

- 新版本统一规则消费时的About/Contact角色别名，识别aboutus、contacts及文件形式，保留原采集manifest和旧角色函数。
- 闭合、安全的联系链接按元素验证。其他位置的嵌套链接不再清空这些链接；嵌套链接自身、未闭合、隐藏、表单内、跨站及含查询参数链接仍不能作为联系提示。静态路径判断必须绑定同一pack的目标实际响应，未访问不推断可达，404/410不能变成PASS。
- TRUST消费已捕获HOME/ABOUT/CONTACT区域，忽略可隔离的脚本等非内容节点，保留介绍路径正文和静态联系观察。组织名称仍需明确标注，整体前置条件或身份未核实时维持UNKNOWN，不认证法定主体、资质或送达。
- customer_presentation增加有引用索引的context_facts。INFO产品名称/参数、SEO标题/描述、TRUST自述上下文、CTA静态链接可作为部分来源观察显示；is_rule_pass始终为false，原Observation状态保留。
- UNKNOWN附带限制分类：未实施、适用关系未建立、需人工核对、部分证据、可见性/送达未核实、来源不足或解析不支持。它们不是网站缺陷数量。
- 模型按原每区域11个值、最多2区域的上限选择输入，去掉重复的Item名称，保留完整标签值对；有空间时纳入Bond/Usage，不扩大token或调用上限。
- qwen-evidence-buyer-1.4.0及输出策略1.2.0明确列出选项不等于标准现货。窄校验拒绝没有引用来源支持的库存、现货、标准规格、交期、MOQ、产能或营销意图陈述；中性待确认问题可保留。这不是完整语义审批，原guard_semantic_approval=false和人工审核边界不变。
- 增量010只为新版本扩展原申请语言返回，沿用原初始化器追加并RESET ROLE，不改008/009或旧数据。

## VF接入材料

consumer目录新增report-view.mjs、report-print.css，并更新原reference及vf-preview-adapter和类型声明。没有修改VF仓库或发布配置。

1. 同步reference.mjs、report-view.mjs、vf-preview-adapter.mjs及其声明文件，保持相对导入。既有mTLS、来源SHA、媒体类型、会话、CSRF和结果GET20秒预算继续先执行。
2. BFF和前端状态保留完整reportView。五维展示使用reportView.tasks：先显示contextFacts作为“来源观察”，再显示已判定规则；UNKNOWN使用limit.text解释，保留原状态。不得把部分来源观察转成PASS或网站评分。
3. reportView仅合并同规则、同结果和同已访问起终点的重复路径；observationIds和sourcePointers完整保留。原buyerTasks仍有全部记录。聚合的来源观察保留bindings及全部来源页，产品范围不同的字段不合并。
4. 使用reportView的访问/失败/候选数量与事实摘要，按需展开原记录。候选链接不进入报告主体，未知数量不作为缺陷数量。
5. 在现有页面加载report-print.css，为按钮、表单、示例及营销区添加data-vrae-print="omit"。打印保留候选数量但隐藏URL长清单；来源和审核边界保留。正文2–3页是VF排版验收目标，尚未冒称浏览器/PDF验收通过。

无需建立新PDF服务或改变现有报告审批流程。VF应用类型检查、浏览器及打印验收由VF团队实施。

## 验证

frozen-replay.json绑定本次PDF对应的真实已提交工件，只读比较新旧规则。原CTA-02为UNKNOWN，新版本可用实际静态href及同次HTTP200证明有限路径PASS。TRUST纳入3页、保留2段介绍路径正文及5个联系链接观察，整体仍UNKNOWN；首页标题和描述独立保留。

同一产品输入为11个值，去掉重复Item并保留Bond/Usage。旧报告的无来源商业推断会被新策略拒绝。消费代码验证22条原观察聚合为21个展示组，五维保留，候选71条不进入打印清单。

这是对真实留存来源的反事实验证，不是新提交任务、正式报告或新模型回执。26份历史工件按原版本全部重放；原工件、AI回执及共享模型账本核对不变。没有重新抓取网站或新增真实模型调用。

正反回归、独立network-none PG及静态检查见validation.json和isolated-pg.json。等待Owner独立验收；本轮未合并部署。

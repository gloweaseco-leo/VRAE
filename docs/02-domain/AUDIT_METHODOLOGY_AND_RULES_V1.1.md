# VRAE 诊断方法论、证据契约与规则库 V1.1

> 状态：规则规格（非已实现算法、非模型或线上诊断结果），2026-11-10。

## 1. 一切以买家任务而不是 SEO 分数为中心

诊断问题顺序：Discover（找得到）→ Understand（看得懂）→ Trust（信得过）→ Inquire（能询盘）→ Search & Technical（基础可被发现/可用）。每一项客观判断必须指出被检查的页面、范围与复核方式；所有推断必须标成 Hypothesis。

## 2. 正确的信息层级

| 类型 | 含义 | 来源要求 | 对外展示 |
| --- | --- | --- | --- |
| SourceSnapshot | 本次下载/浏览器观察的网页快照及时间 | 原 URL、最终 URL、哈希、捕获方式、访问政策 | 不直接共享整站镜像 |
| Evidence | 可被复查的特定页面事实 | snapshot_id、DOM locator/截图框/片段、sha256 | 必要且获准的证据 |
| Observation | 规则从 Evidence 推出的客观事实 | rule_id+version、evidence_ids、覆盖范围 | 经审核可展示 |
| Hypothesis | 可能影响买家行为的商业推断 | observation_id、推断边界 | 必须明确标识“可能” |
| Recommendation | 具体、可验收的改进建议 | 目标买家任务、改进动作、服务适配性 | 经过人工批准 |
| Unknown | 未检查、页面拒绝、数据不足、需属主后台证明 | 缺口/失败码 | 不能自动翻译成网站缺陷 |

模型不能制造虚构的证书、公司规模、客户、转化率或事实，不能自己决定客户是否符合 E3。

## 3. 首批 16 条候选规则

| ID | 检查点 | 可接受事实 | 防误判规则 |
| --- | --- | --- | --- |
| DISC-01 | 首页导航与产品分类 | 有实际可访问产品分类链接 | 没抓到不等于不存在 |
| DISC-02 | 分类→代表产品详情 | 实测或只读 GET 路径 | 不能测试真实提交和购买 |
| DISC-03 | 行业/应用入口 | 观察到的应用页和指向链接 | 非所有行业必需 |
| INFO-01 | 产品名称和基础参数 | 规格标签、数值及来源页 | 不确认规格真实性或适配性 |
| INFO-02 | 技术购买所需材料 | 应用/行业包要求的字段 | 行业包未配置时 UNKNOWN |
| INFO-03 | 英文信息可理解性 | 严重文本缺漏/语言混用等候选 | AI 判断需人工核实 |
| TRUST-01 | 企业主体可见性 | 公司介绍与公开联系路径 | 无证书不代表缺资质 |
| TRUST-02 | 证明材料上下文 | 案例/证书/工厂资料的公开描述 | 不能认证真假 |
| TRUST-03 | 企业名称/联系信息一致性 | 已观察到的公开矛盾候选 | 不强行合并同名法人 |
| CTA-01 | Contact / RFQ 可达性 | 可见 CTA 和真实 href | 按钮出现≠消息送达 |
| CTA-02 | 产品上下文询盘 | 代表产品→联系页的实际只读旅程 | 不发送表单 |
| CTA-03 | 移动端基础呈现 | 390px 下可见导航/溢出等 | 不等于所有设备或无障碍全测 |
| SEO-01 | robots/sitemap/canonical/title | 当前实测响应和标签 | 不代表 Google 实际收录 |
| SEO-02 | 可抓取产品信息 | SSR HTML、可见 DOM、可抓取锚点 | JS 渲染不是自动 SEO FAIL |
| TECH-01 | URL 响应与跳转 | 2xx/3xx/403/404 等证据 | 403/反爬不等于网站业务差 |
| TECH-02 | 图片和基础可访问性 | 关键图资源加载/标题结构候选 | 不宣称 WCAG 合规或全面性能 |

规则引擎需支持 PASS、FAIL_WITH_EVIDENCE、UNKNOWN、NOT_APPLICABLE、ACCESS_BLOCKED；检测项不能仅因缺数据自动 FAIL。规则定义必须带 rule_version、applicability、evidence_requirements、method、false_positive_risks 和 benchmark fixture。

## 4. 代表性页面抽样

不按照网站链接第一个出现顺序抓取，而是优先取得：Home、Catalog、Category、ProductDetail、Application/Solution、About/Proof、Contact；根据行业和限额选最有代表性的路径。L0 建议 3–5 页、L1 最多 8 页，先静态 HTTP 后有限浏览器（必要时）。每份报告都记录观察覆盖率，未覆盖页面不进入否定性判断。

## 5. 确定性优先 + 有证据 AI 解释

1. 采集网关验证 URL/策略并取得有版本的快照。
2. 提取器生成 PageEvidence（不让 AI 自由编造）。
3. Rule Engine 匹配行业包并输出 Observation/UNKNOWN。
4. AI Gateway 仅接收经脱敏、限长、结构化的 Observation 和证据引用；输出 Hypothesis、Recommendation、MissingInformation。
5. Schema 校验结构、引用 ID 存在性与对证据内容的语义支持。
6. Reviewer 可逐条 approve/reject/revise；修订生成新的 report_version。**不可改原始 Evidence 来迎合报告。**

AI 失败自动回退确定性事实并进入人工处理，不是假装“已完成智能诊断”。

## 6. 行业包扩展

IndustryPack 是版本化配置，不将行业字段写死到 Account 或 Product 主表。候选内容：
- industry_id + version、买家画像、产品目录模型和代表页面选择；
- critical_attributes[]，如阀门的压力等级/材质、机械设备的容量/功率等；
- applicability_rules[]、证据需要、行业术语、风险语言与业务目标；
- 没有证据支持时不推断必填参数缺失。

第一阶段仅将工业设备与工业零部件作为验证方向；尚未做行业覆盖率实测。

## 7. L1 报告最小合同

- 检查对象、时间、公开观察范围/禁区与数据局限；
- 最多 3 个最重要的已验证问题，逐项绑定 Rule+Evidence；
- 买家任务受影响的**假设**，不得声称真实成交损失；
- 可执行改进建议、适用 VEYFRONT 标准服务还是定制评估；
- 15 分钟沟通 / 企业微信 / Rebuild 咨询入口（不会自动联络客户）；
- 所有内容绑定审核人、审批时间、报告哈希及分享授权。

如果只有 1 个可确认问题，就只展示 1 个；如果没有可靠问题，就输出 INSUFFICIENT_EVIDENCE 或报告为空并结束，不凑数。

## 8. 反例测试

- 首页未发现产品但站内动态分类正常 → UNKNOWN 或受限覆盖，不称“没有产品”。
- 产品存在规格说明书 PDF 但标签不同 → 不判缺参数。
- 网站有表单但无法验证投递 → 只能确认入口存在，不能说收不到询盘。
- 受 WAF 拦截的英文站 → ACCESS_BLOCKED，不断言技术质量差。
- AI 指向不存在的 evidence_id 或发明“流失 30% 买家” → 拒绝该模型输出。
- 抓取结果由 CDN 验证页组成 → 拒绝当真实业务页面。
- 同一旧站改版后重新审计 → 产生新的 Snapshot/Report，不覆盖历史。

## 9. 商业效果与质量指标分开

技术：规则精确率、可复核证据覆盖率、来源完整性、人工误报确认率；商务：L1 阅读后的真实互动、E2 询盘、经负责人确认的 E3、提案及毛利。测试样本量不足时只能报告已观察个案，不能宣称市场普适性。

详见 [产品纲领](../00-product/PRODUCT_CHARTER_V1.1.md) 和 [验收计划](../03-engineering/ROADMAP_AND_ACCEPTANCE_V1.1.md)。

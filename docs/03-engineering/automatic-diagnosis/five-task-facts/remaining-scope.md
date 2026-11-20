# #179 剩余范围与 V1.1 对齐

本文件补充原 P0-1/P0-2。产品定位、五维和 16 条规则不变，不修改 VF 仓库、页面或发布配置。
所有新提取行为仅在 `l2-industrial-1.0.2 / ra2b6-1.0.2 / ra2c3-1.0.2` 中生效；
旧版本仍按原逻辑重放。内部工业分析版本名不表示将客户报告升级为 L2，也不替代正式 L1 的人审。

## 核心权威校对

| 文件 | 本轮遵守的不变量 |
|---|---|
| [PRODUCT_CHARTER_V1.1](../../../00-product/PRODUCT_CHARTER_V1.1.md) | 证据驱动；不凑 3 个问题；L1 人工批准；不推导成交、营收或 E3 |
| [AUDIT_METHODOLOGY_AND_RULES_V1.1](../../../02-domain/AUDIT_METHODOLOGY_AND_RULES_V1.1.md) | 五维/16 规则；L1 最多 8 页；未知不当缺陷；CTA 可见性、消息送达分别核实 |
| [PRODUCT_AND_OPERATOR_JOURNEYS_V1.1](../../../02-domain/PRODUCT_AND_OPERATOR_JOURNEYS_V1.1.md) | VF 拥有客户页面；VRAE 拥有审核与诊断；客户仍只输网址并勾选一次授权 |
| [SYSTEM_AND_APPLICATION_V1.1](../../../01-architecture/SYSTEM_AND_APPLICATION_V1.1.md) | 原 PG/Worker/Collector/Qwen/Report 服务；不增加平台或跨库；AI 降级保留事实 |
| [DATA_ARCHITECTURE_V1.1](../../../01-architecture/DATA_ARCHITECTURE_V1.1.md) | 快照不可改；新规则版本重放；审批/分享绑定精确 ReportVersion；未知费用不归零 |

## P0-3：证据清单分组

原结果接口新增 `page_scope`，只投影当前已授权且已重放的工件：

- `visited_pages`：实际 FETCHED 页面，含 snapshot_ref、URL、观察时间、HTTP 状态及原请求角色。
- `failed_attempt_records`：未成功的记录及原原因；`http_response_observed=false` 不表示已向网站发出请求。
- `unvisited_candidates`：仅发现但未尝试的地址，明确 `is_defect=false`。
- `unknown_coverage`：角色/覆盖仍未知的原记录，不与未访问混为一类。

VF 主体先展示五维规则检查及实际访问页的引用。候选链接仅显示数量，清单折叠/按需展开，
标题应为“已发现、本次未访问”，不使用 UNKNOWN URL 清单充当诊断正文。
分页或截断不能改变 `capture_summary` 的计数。引用中的原 HTML 片段应按文本呈现。

## P1-1：最多 6 页的有界代表抽样

新自动任务在根签名的后台 delegation 允许时最多取 6 页；旧 4 页 delegation 继续限制为 4 页，
不会由网页请求或用户勾选扩大。旧计划不改写，新上限使用新的计划/授权。
部署时受信后台应通过现有 `enable_intake` 续发 6 页 delegation；无需客户额外操作。

选页使用 Home、Catalog/Category、Product、Contact、About、Application 的覆盖优先级，
识别 `contact.html`、`contact_us.html` 等常见 Contact 地址。排序使用新的辅助角色，
原 CaptureManifest 的角色映射、哈希和历史验证不变；辅助推测不是已验证的页面业务角色。
原 SSRF/DNS/robots/同源范围、请求超时、24 秒采集预算、30 秒原 Worker 租约、总字节预算均保持。
限额或 robots 造成不足 6 页时如实报告，不补造页面，不保证每站都能覆盖全部角色。

## P1-2/P1-3：通用静态产品来源与联系入口

新版本提取已保存字节中的唯一产品路径标题、嵌套文字、TH/TD 或 TD/TD 标签值表、DL、
以及明确 `标签: <span>值</span>` 的行；描述来自 main/article/明确主内容区。
同一包中非产品页重复出现的 H1 可作为公共布局标题排除；剩余标题仍不唯一则保持 UNKNOWN。
不会按客户域名、型号或阀门字段硬编码，不执行脚本、不 OCR 图片，也不将 PDF/未访问资料说成缺失。
脚本/模板/表单等排除区、显式隐藏区、重复属性或歧义结构不会提供正面参数判断。

INFO-01 的 PASS 仍要求名称和至少一项可靠标签值。只有名称/描述时，规则保持 UNKNOWN，
但原文本引用保留，便于补核。已核对的真实旧产品页字节现在能分离主标题和两段描述；
本次仍未可靠配对参数，因此没有伪造产品规格。

CTA-01 新增静态链接部分证据：`static_href_presence=OBSERVED`、`rendered_visibility=UNKNOWN`。
它不是 CTA-01 完整 PASS，不证明可见、目标响应、表单接收或询盘成功。
原 CTA-02 的只读路径验证保留，不提交任何表单。

## P2-1：可用文本锚点进入原 Qwen 链路

复用原 provider、模型、预算、调用幂等和 Guard；不新增第二条模型通道。
新版本允许对已经完整执行重放、且原字节定位验证通过的 INFO-01 名称/描述字面片段建立锚点，
即使 INFO-01 整体仍为 UNKNOWN。该行为只证明原文存在，不升级规则结果、不证明参数缺失。
对应来源 profile 由已验证 evaluator 版本选择；旧 Guard 模块及旧版本行为保持。
仍执行绑定引用、原字节范围、原包哈希、注入检查、输出 schema、真实供应商 usage 和语义需人审的原校验。

送往模型的内容仍为限长的脱敏结构化数据及引用 ID，不发送原 HTML、URL、联系人或原文。
新 profile 增加字面片段角色和原规则 UNKNOWN 标识，并要求有限、条件性的解释。
沿用原最多 2 项输出上限（落在本轮要求的 1–3 项范围内），无锚点仍拒绝派发；
费用未知、模型失败或验证拒绝不能伪装成真实 AI 完成。
测试中的 provider 替身不能作为新真实 Qwen 调用证据；本轮没有重试旧客户任务或新增付费调用。

## P2-2：复用正式报告、人审、版本与分享

已有通道无需重建：Report Service 端口 8443，
`GET /v1/report-authority/audits/{audit_ref}/report`。
使用原独立 REPORT mTLS/Bearer、媒体类型 `application/vnd.vrae.report+json; profile="vrae.report-authority.v1"`、
`X-Report-Profile: VERIFIED_HUMAN_CUSTOMER_REPORT` 及原会话/定向 ShareGrant。
不得把 `/diagnosis` 的未审预览直接改名为正式 L1。

内部流程仍是原 Reviewer/Owner 身份与真实验证 → 审阅精确版本 → 必要修订产生新版本 →
批准当前 content_hash/display_hash → 给当前接收者定向授权 → VF 读取。
VF 正式 L1 页面消费该响应中的 report、report_version、review_decision、display_hash，
且仅当 `formal_human_review=true`、`external_release=true` 且版本/审批匹配时展示为已审核报告。
Owner 内部签发不是额外的客户操作；不要求客户另行 DNS 核验、AI 同意或人工签名。

VF 的一页呈现从已批准内容中保留至多 3 个可信问题及其证据、影响假设、建议、复核方式，
没有可信问题时使用 INSUFFICIENT_EVIDENCE，不把 PASS 或 UNKNOWN 凑成缺陷。
引用与内容必须来自同一个被批准版本，不能混入另一次采集或未审 AI 候选。
Rebuild 咨询入口由 VF 连接现有咨询流程；点击不计入 E2/E3，也不由 VRAE 自动报价或联系客户。

已用新建受控 PG/DNS/TLS 环境运行原 report-api 与 verified-report 演练，
验证版本、审核、定向分享、修订后旧审核失效及撤权拒绝；该证据属于合成身份/来源的协议回归，
不是本轮客户报告已获人工批准。真实批准仍由真实 Reviewer 完成，页面由 VF 团队负责。

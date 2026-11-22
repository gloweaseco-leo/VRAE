# L2 客户交付实施计划 R1–R3

**目标：** 以首份真人审核的真实 L2 报告交付为方向。本文件记录工作包、不变量、版本和本分支实际做到哪里。它不是客户报告。

**本分支没有完成：** 三个真实试点站、真实 Qwen 端到端、真实人审交付。下面的判断都来自合成夹具，不表示跑过 beherohome，也不表示客户已经批准。

## 不变量

- 改变输出使用新版本。`l2-industrial-1.0.7` 及更早的诊断重放不改客户字段。
- `UNKNOWN`、`ACCESS_BLOCKED`、`NOT_APPLICABLE` 和未访问不能变成缺陷或扣分。
- 不新增第二引擎、第二报告或第二审核权威。工业 `IND-*` 不替代通用 16 条。
- 新规则只到 L-B。`FAIL_WITH_EVIDENCE` 进入 `evidenced_pending_review`。`confirmed_obstacles` 只收 L-C；本轮没有 L-C，保持空。
- AI 只走租约结束后的现有 Qwen 链路。失败、超时、费用未知降级为 `AI_UNAVAILABLE`。假设保持 `REVIEW_REQUIRED`。
- 不出现价格、工期、排名、流失额、E2、E3。
- 真实 HTML 不进仓库。不提高 6 页或 30 秒租约。不改 B5A pin 的上位文件。代码不内置审核人姓名。
- 未签字清单只能输出 `REVIEW_REQUIRED`。`CLARIFY_CHANNEL` 永远不能是 `GAP_WITH_EVIDENCE`。
- Controlled 演练不得写成 `formal_human_review=true` 的真实人审。

## 版本

| 名称 | 标识 |
| --- | --- |
| 诊断 | `l2-industrial-1.0.8` 起。Worker 只对新的 `automatic_result` 计划选择它；旧任务仍是 `l2-industrial-1.0.1` |
| 执行器 | `ra2b6-1.0.6` |
| 采购配置 | `procurement-1.2.0` |
| 清单 | `buyer-stages-1.0.0` |
| 提示词 | `qwen-l2-buyer-reasoning-1.0.0` |
| 内容单元 | `vrae.report-content-units.v1` |
| 判断 | `vrae.diagnosis-judgment.v2` |
| 执行摘要 | `l2-executive-2` |

受历史字节钉住的 FindingPackage 构建器仍只接受到 `ra2b6-1.0.5`。1.0.8 用该构建器复验同一证据包，并把 `ra2b6-1.0.6` 的规则行放到确定性诊断的 `buyer_tasks`。这不是第二套发现引擎。

## R1

| 工作包 | 本分支 |
| --- | --- |
| WP-R1-0 试点重放 | 已实现 `scripts/pilot_replay.py`。只读、脱敏、离线 `select_next` 默认顺序。旧回执不一致时退出码 2。合成夹具，不抓站 |
| WP-R1-1 采购清单 | 已实现砂轮草案四项。`approval` 为空。未签字只有 `REVIEW_REQUIRED`。签字后的计算函数可被测试直接调用，不把缺口写入客户结果 |
| WP-R1-2 INFO-02 | 新执行器用清单判断。未签字不得 `FAIL`。`GAP_WITH_EVIDENCE` 映射为 `FAIL_WITH_EVIDENCE`；适用 PUBLISH 项都是 `SOURCE_AVAILABLE` 时为 `PASS`；其余 `UNKNOWN` 或 `NOT_APPLICABLE`。`coverage_note` 写明只覆盖本次产品页。S2 合成路径保留 |
| WP-R1-3 TRUST-02 / TRUST-03 | 声明名称、邮箱、电话做规范化精确比较。两页一致为 `PASS`，冲突为 `UNKNOWN/CONFLICT_REVIEW_REQUIRED`，不足两页为 `UNKNOWN`。证书或案例声明记录到则为 `PASS`，真伪保持 `UNKNOWN`。过期只记比较，不出 `FAIL` |
| WP-R1-4 TECH-01 / SEO-02 | 新增闭合扩展 `MetadataCitation.schema.json`，不改冻结基础契约。404/410 为 L-B 的 `FAIL_WITH_EVIDENCE`；5xx 为 `UNKNOWN/TRANSIENT_NOT_PROVEN`；401/403/429 为 `ACCESS_BLOCKED`。脚本依赖的 SEO-02 为 `UNKNOWN`。投影写明单次测量、含调度开销、不含 DNS、不是体验也不是评分；渲染性能与移动端未测 |
| WP-R1-5 选页 | `select_next(..., sampling='l2-stage-v1')`。默认参数不变。新模式顺序是首页、分类、两个不同分类的产品页、联系、关于。清单要求应用页时才把 APPLICATION 提前。函数不提高页数上限 |
| WP-R1-6 判断 v2 | `page_scope` 在 1.0.8 增加角色与原因码，分母是事先声明的角色。判断 v2 的 `unjudged` 按启用规则，`confirmed_obstacles` 为空。消费端拒绝「建议优先关注」「可以先这样改」 |

## R2

| 工作包 | 本分支 |
| --- | --- |
| WP-R2-1 原生盘点 | `native_business.inventory/restate` 复用同一 `native_document` 的 finding 与 blueprint 标识。不另起报告对象。结论见主题 README |
| WP-R2-2 执行摘要 | 新增 `project_v2`，版本 `l2-executive-2`。`project` 仍是 `l2-executive-1`。D1–D6 与筛选到询价的六段说明不含价格和工期。没有缺陷的报告可以成立 |
| WP-R2-3 / R2-4 推理 | 现有 provider/session 认识新提示词。输出四类候选，Guard 式引用检查会丢弃无证据条目，上限 8。本分支只用假提供者。失败降级为 `AI_UNAVAILABLE`。不得宣称真实 Qwen 已完成 |
| WP-R2-5 内容单元 | `vrae.report-content-units.v1`。参考消费端允许重排，不允许改强度、分组或文本，也不允许把非 `CONFIRMED_BY_REVIEW` 显示成已证实 |

## R3 与并行线

| 工作包 | 本分支 |
| --- | --- |
| WP-R3-1 / R3-2 | `vrae/l2/item_review.py` 记录逐条确认、修改、驳回、哈希批准、撤权和错误接收者。合成身份的 `formal_human_review` 为 false。周汇总在分母为 0 时返回 `NOT_EVALUABLE`。现有账本的 `review/issue/revoke/access` 仍是权威 |
| WP-R3-3 | `docs/03-engineering/automatic-diagnosis/l2-delivery/VF_HANDOFF.md` 与只读参考渲染。不改 VF 仓库 |
| P1 | `vrae/l2/scoring.py` 导入合成标注后返回 `NOT_EVALUABLE` |
| P2 | `vrae/intelligence/pagespeed_adapter.py` 默认关闭，不读密钥，不发请求。未获 Owner 批准 |
| P3 | 不实施：浏览器 CTA-01 可见性、CTA-03、INFO-03、PDF 解析、DISC-03、自动报价 |

## 验证

合成测试在 `tests/industry/test_l2_delivery_r1_r3.py`。`integration/authorized_targets/checks/test_delivery_details.py` 与 `reference.test.mjs` 仍通过，用来证明 1.0.7 的判断投影没有改成 v2。`tests/interpretation/test_fixed_replay.py` 在本基线上会因既有源码字节与 `preserved-history.json` 不一致而失败，涉及 `vrae/findings/builder.py`、`vrae/rules/info01.py`、`vrae/rules/product_facts.py`、`vrae/rules/seo01.py`。本分支没有改这四个文件。

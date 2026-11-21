# 客户预诊断判断

`GET /v1/audits/{audit_ref}/diagnosis` 仍是现网客户预诊断，不是 `GET /v1/audits/{audit_ref}/report` 的正式报告。本增量只给 `diagnostic_version == l2-industrial-1.0.7` 的 `customer_presentation` 增加可选 `judgment`，契约 `vrae.diagnosis-judgment.v1`。旧版本工件重放不带该字段，观察文案仍是原来的「已记录首页导航……」。

判断和买家文案由 VRAE 给出。预览不要再把唯一一条供方核对问题抬成页面标题或改造建议。文案里不得出现「建议优先关注」或「可以先这样改」。本增量不改 VF 仓库，不新建 PDF 服务，不提高 6 页上限和 30 秒租约，不重抓站点，不新调模型，也不打开正式外发。

## 字段

`judgment` 与外层预诊断一样保持 `is_report: false`、`formal_human_review: false`。它不是评分，也不是已审核报告。

| 字段 | 含义 |
| --- | --- |
| `lead` | 结论。结论区只消费这一段。 |
| `confirmed_obstacles` | 只收录 `FAIL_WITH_EVIDENCE`。`is_defect_score` 与 `confirmed_obstacle_count_is_score` 都是 `false`，条数不是分数。 |
| `supplier_questions` | 来自已有 `claims[].questions`，原文保留。`presented_as_priority_fix` 与 `is_confirmed_defect` 都是 `false`。不要把 `rebuild` 渲染成优先改造。 |
| `walked_path` | 只含 `buyer_journey` 里 `result == PASS` 的步骤。 |
| `unjudged` | 主规则 `DISC-01`、`DISC-02`、`INFO-01`、`TRUST-01`、`CTA-02`、`SEO-01` 中，没有 `PASS` 也没有 `FAIL_WITH_EVIDENCE` 的环节。`is_defect` 为 `false`。 |
| `sample_boundary` | 数量来自 `capture_summary`，页面清单来自 `page_scope`。`unvisited_is_defect` 为 `false`。71 个未访问候选不是缺陷。 |
| `scope_hypothesis` | 只有一条。有已证实障碍时为 `REPAIR_RECORDED_ISSUE`；否则已有产品页时为 `CHECK_RECORDED_PRODUCT_PAGE`；两者都没有时为 `NO_BROADER_SCOPE`。`whole_site_rebuild` 为 `false`。 |

`1.0.7` 的观察 `text` 在 `result == PASS` 时改用买家说法，并保留未核验限制。`INFO-01` 且 `source_text_presence == OBSERVED` 时，买家句子以「已看到供方写的名称或描述」开头。其他结果仍用原来的观察文案。

参考消费端 `projectJudgment` 在没有 `judgment` 时不增加键。有该字段时核对契约、两个 `false` 权威位、障碍不计分、供方问题不是优先改造、`unvisited_is_defect == false`、`whole_site_rebuild == false`，以及 `lead`、范围假设、路径摘要、`unjudged` 文案不含上面两句禁止语。通过后原样放进投影；`vf-preview-adapter.mjs` 与 `report-view.mjs` 再原样带上。校验失败则整份投影失败，不改写成另一套语气。

## VF 怎么渲染

结论区使用 `judgment.lead`。供方核对（`supplier_questions`）和已证实障碍（`confirmed_obstacles`）分栏，不要并成一条「建议」。

走通路径的页面标题用 `walked_path.steps[].label`。`DISC-02` 的目标标题是 `INFO-01` 里 `fact_role == NAME` 的产品名，不是 URL 末尾的 `.html` 文件名。`label` 是 `{zh, en}`；产品名两边相同，因为它是供方原文，不是翻译。

范围假设只渲染 `scope_hypothesis` 这一条，不要再并列生成全站重建、优先改造或第二句行动建议。

没有 `judgment` 的旧响应保持现有预览。不要为了补标题而在 VF 里另写判断句。

## 选页没有改

代表页仍由 `vrae.collection.discovery.select_next(..., representative=True)` 选择。尚未覆盖的角色按 `HOME`、`CATALOG`、`CATEGORY`、`PRODUCT`、`CONTACT`、`ABOUT`、`APPLICATION` 优先，其后才是 `OTHER`。代表页模式下，已标成联系目标的 URL 按 `CONTACT` 进入这个顺序。

本轮仓库没有 `www.beherohome.com` 的已提交工件。那次 6 页已访问、71 个候选未访问的结果不能靠改选页重写，因此本增量不改 `select_next`。

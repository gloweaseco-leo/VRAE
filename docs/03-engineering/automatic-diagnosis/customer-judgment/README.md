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

## 实物重放

工件不在仓库，未做实物重放。

查找范围是仓库全文和 git 历史、`docs/03-engineering` 下的证据目录，以及 `tests/` 与 `integration/` 的测试夹具。本机其他常见目录也没有这份正文。唯一出现 `www.beherohome.com` 的地方是本文件。没有可交给现有重放入口的已提交诊断工件、`audit_ref` 或保留 HTML。

因此不能判断 2026-11-21 那份标题为「采购体验预诊断报告」、6 页已访问、71 个候选未访问、0 次失败的 PDF 上，「核对企业资料」（TRUST-01）和「访问与页面结构」（SEO-01）是工件里没有可显示事实，还是 `contextFacts` / `limit` 已经在投影里、只是 VF 预览没渲染。下面只说明投影代码会怎样输出，不是那份 PDF 的重放结论。

相近的计数摘要也不能代替这份工件。`incident-179-20261120/evidence.json` 是 6 页已访问、60 个未访问、0 次失败，证据里没有网址。`retained-context-and-report-quality/frozen-replay.json` 和 `product-scope-and-five-task-delivery/frozen-replay.json` 只有 6 页与 71 个候选的计数和 SHA，`customer_website_submitted` 为 `false`，没有诊断正文。这些文件没有拿来重放，也没有拿来改选页。

### 投影层对 TRUST-01 / SEO-01 的输出

`diagnostic_version` 为 `l2-industrial-1.0.5`、`l2-industrial-1.0.6` 或 `l2-industrial-1.0.7` 时，`integration/authorized_targets/presentation.py` 的 `build` 对每条观察调用 `presentation_context.build` 与 `presentation_context.limit`，写入 `context_facts` 和 `limit`。

TRUST-01 的 `context_facts` 只转写观察行上已经存在、且 `kind` 属于 `ABOUT_TEXT`、`SELF_DESCRIPTION`、`DECLARED_NAME`、`STATIC_CONTACT_LINK`、`TITLE`、`DESCRIPTION`、`CANONICAL`，并带有非空 `citation_indexes` 的子事实。行上没有这些子事实时，键仍在，值是空数组。`limit` 只在 `result == UNKNOWN` 时是对象。TRUST-01 不在未实现名单里（未实现的是 TRUST-02、TRUST-03）。原因 `TRUST_PREREQUISITES_OR_CAPTURE_SCOPE_UNRESOLVED` 落到 `PARTIAL_EVIDENCE`。结果不是 `UNKNOWN` 时，`limit` 为 `null`。

SEO-01 的 `context_facts` 只在 `seo_signals.title`、`description` 或 `canonical` 的 `status == OBSERVED`，并且引用里有相同 `fact_role` 时，输出 `TITLE`、`DESCRIPTION` 或 `CANONICAL`。信号未观察到，或引用角色对不上时，值为空数组。`limit` 同样只在 `UNKNOWN` 时出现。SEO-01 不在未实现名单里（SEO-02 才是 `NOT_IMPLEMENTED`）。原因 `PARTIAL_MISSING_AMBIGUOUS_OR_UNSUPPORTED_HEAD_SIGNALS` 落到 `PARTIAL_EVIDENCE`。

`integration/authorized_targets/consumer/reference.mjs` 的 `projectResult` 把上述字段投影为 `contextFacts` 和 `limit`。TRUST-01 还要与确定性行上的 `context_facts` 按 `kind` 和 `citation_indexes` 对齐；SEO-01 还要信号为 `OBSERVED`、引用 `fact_role` 一致，并且引用落在已访问页上。对不上则整份投影失败。输入为空时输出空数组。`limit` 在结果为 `UNKNOWN`、文案和 `kind` 合法时输出 `{kind, text}`，否则为 `null`。

`vf-preview-adapter.mjs` 把观察放进 `buyerTasks`。`report-view.mjs` 保留观察上的 `contextFacts` 与 `limit`，并在每个任务和整份 `reportView` 上再聚合 `contextFacts`。本仓库的预览适配器会带上这两项。VF 仓库本轮不改。

## 选页没有改

页数上限仍是 6。`vrae.collection.discovery.select_next` 没有改。

代表页仍由 `select_next(..., representative=True)` 选择。尚未覆盖的角色按 `HOME`、`CATALOG`、`CATEGORY`、`PRODUCT`、`CONTACT`、`ABOUT`、`APPLICATION` 优先，其后才是 `OTHER`。代表页模式下，已标成联系目标的 URL 按 `CONTACT` 进入这个顺序。

没有这份已提交工件的重放，就没有「预算内已经有 About 或应用页，却被更不相关的页面占掉」的证据。没有这份证据，就不改选页。

## VF 移交

以下交给 VF 渲染。本仓库不改 VF 仓库，不在 VF 里另写判断句。没有 `judgment` 的旧响应保持现有预览。

- 结论只用 `judgment.lead`。
- 供方问题（`supplier_questions`）与已证实障碍（`confirmed_obstacles`）分栏。
- `supplier_questions.presented_as_priority_fix` 与每条 `items[].presented_as_priority_fix` 必须为 `false`。禁止再渲染「建议优先关注」「可以先这样改」。不要把 `claims[].rebuild` 渲染成优先改造。
- 页面标题用 `walked_path.steps[].label`，不用 URL 末尾的 `.html` 文件名。`label` 是 `{zh, en}`。`DISC-02` 在 `INFO-01` 有 `fact_role == NAME` 的产品名时，两边都用这份供方原文；没有产品名时用「已打开的产品页」/ `Opened product page`。
- 改版范围只渲染一条 `scope_hypothesis`（`kind` 与 `text`）。`whole_site_rebuild` 为 `false`。

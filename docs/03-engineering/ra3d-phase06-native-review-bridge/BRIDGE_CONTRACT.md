# 只读投影合同 · native-review-display-0.6.1

此 schema 名称只属于本目录的显示资料，不是向冻结 RA0/RA3C JSON Schema 增加字段。`native_document` 是实际 `ReportDraft.document` 的完整只读副本；原生 `draft_ref / html_sha256 / editorial_content_sha256 / native_report_version` 与 private/NOT_APPROVED/shareable=false 均原样保留。原 HTML 通过 native `render` 取得精确 bytes，以 write_bytes 保存，没有添加水印、去掉限制或重新排版。

可信输入冻结于 main `696d4ae695041f0eeefa56d22039682a989380b2` 的 `tests/reporting/fixtures/{sources,caller-pins}.json`。通过 `git show SHA:path` 读取，不使用 other worktree 或 mutable QA。expected refs 来自单独 caller-pins，source mutations 不改变这份预期。导入前比较生产 `vrae/**`、`contracts/**` 和 frozen fixture 的 Git blob，记录原始 Git bytes SHA-256 与本地 bytes SHA-256（CRLF 本地差异单列），所有加载模块路径须在本 worktree 的 `vrae/`。

| 显示对象 | 原生来源 / 原文映射 | 核对与缺失处理 |
| --- | --- | --- |
| 报告 id/version/scope/创建时间 | `native_document.metadata`、`.scope` | 不从用户输入或 reviewer 文本赋值；捕获时间另取实际 citation |
| 404 事实 | `/issues/0/fact_claim` | exact text / type / status 与真实 GuardResult、绑定 fact 一致 |
| 影响/行动/复核 | `/issues/0/proposals/{impact,action,recheck}` | exact native Chinese text；保留 HUMAN_REVIEW_REQUIRED，不能人工升格事实 |
| 正向来源陈述 | `/positive_source_claims/*` | 每条有单独 pointer、guard_ref、binding_ref、源字节；不是认证或效果证明 |
| 原始 quote/UTF-8 区间 | `claim.fact.source` | `EvidencePack.resolve(citation.evidence_ref, expected_pack_ref=held)` 后 exact bytes slice == quote.encode('utf-8') |
| source/snapshot/evidence 引用 | `fact.source.citation` 与 `pack.resolve().evidence` | 两者 source/snapshot 必须一致；显示完整值，不用全局列表冒充语义证明 |
| 404 目标状态/href/time | 原生 CTA-02 rule execution 的 `source_page / target_response / citations` | 保留 inseparable edge；同固定 fact quote 再核对，不根据当前网站推断 |
| 200 联系路径 | 原生 CTA-02 PASS row/citation | 实际行/列解析定位到已保留 body 的 anchor；guard_ref/binding_ref=null，明确没有 CTA Guard claim；不伪造 finding |
| scope/UNKNOWN | `.examined_pages / .buyer_journey / .recorded_coverage / .limitations` | 直接保留原生结果。403/WAF 仅作为“本包未另采集、遇到时须限制”的说明，不伪装成本次观测 |
| 精确报告预览 | native `render` 的原 HTML file | sandboxed iframe，只读本地文件；实测独立 renderer URL 与实际 NOT APPROVED DOM |

原生重放顺序：`EvidencePack.load` → `FindingPackage.load` → 每份 `GuardResult.load` → `build_draft` → held draft/html/count 比较 → `ReportDraft.load` → `render`，且 build/load/render 的 HTML bytes 三者完全一致。不会构造 stub ReportDraft 或 mock Guard；不用 accepted test helper 重新 freeze 输入、重签 guard 或从 mutated source 推导可信 pin。

200 CTA PASS 不在现有 RA3B catalog 的允许 CTA 事实集合（该集合只含 404/410 的 `CAPTURED_CTA_HTTP_FAILURE`）；现有 API 没有可用 CTA claim，故不补造。三个真实 INFO/TRUST/SEO source claims 仍可回查；TRUST 仅指原始自述元素，不认证企业身份。native 200 对象仍为 null，不能因投影多展示了 capture row 就称已形成正式报告或批准。

Phase 0.5 复用边界：旧工作台脚本/样式直接引用且原 Git blob 不变。桥接前置文件仅将已验证数据适配到旧形状；旧 target 的 `guard` 是演练状态，200 使用 `NO_CTA_GUARD_CLAIM`，不是伪造原生 Guard 状态。薄展示层校正原先固定日期与 sim-* 说明，增加每条来源 dialog、摘要、覆盖与原生 HTML；不替换原生对象，不将浏览器内存结果写回。

额外的原生来源陈述也须逐项核对，才允许“正向模拟前提”或“范围模拟”继续。其结果仍只是 Phase 0.5 的内存 rehearsal；没有 ReviewDecision、approve_version、check_share、ShareGrant、身份签名或持久 commit。浏览器 state/checkbox/摘要不是权限或真人理解证明。

负例只尝试 detached 副本，原 held pins 与原生正例不修改；native 拒绝和桥接 held-pin 拒绝在日志分别标明。任何意外异常或接受非法输入使命令非零，不能转换成空问题绿报。每次导出保存独立运行 JSON；每次浏览器保存原始输入、FAIL/ERROR/SKIP、CDP 命令、截图与网络事件，不能覆盖历史。

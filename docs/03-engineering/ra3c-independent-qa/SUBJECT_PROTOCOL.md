# Candidate wiring and actual visual evidence

This is an independent QA interface, **not an invented production API**. No
RA3C candidate was inspected to author the 64 oracles or 14 local scenarios.
There is currently no adapter, no reporting module on the accepted baseline,
and no report/visual PASS. Missing wiring is QA_MAPPING_NOT_BOUND, not a proven
production defect. Native ReportVersion is optional under Issues #45/#46.

After a final candidate is identified, record its exact SHA and review a small
separately versioned adapter before Phase B. Its SHA and full diff accompany the
results. Owner adjudication is required for a contradictory oracle; do not tune
the frozen assertions. An unsupported representation is QA_NOT_READY and must
be reported explicitly. These tests are not yet proof of candidate compatibility.

## Adapter transport

`VRAE_RA3C_QA_ADAPTER_PATH` points to a standalone file exposing `bind(reporting)`.
It returns an object with:

- `production_module`: the actual imported `vrae.reporting` module;
- `rejection_types`: actual bounded public exception classes from `vrae.*`;
- `build(context, revision, created_at)` and
  `load(document, html, context, expected_digest)` invoking actual public APIs;
- `origins`: auditable JSON-pointer/DOM field mappings;
- `digest_recipe`: independently reproducible production hash serialization.

The context contains actual accepted EvidencePack/RuleExecution/FindingPackage,
GuardResult plus original interpretation/bindings, separately held expected refs
and scope. All are passed through without filtering, repairing, resealing,
prevalidating attacks or adding fabricated approved claims. No adapter-generated
HTML, report prose, approval flags, expected outcomes or exceptions. Extraction
must preserve exact raw production document/HTML/digest; artifact keys are
`document` (actual dict), `html` (actual UTF-8 bytes), `digest` (actual reference)
and `origin_module` (actual function origin). Loader results use the same shape.
Network/DNS/socket/process entry points are blocked during public calls; an
attempt remains a failure even if production catches the denial. This in-process
gate is defense in depth, not a kernel sandbox or exhaustive egress proof.

JSON origins use `kind=json,pointer=/actual/path` relative to the document or
actual issue item (`root=document` explicitly selects the document). HTML origins
use `kind=html,node_index=N` in independent HTMLParser preorder and optionally
`attribute`. `kind=object,members={...origins...}` projects real fields only;
it cannot synthesize native ReportVersion or issue lists. `kind=absent_native`
is only allowed for native_report and independently checks document absence.
Current test harness requires a real structured document and issue list plus
actual native mutation paths; an HTML-only/differently serialized API cannot be
silently mapped to a fake JSON report. Escalate that QA integration gap.

Root roles: issues, native_report, private, approval_status, shareable, coverage,
unchecked, captured_at, scope, version, language, layout_version, asset_version,
guard_ref, main_text, service_scope_text, objective_texts, objective_binding_refs,
scores, privacy_text. Issue roles: buyer_task, target_status, fact, impact,
impact_status, action, action_status, recheck, finding_id, evidence. Evidence
projection: pack_ref, observed_at, evidence_ref, byte_start, byte_end, quote,
source_url, captured_scope, target_status, href, binding_ref. Every scalar must
have an actual source. Absence cannot become an adapter-manufactured false/empty
value. Lack of a score is inspected through the actual native representation.

Digest recipe supports sorted compact UTF-8 JSON (`ensure_ascii=False`, no NaN),
excluding only declared top-level digest-self fields, either containing actual
HTML/its SHA (`canonical_doc`) or followed by a declared <=16-byte ASCII separator
and exact HTML (`canonical_doc_plus_html`). This is a QA serialization boundary;
a different genuine scheme requires explicit QA mapping review, never a fake
replacement digest. The separate RA0 hash does not prove editorial integrity.

## Actual browser dossier, not automated customer approval

`VRAE_RA3C_QA_OBSERVATIONS_PATH` and `VRAE_RA3C_EXPECTED_CANDIDATE_SHA`
identify an externally captured local QA dossier. It binds exact candidate SHA,
HTML SHA256, `not_customer_approval=true`; viewports `375` and `1280` include
width, browser_version, actual screenshot path/SHA, external_requests (must be
empty), measured scroll/client width, body font, heading count, visible layer
labels, above-fold privacy state and font. Evidence clicks record actual internal,
resolved, correct_quote observations. `capture_tool` identifies the real tool.

The dossier includes substantive `business_review` entries reading_memo,
scope_memo, value_memo: actual observed quote, >=80-character reasoned assessment,
screenshot_refs, `qa_only=true`, `not_report_approval=true`, and local
`decision=QA_OBSERVED_PASS` only after actual reading. The value memo must compare
the genuinely rendered 0-issue and 1-issue outputs and link both exact HTML SHAs
and captures. Evidence metadata is audited alongside actual images and logs;
file existence or self-authored PASS text alone is never visual acceptance.

14px body/12px privacy and no-overflow are independent readability heuristics,
not an accessibility certification. Manual reading must also assess concise
Chinese, hierarchy, honest VEYFRONT scope, useful next discussion and visible
separation of facts/hypotheses/proposals/rechecks. Missing/failed browser evidence
is VISUAL_NOT_VERIFIED. No synthetic mockup, network navigation or customer share.

Current limitation: browser tooling has not been exercised on a real report;
Playwright is absent from the QA Python environment. Cached Chromium alone is
not execution evidence. Phase A provides no screenshots and no HTML UX PASS.

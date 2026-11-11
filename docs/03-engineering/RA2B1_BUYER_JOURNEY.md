# RA-2B-1: captured static buyer paths

Baseline main `8a1b1aca9da5a00c1f3f252f207c7a7b57d3e558`.
Adds DISC-02 category/catalog-path → product-path and CTA-02 product-path →
contact/RFQ-path judgments. No forms are submitted and no visibility, SKU transfer,
inbox delivery, conversion, semantic identity or whole-site quality is asserted.

## Explicit evaluator versions / historical compatibility

New evaluation: `execute(pack, expected_pack_ref=trusted_ref,
evaluator_version='ra2b1-1.0.0')`. Original default `ra2b0-1.0.0` is intentionally
retained, including original DISC-01 output, 15 UNKNOWN results and sealed example.
`verify_execution` dispatches by the recorded supported evaluator version; callers
can additionally pin `expected_evaluator_version='ra2b1-1.0.0'`. Unsupported
versions are refused. Catalog/rule versions remain the frozen **1.0.0**; evaluator
implementation version is separate. Old expected outputs are never regenerated.

## Rule readiness (all 16 IDs / versions unchanged)

| Rule / version | Task | New evaluator status / exact scope or remaining gap |
| --- | --- | --- |
| DISC-01 / 1.0.0 | DISCOVER | Enabled, unchanged: static HOME nav href → category/catalog-path response |
| DISC-02 / 1.0.0 | DISCOVER | **Enabled**: retained category/catalog HTML anchor → captured product-path response; no semantic identity claim |
| DISC-03 / 1.0.0 | DISCOVER | UNKNOWN: no independent industry/application relevance mapping |
| INFO-01 / 1.0.0 | UNDERSTAND | UNKNOWN: no product/spec field parser and locators |
| INFO-02 / 1.0.0 | UNDERSTAND | UNKNOWN: no observed attribute mapping/applicability proof |
| INFO-03 / 1.0.0 | UNDERSTAND | UNKNOWN: no human-verified language judgment |
| TRUST-01 / 1.0.0 | TRUST | UNKNOWN: no company identity/context parser |
| TRUST-02 / 1.0.0 | TRUST | UNKNOWN: no proof/context parser/authenticity evidence |
| TRUST-03 / 1.0.0 | TRUST | UNKNOWN: no entity resolution/comparable passages |
| CTA-01 / 1.0.0 | INQUIRE | UNKNOWN: Browser DOM lacks href; static HTML does not prove rendered visibility |
| CTA-02 / 1.0.0 | INQUIRE | **Enabled**: retained product-path HTML anchor → captured contact/RFQ-path response; no submission/delivery/context-transfer claim |
| CTA-03 / 1.0.0 | INQUIRE | UNKNOWN: no visual layout/overflow geometry evaluator |
| SEO-01 / 1.0.0 | SEARCH_TECHNICAL | UNKNOWN: no sitemap/tag combination/applicability evaluator |
| SEO-02 / 1.0.0 | SEARCH_TECHNICAL | UNKNOWN: no semantic product/crawlability context evaluator |
| TECH-01 / 1.0.0 | SEARCH_TECHNICAL | UNKNOWN: standalone metadata-only Observation evidence bridge deferred |
| TECH-02 / 1.0.0 | SEARCH_TECHNICAL | UNKNOWN: no image/heading context/accessibility evaluator |

Existing [RA-2B-0 matrix](RA2B0_RULE_READINESS.md) retains evidence/risks for
unchanged rules. No independent non-applicability proof exists; the small
IndustryPack applicable_rule_ids list never causes NOT_APPLICABLE.

## New rule decision / evidence requirements

Both new rules reuse bounded Navigation parsing, EvidencePack verification and
resolution, original Observation schema and RA-0 classify_rule. Anchors outside
nav are supported; form actions, script-only links and Browser text without href
are insufficient. Only same-host canonical URLs with supported path roles qualify.
HTTPS downgrade, base tags, duplicate hrefs and unsupported original HTML remain
UNKNOWN. Role classification uses the existing path heuristic, not content semantics.

- PASS: retained observed source body + actual located href + captured target
  HTTP 200 + retained target body + supported final path role (including redirects).
- FAIL_WITH_EVIDENCE: retained observed source body + exact href + independently
  verified target HTTP_ERROR 404/410 with original source/snapshot/status/trace.
  No unretained target-body claim is made.
- UNKNOWN: source/target not captured, raw source/target missing, incomplete/other
  response, unsupported role/HTML or insufficient applicability evidence.
- ACCESS_BLOCKED: the actual source/target snapshot is blocked (403/WAF/robots).

Every objective row binds actual resolvable EvidencePack evidence_refs plus
`source_page`, `citations` (href/line/column/ordinal), and `target_response`
(source_ref, snapshot_ref, original JSON pointer, requested/final URL, time,
HTTP status, error, trace). Independent replay reconstructs all fields; removing
the target metadata edge invalidates the result even after recomputing its hash.
Any future Finding consumer must retain this response-metadata edge.

`journeys` joins identical captured snapshot refs across DISC-01/02/CTA-02,
stopping at UNKNOWN, BLOCKED or FAIL. Good and bad paths remain distinct.
Each step includes its Observation ID, provenance and capture time. Composed paths
are bounded to 256 with explicit truncation; this never asserts full-site coverage.
`recorded_capture_scope` preserves source tenant/run/policy/version/terms references
and explicitly says recorded scope is **not current authorization**. Original
coverage and limitations remain visible.

## Replay

`python scripts/verify_ra2b1.py` loads the new committed offline fixture and pinned
expected execution: HOME → category/valves → products/valve-v1 → contact, three PASS
steps. It also checks deterministic repeat and the legacy execution ref. Only the
new fixture can be regenerated with `--write-example`. Existing
`python scripts/verify_ra2b0.py` and `python scripts/verify_ra2a.py` still replay
unchanged sealed outputs. All inputs use the existing synthetic transport/DNS;
only GET is observed, no network or form submission.

All legacy safety/collection/evidence contracts and frozen files are unchanged.
No production platform, real website collection, model, DB, API, UI, CRM, Finding
or later-stage work. Offline synthetic consistency is not signed authenticity,
current authorization or production-readiness certification.

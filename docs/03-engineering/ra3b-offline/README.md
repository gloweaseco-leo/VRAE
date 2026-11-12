# RA-3B private offline per-claim guard

Issue: https://github.com/gloweaseco-leo/VRAE/issues/40

Started from independently fetched accepted main `7e62bfcd1a900630b80b02850a0086cc950e4138` in new worktree `ra3b`, branch `codex2/ra3b-claim-provenance`. No PR #37 reuse, no unaccepted RA-3A imports, no intelligence edits. Final integration/CI evidence is recorded separately.

## Business demonstration

Run `python scripts/verify_ra3b.py` without network or provider access. This replays `tests/interpretation/fixtures/fixed-replay.json`, including raw captured bytes, complete pack, C3 package, individual bindings and fixed guard expectations. Run `python -m pytest tests/interpretation -q` for hostile input tests.

Three distinct industrial synthetic captures preserve an explicit company self-description, product name/specification text, original title/canonical tags, and contact responses 200, 404 and 410. A narrow source-element statement includes the exact original HTML quote and byte range. This proves only that those source bytes were captured. It never proves the company identity, factory, certificate, qualification, product accuracy, SEO outcome, deliverability or reputation.

The 404/410 claim names the exact static href, captured HTTP status and capture-time limitation; its individual citation includes the full replayed target response and redirect edge. C3 TRUST abstains on those failed contact captures. The 200 TRUST positive is demonstrated on its separate pinned pack; no blending captures to manufacture a positive.

Private queue examples: “A buyer may need human help confirming the captured contact route.” and “A human should review the captured route before suggesting a change.” Both remain `HUMAN_REVIEW_REQUIRED`. The unrelated objective assertion “This certified factory loses $100000 in sales.” has valid IDs but receives `REJECTED / UNSUPPORTED_OBJECTIVE_ASSERTION`.

## Trust boundary and API

`catalog(pack, package, **pins)` independently verifies the immutable pack, execution and C3 package and constructs a closed vocabulary of narrow literal statements. `binding(...)` creates an **untrusted** proposal only. `validate(interpretation, bindings, pack, package, **pins)` checks the frozen AIInterpretation contract and requires exactly one binding per array entry, matching its exact text/pointer. No input text is rewritten. Hypotheses may carry a separately typed objective source statement; this is an internal sidecar convention, not a change to the v1 contract.

Each binding carries the version, complete verified context, observation/rule version, source fact, citation index, original citation/locator, retained quote, original byte range, coverage status/note and content-addressed reference. Context includes caller-held pack/execution/package pins, evaluator/builder/guard versions, tenant/run/policy/version, catalog hash, coverage and recorded capture scope. Citation equality is checked against independently replayed facts; a new outer hash cannot authorize changed source content, positions, target responses or context. Global IDs are checked for consistency only and confer no individual support.

Diagnostic claim references are independently computed canonical digests. A malformed declared binding reference still causes rejection, and its untrusted content is never reflected into the guard's diagnostic reference field. Original claim text and the submitted binding remain unchanged.

Callers must hold all trusted pins independently. `expected_scope` contains tenant_id, run_id, policy_id and policy_version; these pins represent recorded scope, not present authorization. No API accepts a model-supplied replacement for caller pins. Only C3 builder `ra2c3-1.0.0` and evaluator `ra2b6-1.0.0` are supported by this guard. Historical C0/C1/C2/C3 code/defaults and fixtures remain unchanged.

`GuardResult.load(..., expected_guard_ref=..., **pins)` replays all inputs and compares every result byte. A freshly hashed forged “verified” result is rejected. A directly constructed result or a checksum by itself is not approval. Inputs are canonical UTF-8 JSON bounded to 1 MB each, at most 256 claims/bindings, at most 512 catalog facts; malformed Unicode, non-finite JSON values and unsupported structures fail closed. Errors contain only fixed codes; the guard logs nothing. Individual failures contain pointer, binding digest, fixed status and fixed reason, never source contents.

## Semantic and security ceiling

Only exact generated narrow statements can obtain `SOURCE_FACT_BINDING_VERIFIED`. Arbitrary paraphrases, hypotheses, recommendations and missing-information prose cannot receive that status, regardless of IDs or input `VALIDATED`. Type labels are not a semantic classifier: a dishonest factual statement placed in a HYPOTHESIS field may be routed to human review, never source verification. Unsupported objective statements are rejected. Unknown/blocked observations produce no objective facts and cannot become AI-origin FAIL.

The instruction lexicon is a conservative rejection aid, **not a universal prompt-injection detector**. Known role delimiters, tool commands, report sharing, pin override and secret-leak instructions are rejected in source citations and proposed prose. Unknown instruction wording cannot cause execution: this module has no tools, network, provider, approval, sharing or report capability. Free prose always remains unapproved. Consumers must preserve this boundary and must not treat human-review items as facts.

Instruction scans recurse through actual source/citation strings before JSON escaping, including decoded text and LF/tab separators. Untrusted interpretation/model/reference metadata is also checked, with identifier separators normalized only for rejection checks; original input text/IDs are never rewritten in the stored interpretation or binding.

All results are private, `NOT_APPROVED`, unshareable, not reports and not semantic approval. This work does not certify external authenticity or current authorization, call a real model, generate customer reports, deploy, perform RA-3C/D, or evaluate deferred human Gold (still 0/26).

## Test matrix

| Area | Expected behavior | Proof |
| --- | --- | --- |
| TRUST/SEO/INFO original elements | Literal proof only, exact retained byte range | `test_literal_sources_have_individual_byte_proof` |
| Actual CTA 404/410 | Source href plus full captured target response | `test_actual_cta_failure_keeps_bound_source_and_target` |
| 403/500, unretained source | No objective defect/source proof | unknown/blocked and no-retained tests |
| Hypothesis/recommendation/missing information/paraphrase | Human review only | `test_prose_never_receives_semantic_approval` |
| Certification/qualifications/factory/traffic/revenue/ranking/sales loss/email delivery | Reject unsupported objective assertion | valid-IDs unrelated-claims tests |
| Detached/external/rescaled/split/merged quote; position/evidence/source/snapshot/status/version forgery | Reject despite resealing | forged-citation tests |
| Redirect/target-status/source forgery | Reject | forged-target tests |
| Source/suggestion/ID prompt injection | Reject or fail closed | injection and contract tests |
| Cross-capture / cross-tenant swaps | Reject or fail closed | swap tests |
| Pack/execution/package/guard/evaluator/builder/run/policy pins | Fail closed | trusted-pin tests |
| Approval/shareable/private/version escalation | Fail closed despite new hash | package-forgery and result-replay tests |
| Missing/duplicate bindings; false pointers/types/text; global IDs alone | Reject or fail closed | claim-coverage tests |
| Oversized / invalid Unicode / invalid JSON / extra contract fields / NOT_RUN / REJECTED | Reject or fail closed | contract tests |
| Fixed archive and historical bytes | Exact replay, distinct capture pins, historical SHA checks | `test_archived_fixed_replay` |

`preserved-history.json` anchors SHA-256 values to the accepted main Git blobs. The check permits Git's ordinary CRLF checkout conversion by hashing LF-normalized text; it does not change any historical file. Captured raw response bytes remain base64-preserved and are checked without newline normalization.

The same historical manifest is available under the new test fixtures, because the unchanged isolated HTTP image excludes `docs/`. Only its explicit `VRAE_ISOLATED_LAB=1` test invocation may report absent docs as unavailable; every missing source/contract/test artifact still fails, and every source proof still replays. The CLI and full-repository jobs require all 70 historical files. The existing sealed-Gold minimal-layout reconstruction tests also continue unchanged. The first hosted run exposed this docs dependency (`b3182a9`, isolated-http); it is retained as negative evidence, not counted as a pass.

See `fixed-replay-result.json`, Python-version JUnit XML, final validation summary and hosted CI links for executed results. No accuracy score or customer-facing output is claimed.

# RA-2B-0: bounded rule readiness

Baseline main: `cf99cfdc09f7355c98fd6e1c52bd1f401f3b7d98`.
Original `rule_catalog.v1.json` is reused unchanged: catalog **1.0.0**, every
rule **1.0.0**, all 16 IDs / five buyer tasks retained. Evaluator implementation
version is separately `ra2b0-1.0.0`. Observation schema and RA-0 `classify_rule`
are reused. No Finding is generated. Runtime gaps are in `vrae/rules/readiness.py`.

## 16-row implementation matrix

P/F below describe necessary evidence, not claims that deferred rules are implemented.
For every deferred row the executable result is UNKNOWN (no objective evidence_ids).
Missing configuration or an omitted ID in the current small IndustryPack does not
prove NOT_APPLICABLE. No independent non-applicability decision is available.

| ID / version | Task | Evidence / applicability | Positive / counterexample | Unknown, blocked, false-positive boundary / gap | Enabled |
| --- | --- | --- | --- | --- | --- |
| DISC-01 / 1.0.0 | DISCOVER | Retained HTTP homepage HTML; explicit static nav anchor href; CATEGORY/CATALOG **path role** and same-pack target response | P: target 200 + retained body + category-path final URL; F: that exact target captured 404/410 | No nav/raw/target → UNKNOWN; 403/WAF/robots → ACCESS_BLOCKED. Per-link scope, not rendered visibility, semantic category verification or site-wide absence | **Yes, bounded** |
| DISC-02 / 1.0.0 | DISCOVER | Category/product identities and linked sequence | P: verified category→product href; F: observed broken specific path | Unvisited is unknown; identity/sequence parser absent; never submit forms | No |
| DISC-03 / 1.0.0 | DISCOVER | Industry relevance + application link/context | P: relevant verified entry; F: scoped broken required entry | No industry applicability mapping; cannot infer universal requirement | No |
| INFO-01 / 1.0.0 | UNDERSTAND | Product identity + basic spec fields/locators | P: located spec; F: independently established required field contradicted in bounded scope | No field/identity parser; displayed values not certified | No |
| INFO-02 / 1.0.0 | UNDERSTAND | Applicable IndustryPack requirement + observed attribute | P: required located attribute; F: sufficient scoped contradiction | Pack has material requirement, no attribute mapping/applicability proof; missing configuration → UNKNOWN | No |
| INFO-03 / 1.0.0 | UNDERSTAND | Visible English text/context + human judgment | P/F: verified clarity judgment | No semantic/human judgment implementation; text keywords insufficient | No |
| TRUST-01 / 1.0.0 | TRUST | Company identity/profile/contact evidence | P: verified identity/context; F: observed bounded contradiction | No identity parser; no certificate does not imply no qualifications | No |
| TRUST-02 / 1.0.0 | TRUST | Displayed proof and context | P: contextual proof; F: observed context mismatch | No proof parser; presence does not establish authenticity | No |
| TRUST-03 / 1.0.0 | TRUST | Comparable company/contact passages, same legal entity | P: verified consistency; F: observed conflict for same entity | No entity resolution; never merge namesakes | No |
| CTA-01 / 1.0.0 | INQUIRE | Visible CTA **and real href**, same observation/context | P: visible located href; F: observed broken scoped CTA | Browser DOM only tag/visible/text, no href; HTML href cannot establish visibility; no inbox claim | No |
| CTA-02 / 1.0.0 | INQUIRE | Verified product-context→contact read-only path | P: captured journey; F: scoped broken path | Product/context path evaluator absent; no form submission | No |
| CTA-03 / 1.0.0 | INQUIRE | Approved mobile viewport + layout geometry | P: scoped layout; F: measured overflow/navigation defect | No geometry evaluator; not all-device/accessibility certification | No |
| SEO-01 / 1.0.0 | SEARCH_TECHNICAL | Permitted robots/sitemap responses and canonical/title tags | P: verified metadata combination; F: scoped contradiction | Sitemap/tag combination/applicability absent; hashes alone not tags; no indexing claim | No |
| SEO-02 / 1.0.0 | SEARCH_TECHNICAL | Product HTML/DOM + actual anchors/context | P: observed crawlable product context; F: sufficient bounded contradiction | Product context evaluator absent; JS is not automatic failure | No |
| TECH-01 / 1.0.0 | SEARCH_TECHNICAL | HTTP response/redirect metadata and an Observation evidence bridge | P: scoped permitted response; F: captured broken response | Non-200 snapshots have no observed evidence_ref. Metadata-only bridge deferred; DISC-01 instead cites actual homepage href Evidence plus target source metadata; 403 is blocked | No |
| TECH-02 / 1.0.0 | SEARCH_TECHNICAL | Image/heading context and bounded applicable requirements | P: verified resources/structure; F: observed scoped defect | No context/layout evaluator; not WCAG/performance certification | No |

## Executable first business judgment

`python scripts/verify_ra2b0.py` loads the committed offline industrial parts pack
and its caller-held expected ref; replays every Observation and asserts deterministic
equality. The input was produced by the existing collector using only synthetic
DNS/transport fixtures with `retain_raw_html=True`; no real sockets or third-party
websites. Regeneration is explicit: `python scripts/verify_ra2b0.py --write-example`.

The homepage links to valves and pumps: the captured valves category-path response
is 200 (PASS); the pumps href target returned 404 (FAIL_WITH_EVIDENCE). These are
separate link-scoped Observations, not a whole-rule/site-wide fail. Other 15 rules
output UNKNOWN, grouped by the original five buyer tasks. No text keyword list is
used to infer meaning. Existing path-role classification is explicitly a heuristic;
PASS certifies only the stated static link/HTTP scope, not semantic catalog quality.

`execute(pack, expected_pack_ref=trusted_ref)` refuses absent/wrong pins and replays
EvidencePack verification first. Each RuleExecution carries catalog hash/version,
evaluator version, rule version, scope, tenant/run, full coverage, and limitations.
Objective Observation.evidence_ids are actual EvidencePack evidence_refs (homepage
body and, for PASS, retained target body). Citations include source ref, original
JSON pointer, page ref, original decoded href with HTML line/column/anchor ordinal,
and capture time. Target response contains its source ref, original page pointer,
page ref, URL/final URL, timestamp, status/error and redirect trace. The 404 response
body is not retained and no claim is made about its content: its independently
verified source metadata supports the bounded response-status assertion.

`verify_execution(output, pack, expected_pack_ref=trusted_ref)` replays the exact
raw anchors and target metadata and compares the entire deterministic execution,
including statements, provenance and coverage. Recomputing an output hash is not
enough to accept a fabricated assertion. Callers must obtain trusted refs separately;
the example file is trusted local synthetic input, not remote authorization.

## Limits

No current authorization/authenticity proof, live user experience, rendered
visibility, semantic category validation, complete site absence, inbox delivery,
industry-wide quality, Finding/AI/report or production-readiness claim. Bounded
UTF-8 HTML <=128 KiB, <=128 explicit nav anchors; base tags/duplicate hrefs/ambiguous
or unsupported markup yield UNKNOWN. Dynamic-only navigation remains UNKNOWN.
Collectors, RA-0/RA-1/RA-2A contracts, infrastructure and all CI gates are unchanged.
RA-2B-1 and RA-2C remain outside this work package.

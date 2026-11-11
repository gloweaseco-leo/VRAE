# RA-2B-3: opt-in positive static product information Observation

Issue #18. Development base main:
`b7e2520ef48b956f89d4b300fdba9a3a5544ff3f` (RA-2B-2 Owner FINAL PASS).
Independent worktree `D:/Projects/VRAE-Codex2/.worktrees/ra2b3`, branch
`feat/ra2b3-info01-bounded-observation`. Draft for Owner independent acceptance.

## Business result and version boundary

Explicit `execute(pack, expected_pack_ref=trusted_ref,
evaluator_version='ra2b3-1.0.0')` enables the INFO-01 positive source-text subcheck.
The exact default remains `ra2b0-1.0.0`; `ra2b1-1.0.0` remains supported unchanged.
The original catalog 1.0.0, all 16 rule IDs and all rule versions 1.0.0 remain intact.
Legacy sealed fixtures and execution refs are never regenerated.

The new adapter calls the accepted `product_facts.extract` with the caller's
trusted EvidencePack pin; it does not copy or change the parser. Each supported
captured product-path page produces a separate Observation. Only extractor
`EXTRACTED` pages yield PASS: one unambiguous nonempty plain-text h1, at least one
supported TH/TD pair, and no empty/duplicate/unsupported parameter in that page's
extracted set. Even if another field is good, an empty or conflicting row leaves
the page UNKNOWN. One nonempty pair is sufficient; field labels are not matched
to an industry keyword list. Page roles are existing URL heuristics, not SKU identity.

PASS states only: "A product display name and at least one label-value
specification were observed in this captured static HTML." This does not certify
visibility, accuracy, completeness, authenticity, engineering fit, standard
conformance, buyer comprehension or commercial value. No INFO-01 FAIL or
NOT_APPLICABLE path exists in the adapter. Missing specs and empty values do not
prove website defects. The extractor's original bounds and unsupported-markup
behavior remain unchanged; rich text, DL, JS and variant controls are unsupported.

Missing original bytes, unvisited pages, incomplete responses, unsupported markup,
empty/duplicate labels or values and dynamic variants remain UNKNOWN. Existing
capture-classified 403/WAF/robots become ACCESS_BLOCKED. Browser-only evidence
cannot establish static TH/TD facts. No captured product source produces a single
UNKNOWN row with original execution coverage (including unvisited inventory).
One positive page cannot turn other unknown pages into positive observations.

## Provenance and independent replay

Every row preserves original page response metadata: source/snapshot refs, source
JSON pointer, requested/final URL, observed_at, HTTP status/error/redirect trace.
Every retained name/label/value citation preserves exact decoded text, evidence_ref,
source/snapshot refs, body SHA256, original evidence JSON pointer, URL/time,
element structural path, line, column and original opening tag. `fact_role` and
zero-based `field_index` associate each label with its value; name index is null.
Path bracket indices are ordinal among all element siblings, not XPath tag indices.
Lines are one-based, character columns zero-based, as in the accepted extractor.

Objective PASS evidence_ids are the deduplicated actual EvidencePack evidence_refs
from these citations. Unknown/blocked observations have no objective evidence_ids,
even when their bounded empty/conflicting text is available as contextual citations.
Observation validates against the unchanged original schema. `verify_execution`
recomputes the whole result from the trusted pack, including text, coordinates,
versions, statement, coverage and policy scope. A freshly recomputed output hash
cannot authorize fabricated facts. Pin trust must come from the caller, not an
untrusted document's self-reported ref; this is offline consistency, not signatures
or current collection authorization.

`python scripts/verify_ra2b3.py` defaults to offline replay of the new sealed
`ra2b3-evidence/product-observation.json`. Explicit `--write-example` derives ONLY
the new example from the already accepted RA-2B-2 synthetic pack. No old file is
rewritten. It verifies the extractor facts ref, new execution and historical refs,
then independently checks every citation against original source lines without
reusing the parser. This alternate verification code path is not Owner signoff.

Example: fictional `SV-40 flanged isolation valve`; pressure `PN 40 (4.0 MPa)`.
Original raw HTML line 10, TH column 4 and TD column 29. Full pack/source/snapshot/
evidence/Observation/execution IDs and locators are sealed in the new JSON and raw
replay logs. The original product pack and product_facts ref are unchanged.

## All 16 rules in the new evaluator

| Rule / version | Buyer task | Status in ra2b3-1.0.0 |
| --- | --- | --- |
| DISC-01 / 1.0.0 | DISCOVER | Enabled, original bounded static home nav behavior unchanged |
| DISC-02 / 1.0.0 | DISCOVER | Enabled, original bounded category-to-product href behavior unchanged |
| DISC-03 / 1.0.0 | DISCOVER | UNKNOWN, no industry/application applicability mapping |
| INFO-01 / 1.0.0 | UNDERSTAND | Enabled only for positive static h1 + TH/TD facts; UNKNOWN/BLOCKED otherwise; no FAIL |
| INFO-02 / 1.0.0 | UNDERSTAND | UNKNOWN, no independently applicable required-attribute mapping |
| INFO-03 / 1.0.0 | UNDERSTAND | UNKNOWN, no language judgment |
| TRUST-01 / 1.0.0 | TRUST | UNKNOWN, no verified company identity parser |
| TRUST-02 / 1.0.0 | TRUST | UNKNOWN, no contextual proof/authenticity validation |
| TRUST-03 / 1.0.0 | TRUST | UNKNOWN, no same-entity consistency resolution |
| CTA-01 / 1.0.0 | INQUIRE | UNKNOWN, no visible CTA with proven href |
| CTA-02 / 1.0.0 | INQUIRE | Enabled, original bounded product-to-contact href behavior unchanged |
| CTA-03 / 1.0.0 | INQUIRE | UNKNOWN, no viewport geometry evaluator |
| SEO-01 / 1.0.0 | SEARCH_TECHNICAL | UNKNOWN, no applicable metadata combination evaluator |
| SEO-02 / 1.0.0 | SEARCH_TECHNICAL | UNKNOWN, no semantic product crawlability evaluator |
| TECH-01 / 1.0.0 | SEARCH_TECHNICAL | UNKNOWN, no standalone response-metadata Observation bridge |
| TECH-02 / 1.0.0 | SEARCH_TECHNICAL | UNKNOWN, no contextual resource/heading evaluator |

Twelve candidate rules remain deferred. Original GAPS/readiness messages are
unchanged to retain historical output identity. Journeys still compose only
DISC-01/02/CTA-02, without adding product-info facts to the journey denominator.
FindingBuilder remains untouched and accepts only `ra2b1-1.0.0`; tests explicitly
prove it rejects the new execution with either a new or an old claimed evaluator.
Codex 1's RA-2D benchmark files and denominator are untouched.

## Verification and remaining gates

Red log: actual new positive test fails with RULE_VERSION_UNSUPPORTED before
implementation. Green log: dedicated INFO-01 cases including captured positive,
single-pair labels without keyword inference, mixed pages, empty/conflict/variants,
raw/visit gaps, WAF/robots/403/404/500, malformed/JS input, Browser-only input,
legacy default compatibility and FindingBuilder refusal. Resealed output mutations
cover names/labels/values, line/column/path, evidence IDs/refs, source/snapshot,
hash/time/URL, tenant/run/policy, versions, statement, result and coverage. Pack
tampering and independently valid cross-scope/old packs must fail the trusted pin.

Full Python 3.11/3.13 checks and all RA-2A/B0/B1/B2/C0/B3 offline replays use
`python docs/03-engineering/ra2b3-evidence/regress.py`. Commands, interpreter, source
head, exit codes and original output are retained per interpreter. Existing host
Linux isolation skips remain explicit; actual isolated-http/browser gates run in
the four-job hosted workflow. Final head/base/PR merge SHA and job/artifact links
will be recorded in the Draft PR after completion, without changing tested source.

Only the execution opt-in dispatch, new INFO-01 adapter, dedicated tests/replay/
evidence/docs change. No extractor, FindingBuilder, benchmark, collection, browser,
security, schema, industry pack, frozen plan, CI or historical example changes.
No real website, external model, report/share feature, RA-3, merge or deployment.

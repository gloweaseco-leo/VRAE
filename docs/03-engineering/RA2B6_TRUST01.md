# RA-2B-6: explicit bounded positive TRUST-01 (Draft, Owner audit pending)

## Current Phase B implementation

The sequencing gate was visibly satisfied before any dispatcher edit. Owner
FINAL PASS for PR #29 exact head `33f2fb93755ee347ac820894d66b74747dcf3984` is recorded at
https://github.com/gloweaseco-leo/VRAE/pull/29#issuecomment-6796755776 . GitHub reports
PR #29 MERGED at 2026-11-11T13:12:50Z, main
`8c1e8960c1aa50af359d180e97fcb5d658bf0590`. After fetch, that accepted main was merged
without conflicts at `d977d86621672c3015733e0e5ad8929a47e4b574` (parents: Phase A
checkpoint `888229cbe7992b7b0fd2c27147a91648991fe42a` and the accepted main).
No unreviewed branch, cherry-pick, rebase or force-push was used.

Only then was execution.py minimally extended for explicit
`evaluator_version='ra2b6-1.0.0'`. It inherits the accepted five bounded checks
DISC-01/02, INFO-01, CTA-02 and SEO-01, and adds this sixth TRUST-01 source-only
subcheck. All other fifteen execution rows are exactly the ra2b4 rows for the
same pack; journey composition and coverage stay unchanged. Ten rules remain
deferred UNKNOWN. All 16 IDs, rule/catalog versions 1.0.0 and old default remain.
Historical ra2b0/b1/b3/b4 stay byte-for-byte compatible with their sealed refs and
keep TRUST-01 disabled/UNKNOWN. New-version execution remains private like ra2b4.

This is Draft opt-in code awaiting Owner independent acceptance, not production
authorization or a declaration of trustworthy companies. All scope/status rules
below still apply. verify_execution replays the complete new execution against
the caller-pinned pack with the expected new evaluator version, including every
original citation, metadata edge, policy/run scope and coverage. Accepted ra2c0
and ra2c1 FindingBuilders reject both the real new execution and resealed old-version
spoofs. No new FindingBuilder or report integration is included.

New enabled-version demo: `python scripts/verify_ra2b6_execution.py`. It loads the
separate sealed `tests/rules/fixtures/trust01-execution.json`, reproduces nine fixed
synthetic packs, verifies all execution pins and all four historical refs per pack,
checks original bytes/positions without the source parser, and demonstrates
simultaneous source-only SEO-01 and TRUST-01 positives. Default writes nothing;
explicit --write-example writes only the new execution fixture. No historical or
Phase A preparation fixture was rewritten. The earlier
`python scripts/verify_ra2b6.py` still replays preparatory wrappers with false
trust01_enabled, and old ra2b3 remains disabled; that wrapper is not an evaluator.

Phase B has 104 dedicated tests, including nine-case status/inheritance matrix,
complete resealed RuleExecution forgery, strict pack/version pins, and actual old
FindingBuilder refusals. Phase B red genuinely failed RULE_VERSION_UNSUPPORTED
after the accepted main merge but before dispatcher implementation. Full raw
Phase A and Phase B evidence are retained separately. Final exact head/latest-main
four hosted CI links and actual counts are recorded in the Draft PR.

## Archived Phase A checkpoint (historical gate state)

The following describes Phase A at head 888229c, before the visible PR #29
merge gate. Its source, pins and original logs are preserved. Its blocked status
does not describe current Phase B source; the pure preparation wrapper remains
intentionally PREP_ONLY even when consumed by a separate opt-in execution.

### Phase A: PREP ONLY / INTEGRATION BLOCKED

Issue #30. Development base: Owner-accepted main
`a55b362cad7147b2c8da31a7842f6d4f36eba5fa`. Independent worktree
`D:/Projects/VRAE-Codex2/.worktrees/ra2b6`, branch `feat/ra2b6-trust01-optin`.

**TRUST-01 NOT ENABLED.** This checkpoint is a pure preparatory adapter and
synthetic validation, not an enabled diagnostics-rule milestone. PR #29 owns
shared execution dispatch until independently Owner-accepted and merged.
Phase A does not edit execution.py, __init__.py, readiness.py or any SEO file.
Phase B may begin only after GitHub main actually includes accepted PR #29;
first safely merge that accepted main, then add a new explicit evaluator version.
No unreviewed branch import, rebase, force-push or self-merge is authorized.

## Pure adapter and replay boundary

`vrae.rules.trust01.prepare(pack, expected_pack_ref=caller_trusted_pin)` calls the
unchanged accepted `trust_facts.extract` itself, not a caller-supplied facts dict.
It returns a deterministic `tp-`-addressed Phase A preparation with one bounded
TRUST-01 Observation row, explicitly `phase=PREP_ONLY / trust01_enabled=false`.
`evaluate_trust` exposes those pure rows for a future separately gated dispatcher.
No import of execution or shared dispatcher is needed in the adapter.
`verify_preparation` fully replays from the trusted EvidencePack and compares
canonical bytes. A detached Observation or recalculated facts/Observation/wrapper
hash cannot prove the preparation. No RuleExecution is created in Phase A.

Frozen row metadata is TRUST-01 / rule 1.0.0 / buyer task TRUST. Catalog and
schema remain unchanged. Complete original source facts, their version and ref,
individual primary/label citations, source pages and response edges, tenant/run/
policy/terms scope, capture times, body hashes, raw elements, line/column/path,
coverage and unvisited inventory remain inseparable row context. Prepared PASS
fact IDs are only the deduplicated actual pack refs for qualifying name/intro/link
citations. ADDRESS text remains context, not a substitute for any prerequisite.
UNKNOWN/BLOCKED rows have empty objective evidence IDs even when source text is
available as context. Output is detached canonical JSON and bounded to 8 MB.

## Independent prerequisites

The source extractor's EXTRACTED flag alone is insufficient. The adapter requires:

1. Exactly one distinct consistently declared company/organization name string.
   Organization-scope name and exact Company/Organization/Legal name table labels
   (including the accepted Chinese equivalents) qualify as self-declarations.
   **Brand name alone does not qualify.** No legal truth or entity ownership is verified.
2. At least one structured, nonempty SELF_DESCRIPTION original paragraph.
3. At least one retained supported STATIC_CONTACT_LINK with original text/href,
   coordinates and evidence refs. Same-origin contact path or mailto/tel literal
   presence is not reachability, deliverability, ownership or a completed inquiry.

PASS statement is exactly: “At this capture, website source contains explicit
self-declared organization text, company introduction and at least one static
public contact link.” This is source text only, not rendered visibility, company
legitimacy/trustworthiness, factory/certificate/qualification authenticity, legal
due diligence or fraud screening. No FAIL_WITH_EVIDENCE or NOT_APPLICABLE path exists.

## Conservative reducer / scope matrix

Claimed scope is **all actual captured HTTP HOME/ABOUT/CONTACT pages plus known
discovered unvisited candidates in this pinned pack**, not the whole website.
Unverified role names without a discovered URL do not invent missing pages.
A single HOME page with all three retained facts and a mailto literal can qualify;
there is no mandatory /about URL if the original structured introduction is on HOME.

| Bounded inputs | Prepared row result |
| --- | --- |
| All relevant captured pages EXTRACTED; no unvisited relevant candidates; independent name + intro + link all retained | PASS |
| Extractor EXTRACTED but no SELF_DESCRIPTION | UNKNOWN |
| Extractor EXTRACTED with only Brand name | UNKNOWN |
| Any relevant captured page UNKNOWN, including JS, raw absent, empty/unstructured, conflicting names or error response | UNKNOWN |
| Any known relevant discovered page NOT_VISITED | UNKNOWN |
| Any relevant captured page ACCESS_BLOCKED (403/WAF/robots), even if another page supplies all three facts | ACCESS_BLOCKED |
| Contact target captured 404/410/500 | UNKNOWN for unresolved declared scope; literal href and full response edge retained; no defect |
| Contact target captured 403 | ACCESS_BLOCKED; literal href and full response edge retained; no company verdict |
| Repeated equal declared names / duplicate hrefs | Keep every original citation/coordinate; collapse only exact trimmed case-folded name equality and evidence-ID set |
| Conflicting companies or same brand with distinct legal self-name strings | UNKNOWN; no brand-to-legal-entity resolution |

ACCESS_BLOCKED means at least one relevant captured page was blocked; the row
explicitly lists blocked indices and all other source statuses. It does not label
every page blocked. No aggregate PASS hides an unknown/unvisited/blocked selected
page. These conservative target-error outcomes preserve uncertainty about scope;
they do not turn a failed target into a business defect. Successful HTTP metadata
also never establishes valid inquiry. Missing evidence does not imply untrustworthy,
nonexistent, unqualified or fraudulent companies.

## Offline synthetic preparations

`python scripts/verify_ra2b6.py` replays the new sealed
`tests/rules/fixtures/trust01-preparation.json`, reproduces eight fixed synthetic
transport cases and independently checks original raw source slices/hash/text.
It does not use the extractor parser for line/column checks. Default replay writes
nothing; explicit --write-example writes only this new preparation fixture.
It also verifies accepted ra2b3 TRUST-01 stays disabled and UNKNOWN.

Cases: complete Heshan Meridian Valve Works source scope; no introduction despite
extractor EXTRACTED; brand-only Harbor Motion; robots block not rescued by captured
contact; contact 404 preserves literal; single HOME Fictional Pump Works with mailto;
dynamic ABOUT; absent original bodies. Full packs, original bytes, source facts
refs, prepared rows and preparation pins are retained separately from all accepted
historical fixtures. Name example: original ABOUT line 3 / column 0,
`/html[1]/main[1]/h1[1]`, text `Heshan Meridian Valve Works`; introduction is original
line 6, contact anchor original line 8 / column 0. Manufacturing claims are quoted
as self-descriptions only, not verified capabilities.

Dedicated tests cover prerequisites, brand/legal confusion, duplicate names/links,
unknown/blocked scopes, target metadata, raw absence, independent trusted pin,
cross tenant/run/policy, changed bytes and replay of rehashed name/paragraph/href/
coordinate/hash/time/metadata/coverage/Observation/wrapper forgery. Baseline default
and opt-ins are checked unchanged and new ra2b6 is rejected by existing dispatch.
Initial red is the actual missing-module collection error before implementation;
it is not claimed as a semantic assertion failure. Original red/green/replay/full
logs, interpreter, source path, source HEAD and exit codes live in ra2b6-evidence.

## Phase B remaining gate

While PR #29 remains unmerged, the shared dispatcher cannot change. This Draft
is **PREP ONLY / INTEGRATION BLOCKED**, even if Phase A CI is green. Once accepted
PR #29 is visibly in main, merge only that accepted main, add explicit ra2b6 opt-in
while preserving ra2b0/b1/b3/b4 sealed refs and default, retain all five accepted
bounded checks including SEO-01, and enable only this sixth bounded positive check.
Then verify complete new RuleExecution replay against original source text and
metadata; demonstrate ra2c0/ra2c1 builders reject the actual new evaluator; rerun
full compatibility and four real exact-head/latest-main CI gates. A detached
prepared Observation never substitutes for that work or Owner acceptance.

No FindingBuilder, Gold, old fixtures, extractor, catalog, schema, collector/browser,
policy, security/CI/infra, dependencies, frozen roadmap or Codex 1 file changes.
No real site/model, report/share, deployment, self-merge or RA-3.

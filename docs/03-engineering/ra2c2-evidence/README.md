# RA-2C-2: SEO source facts in a private diagnostic package

Issue [#31](https://github.com/gloweaseco-leo/VRAE/issues/31), new worktree and
`feat/ra2c2-seo01-finding-package` from verified accepted main
`8c1e8960c1aa50af359d180e97fcb5d658bf0590` after PR #29 merged.

The business addition is an internal diagnostic package containing independently
replayable homepage search-entry source facts, product facts and procurement-path
facts alongside a separately proven broken contact href. SEO presence is a
positive fact, never a defect or an SEO score.

Explicit opt-in only: builder `ra2c2-1.0.0` requires evaluator `ra2b4-1.0.0` and
caller-pinned pack/execution/evaluator/builder/package references. Default builder
remains `ra2c0-1.0.0`. The only production change is minimal version dispatch,
separate positive grouping and bounded limitations in `vrae/findings/builder.py`.
No rules, collector, EvidencePack, contracts, security, CI, TRUST files, old
fixtures, Gold records or frozen roadmap are modified.

## Reproduce the business example

Run `python scripts/verify_ra2c2.py` without its fixture-generation flag. The new
`tests/findings/fixtures/seo01-private-package.json` contains the complete retained
original HTML objects, EvidencePack, RuleExecution, private FindingPackage and
historical references on this new synthetic pack.

| Group/outcome | Actual sealed example |
| --- | --- |
| `checked_seo_signals` | One HOME Title/Canonical/optional description source-positive group |
| `checked_product_facts` | One SV-40 valve name and three basic specification fields |
| `checked_positive_paths` | Two captured discovery steps: home → category → product |
| Factual defect | Exactly one CTA-02 product → `/contact` captured HTTP 404 |
| UNKNOWN / ACCESS_BLOCKED | Preserved as UNKNOWN-kind items with empty objective evidence IDs; RFQ is 403 |

Title is `SV industrial valves & components`; its raw retained source contains
`&amp;`. Canonical href is `/`, resolved to `https://example.org/` without fetching
that canonical target for this judgment. Exact tag text, line/column/character
ranges, evidence/source/snapshot IDs, body hash, capture time, response metadata,
rule version and recorded capture scope remain in the inseparable provenance.
The 404 Finding preserves the original source href, target source/snapshot/status,
error and redirect trace, plus the unchanged native Evidence bridge/graph guard.

The sealed package is private, NOT_APPROVED and not shareable. Missing/conflicting/
external/dynamic/unretained metadata stays UNKNOWN, blocked access is not a defect.
Only actual captured 404/410 href failures can create objective defect items.
Title/Canonical presence does not prove indexing, rankings, crawler access, SEO
health, canonical selection, target availability or whole-site completeness.
Robots/sitemap remain UNKNOWN without separately resolvable evidence. No customer
report, public artifact, new review authority or human Gold conclusion is created.

## Actual engineering evidence

- `red.log`: the pre-change builder rejected the new explicit version with
  FINDING_INTEGRITY. The first positive test passed after the minimal adapter.
- Dedicated tests cover original source resolution, schema/native evidence
  bridge, 404/410 versus 200/403/500/503, partial/ambiguous/blocked metadata,
  optional description, and independently rehashed package/execution forgeries
  of title/canonical/tags/locators/metadata/scope/version/404 evidence and private,
  approved or shareable state. Corrupt original bytes and all trusted-pin
  mismatches are rejected. Historical C0/C1 package canonical bytes/refs and
  default dispatch are checked against unchanged sealed fixtures.
- `regress.py`, `python311/summary.json`, `python313/summary.json` retain full
  actual command exits and outputs: compile, Ruff, mypy, full pytest, pip check,
  every accepted historical RA-2A/B/C/D replay, new C2 replay, simulated review
  and the forged-Gold rejection (expected exit 1).
  Both Python 3.11/3.13 full runs passed 1096 tests with 25 host-only lab skips;
  all 19 commands per version matched expected exits. There are 94 dedicated
  SEO Finding integration tests. Hosted labs separately run the skipped cases.
- `replay.log` is the first sealed replay. Final replay output is command 15 in
  each regression directory. Regression logs preserve the historical
  GOLD_LABEL_PENDING / QUALITY_GATE_NOT_EVALUABLE result and original 26 units.
- Known Windows sandbox pytest temp-directory denial was encountered in earlier
  work packages. These full regressions use the approved environment outside
  that filesystem sandbox, without changing or skipping tests to accommodate it.
  Redirected UTF-16 diagnostic logs are converted to UTF-8 and diagnostic line
  endings/trailing whitespace normalized; original sealed bodies/refs are intact.
- Final exact HEAD/base, hosted four-job CI and raw browser artifact digest are
  recorded in the Draft PR after commit; original red/green records stay here.

Stop at Draft for Owner independent audit. No self-merge, deployment or RA-3.

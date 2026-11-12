## Independent RA-3B QA: frozen tests, honest prerequisite RED

Refs #43, companion to functional Draft PR #42 / Issue #40. New isolated
`test/ra3b-independent-adversarial` worktree from accepted main
`8379e5f63d3feaa66a646d8a19d866a693162c99`, after actual RA-3A #41 merge.
Only new Codex-1 exclusive QA paths are added; no production, developer tests,
historical fixtures/Gold, CI, dependencies or Codex-2 branch modifications.

The independently committed V1.1/Issue #40/#43 matrix precedes candidate module
inspection. It covers real evidence IDs attached to invented legal registration,
ISO/factory/ranking/conversion/revenue/causality claims; cautious prose needing
human review; source/scope tampering and rehash; cross-pack/tenant swaps;
injection, false approval/sharing, abstention and one-to-one claim provenance.
Source consistency cannot prove external authenticity or business outcomes.

- Matrix commit: `fe73cea79e87b8b2f8085e0b554fcca055ab1a2f`.
- Final source freeze: `68336821bb2b8c919b0d04bd86400c165329d9a6`.
- Final freeze manifest commit: `0c1fc1c2be98058c15d5fad7041c02099ef231fb`.
- Test Git blob: `e2f188fe234db3131d6ea1604b05d25f4ffd8e61`.
- Test SHA256 (Git/LF bytes): `74d595b26f3ba570029194966902568e0365d104eb53e8056741087427892209`.
- Inputs Git blob: `7fa3a75e3001ad9c95abee2aff66a2b73a32e740`; 14 independent synthetic captures.
- 224 **planned** parameterized cases; no claim these executed/passed on main.

Python 3.11.15 and 3.13.13 on main plus frozen QA each produce genuine
**PREREQUISITE_RED**: independent QA and full pytest exit 2, one collection error,
zero skips, missing `vrae.interpretation`. No skip/xfail/stub/fake GREEN. All
non-feature engineering checks, 14 source fixture replays and historical/RA3A
fixed replays are recorded separately. Full pytest does not execute past its
collection failure; this is not a full-regression PASS or a candidate defect.

Read [matrix, freeze history, risks and reproducible commands](docs/03-engineering/ra3b-independent-qa/README.md),
[final test/input hashes](docs/03-engineering/ra3b-independent-qa/FREEZE.json),
[static case inventory](docs/03-engineering/ra3b-independent-qa/CASE_INVENTORY.json)
and [raw local evidence index](docs/03-engineering/ra3b-independent-qa/evidence-index.json).
Initial sample corrections and two pre-candidate mutation-field corrections are
disclosed; initial records preserved. Matrix requested API-only inspection, but
the Git read returned full production guard logic; this broader read is explicitly
disclosed. No candidate test/helper/fixture was used or executed to tune outcomes.

## Pending mandatory gates — DO NOT MERGE

PR #42's observed development head `336bad8cd3a4573dbd18d360cefbff80fd33a979`
has **not** been executed/claimed final. No Owner/Codex-2 final-ready notification
was available. On that notice, fetch exact functional SHA, create a separate
detached throwaway workspace, overlay only unchanged frozen QA files, execute
both Python versions, and report genuine defects to #42 for Codex-2 to fix.
Any revised source SHA requires unchanged QA reruns. Candidate GREEN, full
combined regression and four successful real hosted CI on then-current accepted
main remain **PENDING**. Current main lacks RA3B, so this Draft's hosted test CI
is expected RED and must not be cosmetically made green.

Draft only; STOP for Owner coordination/independent review. No self-merge,
developer-branch rewrite, real model/provider/paid tokens, live website, customer
report external sharing, deployment or RA3C/D. Human Gold remains deferred 0/26,
quality N/A. Exact final QA HEAD and actual hosted run/job/merge-ref evidence are
reported in the audit comment without changing frozen source.

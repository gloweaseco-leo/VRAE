# RA-2D-0: candidate benchmark ready; human Gold pending

Accepted baseline: `e544fd31c9db66dfc7e5760d58e0503ff3fa5162`.
Independent worktree/branch; no production/INFO-01/Codex-2 files changed.
Replay: `python scripts/verify_ra2d0.py` (offline only).
Full machine-readable matrix and **26 unsigned review packets**: [report.json](report.json).
Original response bodies, policy/limits, sealed EvidencePacks/RuleExecutions/
FindingPackages and authored candidate annotations: `tests/benchmark/samples/`.

## Actual seven-sample / six-type matrix

Counts below are observed outcomes of DISC-01 / DISC-02 / CTA-02, **not human Gold
accuracy**. Two access-boundary variants count as one type, not artificial diversity.

| Sample | Real structural/coverage difference | Reachable | Broken href | Unknown | Blocked |
| --- | --- | ---: | ---: | ---: | ---: |
| static_catalog | Retained static HOME→CATEGORY→PRODUCT→CONTACT | 3 | 0 | 0 | 0 |
| mixed_broken_paths | Mixed reachable edges, explicit 404 category/contact, 410 product, separate RFQ403 | 2 | 3 | 2 | 1 |
| spa_navigation | Application shell and JS-only route, no static nav | 0 | 0 | 3 | 0 |
| waf_challenge | HTTP200 challenge body, no observed business homepage | 0 | 0 | 2 | 1 |
| robots_denied | Explicit robots refusal before business page inspection | 0 | 0 | 2 | 1 |
| redirect_budget | Same-role redirect verified, two-page budget prevents product visit | 1 | 0 | 2 | 0 |
| unretained_html | Complete responses captured but raw HTML not retained | 0 | 0 | 3 | 0 |
| **Total** | **26 active-rule units** | **6** | **3** | **14** | **3** |

The other 13 rules per sample (91 deferred rule/sample cells) and mobile layout
remain explicitly unassessed. No INFO-01 changes or semantic product-quality claim.

## Scoring / independent review boundary

- Unit: rule/version + source URL + target URL + source capture time + original
  anchor ordinal; source/target locators, href and response/trace remain reviewable.
- CANDIDATE expectations are authored in `scenarios.py`, not copied from evaluator
  results. Fixture input is recaptured with strict synthetic-only transport and
  must match its sealed pack ref. Archived pack, whole execution and whole finding
  package are independently replayed before any count.
- Candidate-only TP/FP/FN/TN uses explicit PASS/FAIL on **both** sides; positive
  means a broken-link defect. UNKNOWN/BLOCKED never count as TN or PASS. Abstained
  expected defects, unsupported defects, unjustified passes and uncovered units
  are separately visible. No precision/recall is inferred from the nine binary
  candidate comparisons (TP3/TN6/FP0/FN0); agreement is not human validation.
- Four zero-binary-denominator cases have no evaluable accuracy, not 100% accuracy.
  Actual unknown/blocked rates use observed active-rule units only, excluding the
  13 deferred rules. Missing candidate units become review gaps, never completed
  coverage. Candidate FP/FN and UNKNOWN-as-PASS counterchecks are executable tests.
- Official Human Gold TP/FP/FN/TN/precision/recall/denominator are **null / N/A**.
  `GOLD_LABEL_PENDING`, `QUALITY_GATE_NOT_EVALUABLE`. No independent reviewer,
  signature or timestamp exists; none is invented. This work package intentionally
  cannot approve or ingest self-declared GOLD_APPROVED labels.
- Each review packet binds controlled sample SHA, candidate-label hash, exact
  pack/execution/package pins, rule version, scope/time, observed source/target
  metadata and locators. Human label/reviewer/time/adjudication/conflict resolution/
  Owner approval reference remain null. Owner must independently inspect raw input
  and evidence, record decisions/conflicts and sign before official quality scoring.

## Actual negative evidence / limits

Three intentionally invalid diagnostic artifacts are actually replayed and
rejected after rehashing: target metadata removal, whole-site product/inquiry
overclaim, and treating 403 as a defect. They are logged as rejected counterexamples,
never added to verified accuracy counts. No baseline false-positive rate is claimed:
candidate agreement and rejection tests cannot establish human-reviewed precision.

`red.log` is initial missing-module collection exit2, not an assertion failure.
`green.log` records 31 focused tests passed. Full local Python 3.11/3.13 suites each
actually ran **660 passed / 25 environment skips**; all ten commands exit0 (original
five engineering gates and five fixed demonstrations). The skips are 24 dedicated
HTTP-isolation tests plus one Browser-isolation function, run in their hosted labs.
Commands, versions, source worktree and complete outputs are in `python311/` and
`python313/`. Re-run: `python docs/03-engineering/ra2d0-evidence/regress.py python311`
(or python313). Actual hosted run/job results will be attached to the exact commit
in the Draft PR. Engineering checks are separate from the unassessed quality gate.

Manifest pin:
`cdea4fd2db9abcdce16e31632c9f6c96ff27fe32eb7a37ffc8711b432655a8fa`.
Canonical JSON hashes avoid platform line-ending differences. Re-sealing is
explicit (`--write-samples`), never automatically blesses changed refs or Gold.

Known limits: seven offline synthetic samples, six structural/coverage types,
three accepted static-path rules only; no real websites, semantic product identity,
visibility, mobile assessment, real authorization/authenticity, customer accuracy,
production readiness, new framework/platform, review UI, AI or RA-3 implementation.
RA-2D FINAL PASS and precision ≥90% remain **unestablished**.

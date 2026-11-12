## Problem and behavior

AIInterpretation's global evidence IDs do not establish support for individual statements. This adds a separate private versioned per-claim binding and replay guard: exact captured source elements and bound CTA 404/410 responses can receive literal-source verification; hypotheses, paraphrases, recommendations and missing-information prose require human review. Unsupported objective assertions are rejected without altering the original text. No result approves semantics, reports or sharing.

Refs #40. New independent worktree/branch from accepted main `7e62bfcd1a900630b80b02850a0086cc950e4138`. Only interpretation, its tests, its verification script and RA-3B evidence are changed. No intelligence/RA-3A branch integration, frozen-contract changes, model/provider calls, customer reports, deployment or RA-3C/D.

## Evidence and validation

- Three independent pinned synthetic capture packs: TRUST/SEO/INFO positives and actual CTA 404/410 source-target edges.
- Frozen replay includes raw bytes, complete source packages, individual bindings, expected results, and a short private human-review queue.
- Adversarial coverage includes unrelated claims with valid IDs, company self-description inflation, traffic/revenue/ranking/sales-loss assertions, source/position/redirect/status/policy/version forgery, cross-capture/tenant swaps, quote laundering, source/suggestion/ID injection, privilege escalation, invalid JSON/Unicode and bounds.
- Historical Git-blob SHA-256 checks preserve 70 contract/rule/finding/Gold-related files. Deferred human Gold remains 0/26.
- Python 3.11/3.13 full regression and four hosted CI results will be pinned in the final audit handoff on final HEAD and then-current accepted main. This PR remains Draft pending those results and Owner audit.

Demo, API trust boundary, matrix and limitations: [RA-3B evidence](docs/03-engineering/ra3b-offline/README.md). Injection pattern matching is conservative; safety rests on closed-world literal verification, mandatory human review for prose, and the absence of execution/approval/sharing capabilities. Source consistency does not establish external authenticity or current authorization.

STOP for Owner audit. No self-merge.

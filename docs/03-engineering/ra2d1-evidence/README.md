# RA-2D-1 evidence — human work remains pending

Baseline `1f88cc4148d2e905c387af82f5943683d3507a72`, independent worktree/branch.
Reviewer entry: [26-row Markdown](../ra2d1-review/reviewer.md) /
[CSV](../ra2d1-review/reviewer.csv) / [blank JSON](../ra2d1-review/review-input.json).
[Workflow, import/signature trust contract and limits](../ra2d1-review/README.md).

All actual human fields remain blank. Default read-only replay:
`python scripts/verify_ra2d1.py` → HUMAN_REVIEW_READY / GOLD_LABEL_PENDING /
QUALITY_GATE_NOT_EVALUABLE, 0 verified /26 pending, metrics N/A. No real authorized
human review, signing key, signature or approval is supplied by this package.

## Actual red / green / negative evidence

- `red.log`: initial missing-module collection exit2, not a semantic assertion.
- `red-simulated-origin.log`: actual **1 failed /34 deselected**. A controlled
  positive-verifier stub plus adversarial relabeling of DEMO metadata caused two
  simulated rows to count as eligible in the prototype. No real signature or
  authorization was involved. Reserved SIMULATED_* identities/references now
  remain ineligible independently of origin/verifier; the same test is green.
- `green.log`: 35 focused tests passed. The final full run adds one pure simulated
  partial-review policy case (36 new tests total). Partial real review never gives
  an evaluated overall gate; warnings/provisional statistics remain separate.
- `negative-forged-gold.log`: deliberately invalid SIMULATED Gold stamp rejected.
- `temp-permission311.log` / `temp-permission313.log`: initial full local runs had
  723 passed /25 skipped /4 tmp_path setup errors because Windows sandbox denied
  access to the shared pytest temp directory. Raw failures are retained. Both
  complete runners were rerun outside that sandbox after tool approval; no tests
  removed, weakened or added to skip lists.
- Final `python311/` and `python313/`: each **728 passed /25 existing environment
  skips**. All 13 command outcomes match expectations: normal commands exit0;
  the forged-stamp CLI deliberately exits1. Interpreter, command, expected/actual
  exit codes and complete outputs retained in each summary/log set.
- The 25 skips are 24 dedicated HTTP-isolation cases plus one Browser-isolation
  function, executed separately by the original hosted security jobs.

Full replay: `python docs/03-engineering/ra2d1-evidence/regress.py python311`
(or python313). DEMO: `python scripts/verify_ra2d1.py --reviews
docs/03-engineering/ra2d1-review/SIMULATED_NOT_HUMAN_GOLD.json`.
It demonstrates FP/FN disagreement without becoming real human Gold.

Original seven-sample manifest, sample pins, old report and historical replays
remain byte-for-byte unchanged. Git diff against baseline contains no production,
old benchmark, INFO-01, safety/CI/schema/lock or frozen-document edits.

Hosted exact-HEAD run/job logs and raw Browser artifact audit will be attached in
the independent Draft PR when complete. Engineering success is **not** Gold
approval, accuracy ≥90%, RA-2D FINAL PASS, production readiness or RA-3 authority.

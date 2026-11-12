# RA-3B Owner audit handoff

Draft PR: https://github.com/gloweaseco-leo/VRAE/pull/42 — refs Issue #40; no self-merge.

Accepted base independently fetched/read back: `7e62bfcd1a900630b80b02850a0086cc950e4138`. The new worktree/branch never reused PR #37 and never merged unaccepted PR #41. Only the four Issue #40-owned areas changed. Main is fetched again immediately before the final evidence commit and again after final hosted CI. The final PR body records the exact final HEAD, accepted-main readback and four final job URLs; recording that completion in a new commit would otherwise move the tested HEAD.

## Executed local validation

| Check | Result | Evidence |
| --- | --- | --- |
| Python 3.11 full regression | 1530 passed, 25 skipped, no failures/errors | `pytest311.xml` |
| Python 3.13 full regression | 1530 passed, 25 skipped, no failures/errors | `pytest313.xml` |
| Independent RA-3B suite | 83 passed | `interpretation.xml` |
| Replay portability correction, full repository | 1 passed | `replay-portability.xml` |
| compileall / ruff / mypy / pip check / CLI fixed replay | Both versions all exit 0 | `py311-checks.json`, `py313-checks.json`, numbered logs |
| TRUST/SEO/INFO and CTA 404/410 fixed replay | Private source binding verified; prose review required | `fixed-replay-result.json`, frozen test fixture |
| Original history | All 70 accepted Git-blob SHA-256 checks in full repo | `preserved-history.json` and both CLI logs |

Full Windows runs started on core guard candidate `b3182a9421d71f0cd198b4265458c394fedc138e`; core guard bytes remain unchanged in the portability correction `85581d3`. The replay/CLI portability correction was separately rerun after the change. The **final hosted full regressions on final HEAD** are the authoritative final-revision verification. Local skips are the original 24 isolated HTTP cases and one isolated browser case, not substituted synthetic passes. They execute in their genuine hosted isolation jobs.

Initial default-temp Windows attempts encountered five pytest temporary-directory permission errors; full reruns used separate writable basetemp directories. An initial test-authoring type error was corrected before these recorded successful runs. No existing tests or security policy were weakened.

The first hosted HTTP failure (`b3182a9`) exposed the new replay test's dependency on a docs file omitted by the unchanged minimal image. `initial-ci-red.json` and `initial-ci-red-log.json` retain the actual negative result. The manifest is now supplied in new test fixtures. The explicit isolated-layout invocation lists unavailable docs instead of claiming to verify them; all retained source/evidence/contract/test history checks still run. The CLI/full repository checks require every historical path. No Dockerfile, CI, collector, browser or security code changed. Final green evidence must come from a new genuine run, not relabeling this failed job.

## Review boundary

See `README.md` for the per-claim API, business demonstration and complete negative matrix. Only exact generated narrow source statements can pass literal binding verification. Free prose cannot gain semantic approval, and arbitrary unrelated objective assertions are rejected even with valid IDs. Numeric type laundering is rejected using canonical-byte equality rather than Python's bool/int equality.

Raw bytes, positions, complete citations, full C3 artifacts, caller-held scope/version/hash pins and per-claim checksums are replayable in `tests/interpretation/fixtures/fixed-replay.json`. Three capture packs remain distinct. No global list is used as individual semantic proof. Human hypotheses and recommendations remain private `HUMAN_REVIEW_REQUIRED`, and all guard results remain `NOT_APPROVED`, unshareable and not reports.

No real model/provider call, token purchase, customer report, deployment, RA-3C/D, or human-Gold evaluation took place. Gold remains 0/26 unevaluated. Source consistency is not external authenticity or current authorization; instruction pattern checks are conservative and do not claim universal injection detection. STOP for independent Owner audit.

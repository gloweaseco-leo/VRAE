# PR #44 final accepted-main integration

Authority: [Owner final integration GO](https://github.com/gloweaseco-leo/VRAE/pull/44#issuecomment-6812567914).
Functional #42 was independently confirmed actually merged. Fresh accepted main:
`1d9d08ec3b99fc10ff7ea181d210250841ee39a3`.

## Exact integration and immutable sources

Original independent QA worktree/branch retained:
`D:/Projects/VRAE/.worktrees/ra3b-independent-qa`,
`test/ra3b-independent-adversarial`. Clean before fetch/merge. Executed exactly
`git merge --no-edit origin/main`, conflict-free ordinary merge:
`6846fbe2eea46611758bb661de8ecc62f679f9d2`.
Ordered parents: prior QA `5e34075b671106ad37a034b76e01b8aa8eaa5de7` + accepted
main `1d9d08ec3b99fc10ff7ea181d210250841ee39a3`. No rebase, force push or cherry-pick.

Recursive tree and working Git hash verification proves:

- All **1307 accepted main files** retain exact blobs and modes;
  includes **35 RA3B files**, **19 RA3A files**, **177 prior QA files** and all
  rules/findings/contracts/Gold/security/CI/dependencies/history.
- All **80 original exclusive QA files** retain exact prior QA blobs, including
  original V1 source snapshot, 223/1 RED/JUnit/raw/reproduction, Owner adjudication
  V2 patch/manifest/224-case source, all 14 input captures and V2 GREEN records.
- All **1387 integrated working files** match their Git blobs.
  [source-proof.json](source-proof.json) contains the complete original main file
  list/blob/mode map and QA-exclusive list, including explicit RA3B/RA3A/prior-QA paths.
- Four old raw archives rechecked for exact archive digest and all **265 entries**
  for byte count/SHA256. No historical record is rewritten or relabeled.

Fixed source pins remain: V2 test blob `84dcb51e794310d5bfa6426042e50c1d785bcef6`,
SHA256 `7317c9425370e86b46fede118d9be5bed533ba0c11486df6fc163b48413451a3`;
input blob `7fa3a75e3001ad9c95abee2aff66a2b73a32e740`, SHA256
`7a8c8177b1ef2bc7baa15628d621b5c2a89ae4ac0b50a589553d961c10282428`;
original V1 source snapshot blob `e2f188fe234db3131d6ea1604b05d25f4ffd8e61`.

## Fresh local full repository and independent regression

Both runs test exact integrated merge HEAD
`6846fbe2eea46611758bb661de8ecc62f679f9d2`. The later evidence commit adds only
this new QA documentation/record directory; frozen source and all accepted main
files remain unchanged. Four new hosted jobs must separately verify final exact
QA HEAD + current accepted main, as pinned in the final PR audit comment.

| Runtime | Full passed | Failed / errors | Host-only lab skips | Dedicated V2 | Prior QA in full | Commands |
| --- | --- | --- | --- | --- | --- | --- |
| Python 3.11.15 | 1872 | 0 / 0 | 25 | 224 / 0 skip | 139 | 26/26 expected exits |
| Python 3.13.13 | 1872 | 0 / 0 | 25 | 224 / 0 skip | 139 | 26/26 expected exits |

All 224 V2 cases and 139 frozen prior adversarial cases also individually pass
inside each full JUnit. No skip/xfail in independent V2. The only full-suite skips
are 24 disposable isolated HTTP cases + 1 isolated browser case, with exact node
and reason lists in summaries. They are not substituted for genuine hosted lab
execution. Security/domain/contract group passed counts are
286 /
286.

Each runtime records 26 exact commands: all 14 independent source-input replays,
compileall/Ruff/mypy, full pytest, dedicated unchanged 224-case pytest, pip check,
all 17 historic fixed verifiers (RA2A; B0-B6 and B6 execution; C0-C3; D0/D1;
RA3A offline Fake/NOT_RUN; RA3B private deterministic replay), simulated-Gold
replay and forged-Gold required rejection **exit 1**. Every expected exit matches.
The old contracts, sealed source refs and human Gold labels are not regenerated.

Tests use new per-runtime workspace-owned basetemp directories to avoid previously
observed Windows default-temp permission failures. This is an environment choice,
not a weakened test or security policy. Full local runs are serial. Before/after
source and original archive audits match and original QA worktree stays clean
through both runs. Actual commands/cwd/times/exits/log hashes are indexed.

## Original evidence and final hosted gate

[evidence-index.json](evidence-index.json) contains both complete runtime summaries
and original file size/SHA256. [local-raw.zip](local-raw.zip) losslessly retains
**62 raw files**, SHA256 `cc13edeb2e3152e3c8987d6817a6f3c2639f22004cf685c696d0cec323b24335`.
Every ZIP member was reread and independently verified. Full/QA JUnits and
summaries are also readable in `python311/` and `python313/`; existing Git text
CRLF normalization may affect readable copies, so raw hashes refer to ZIP bytes.

The final exact QA HEAD, fresh pull_request run and four job links, actual test
merge-ref/ordered parents and all original checkout log SHAs are recorded in the
PR audit comment after CI completion. Original browser ZIP must match GitHub
digest and actual 16-scenario/247-record security checks: unauthorized connections
and writes zero, cleanup verified, ordinary worker exit 0, intentional worker-kill
exit 137 and expected negative absence/cleanup probes exit 1. Earlier original-main
import RED remains historical and cannot count as this new four-success gate.

## Exceptions, limitations and stop point

- Initial sandbox read of the Owner GitHub comment was socket-denied; approved
  retry succeeded before fetch/merge, verifying exact accepted main. No stale merge.
- Setup inspections guessed nonexistent `ra3b-offline/regress.py`, `tests/domain`
  and `tests/browser/test_isolated.py`; correct accepted files were then inspected.
  These are diagnostic path lookup errors, not test regressions or source edits.
- Existing LF/CRLF diagnostics are retained; all source integrity is compared by
  exact Git blobs/modes plus working Git hashes, raw archive integrity by original
  bytes. No Git settings or fixture bytes were altered.
- Original V1 import RED, 223/1 oracle contradiction and historical recorder
  exceptions remain preserved. V2's single Owner-authorized repair is not changed
  here; no new assertion/fixture/schema/production/CI edit is made.
- Finite synthetic consistency is not universal semantic entailment, legal identity,
  certificate/factory authenticity, SEO rank, real revenue/causality or current
  authorization. Prose remains HUMAN_REVIEW_REQUIRED, private, NOT_APPROVED and
  nonshareable; literal binding cannot grant reviewer/report/share authority.
- Only fake/local interpretation/accounting behavior is exercised. No live model,
  real tokenizer/pricing/invoice reconciliation or production readiness established.
  Human Gold remains owner-deferred 0/26, quality N/A.

**Draft retained. STOP for Owner exact-SHA FINAL PASS; no self-merge. No RA3C/D,
real model/provider/paid call, live site, customer report/share or deployment.**

# INDEPENDENT_QA_V2_CANDIDATE_GREEN — exact unchanged candidate

Version: **OWNER_ADJUDICATED_QA_V2**.
Authority: [Owner final oracle adjudication](https://github.com/gloweaseco-leo/VRAE/pull/44#issuecomment-6812189251).
Owner decision on the original failure remains
TEST_ORACLE_CONTRADICTION_CONFIRMED / IMPLEMENTATION_DEFECT_NOT_DEMONSTRATED.
The original RED is preserved, not relabeled.

## Pinned source versions and narrow authorized difference

| Item | Exact pin |
| --- | --- |
| Unchanged functional candidate | `d9d4e234a01a27a4543404b7060c8867e60d0309` |
| Original frozen QA HEAD | `8b961b72ce544251e6f28177cc0ea183f7486af0` |
| Original RED evidence HEAD | `6d81b46313102d47799cead08f89b565a2eafc0d` |
| V2 source commit | `c8d32ea3719c709332e5aba921ba5612a5ec1600` |
| V2 manifest / actual QA run HEAD | `f2996b2a61511453d37a0796d018ab6a4a74539d` |
| Original test Git blob | `e2f188fe234db3131d6ea1604b05d25f4ffd8e61` |
| V2 test Git blob | `84dcb51e794310d5bfa6426042e50c1d785bcef6` |
| Original test SHA256 | `74d595b26f3ba570029194966902568e0365d104eb53e8056741087427892209` |
| V2 test SHA256 | `7317c9425370e86b46fede118d9be5bed533ba0c11486df6fc163b48413451a3` |
| Unchanged input Git blob | `7fa3a75e3001ad9c95abee2aff66a2b73a32e740` |
| Unchanged input SHA256 | `7a8c8177b1ef2bc7baa15628d621b5c2a89ae4ac0b50a589553d961c10282428` |

Only parameter node
`test_fact_tamper_even_with_recomputed_hashes[True-fact_ref]` changes its attack
construction, under explicit Owner authorization. The forged inner ref remains
`forged-codex1`; only the outer binding_ref is recomputed. Pre-validation
assertions require that the inner ref remains forged and canonical full binding
bytes differ from the original legal input. Expected rejection is not weakened.

Original source and manifest are copied byte-for-byte by Git blob to
`original-test.py.txt` and `original-FREEZE.json`; original active manifests,
all 14 synthetic inputs, matrix and old 223/1 JUnit/raw/SHA/reproductions remain
unchanged. The original source history is also retained. Exact patch:
`v1-v2.patch`; versioned source manifest: `manifest.json`; AST/diff proof:
`diff-proof.json`; unchanged 224-case parameter inventory: `case-inventory.json`.
AST nodes outside the sole function and all decorators/parameters are identical.
The `False-fact_ref` and other 222 cases preserve their exact previous paths.

## Actual dual-Python full 224-case results

| Runtime | Collected | Passed | Failed | Errors | Skipped | xfail / xpass | pytest exit | Actual duration |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Python 3.11.15 | 224 | 224 | 0 | 0 | 0 | 0 / 0 | 0 | 142.40s |
| Python 3.13.13 | 224 | 224 | 0 | 0 | 0 | 0 / 0 | 0 | 134.12s |

No skip/xfail/stub, deselection, assertion suppression or temporary implementation.
These are **actual** counts and exits, not planned-case counts. This is an isolated
independent-suite result, not full-repository regression or Owner FINAL PASS.

Run from new detached worktree
`D:/Projects/VRAE/.worktrees/ra3b-qa-v2-candidate-d9d4e234a01a`:

```text
D:/Projects/VRAE/.venv/ra1a311/Scripts/python.exe -m pytest -q tests/interpretation/test_ra3b_independent_adversarial.py --tb=short --junitxml=D:/Projects/VRAE/.worktrees/ra3b-independent-qa/.venv/ra3b-independent/qa-v2/python311/qa.xml
D:/Projects/VRAE/.venv/ra1a313/Scripts/python.exe -m pytest -q tests/interpretation/test_ra3b_independent_adversarial.py --tb=short --junitxml=D:/Projects/VRAE/.worktrees/ra3b-independent-qa/.venv/ra3b-independent/qa-v2/python313/qa.xml
```

The V1 candidate worktree/overlay remains separate and unchanged. The new V2
candidate contains only two untracked QA overlays: test and input JSON. Before/
after each full run, the external recorder verifies exact candidate HEAD/tree,
zero tracked candidate changes, exact overlay bytes/Git hashes and correct actual
guard/test imports. No Codex-2 branch/worktree or production source modifications.

## Preserved RED to GREEN comparison

| Runtime | V1 observed | V2 observed | Identical inventory | Other 223 outcomes |
| --- | --- | --- | --- | --- |
| Python 3.11 | 223 pass / 1 fail | 224 pass / 0 fail | same 224 node IDs | all remain PASS |
| Python 3.13 | 223 pass / 1 fail | 224 pass / 0 fail | same 224 node IDs | all remain PASS |

`candidate-d9d4e234a01a/red-green-comparison.json` compares full JUnit node sets
and verifies the only outcome difference is the Owner-adjudicated parameter.
Old RED/JUnit/raw ZIP under `../phase-b-d9d4e234a01a/` remains untouched, including
the earlier recorder exception and complete rerun. V2 has no unexpected test or
recorder failures; no old exception is erased by this GREEN.

Supplementary actual attack proof on both runtimes (not extra suite cases):

- Canonical full binding before SHA256:
  `f8601b836adabd15649683572a225d97242c496041a4c838d2705b2cf4d061bf`.
- After forged inner ref plus valid outer reseal SHA256:
  `5d598dd38136bee1a6b42bc67b275de6fbbc5e58677055bd944a7fbb99147d0c`.
- Actual inner ref remains `forged-codex1`, differs from the correct derived ref.
- Outer wrapper hash is independently valid; actual candidate verdict is
  **REJECTED / UNBOUND_SOURCE**.
- Result remains NOT_APPROVED, shareable=false, semantic_approval=false.

This now tests a surviving inconsistent inner reference under an attacker-resealed
outer wrapper, unlike the original V1 no-op. Existing positive literal proof,
prose HUMAN_REVIEW_REQUIRED ceiling, fabricated credentials/ranking/revenue and
causality, cross-tenant/capture, injection, UNKNOWN/BLOCKED and approval guards
all remain exercised by the other unchanged passing cases.

## Raw artifacts and integrity

Under `candidate-d9d4e234a01a/`: both full JUnit files, stdout/stderr, summary with
complete commands/cwd/import paths/timestamps/source hashes, setup proof, both
supplementary attack proofs, external recorder source and raw index.

Authoritative raw bytes are in **raw-evidence.zip**, **23 entries**, SHA256
`397912e34cf6b5993e05cf468fac6c480fa3bab4709d0726c85ea67d5c5a0023`.
Every original entry's size/SHA256 is listed in `index.json`; the ZIP is reread
and verified. Readable Git text copies may normalize CRLF under existing Git
configuration; original bytes remain lossless in the ZIP. No Git configuration
or production CI is altered. Earlier sandbox GitHub denial was retried with
approved access before source authorization/read-back; no source was guessed.

## Risk conclusion and stop point

Verdict: **INDEPENDENT_QA_V2_CANDIDATE_GREEN**, only for the pinned unchanged
functional SHA plus explicitly versioned Owner-adjudicated V2 suite. No production
defect demonstrated by the original contradictory case; no production fix made.

Finite synthetic consistency checks do not prove arbitrary language entailment,
legal identity/certification/factory authenticity, SEO ranking, real revenue/
causality, current source permission or customer readiness. Hypotheses/advice
remain HUMAN_REVIEW_REQUIRED; literal binding is not approval or sharing. Human
Gold is OWNER_AUTHORIZED_GOLD_DEFERRED 0/26, quality N/A.

Draft #44 remains open and unmerged. Main still lacks RA3B: automatic baseline
hosted import RED must remain honestly RED and is not this candidate's verdict.
No main integration or new combined four-success CI is claimed here. After
functional acceptance/merge, a separate Owner instruction/signoff governs QA main
integration, full-repo dual Python/replays and four new hosted successes.

**STOP for Owner FINAL PASS. No self-merge, real provider/paid model, real site,
customer report/share, deployment or RA3C/D.**

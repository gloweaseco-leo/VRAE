# RA-3B independent adversarial QA — prerequisite RED, candidate pending

Refs [Issue #43](https://github.com/gloweaseco-leo/VRAE/issues/43),
[Issue #40](https://github.com/gloweaseco-leo/VRAE/issues/40),
[functional Draft PR #42](https://github.com/gloweaseco-leo/VRAE/pull/42).
This is Codex-1 QA, not RA-3B functional development or final acceptance.

New exclusive worktree `D:/Projects/VRAE/.worktrees/ra3b-independent-qa`, branch
`test/ra3b-independent-adversarial`, starts from freshly verified accepted main
`8379e5f63d3feaa66a646d8a19d866a693162c99`. RA-3A #41 was actually merged.
No reuse/access of the Codex-2 worktree and no changes to its branch or tests.

## Independent freeze and inputs

Matrix was committed first at `fe73cea79e87b8b2f8085e0b554fcca055ab1a2f`,
before reading the functional interface. Read-only production API declarations
were then inspected from remote Git objects at development head
`336bad8cd3a4573dbd18d360cefbff80fd33a979`; that SHA is **not** claimed ready,
executed, reviewed or accepted. No candidate tests/helper/fixtures were read or
imported. Oracles come from V1.1 and Issues #40/#43, not candidate expectations.

`MATRIX.md` is the normative independent scenario/oracle freeze.
`CASE_INVENTORY.json` statically expands **224 planned cases**, not passed tests.
Frozen inputs are 14 new local synthetic captures on accepted APIs, with literal
caller-held pack/execution/package/scope/version pins. Positives independently
replay title/canonical/product/self-declared name; negatives cover 404/410/403,
WAF/robots, absent raw, JS-only/unvisited/optional missing/conflicting identity,
source instruction and a self-declared certificate string. No real website.

`build_inputs.py` is a one-time reproduction aid and refuses overwrite. Inputs
were generated before candidate execution. Initial uncommitted positive sample
lacked a structured introduction and a recognized contact element under accepted
C3; corrected using accepted contracts before the first input/source freeze.
This was QA sample preparation, not a candidate defect.

First source freeze: `780455960dd04bf1f10c2a634412b70ba56ab884`;
`FREEZE-v1.json` retains its exact original blobs/SHA256. Both initial baseline
runs are retained. A pre-candidate review of **accepted native locator/schema**
found two mutation keys should target existing `element.path` and
`snapshot.captured_at`, rather than add fields `dom_path` and `fetched_at`.
Those two mutation destinations were corrected and explicitly re-frozen; no
scenario, expected status, source input or candidate-dependent oracle changed.
`FREEZE.json` pins the authoritative final test source and unchanged inputs;
final-baseline runs must be the evidence used for that freeze. Original records
are retained, never overwritten. No candidate has been executed in either freeze.

## Honest RED and execution

Accepted main has no `vrae.interpretation`. The test imports the real public API
directly. On this QA branch, both independent QA and full pytest **really fail
collection, exit 2**, with `ModuleNotFoundError: vrae.interpretation`; JUnit has
one collection error, zero skipped, no executed feature tests. This is
**PREREQUISITE_RED**, not 224 failed assertions, feature GREEN, or a defect
attributed to PR #42. No skip, xfail, monkeypatched module, stub or hidden fallback.

Run from this worktree, separately for Python 3.11/3.13:

```text
python docs/03-engineering/ra3b-independent-qa/run_qa.py --mode baseline --expected-source <QA HEAD> --out <new-output-directory>
```

Each run records 24 commands: independent replay of all 14 source cases,
compileall, Ruff, mypy, QA/full pytest, pip check, all 15 historical RA2A/B/C/D
fixed replays, RA3A offline demo and forged-Gold expected exit 1. The runner's
exit 0 means recorded exits match expected RED; summary explicitly states
`feature_qa_pass: false`, not a passing feature gate. Raw pytest exits remain 2.
Old production fixtures, refs, rules, 139 prior QA tests, Gold, security and CI
files remain unchanged. This does not claim the original full suite executed
past its expected collection error. Historical commands are recorded separately.

## Candidate and CI gates still open

Issue #43 requires an Owner/Codex-2 final-ready notification before execution.
The last observed PR #42 head is development-only and no such notice was present.
Do not interrupt the developer or test a moving branch as a final candidate.

After final-ready notice and exact 40-character functional SHA:

```text
git fetch origin refs/pull/42/head
python docs/03-engineering/ra3b-independent-qa/prepare_candidate.py --source <exact-functional-SHA> --ready-notice <GitHub-final-ready-comment-URL>
```

Helper creates a new detached throwaway worktree, refuses any exclusive-path
collision, overlays only tracked QA files, and verifies original tracked source
is unchanged. It does not push or alter either developer branch. In that isolated
root, run the unchanged frozen suite and full regression on both Python versions:

```text
python docs/03-engineering/ra3b-independent-qa/run_qa.py --mode candidate --expected-source <exact-functional-SHA> --out <new-output-directory>
```

Requires exactly 224 QA cases, zero failures/errors/skips/xfails, full regression,
all historical replays and source identity. Real assertion failures are reported
reproducibly to PR #42, with exact source+QA SHAs, node ID, raw log and input pins.
Codex-2 fixes its own code; never change the oracle to accommodate a failure.
Any source HEAD change requires unchanged QA rerun on both Python versions.

This Draft QA PR's feature-dependent hosted CI should be honestly RED against
current main. Do not weaken/remove tests or alter CI for cosmetic success; do not
merge QA first. Four successful real hosted jobs on combined accepted RA3B main
+ frozen QA, with actual checkout merge-ref parents/artifact proof, remain a later
Owner integration gate. Baseline RED CI is not candidate acceptance evidence.

## Risks and boundaries

- Candidate GREEN/compatibility has not been established. Finite synthetic
  adversarial examples do not prove arbitrary natural-language entailment.
- Literal source consistency cannot authenticate legal entities, ISO certificates,
  factories, ownership, search ranking, conversion, delivered inquiry, revenue or
  commercial causality. Real IDs and a valid schema cannot establish these facts.
- Hypotheses/recommendations/missing-information prose keep HUMAN_REVIEW_REQUIRED;
  a source fact is not semantic approval, human review or a ShareGrant.
- Injection probes require rejection or cautious human review, no automatic
  authority and no output logging/network. Conservative safe quoting is allowed;
  this finite suite does not certify every command/exfiltration detector.
- Current SourcePolicy/real-world authorization and external authenticity are not
  established by a historical checksum. Hashes are integrity, not signatures.
- Human Gold is OWNER_AUTHORIZED_GOLD_DEFERRED 0/26, quality N/A. Fake byte-unit
  ESTIMATED accounting is not provider billing reconciliation or semantic proof.
- No real model, SDK call, paid tokens, real-site fetch, customer report, sales
  contact, deployment, RA3C/D or RA4-RA6. Draft only, no self-merge.

Final result records, raw archive/index and hosted CI links are added after actual
runs. Pending gates remain explicitly pending; do not infer a final PASS here.

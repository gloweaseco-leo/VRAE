# RA-2C-3: private TRUST self-declaration source evidence

Issue [#34](https://github.com/gloweaseco-leo/VRAE/issues/34), new worktree/branch
`feat/ra2c3-trust01-finding-package` from verified accepted main
`4b5ebe689f048ba20d38354ae7c03d4bbaf37c6a`; prerequisite PR #32 was read back as merged.

The new business capability is a private package that retains the website's
quoted organization name, structured introduction and static public contact
href with the complete verified provenance, separately from SEO tags, product
text, checked paths and actual 404/410 Findings. Explicit builder `ra2c3-1.0.0`
accepts only caller-pinned evaluator `ra2b6-1.0.0`. C0/C1/C2 and default dispatch
remain unchanged. Only `vrae/findings/builder.py` changes in production.

## Replay and observed scope constraint

Run `python scripts/verify_ra2c3.py` without the generation flag. The new
`tests/findings/fixtures/ra2c3-private-packages.json` seals the retained bodies,
EvidencePacks, executions and packages for five captures of the same synthetic
industrial site. It also pins the C0/C1/C2 results on the new positive pack.

| Contact response | TRUST result | Positive TRUST groups | Actual contact defects |
| --- | --- | --- | --- |
| 200 | PASS | 1 | 0 |
| 404 | UNKNOWN | 0 | 1 CTA-02 |
| 410 | UNKNOWN | 0 | 1 CTA-02 |
| 403 | ACCESS_BLOCKED | 0 | 0 |
| 500 | UNKNOWN | 0 | 0 |

All five preserve separate SEO and product source-positive groups. The positive
capture has three checked paths. Broken captures have two positive paths plus
exactly one captured source href → target HTTP 404/410 edge with the native RA-0
Evidence bridge. TRUST UNKNOWN retains available source facts and response
metadata as candidate provenance, with no objective IDs, severity or defect.

**Resolved Owner interpretation:** Issue #34 originally described a single package
with positive TRUST and one broken contact. The frozen B6 evaluator makes that
combination impossible: all HOME/ABOUT/CONTACT captured pages are in the TRUST
aggregate, and any contact 404/410 makes it UNKNOWN. `scope-reproduction.log`
records the original rule-only experiment before adding the contact self-link
used by the final fixture; the sealed replay demonstrates the same constraint.
No rule or status was changed to manufacture simultaneous PASS and a defect.
The five status captures are a matrix, not a claim of simultaneous PASS and a
contact defect. The issue was raised during development. Owner's targeted
[clarification on Issue #34](https://github.com/gloweaseco-leo/VRAE/issues/34#issuecomment-6798751555)
explicitly supersedes the contradictory fixture expectation: use two separately
pinned packs, positive TRUST/SEO/INFO/paths and CTA defect plus TRUST UNKNOWN.
The sealed positive and 404 cases implement that clarification; 410/403/500 are
additional status-matrix proofs. No new permission or rule change is needed.

## Integrity and actual tests

- `red.log`: the unchanged builder rejected the new version (FINDING_INTEGRITY).
  Its first positive test passed after minimal opt-in dispatch/grouping.
- `scope-probe-command-error.log`: the first shell-inline scope probe had a
  quoting SyntaxError. The corrected command's actual results are preserved
  in `scope-reproduction.log`; no collection/rule error was suppressed.
- `focused-first.log`: 101 passed / 2 failed because two test input assumptions
  disagreed with the frozen scope. A category-only unvisited candidate does not
  block TRUST, so the test now creates an actual unvisited ABOUT candidate.
  A browser source with an uncaptured HOME viewport does block TRUST; its test
  now requires UNKNOWN and no source promotion. Production rules stayed intact.
- `focused-green.log`: 103 passed after those corrections. `focused-final.log`:
  108 passed, including the sealed matrix, old evaluator/preparation rejection
  and private-state execution tampering. C0/C1/C2 canonical bytes/refs and old
  default dispatch are checked against original sealed fixtures.
- `regress.py` records actual exits, stdout/stderr for both full Python versions:
  compile/Ruff/mypy/pytest/pip check, every historical replay including B6 Phase A
  and execution, new C3 replay, simulated Gold and forged-Gold rejection (exit 1
  expected). Full logs/summaries are in `python311/` and `python313/`.
  Python 3.11/3.13 full pytest each passed 1308 tests with 25 host-only lab skips;
  no skip/xfail was added. Hosted HTTP/browser jobs execute the isolated labs.
- Source tests independently resolve exact raw elements from original body
  hashes and line/column positions, source/snapshot/evidence IDs, URL/time,
  original HOME/CONTACT roles, label text, HTTP target state/trace, tenant/run/
  policy and rule/evaluator/builder refs. Rehashed package/execution/source-body
  forgeries and private/approved/shareable changes are rejected.
- Diagnostics converted from PowerShell UTF-16 use UTF-8; diagnostic line
  endings and trailing whitespace are normalized. Original sealed bodies,
  historical files and package refs are never rewritten. Full regressions use
  the approved environment outside the known Windows pytest temp sandbox denial.
- Final exact HEAD/base, hosted CI, raw security artifact hash and any Codex-2
  independent QA findings are recorded in the Draft PR. Codex-2's exclusive test,
  fixture and independent-qa paths are neither edited nor included in this branch.

## Risk and limits

1. Positive TRUST and a captured contact defect are demonstrated with separate
   pinned packs per Owner clarification. They cannot be asserted as one capture.
2. Source self-declarations do not authenticate a legal entity, factory,
   certificate, qualification, ownership, true capability or trust score.
3. Static mailto/tel/href presence and recorded HTTP response metadata do not
   prove deliverability, completed inquiry, contact ownership or current access.
4. Aggregate scope is deliberately conservative: missing relevant pages/raw
   HTML, conflicting names or blocked evidence remain UNKNOWN/ACCESS_BLOCKED.
5. Private=true / NOT_APPROVED / not-shareable is retained; there is no customer
   report, public share grant or new external review authority. Human Gold is
   still 0/26, GOLD_LABEL_PENDING / QUALITY_GATE_NOT_EVALUABLE.
6. Codex-1's tests are not Codex-2 independent QA or Owner FINAL PASS. Any separate
   QA repro must be resolved by Codex-1 without editing Codex-2's exclusive files.

Draft only. No self-merge, deployment, real enterprise site, AI/model call or RA-3.

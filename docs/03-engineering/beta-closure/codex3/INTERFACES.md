# First missing interface and minimal integration handoff

Accepted main447005b only. No unmerged sibling code/data is included. This is an interface proposal,
not a request to weaken Guard, SourcePolicy, RLS, origin/epoch, lease or COMMIT guards.

| Exact accepted seam | What the real S1 call proves | What it does not provide | Responsible dependency |
|---|---|---|---|
| `apps/api/ra4b.py` -> `store.admit` -> `ra4b_test.admit` | HTTP202 after committed request/run/job for accepted-404/200 | New raw-input processing or generated report persistence | C1/Owner versioned processing bridge |
| `ra4b_test.claim` in migration0004 | job/run/token/lease sequence/until, current authority checked | SourcePolicy/raw input/Guard/report locator output | C1 B4 contract |
| `worker/ra4b/main.py` | Current low-role claim and original finish -> durable DONE | No Collector, execute, build_findings, Guard or build_draft invocation | C1/Owner |
| `ra4b_test.status` in migration0004 | Caller-bound request/job state and report metadata from JOIN to existing reference | Proof that this job generated that report, or assigned Reviewer projection | C1 B4-P2 |
| `tests.reporting.synthetic.proposal_bundle` / `ra3b-1.0.0` catalog | CTA404/410 fact and bounded INFO/TRUST/SEO source claims | DISC defect fact inclusion; live DISC-404 yields unsupported_rule_findings1 | C1 Issue94 versioned Guard/report |
| `apps.operator_console.b5a_profile` | Strict signed Reviewer role/profile, two pinned original tasks | Dynamic projection from newly admitted B4 task/result | C1 task contract + C2 accepted SSR integration |
| `apps.operator_console.b5a_preview` | Original unsaved contract validation | Durable per-claim intent/receipt, actual approval | C2 PR89 then accepted main |
| Original SSR nonimplemented POST/share |501 NOT_IMPLEMENTED, no share occurs | B6 exact-version private delivery/read/revoke API | C2 PR92 after PR89 |

Minimal safe next change belongs in the responsible accepted versioned business package, not this
runner: provide a typed current-lease-bound source/result seam and an authorized read projection
linking tenant + request/run/job + source_ref/hash + actual execution/package/Guard/report version
pins + Reviewer assignment. Any new role/function capability must have an exact Owner-approved
permission diff and native negative tests; no admin runtime, raw SELECT grants or SET ROLE workaround.
The old Worker and0001-0004 stay unchanged under this S1 scope. A status JOIN against a preexisting
report is not substituted for a generated result. A new opaque ID or caller-written state row alone
cannot satisfy the missing proof.

When C1/C2 are merged and independently accepted, merge only that main normally into this worktree,
record merge parents, update the explicit producer/consumer versions in this runner, and rerun from
fresh owned resources. Do not cherry-pick Draft89/92 or copy their checkpoint files.

S4 is a separate L3 safety decision: old-first fixed checkpoint currently unavailable, MAX3 remains
exhausted, and historical A1/B7 state remains paused. A future deterministic synthetic fixture exception
must name its precise fresh test-only paths/data/permissions against the then accepted main. No seed,
UUID/default rewrite, RLS/operator/B-path change is implemented by this integration handoff.

# S2 / C2-2 B5B incremental consumer

Current M2 continuation after Owner merged PR104: [M2 contract and boundaries](M2.md).
The following sections describe the previously validated sealed-preview increment;
its old missing-result state and CI counts are historical, not this M2's status.

Current continuation: [Owner6896489543](https://github.com/gloweaseco-leo/VRAE/pull/103#issuecomment-6896489543),
[M2 delivery](https://github.com/gloweaseco-leo/VRAE/pull/103#issuecomment-6895931265),
and the accepted [synthetic L0/L1 charter](../L0_L1_STAGE_CHARTER_V1.1.md).
Normal accepted-main sync: `a210d52ff10616113b9a5c2712fe7c0d8ac37be7` (documentation only).
Continue this PR autonomously within new modules; no self ready/merge/deploy.
Only synthetic websites. No real customer, external recipient or paid model.

M2 entry: existing signed home → **合成任务审核工作区** (`/b5a/tasks/{task}/b5b/m2`).
This currently returns409 with explicit missing-port states. Source selection,
internal approve/reject/revise, version receipt and Chinese A4 export controls
remain disabled until C1's authenticated generated-result/task port is merged.
The prepared review form binds version/hash and at most3 issue IDs; it is not
mounted as an authority or write endpoint. No new review database or alternate
report source is invented. This is UI preparation, **not M2 business PASS**.

Owner authority: [Issue95 comment6893284620](https://github.com/gloweaseco-leo/VRAE/issues/95#issuecomment-6893284620).
Initial accepted base: `d63ea0b007ab4841000ff80c6d8c651d6ff4956f` (PR89/99/92).
Normally synchronized accepted main: `67acff97689514fdede01f2aab81dd5a7a96b9cd`
(Owner merged PR100 S1 DISC; no lease-bound Worker result interface).
Subsequent normal sync: `6769f348e3f54b8b2964a43ec0041e17ba139686`
(Owner merged PR102 six-schema recovery; B5B source and default IDs unchanged).

This adds an entry in the existing signed `/b5a/` SSR and consumes the accepted
B5-P0/B3 and B6-P0 ports. There is one HTTP server and no second SPA, identity
provider, persistence implementation, report generator or delivery transport.
All existing B5A/B5P0, B3/B4, identity, SQL/roles/RLS, Guard and original workflow
files remain unchanged by B5B. PR100 is incorporated only through its independently
accepted main merge; no unmerged PR100/102 or sibling source is imported.

## What can be used

- Signed, currently authorized sealed Reviewer task: original per-Claim rehearsal,
  B3 atomic intent, immutable original-key receipt, duplicate lookup and restart
  readback remain the accepted implementation. This is TEST_ONLY_REVIEW_INTENT,
  NOT APPROVED, never a human approval.
- The same session opens a B6 current-only private candidate panel and the
  **unmodified original B6 private document bytes**. The Reader rechecks original
  PG bytes, identity/assignment, version and descriptor policy. No source prose,
  contact, credential or redeemable access link is rendered by the new panel.
- Sharing checks call the accepted deny-only B6 Gate. Every operation, including
  CREATE_GRANT, ISSUE_TOKEN, recipient access, approval and send, remains denied.
  A CSRF-bound authenticated check creates only an in-memory denial receipt.

## Explicit missing accepted ports

| UI state | Exact missing interface and current accepted seam |
|---|---|
| `BLOCKED_NO_ACCEPTED_REVIEWER_TASK_STATUS_PORT` / UNKNOWN | PR99's actual B4 APP status reader exists, but its APP-authenticated `/v1/audit-requests/{request_id}` is not Reviewer authority. There is no independently accepted authenticated mapping from this signed Reviewer task/assignment to that request/run/job. No APP config, bearer, DB query or caller-supplied status enters SSR. |
| `BLOCKED_NO_ACCEPTED_LEASE_BOUND_RESULT_PORT` / UNKNOWN | No accepted current-lease/epoch-bound Worker result producer/read contract joins an actual result manifest/report version to its request/run/job and current authorized Reviewer assignment. Configured input references, source JOINs and sealed 404/200 reports are not generated Worker output. |

Accepted PR100 supplies a versioned DISC renderer and46 default tests, not the
missing current-lease-bound result or Reviewer task-state ports. These states
cannot be enabled by a query, uploaded JSON, caller UUID, claimed
DONE flag, approval or share grant. The new result URL returns HTTP409 after
current authorization. Unauthenticated, revoked, cross-tenant/task and invalid
version requests reveal no private data. New routes reject all query metadata.
Any future trust-crossing port requires independent Owner acceptance and an
explicit integration change; this increment does not silently activate it.

This is meaningful independent preview/receipt/UI work, not a completed
task-to-generated-report business path or full B5/B6 EXIT. Beta remains 2/7,
Human Gold0/26 and G1/G2/G3 NO-GO.

## Native verification

Use the accepted Python3.11/3.13 locks, Docker PG16 and Node22. Install only
`requirements-ra1a.lock` and `requirements-ra4a-p2b2a.lock`. Set
`B5B_CHROMIUM` to the actual Chrome executable (`/usr/bin/google-chrome` on CI;
`C:/Program Files/Google/Chrome/Application/chrome.exe` on this Windows host).

```text
python -B -m integration.b5b.run local-311
python -B -m integration.b5b.run local-313
```

Use each command's matching interpreter and a new owned label. Never reuse a
failed label or rerun unchanged source to select green. The runner:

1. Verifies current source bytes against committed Git blobs.
2. Runs original B5 55 assertions unchanged using its original fixture, plus
   31 real B5B PG/HTTP cases and21 pure boundary/publication/UI cases:107 expected,
   no skips. A count is not a PASS claim; inspect actual current native XML.
   Cases cover tenant/version/revocation, original unknown/half-commit/lost
   response, actual child restart and original-key receipt, and11 deny operations.
3. The **unchanged** independent B5-P0 hosted job runs original PR89 Chromium63
   assertions/12 screenshots. The new B5B job runs current-only preview, original B6 document,
   BLOCKED result and actual PG revocation journeys at1280/375/320 (18 screenshots).
   The new browser reuses original CDP transport, input and cleanup code;
   HTTP25s/CDP30s and original authentication/transaction thresholds are unchanged.
   New browser inspection, denial and blocked-result groups authenticate with
   separate fresh signatures under the same original90s lifetime; no expired
   session is treated as a positive authorization. The new suite expects94 assertions
   on one real browser tab, including explicit M2 blocked UI. It creates zero
   duplicate rehearsal intents. The duplicated old-receipt browser assertion was
   removed only from the new consumer suite; original receipt/revocation tests
   and the complete original browser workflow are unchanged.
4. Verifies original-byte/catalog roots, three owned PG resource groups,
   all84 case databases dropped, actual Chrome exit and child termination.
5. Exports only scanned native JUnit, SHA/CRC retention, bounded browser metadata,
   18 screenshots, source hashes and cleanup. Raw logs, profile files, signer,
   passwords, cookies, private journals and raw failed native XML stay private.
   Browser RED now retains exact original native XML when all cases passed and
   no captured streams/properties/credential pattern is present; otherwise the
   accepted sanitizer retains actual outcomes and raw SHA+CRC privately indexed.
   failure suite/code/phase/assertion counts and actual cleanup flags, including
   false flags. Never publish raw headers, token-bearing CDP commands or stacks.

New tests live outside default `tests/`: accepted default2564 IDs (original2473,
B5two, B643, DISC46) and25 original
skips, QA118/Review127, B4 Worker/restore and original CI are not extended or
modified. `.github/workflows/b5b.yml` adds dual-minor genuine PG/signed SSR/browser
acceptance alongside every original workflow. Read all actual current Jobs;
do not substitute a prior SHA's green or ignore a genuine original B4 RED.

## Controlled local entry and stop

The fixture provisions only accepted synthetic404/200 originals, one real PG16
instance, private Reviewer/B3 profiles and B6 descriptors; the signer/admin stay
outside the SSR child. `integration.b5b.http_server` accepts only local profile,
bridge, policy, audit and ready paths beneath `integration/b5b/.runtime/`.
It uses the original loopback server, headers and HttpOnly/SameSite cookie path.
Tokens are supplied only by the independent fixture issuer, never in a URL,
HTML field, public artifact or UI credential editor.

The runner owns and stops its child, Chromium, case databases and labelled PG
container/network/volume in `finally`; it never globally prunes Docker. All
runtime material is ignored and confined to the owned checkout. Historical
PR89/PR92 RED in their original worktrees remains untouched. No production
customer, paid model, real ShareGrant, notification, deployment or merge is run.

Owner's current autonomy charter supersedes the first delivery's STOP. Ordinary
new-module RED is diagnosed and corrected within scope. C1's unmerged dependency
does not authorize fake output or legacy permission changes.

## Local RED retained for independent review

The first candidate's3.13 native94 run retained93 PASS/1FAIL at a late duplicate
submit; the original browser's first1280/404 submit retainedHTTP403/zero writes.
Neither failure was rewritten. One short diagnostic is not the full63-browser
acceptance and does not establish the first403 root cause.

On subsequent source `e80c2e8`,3.11 native94/94 and original Chromium63/63 with12
screenshots completed. The new browser then crossed its90s signature lifetime;
its independent positive groups now authenticate separately.3.13 native remains
93/94 with a real25s timeout in GET private-preview before the REDEEM_TOKEN denial
operation was reached. Its exact root cause is UNKNOWN. No timeout, permission,
old test or source-current check was relaxed to turn this local failure green.

Original PR103 `d607d39` remains22/24 hosted jobs, both B5B browser jobs RED;
all21 original ZIPs have been downloaded/hash-verified privately. R3 focused
browser RED and false Chrome cleanup flags are also retained without rewriting.

The first continuation's10 new pure tests pass on both Python minors. A focused
private-stack diagnostic also caught native ReportDraft/ReviewTarget recursive
replay during a25s HTTP timeout. The single-tab focused browser still reached
30s CDP timeout at first1280/404 signed session, with original PG bytes already
returned and target replay in progress. This is **not a browser fix PASS** or
proof of the historical hosted failure's root. No original replay, authorization,
PG timeout, session90s or HTTP25s/CDP30s threshold was relaxed. Current hosted
RED publication will identify its actual first browser phase independently.

On `e5da6d2`, hosted native104/104 passed in both minors, then the375/404
`bounded-original-B6` assertion failed. Those22/24 Jobs and all21 ZIPs remain
separate in private `ci-m2/`. The B6 raw HTML's inline-style/meta-CSP conflicts
with the accepted SSR's HTTP `style-src 'self'`, leaving the long fingerprint
unwrapped. New `/private-view` places only verified B6 body content in the existing
same-origin styled frame; original `/private-document` still returns the exact
original bytes/hash and original HTTP CSP is unchanged. No iframe or new style
permission. A real Chrome presentation-only probe using the verified official
B6 artifact reproduced old overflow at375/320 and proved the new view bounded
at1280/375/320 with the same response CSP. This probe is not PG/auth/Worker proof.
New view permission denial and exact-original-on-browser-RED retention extend
native collection to106; the related11 pure cases passed in both minors.

The subsequent `809701b` reached post-browser protection aggregation in both
minors but failed the new unconditional all-roots-equal assertion. Original B5-P0
`test_revision_race_after_original_read_before_submit` intentionally registers
v2 through the accepted fixture writer, then refuses the stale submit with zero
business rows. Its accepted historical and current independent B5 evidence agree
on exact roots `d8c87d4...`→`3fa303b...`. The new aggregator now verifies that one
exact original-source-pinned transition, zero business rows and all other roots
unchanged (52 original cases +31 new PG cases +browser). It does not rewrite any
observation or accept an arbitrary changed root. Original test/query/SQL files
are unchanged. A read-only plan probe did not reproduce ordering drift and is
not claimed as the cause. Related verifier negatives bring collection to107;
12 focused cases pass in both minors. Post-browser diagnostic/native files are
now published before integrity checks, so another gate RED cannot silently lose
all artifact evidence. Pending status is never called PASS.

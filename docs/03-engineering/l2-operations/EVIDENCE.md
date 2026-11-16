# Native C3 package evidence (not complete L2 E2E)

Tested source: `c04d7599f1da3582a6732df919a7a87e88546def`.
The subsequent evidence commit changes documentation/artifacts only. The full
C3 application, verifier and test trees remain byte-for-byte unchanged in Git.
This is not a claim that a future PR SHA was tested in advance. r5/r6/r7 remain earlier passing evidence; r8 includes the precise first-CI fixes.

- Native Windows Python3.11.15: **43/43**, post-PG-restart **1/1**.
- Native Windows Python3.13.13: **43/43**, post-PG-restart **1/1**.
- PostgreSQL16.15 (`server_version_num=160015`) by pinned local image
  `sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea`.
- Actual independent PG container restart on each version, followed by native
  `l2_ops_runtime` read through BriefService and checks of remaining SQL rights.
- Identical persisted document content SHA after both restarts:
  `6178ab096049fcb3adddf8c71290527f637b5305f41b665205655dcc1486a224`.
- Real deferred COMMIT failure raises and leaves no visible brief; successful
  identical retry is byte-identical, conflicting same-reference writes refuse.
- Runtime UPDATE/DELETE/DROP/CREATE refused. No original SQL/RLS/Worker or old
  APP/Reviewer grants changed. Bootstrap rejects using those old roles.
- Current-reader refusal/revocation, source/task/report/review/blueprint version
  mismatch, L1-as-L2, payload edits and rehashed business-authority edits refuse.
- Six actual beta_internal CLI runs (3 modes x2 native versions), all
  SOURCE_VALIDATED_NOT_DIAGNOSED; task_created=false, network_requests=0.
- `mypy vrae`:105 files pass; new-scope ruff passes. CI workflows and original legacy classifier assertions unmodified. The B5A publication helper now pins the five Owner-accepted PR108 documentation blobs, preserving all other original-file freezes; it reports those five accepted changes explicitly.
- Owned PG containers and networks removed. Other workspace/container resources
  were not stopped or deleted. Private credentials/raw RED originals retained
  under ignored `.private`; public failed copies redacted with original hashes.

Raw JUnit/text, source manifest, actual port mappings, readback and measured wall
nanoseconds are in `r8/` (six unchanged CLI demonstrations remain in `r5/`). Actual package-validation wall durations were
30,719,000,000ns and25,938,000,000ns, excluding final cleanup. These are automated
validation measurements, not real diagnostic Worker costs or human labor.
Monetary amount is UNKNOWN/null, no invoice reconciliation or paid model call.

RED remains: r1 transport setup, r3 consultation fixture shape, r4 restart
transport plus its independent port-change probe; ingestion anchor RED separately
recorded. r4 original bytes are private, with SHA manifest and sanitized public
copies; no vanished original is represented as recoverable from its hash alone.

## Outstanding full-product integration

The baseline main has accepted M3 L1 operation, not accepted L2 deep-result ports.
No L2 APP202/Worker/report/review/browser operation is claimed by these tests.
TestOnlyReader data is exclusively synthetic adapter test data; it cannot be
loaded as a production result or a real new-task report through this package.

Required next inputs after Owner merge: C1's real L2 source/IndustryPack/deep
result reader; C2's version-bound L2 review/blueprint context and unique-SSR hook.
Compose CurrentReader against those accepted ports; then run actual operator
source -> APP202 -> Worker -> L2 findings -> review -> RebuildBrief on one SHA.
Existing M3 lifecycle is preserved, not reimplemented. C3 coordination:
Issues94/95, specifically Issue95 comment6907522982.

No real consultation evidence or rate supplied: no E2/E3 claim, no real human
approval/customer or external delivery. Missing customer authorization is not a
blocker to the implemented offline capability.


## First CI and controlled correction

First HEAD e4f81fc9a1209dec21126d94ca0bafe34d9bb850 completed 14 workflows /
30 jobs:21 success,9 failures, all attempt1. Complete original job IDs/links and
retained-log digests are in first-ci-red.json. No old-HEAD manual rerun.

Three proven causes: two E731 assignments (5 jobs), PR108 documentation baseline
mismatch already present on accepted main (2 jobs), and five new PG-only skips
refused by the original exact-25-skip ordinary classifier (2 jobs).

Corrected E731 with ordinary functions. Five accepted document paths are pinned
to exact Git blobs from Owner main6a7c39b2; mismatched commits/dirty content,
original identity/SQL/unlisted documents remain refused. Native real temporary
Git history tests cover all six cases; current repository source snapshot is in
r8/frozen-source-current.json. Source metadata checks no longer import an
unnecessary database driver; root/runtime paths are unchanged.

New PG and Git/runtime integration tests reside outside ordinary tests/, invoked
explicitly by the real PG validator. Missing PG context now fails these explicit
integration tests; none skips. The ordinary C3 suite is33/33 with zero skips;
original legacy exact25, QA118 and review127 assertions remain untouched.
The separate runtime10 + ordinary33 give43 native cases, plus post-restart1.
No Docker image, CI workflow or old classifier was relaxed. Old isolated image
copies no integration/ or Git binary; keeping these real operation tests in their
explicit suite also preserves that original runtime contract.

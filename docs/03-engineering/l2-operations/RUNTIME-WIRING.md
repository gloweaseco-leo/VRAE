# PR112 actual launcher/runtime wiring, not P40 FINAL PASS

Owner continuation: PR112#6920169305. Accepted main remains6b2a2dff. No PR114
unmerged code is read into/executed by this worktree. Original RED/dump remains.

## Actual code and operation

The original beta_internal.py l2 app-start/status/verify/stop now provisions the
native task controller into the ORIGINAL B5B SSR via its original private stdio
configuration. No second server, report engine or review engine is introduced.
The TaskWorkflow/TaskClient keeps original404/200 and one registered P40 source.

NativeTasks takes the original journal's TaskHandle, original signed current M1
session and server-registered bundle. GET/POST /b5a/m2/task/<ticket>/native accepts
only the original CSRF. produce_current invokes real C1 full replay, then accepted
C2 NativeSource with independently checked task/pack/bundle/first-created-time.
A Worker DONE is not a native report. Mismatched produced task is denied.

The fixed private Controlled actor must match the original M1 issuer/subject/
tenant. C2 scope names only the currently produced native report. Changing task
clears old sessions/challenges/actions but preserves revoked keys and used JWTs;
switching back cannot resurrect an old session. Same-task M1 reauthentication
keeps report/receipt and original C2 expiry. No role, TTL or old SQL is changed.
Original current M1 task/pack authority is held around C2 report/review handlers;
Brief uses its existing double current context through actual PG COMMIT.

Original protected database correctly denied CONNECT to the new C3 role during
runtimewire311. That RED and failed cleanup CASE remain retained. The corrected
runtime uses a C3-only database vrae_l2_internal IN THE SAME original PG instance;
only this new database gets CONNECT and only its namespace gets INSERT/SELECT.
The old database ACL is checked byte-for-byte unchanged and old CONNECT remains
false. No old role/permission, HBA, migration, RLS, Worker, Guard or lease changed.
Public keys only enter SSR. The separate original parent signer handles observed
M1/C2 challenges; new SSR boots require new signed login. No signing key enters
SSR. Actor is explicitly synthetic Controlled; not formal human review.

## Current startup commands

```text
python scripts/beta_internal.py l2 app-start --run <fresh-run> --minor 3.11
python scripts/beta_internal.py l2 app-status --run <same-run>
python scripts/beta_internal.py l2 app-verify --run <same-run>
python scripts/beta_internal.py l2 app-stop --run <same-run>
```

Current mode is PREPARATION_NOT_L2_E2E and P40 disabled at server as well as UI.
readiness.ACCEPTED_PERFORMANCE_MAIN is deliberately None. Only AFTER Owner
notifies accepted performance/pin main may that checkpoint be populated and
normally synced ancestry verified; no CLI/browser flag can bypass it.

Once accepted, the existing operator path is: original assigned source signed
login -> task catalog P40 submission -> actual queue/Worker status -> original
new-task signed challenge/login -> that ticket's native entry -> produce/resume
C1/C2 -> C2 Controlled signed login -> industrial report/evidence/seven blueprint
packages -> version-bound item review -> actual internal Brief PG save/readback.
If a signature expires, reauthenticate the original task and resume the SAME
report. No deadline is renewed by a snapshot or Worker lease. After actual PG/
service restart, reauthenticate/resume with the persisted first-created stamp;
existing C2 versions/receipts stay in the original private routing volume.

RebuildBrief remains internal only. Consultation/rates/customer approval and
unattested human labor stay UNLINKED/UNKNOWN; no E2/E3, delivery or L2M action.

## Exact actual receipts

- d25de79f242da9e171dc321f7a0200c920aec3ec: native Windows3.11.15/3.13.13 EACH
  125/125 + actual PG16.15 restart-marker1/1, default full C3 suite. Detached M1
  boundary is explicit: NOT actual P40 Worker/signature/browser/Brief E2E.
  runtimetask125/ holds raw JUnit, source manifest and per-minor owned cleanup.
- bddeb1a73bc4bc1444b7e1179313bd97cdfd0873 changes only the startup storage
  connection/bootstrap/failure-cleanup audit from that preceding application
  candidate. runtimewire311b/313b both started real PG16, original API/independent
  Worker bootstrap404/200, one original SSR, new controller/public-key config and
  own-role connection. Both actual Chrome preparation5/5 + screenshot1. Direct
  new-native-route GET403 proves dispatcher is mounted/disabled, zero P40 task.
- Both second runs CLOSED; original stage cleanup has zero error and recorded
  current PG container/volumes are absent. Old anonymous volumes UNKNOWN_UNTOUCHED.
- runtimewire311 keeps original startup/cleanup RED, including correct old-DB
  CONNECT denial; current IDs recorded before cleanup independently verify gone,
  without changing either original failure to PASS. Controller fixture-import
  and source-allowlist RED XML stays in controller-red/; later8/8 is separate.

The next acceptance still requires a new Owner-accepted performance main and
ONE causally justified real P40 dual-Python round, actual same-run eight-page
pack -> native C1/C2 -> Chrome Controlled item review -> Brief COMMIT -> identical
pins/report/receipt/Brief PG/service restart readback. Only then propose FINAL
PASS and push the controlled new candidate for natural all-job CI on PR112.
Current remote remains099b8a Draft; no push, CI retry, external site or production.

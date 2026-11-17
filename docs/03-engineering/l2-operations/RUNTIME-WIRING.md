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


## S0 A04 live verification protocol (2026-11-16)

Accepted performance main a9604f570528e599a0b8215a8957208d76e47b89 and the
PR115 docs are merged normally. Historical executable e39de059eb77dafea1af55d50369d7a99ae034cb
completed independent 3.11/3.13 APP202 / original Worker / same eight-page P40+V25
pack / full C1+C2 / Chrome item review / actual Brief / real restart positive
journeys (12 assertions and seven screenshots each). Those are positive-only
records, not A04 completion or FINAL PASS. The old lease RED remains retained.

The completion record in the dedicated C3 PG database is a durable **pending
fence**, not a distributed transaction or an access grant. The original M1
signed request transaction and C2 directory + SQLite transaction are held while
Brief bytes commit. The original task, assignment, anchor, policy and current C2
review deadlines are minimized; a deferred C3-only PG constraint also checks the
actual commit deadline. The adapter checks live task connection/session and C2
ledger identity before writing and after writing. Both source contexts must exit
successfully, followed by a fresh exact pins/review/blueprint CAS, before the
completion fence is written. Every public read still invokes both original
current contexts; the fence cannot make a stale or revoked Brief current.

SQLite and the dedicated PG database cannot commit atomically. A source failure
or revocation around a completed PG write may leave immutable bytes without a
completion record. `get` refuses that pending row; HTTP never claims it is a
current saved Brief. An authenticated retry of the same bytes can finish the
fence; different bytes at the same Brief ref conflict. There is no delete,
compensation by rewriting history, or resurrection of a revoked SID.

`runtime_audit.py` is an explicitly TEST_ONLY **fault-injection protocol**, not an
HTTP endpoint, signer, replacement authority or alternate report engine. Only
the local operator can queue one of eight closed cases in this run's exact owned
SSR volume. A real POST must first pass original C2 identity, origin, one-use
CSRF, fixed actor mapping and exact native reader checks. The queue must name the
currently active real job. Unknown cases, extra fields, wrong jobs and previous
receipts are refused. Ordinary launches have no queue and no probe side effect.
Audit Briefs have distinct `s0-audit-*` references and cannot replace the business
Brief. No original SQL/RLS/Worker/lease/Guard or grants are changed.

The live probes use the existing original reader and C2 ledger, with these actual
fault points: duplicate same-byte PG writes; another tenant/run/job; termination
of the C3 role's own PG backend before commit; loss of the original signed-reader
PG connection; temporary unavailability of the same SQLite file (original bytes
retained/restored); a real C2 decision committed after source-context exit; a
competing real C2 review thread blocked by the original held lock; permanent C2
key revocation at the C3 commit boundary. The last case requires a real new SSR
boot/key and new login: the revoked key and old SID are never un-revoked.

Chrome also performs an actual native blueprint revision, submits an unused old
version form, replays a consumed Brief nonce, checks invalid actor/report scope,
waits out the original task deadline, and signs in afresh to the same task. New
Controlled decisions and versions are retained; a rejected current review may
produce a clearly REJECTED internal preview, never display an older approved
Brief as current. The final version and current receipt/Brief are checked after
another real PG/service restart. Actual source hashes, full pins, fault results,
PDFs/screenshots and exact owned-resource cleanup remain necessary evidence.

Current execution status: A04 probes implemented, **not yet passed**. No new push
or FINAL PASS assertion is authorized by the earlier positive-only journeys.


### First live A04 driver RED and causal correction

At executable 407f5a0a3b0e736e7246f4a3fd0019d87b7616f1, run s0a04311a
created real job 6ed4c7e6-3f56-4527-9402-1683a46e625e, committed the native
P40 pack, and passed all eight live fault probes (including pending compensation,
competing C2 review and permanent key revocation). Real Chrome then appended a
native blueprint version, but the driver's attempted fetch submission failed.
The actual HTTP header retained connect-src 'none'; a separate read-only Chrome
probe recorded the explicit CSP security event and TypeError: Failed to fetch.
That is a C3 driver RED, not a failed Worker/Guard or a passed old-version check.

The original assertions, browser failure, exact two private PG dumps, original
C2 SQLite file, eight probe receipts and source proof are preserved. The overall
journey remains RED despite earlier passing assertions. No same-HEAD random
retry is permitted. Additionally the unused old form must be fully filled and
valid before the new version is appended; otherwise missing required fields
would be an invalid oracle for old-version rejection.

The correction uses native same-origin POST form navigation and ordinary GET
navigation, retaining the original CSP and all deadlines. It first proves the
unused old form is valid, then appends the real new version before submitting
that exact old form. It also submits a valid Brief form with an untrusted tenant
field as a real browser negative. No CSP, auth, CSRF, SQL, permission, Guard or
Worker lease is relaxed. Fresh same-task authentication precedes the final
version's item review; it does not renew any old SID or Worker lease.

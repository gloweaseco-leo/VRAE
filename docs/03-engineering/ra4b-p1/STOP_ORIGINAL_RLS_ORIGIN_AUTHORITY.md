# B4-P1: original-policy compatibility restored; live Worker authority STOP

State: **B4_P1_STOPPED_ORIGINAL_RLS_ORIGIN_APP_AUTHORITY_NOT_ACCEPTED**.

Read Owner [comment 6850652979](https://github.com/gloweaseco-leo/VRAE/issues/78#issuecomment-6850652979), decision `RA4B_P1_RLS_POLICY_COMPAT_GO`, posted 2026-11-13T10:47:08Z. Removed only the two newly added policy objects from unmerged 0004. Kept dedicated `ra4b_test_*` roles, exact narrow function grants, guarded finish, current-origin/source/policy validation and deferred commit trigger. No original policy, frozen assertion, 0001–0003, old adapter or existing workflow changed.

## Fresh actual PG16 result

Python **3.11.15**, PostgreSQL **16.15**, fresh 0001→0002→0003→0004:

- Original ten policies read back byte-identically before and after 0004. Original role count remains eight.
- **Frozen P1 54/54 PASS after 0004**. Native JUnit, catalog and all 54 call outcomes are in `original-rls311-v1/p1-after-0004/`. New B4 roles were present throughout this test; no transient role removal, policy filtering or frozen-source edits.
- Then the unchanged B4 safety file ran with fail-fast as requested on a new actual failure: **6 passed, 1 failed; 10 further cases not executed**. These six passed cases cover both tenants' actual new-role catalog/raw SQL denials and valid 404/200 APP durable admission/status/idempotency paths.
- The first lease-dependent case fails **before policy revocation is attempted**. `store.claim` reaches actual COMMIT and its deferred trigger raises **SQLSTATE `42501`, `RA4B_ORIGIN_APP_DENIED`**. This is not a completed revocation/expiry safety matrix and not a usable Worker claim path.

Exact native exception chain:

```text
store.claim -> COMMIT
ra4b_test.commit_guard
ra4b_test.require_run
42501 / RA4B_ORIGIN_APP_DENIED
```

`original-rls311-v1/actual-sql-failure.json`, `b4-tests.xml` and the original console log retain the failure. The first evidence export additionally failed on its diagnostic query's incorrect `event_type` column; the actual outbox column is `kind`. The process had loaded the earlier script despite the on-disk correction. Its native exception, failed export and cleanup are preserved without rewriting that run. No catalog or full acceptance PASS is invented for the failed export.

## Bounded diagnosis after STOP

Development stopped. A separate, explicitly diagnostic fresh PG16 instance (`original-rls311-diagnostic/`) reproduced the same single claim failure and completed catalog/state capture. This is a **reproduced RED**, not a rerun presented as acceptance green. No B4 implementation was changed for the diagnosis.

Live evidence confirms:

- Four real APP/Worker connections authenticate as their own exact `ra4b_test_{a,b}_{app,worker}` identities. Actual SESSION_USER/current_user, database and version are recorded. No session impersonation.
- Each role inherits only its new APP or Worker group, with no privileged flags or old group membership. Raw table privilege checks are false and the exact named B4 function EXECUTE grants are recorded; legacy unguarded `ra4a.finish` is not executable by B4.
- Original private policies are exactly `db_role = SESSION_USER`, with ENABLE/FORCE RLS. B4 functions are SECURITY DEFINER owned by `ra4a_owner`, use the fixed safe search path and have no PUBLIC EXECUTE. The actual APP and Worker principals are enabled TEST_ONLY with active same-tenant assignments.
- Actual APP admission and status succeed. Worker claim fails at deferred validation with the same `42501 / RA4B_ORIGIN_APP_DENIED`.
- The full requests/runs/jobs/audit/outbox fingerprint before claim and after rollback is identical. Job remains `PENDING`, lease sequence/attempts are zero; run remains `QUEUED`, with only one `ADMITTED` audit row and one undelivered `TEST_ONLY_ADMITTED` event.
- Both instances' container/network/volume cleanup is verified. Both runs' actual-credential scans match zero within their output directories. This is not clearance to publish the entire uncommitted workspace.

The live catalog and failing check locate the cause: tenant-scoped original `ra4a` policies permit B4 request/job access through definer functions, but original **private** session policies hide the originating APP row from a different actual Worker SESSION_USER. SECURITY DEFINER changes effective privileges, not SESSION_USER, and the owner remains subject to FORCE RLS. The guard therefore cannot affirm current originating APP principal/assignment authority. The protected failing guard is retained verbatim in `ORIGIN_AUTHORITY_CHECK.sql.txt`.

## Required decision and current boundary

Owner explicitly requires: **“If removing the policies means genuine B4 functions cannot pass under existing RLS without expanding other forbidden source/DDL, immediately STOP with the exact SQLSTATE, catalog and minimal new Owner decision request.”** That condition is now proven. Removing the current-origin check, using legacy/admin runtime credentials, changing SESSION_USER/GUC, bypassing FORCE RLS, or altering original policy definitions is not authorized and has not been done.

Minimal separate decision requested: authorize a B4-only current-origin authority read mechanism while retaining the original ten policies. One bounded design for Owner consideration is **new B4-private authority projection tables with transactionally coupled B4 triggers on trusted original principal/assignment changes**, contained in new 0004. It must preserve authoritative updates/deletion/TRUNCATE and serial revocation/rollback, grant no runtime raw access or independent projection writes, and retain finish/commit checks. Such new tables/triggers and the corresponding guard read path need explicit approval; none is implemented here. An Owner-specified alternative is equally possible if it preserves these boundaries.

All historical 3+3 RED, role-count 53/54 RED, policy-count 53/54 RED and this new Worker failure remain intact. `ORIGINAL_RLS_STOP_EVIDENCE.json` verifies retained history hashes and seals actual new receipts/source. Only Python3.11 P1 is newly 54/54; Python3.13, complete B4 negative coverage, remaining regressions, real HTTP/independent Worker acceptance and hosted CI remain outstanding after STOP. No push, new PR, hosted CI, self-merge, deployment, native human approval or ShareGrant occurred. Legacy broad SELECT remains G1 hard NO-GO debt.

# B4-P1 preflight: Worker authority contract decision required

State: **B4_P1_BLOCKED_BY_P1_CONTRACT_NOT_RUNTIME_CANDIDATE_NOT_B4_EXIT**.

Authorization: [Issue #78](https://github.com/gloweaseco-leo/VRAE/issues/78), exact entry `f9c64dacafffa08806890fcacf04f3da5723c040`. Independent branch `codex1/ra4b-p1-private-api-worker-testonly`. No API/Worker runtime, migration 0004, workflow, push, PR, deployment or native approval has been created.

## Observed on actual PostgreSQL 16

Both actual Python 3.11 and 3.13 preflights executed the unchanged accepted migrations 0001–0003 and `TestOnlyPostgres.admit/claim/finish` against separate disposable PG16 instances. The APP, Worker and fixture administrator used genuine independent authenticated connections. No actor dictionary, GUC or session-user impersonation was used.

Each run has **3 failed required invariants, zero skips** in native JUnit:

1. `ra4a_test_a_worker` has SELECT on `ra4a.requests/jobs/policies/references` through the accepted P1 grants, despite the Issue's stated no-raw-SELECT assumption. Its actual superuser/BYPASSRLS/CREATEROLE/CREATEDB flags are all false. The probe inspects grants and does not use raw-table reads through Worker credentials.
2. APP durably admits an accepted synthetic reference; Worker commits a valid lease; a separate administrator commits policy `REVOKED`; `finish` still succeeds. Actual persisted run/job become `TEST_ONLY_CONSUMED` / `TEST_ONLY_DONE`, with an undelivered `TEST_ONLY_CONSUMED` private outbox event.
3. The same sequence with policy expiry committed before `finish` also succeeds.

These observations describe the accepted synthetic P1 consumption contract, not a newly opened production approval path. They are incompatible with claiming the stricter current-policy fail-closed B4 runtime requested in Issue #78. No customer/site/model/external delivery or native ReviewDecision was involved.

Evidence per interpreter: `actual-311/` and `actual-313/` contain `tests.xml`, actual privilege/catalog observations, post-invalidation persisted rows, migration source SHA, server/runtime receipt, actual credential scan and verified owned-resource teardown. Original console exports are `actual-311.log` and `actual-313.log`. Initial internal-network startup attempts are retained separately; those attempts cleaned up before executing policy tests. The successful SQL preflight reuses the accepted loopback-only P1 lab and makes no B4 API/Worker egress-isolation claim.

## Why implementation is stopped

The approved 0004 exception permits a minimal APP read/status function. It does not authorize new Worker policy guards, altered queue completion semantics, extra Worker grants, or a new narrow-role contract. Editing 0001–0003 or the persistence adapter is expressly forbidden. A prior APP status check, in-memory flag or lease alone cannot make current-policy validity atomic with Worker completion. Giving the Worker APP/admin credentials or silently relying on existing broad SELECT would violate the requested boundary.

Issue #78 explicitly requires **“STOP ... need to enlarge contracts.”** No existing source, privilege, assertion or timeout has been modified to force a pass.

## Minimal additional Owner decision requested

Please explicitly authorize an additive B4-only authority seam within 0004, beyond APP status:

- New TEST_ONLY runtime principals with explicit narrow ACLs and no inherited raw-table SELECT; preserve all original fixture principals and grants for accepted regressions.
- B4 Worker `claim_current` / `finish_current` wrappers that call the unchanged P1 operations while verifying actual SESSION_USER, tenant/assignment, current unrevoked/unexpired policy and exact current synthetic reference. Worker receives only its own credential and cannot directly bypass the guard through an unguarded completion grant.
- An explicitly approved transaction/commit validity mechanism, including policy revocation serialization and expiry-at-commit checks. Any trigger touching an accepted queue table must be separately named and authorized; none is applied here.
- Permit the new B4 adapter to call this guarded seam instead of exposing the old unguarded `finish` directly. The already approved APP status function remains read-only; cancel remains truthful 501 with zero side effects.

After that scoped GO, resume the actual loopback HTTP 202-after-commit + separate constrained Worker implementation and the full prescribed local/hosted matrix. Keep B3, native human decisions, ShareGrant and full B4 exit denied.

An alternative would require Owner to explicitly redefine this increment's in-flight policy-revocation/expiry semantics as synthetic bookkeeping. This preflight does not make that relaxation.

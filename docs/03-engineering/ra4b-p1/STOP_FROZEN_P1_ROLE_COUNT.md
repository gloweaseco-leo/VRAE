# B4-P1: mandatory stop on frozen P1 regression

State: **B4_P1_STOPPED_FROZEN_P1_REGRESSION_NOT_ACCEPTED**.

The historical `OWNER_DECISION_REQUIRED.md` and original dual-Python `actual-311/` and `actual-313/` RED remain unchanged. Owner resolved that earlier authorization blocker in [comment 6849788951](https://github.com/gloweaseco-leo/VRAE/issues/78#issuecomment-6849788951), decision `RA4B_P1_0004_SECURITY_HARDENING_GO`. This file records a subsequent, distinct stop.

## Actual result

On actual PostgreSQL **16.15**, Python **3.11**, the added guarded B4 SQL matrix passed **17/17**, including independent authenticated narrow roles, raw SELECT/DML and old-finish denial, revoke/expiry after lease, expiry during an open transaction, current source/version checks, stale lease, exact valid retry and concurrent revocation serialization. The SQL matrix was green in `sql311-v3/` and again in `sql311-v4/`.

The next stage ran the **unchanged** original P1 suite after 0004: **53 passed, 1 failed, 0 skipped**. The failure is `integration/ra4a/test_pg.py::test_real_version_catalog_and_owner_force_rls` at line 44. It asserts exactly eight roles matching `rolname LIKE 'ra4a_%'`. The actual catalog contains twelve after 0004 adds four narrow identities named `ra4a_test_b4_*`. All twelve retain false superuser/BYPASSRLS/CREATEROLE/CREATEDB flags. This is a namespace/count compatibility regression, not permission to weaken the assertion.

Native evidence:

- `sql311-v4/tests.xml`: added B4 matrix, 17 passed.
- `sql311-v4/pg2/tests.xml` and `pg2/stdout.log`: frozen P1 failure, 53/54 passed.
- `sql311-v4/pg2/pg-catalog-and-calls.json`: actual roles, original migration SHAs, 54 call outcomes and exit 1.
- `sql311-v4/teardown/teardown.json`: owned container, network and volume each verified absent.
- `sql311-v2/`: prior Docker startup timeout, preserved. `sql311-v2/cleanup-recheck/teardown.json` subsequently verifies owned resources absent after Docker recovered.
- `STOP_EVIDENCE.json`: byte SHA256 ledger and local source/HEAD identity.

## Why work stopped

Owner's latest comment explicitly requires: **“If 0004 causes regression on original P1 contract, do not suppress/mask old suites: STOP and return minimal cause/diff.”** This exact condition has occurred. Development and further acceptance runs stopped when the native P1 RED was inspected. Neither changing original tests nor running only pre-0004 P1 to claim compatibility is allowed.

Protected 0001–0003, all existing persistence adapters, frozen assertions and existing workflow files remain unchanged from accepted entry `f9c64dacafffa08806890fcacf04f3da5723c040`. No push, new Draft PR, new hosted CI, merge or deployment occurred. Codex2 PR #74 was not changed.

The API and independent Worker adapters and Linux runtime supervisor are initial local source only. **Their actual HTTP/container acceptance has not run.** Python 3.13 hardening acceptance, remaining frozen suites, restart/backup recovery, complete source/catalog/privacy packaging and hosted CI remain outstanding. This is not a B4-P1 accepted runtime or G1 exit.

## Minimal proposed repair, deliberately not applied

`PROPOSED_ROLE_NAMESPACE_FIX.diff` changes only the four new B4 identities from `ra4a_test_b4_{a,b}_{app,worker}` to `ra4b_test_{a,b}_{app,worker}`, consistently in new 0004 and its new B4 adapter/test provisioning files. New groups `ra4b_app` and `ra4b_worker`, exact ACLs, guard conditions and all eight legacy identities are preserved. No accepted migration, function or assertion changes.

The new B4 adapter does not use the legacy `TestOnlyPostgres` constructor's role-name restriction. The SQL functions authenticate actual SESSION_USER and trusted assignments, so this proposed namespace separation need not use legacy credentials or relax a runtime role check. The repair has not been applied or tested and carries no PASS claim.

Requested follow-up Owner decision: permit this explicit B4-only namespace correction and resume validation after this mandatory stop. Then rerun both Python versions against fresh actual PG16, including the unchanged frozen P1 suite after 0004, before any controlled push/Draft PR/CI. Retain all original and new RED evidence. Legacy broad SELECT remains recorded G1 hard NO-GO debt.

# B4-P1: role compatibility repaired; separate frozen policy-count RED

State: **B4_P1_STOPPED_FROZEN_P1_POLICY_REGRESSION_NOT_ACCEPTED**.

## Applied Owner authorization

Read latest Owner [comment 6850401668](https://github.com/gloweaseco-leo/VRAE/issues/78#issuecomment-6850401668), `RA4B_P1_ROLE_PREFIX_COMPAT_GO`, posted 2026-11-13T10:33:40Z. Applied only new B4 files:

| Original new B4 role | Corrected dedicated role |
| --- | --- |
| `ra4a_test_b4_a_app` | `ra4b_test_a_app` |
| `ra4a_test_b4_b_app` | `ra4b_test_b_app` |
| `ra4a_test_b4_a_worker` | `ra4b_test_a_worker` |
| `ra4a_test_b4_b_worker` | `ra4b_test_b_worker` |

B4's own adapter in `vrae/application/ra4b/store.py` validates the exact new role allowlist, trusted fixed role-to-tenant binding, loopback/canonical database, actual authenticated SESSION_USER, version16, nonprivileged flags, actual inherited group allowlist, no raw business/private/bytes/review table privilege, and the exact allowed B4 EXECUTE set. Original `vrae/persistence/postgres.py` remains unchanged; there is no SET ROLE/GUC impersonation in the adapter.

The proposed historical patch had CRLF/context mismatch with `git apply`; no partial git patch was applied. The same four-file exact namespace substitution was applied directly, followed by the new adapter checks. This did not modify historical evidence.

## Actual new validation

Fresh PG **16.15**, Python **3.11**, `compat311-v1`:

- **17/17** B4 security tests PASS, including both tenants' genuine APP and Worker connections under new names and the adapter's real ACL/membership checks.
- The unchanged frozen P1 suite reports **53 passed, 1 failed, 0 skipped**.
- The previous role-count assertion now passes: actual `ra4a_%` roles are exactly **8**. No B4 roles were transiently dropped or hidden for this check.
- The same original test then reaches line **52**, which requires exactly **10** policies across `ra4a` and `ra4a_private`. Actual count is **12** because 0004 adds `b4_origin_app` and `b4_origin_assignment` on the existing private tables.
- `compat311-v1/pg2/pg-catalog-and-calls.json` retains native role/policy catalog, migration SHAs, all 54 actual call outcomes and exit 1. `pg2/tests.xml` and `pg2/stdout.log` retain the unmodified failing assertion.
- `compat311-v1/teardown/teardown.json` verifies owned container, network and volume removed. Actual credential assertions in the runner passed after cleanup; no publication clearance for the entire uncommitted worktree is claimed.

This is a newly observed policy-count regression, not a repeated role naming failure. Original `actual-311/`, `actual-313/`, `sql311-v4/`, `STOP_EVIDENCE.json` and `STOP_FROZEN_P1_ROLE_COUNT.md` remain intact. `POLICY_STOP_EVIDENCE.json` seals this run and verifies the original retained evidence hashes.

## Exact cause and STOP

`MINIMAL_POLICY_CAUSE.diff` isolates the two new policy definitions responsible for the catalog change. They provide visibility and row-lock access for the guarded Worker to validate the originating APP principal/assignment under FORCE RLS. **Removing them alone would break the required current-origin authorization check**; that is not a valid fix. Altering existing policies or making a privileged definer bypass RLS would widen the protected contract. Changing the frozen count to 12, filtering its catalog query, or running P1 only before 0004 is prohibited.

The governing hardening GO explicitly says: **“If 0004 causes regression on original P1 contract, do not suppress/mask old suites: STOP and return minimal cause/diff.”** The follow-up naming GO replaces only the role-prefix STOP and says any other RED must remain RED and be investigated separately. Work stopped at this actual failure. No push, new PR, hosted CI, merge or deployment occurred.

## Required separate decision

A compatibility-safe design must retain the original ten policies while still validating current originating APP authority during Worker finish and at deferred validation. A possible bounded follow-up is B4-private authority projection tables, maintained transactionally by B4-only triggers on the trusted principal/assignment tables, with no new policies on the original schemas. This would require an explicit change to the current guard design and independent tests proving that updates, deletion, TRUNCATE, concurrent revocation and rollback cannot leave stale authority. It has **not** been implemented, approved or accepted here. No such table may become an offline or independently writable authority substitute.

Owner decision needed: authorize that precise additional B4-only database design, or provide another approved way to read current originating APP authority while preserving all frozen policy contracts. Do not relax current-policy/assignment/expiry enforcement or modify 0001–0003, the original adapter, assertions or existing workflows.

Python3.13 hardening, remaining regressions, actual API/Worker container acceptance and hosted CI remain **NOT RUN** after this stop. The API/Worker and Linux supervisor/harness are initial local source only. This is neither an accepted B4-P1 candidate nor G1/G2/G3 exit. Legacy broad SELECT remains G1 hard NO-GO debt.

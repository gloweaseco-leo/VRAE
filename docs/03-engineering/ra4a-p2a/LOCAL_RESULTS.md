# Actual local results — P2A

| Runtime | Fresh P1 v1 | Unchanged P1 replay on v2 | Original pure | New pure | New P2A PG |
| --- | --- | --- | --- | --- | --- |
| Python3.13.13, dev-full-04 | 54 PASS | 54 PASS | 11 PASS | 14 PASS | 86 PASS |
| Python3.11.15, local311-fresh | 54 PASS | 54 PASS | 11 PASS | 14 PASS | 86 PASS |

All listed JUnit failure/error/skip counts are zero. Compile, ruff, mypy and pip
check also pass. Original P1 tests/SQL/contracts are unchanged; the second54 is a
distinct compatibility replay, not108 independent test cases. Actual migration
ledgers are checked as v1 only before migration and v1+v2 afterwards. P2A86 call
IDs and original/new pure test classes are separately retained in raw evidence.

Both complete runs perform real PG16.15 binary pg_dump/pg_restore into a fresh
same-cluster DB, independently held original current404/zero200 bytes, generated
SHA/length, cross-tenant denial and stale-version refusal after restore and actual
container/named-volume restart. This is not cross-cluster DR certification.

3.13 began at entry main with uncommitted P2A code. Source-manifest+full snapshots
are retained and compared byte-for-byte (LF source normalization) to the later
committed functional HEAD. 3.11 fresh began at ordinary merge11cb307. Main advanced
via independently Owner-passed PR65; that approved cf11278 main was ordinary-merged
with no conflict, preserving all of its source/QA/app blobs except the two explicitly
authorized minimal P2A infra/workflow changes. No Codex2 development branch touched.

DEVELOPMENT_DISPOSITIONS.md names all earlier genuine failures and the excluded
reused-v2/interrupted 3.11 attempt. Those raw files remain separate and unchanged;
no partial/interrupted phase is counted as a passing fresh migration. Actual current
lab password-string scans report NO_MATCHES and normal owned-resource deletion/
absence is retained. Original P1 failure-before-STATE cleanup remains mandatory
in both new hosted jobs. Final exact-head hosted gates remain required.

Retain Draft; no native human approval/ReviewDecision/ShareGrant, cloud/provider,
customer/model/live site/paid calls or deployment. Human Gold0/26. Await Owner P2A
FINAL PASS only after six new CI jobs and original artifacts/checkout audit.

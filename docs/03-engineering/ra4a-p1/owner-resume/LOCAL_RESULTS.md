# Owner-authorized repair and main integration — actual local results

Ordinary merge commit 3eceea972ef1ec4bf68ee68654b90a5ff7e30a14:
ordered parents 47d90963520793f651b2d05e66747a633df6f130 (bounded fix),
9d138ba57e0b442b9dace1a2247d7aaa46ca38ac (Owner-accepted main).
No conflict/rebase/force/cherry-pick. Original latest-main files, including RA4C0
operator console, tests, and approved Dockerfile COPY, are compared blob/mode
exactly by MAIN_INTEGRATION_SCOPE.json; original PG SQL/business/tests unchanged.

On that functional source with real PostgreSQL 16.15:

| Runtime | PG integration | Pure tests | Compile/ruff/mypy/pip |
| --- | --- | --- | --- |
| Python 3.11.15 | 54 PASS, zero fail/error/skip/xfail | 11 PASS | all exit 0 |
| Python 3.13.13 | 54 PASS, zero fail/error/skip/xfail | 11 PASS | all exit 0 |

source-3eceea9/ contains complete raw stdout/stderr, JUnit, commands, actual catalog,
role/RLS/grants, migration v1 checksum, call reports, backup/dump/restore and actual
volume restart evidence. Actual SQL migration SHA256 remains
0557738e22e83a6f1c991e8c2a796749ce43845ad80fec44d8dc4c891fd9b5e2.
Both restore data hashes match; restart committed IDs persist and fsync,
synchronous_commit/full_page_writes are on. This is synthetic same-cluster
fresh-database restore, not certified cross-cluster disaster recovery.

The sealed resumed archive preserves the original startup RED/cause diagnostic,
cleanup classifier RED/fix, actual zero-deadline failure + three cleanup checks,
successful target SQL smoke and these new dual runs. Each stage stays separately
labeled. Actual local lab passwords are scanned before archiving; no password
state/Env is uploaded. Final local resource deletion/absence is recorded separately.

Final candidate adds evidence only after functional source; final exact-head
four legacy and two real-PG hosted jobs/artifact/checkout audit remain mandatory.
Keep Draft. No P1 FINAL PASS or merge until Owner independently accepts. No real
human identity, immutable object-service proof, approval, ShareGrant, actual Worker,
API/customer delivery, external calls/models/payment/deployment. Human Gold 0/26.

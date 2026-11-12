# Actual local P1 delivery evidence

Accepted base: 225ded57add21680171cfaecac9f89df6b1af155.
Tested final functional source: 2fae64777b44898281b9044169c4cc73ff63c19c.
Subsequent evidence-only delivery commit must retain these exact source blobs.

| Actual local gate | Python 3.11.15 | Python 3.13.13 |
| --- | --- | --- |
| Real PostgreSQL 16.15 integration, no mocks | 54 PASS / 0 fail/error/skip/xfail | 54 PASS / 0 fail/error/skip/xfail |
| Pure no-PG unit cases | 11 PASS | 11 PASS |
| compile, whole-vrae/tests + new integration/infra ruff, mypy, pip check | all exit 0 | all exit 0 |
| Real pg_dump/pg_restore + low-privileged restored RLS | PASS, exact data digest match | PASS, exact data digest match |
| Real container restart, committed queue and idempotency retained | PASS | PASS |
| Two concurrent connections / row locks / current-policy publication | PASS | PASS |

Every stage has separate commands.json, source manifest, stdout/stderr and JUnit.
pg-catalog-and-calls.json is actual pg_catalog output, not schema declarations
restated as evidence. backup-restore.json records actual dump hash/commands and
source/restored data hashes. Independent run snapshots differ in random UUID/time;
each restoration matches its own source, not a fabricated cross-run identical dump.
real-restart.json records actual owned data volume and fsync/synchronous_commit/
full_page_writes=on. SQL outbox remains private/undelivered; no native approval or
ShareGrant exists. Owned container/network/volume removal is recorded separately.

Initial 47/52/53-case stages and initial transport setup RED/fix remain labelled
as such. Raw logs with their actual extra trailing newlines are retained; source
whitespace checks do not rewrite historical raw execution bytes. raw-local-evidence.zip
is authoritative for original byte hashes where Git normalizes Windows newlines.

The original 81bac74 dual-runtime 54-case results remain unchanged. The only
functional-candidate delta after that was the owned teardown diagnostic handling
of Docker's omitted optional Tmpfs field. Its actual nonzero stderr is preserved;
no resource had been deleted at that failure. The fixed 2fae647 source is rerun
on both Python versions and its final owned-resource teardown must actually pass.
Restore proof uses a fresh database in the same disposable PG cluster; role/
credential bootstrap and independent-cluster disaster recovery are not certified.

SOURCE_SCOPE.json proves all original 3176 main blob/modes unchanged, including
old QA V1/V2, reviewing/reporting/Guard, Docker/CI/schema/dependency/Gold files.
All changes are new permitted Issue62 paths. No pyproject optional group was
needed; PG requirements are separate and pinned. The actual credential strings
are scanned out of the archive and neither state file nor passwords are committed.

## Hosted final gate

Before Owner acceptance, final exact PR HEAD + current accepted main must obtain
all four untouched original jobs and both new PG16 matrix jobs SUCCESS. Verify
actual checkout merge-ref ordered parents and raw logs. The original full jobs
must retain actual 127 D1/D2 and 118 RA3C QA V2 calls; new PG jobs must contain 54
actual real-PG calls, JUnit/catalog/backup/restart/teardown artifacts. Status/counts,
job links, precise final SHA and hashes are supplied in the final PR receipt;
earlier local/CI snapshots are never relabelled as newer HEAD results.

## Residual limits / NO_GO

This is RA4A P1 engineering ENTRY only. The migration administrator and synthetic
fixtures are trusted; runtime never receives those credentials. DB login roles
authenticate synthetic database principals, not real humans, and custom GUC/JSON
claims never create tenant authority. The production identity/object/review port
always refuses. No real source bytes in an immutable object service are supplied
by a row/digest, no real Worker/API, external broker, delivery, exactly-once promise,
native ReviewDecision, APPROVED report, ShareGrant or customer access exists.
The DB's dedicated network is loopback-published, not a kernel egress sandbox.
Full production disaster recovery/power loss/rotation, verified auth and protected
object integration need P2/RA4B and separate Owner GO. No paid/live/model/site,
cross-product link or deployment. Human Gold stays 0/26. Keep Draft, await
RA4A_P1_FINAL_PASS; no self merge/deploy and no full-stage EXIT claim.

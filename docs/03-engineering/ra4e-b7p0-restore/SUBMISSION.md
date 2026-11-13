# B7-P0 controlled Draft submission

Authority: [Owner third gate](https://github.com/gloweaseco-leo/VRAE/issues/81#issuecomment-6856373667).
Base: `4fd1ce15f4bc2e596111aa2e8fe86a2a46ba640d`.
Branch: `codex2/ra4e-b7p0-disposable-pg-restore`. No B4/0004 dependency.

This TEST_ONLY precursor creates fresh independent PG16 source/destination
containers, networks, volumes and credentials for each standalone run. Actual
custom pg_dump/pg_restore must preserve independent row/BYTEA/catalog roots,
accepted original 404/200 bytes, audit/outbox and TEST_ONLY review receipts.
Readiness follows import, exact manifest comparison, original-source verification,
actual runtime SQL permission audit, then another unchanged-state comparison.

Only 13 authorized table ACL representations become sorted effective tuples
(grantee/PUBLIC, grantor, privilege, grantability). NULL uses owner defaults;
explicit empty ACL has zero entries. Raw representations remain evidence.
Owner and relkind, default/column/schema/database/sequence/function ACLs,
membership and role attributes, RLS/FORCE RLS and actual SQL rights remain gates.
No sequence is fabricated when the catalog contains none.

Each complete pair executes 23 cases, including 650 actual private SQL denials
per audited source/verified destination, correct scoped reads, wrong-tenant and
revoked-principal/assignment denials, corrupt archive/SHA, pre-data-only import,
wrong target after a valid manifest control, actual blocked backend termination
and rollback, fresh recovery, lease/replay, and genuine post-import row mismatch.
Each interpreter repeats with a wholly fresh pair: 46 tests, four environments.

## Local and hosted execution

Install existing accepted locks, without editing them:

```sh
python -m pip install -e '.[dev]' -c requirements-ra1a.lock
python -m pip install -r requirements-ra4a-p2b2a.lock -c requirements-ra1a.lock
python -m ruff check integration/ra4e tests/operations/ra4e --select E4,E7,E9,F
python -m pytest -q tests/operations/ra4e/publication_checks.py
python -B -m integration.ra4e.run docs/03-engineering/ra4e-b7p0-restore/local-UNIQUE
```

Use Python 3.11 and 3.13 independently; output names must not exist. Docker is
required. Every run records actual HEAD, ordered HEAD parents, CI SHA/run ID,
source module hashes, migration hashes and tracked protected blob/mode digest.
No result is predeclared. Historical uncommitted-source results in `review/` are
explicitly prior evidence, not final committed-HEAD or hosted execution claims.
Original raw JUnit/logs remain local; the ledger preserves hashes and original
RED/ERROR/BLOCKED status. Rebuilt public XML contains only test names/status.

## Public artifact boundary

The workflow uploads **only** `public-artifact/`, after a successful scan gate
and complete file-inventory/hash readback. Export classifies known B7 producers:
source IDs, counters/hashes, SQLSTATEs, ordered stages, ownership/cleanup, raw and
effective ACL tuples on the authorized 13 tables, and names/status-only XML.
Runtime SQL matrices are reduced to counts/digests and scoped allow/deny proof.
Full catalogs, diagnostic snapshots, arbitrary files, raw JUnit/logs, dump archives,
state, generated passwords, keys and original BYTEA/graphs are excluded.
Each export has classification/provenance and SHA/size for every evidence file,
then token/key patterns and actual generated credentials are checked. Missing
credential inventory fails closed. The artifact action verifies the exact file
set and hashes; publication failure prevents upload even on a RED test run.
Failure-path checks cover credential match, token pattern, unknown files,
missing credential inventory and JUnit exception/stream stripping.

Only this isolated workflow is added. Existing standard four, PG two, identity
two and C3 read two jobs remain unchanged; B7 adds two. Actual scheduling and
conclusions must be read from GitHub. The first hosted cycle ends the authorization:
no retry, correction push, merge or ready-for-review transition without Owner.

## Limits

Legacy P1 broad grants remain security debt; compatibility is not least-privilege
approval. Dedicated bridges/loopback checks do not prove kernel egress isolation.
No authentic IdP, production API/Worker, native ReviewDecision, ShareGrant,
customer/site/model fetch, deployment, full B7 EXIT or G1/G2/G3 approval.
B7-P0 FINAL PASS remains pending Owner independent exact-SHA review.

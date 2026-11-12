# RA4A P1 real-PG entry slice, not production authority or RA4A exit

Owner Issue #62; baseline 225ded57add21680171cfaecac9f89df6b1af155.
Only new Issue62 paths are used; no existing pyproject, dependency, schema,
reviewing/reporting/Guard, test, Docker, workflow or operator console is changed.

## Trust and actual SQL boundaries

The lab pins official PostgreSQL 16.15 by image digest in infra/ra4a/image.txt.
Each lab has its own labelled container, dedicated network, data volume and
ephemeral SCRAM passwords in an ignored state file, never an uploaded artifact.
Only 127.0.0.1 is published. A dedicated bridge is NOT kernel egress denial;
no claim of browser-style network sandboxing is made for the trusted DB engine.
No cloud DSN or production credentials are discovered or accepted by the adapter.

Migration administrator is distinct from NOLOGIN/NOSUPERUSER/NOBYPASSRLS owner,
application and worker groups, and separate TEST_ONLY synthetic LOGIN principals.
The privileged migration/fixture administrator is trusted and can of course
reconfigure its own lab. Runtime roles cannot acquire it. The protected principal
and assignment tables map database SESSION_USER, not current_user, arbitrary
JSON, role names from HTTP, custom GUCs or report creator strings. SET ROLE to an
allowed group cannot change that login mapping. No human identity provider exists.

All eight tenant tables and both private principal/assignment tables have ENABLE
and FORCE RLS with explicit USING/WITH CHECK. Runtime SELECT is tenant-filtered;
direct INSERT/UPDATE/DELETE/TRUNCATE and private mapping access are revoked.
This is deliberate: direct same-tenant business writes must not bypass atomic
admission. Security-definer functions are owned by the non-bypass owner, use a
fixed trusted search_path ending in pg_temp, and revoke default PUBLIC execution.
Actual pg_catalog/privilege checks and direct SQL denials are acceptance evidence.

## Atomic metadata admission

The optional driver is separately pinned in requirements-ra4a.lock. Original
runtime requirements/CI remain untouched. Pure default-root tests import no PG
driver or database. Real DB tests live outside default testpaths in integration/ra4a.

In one actual PG transaction, admit validates synthetic login/active assignment,
current allowed policy/version and expiry, optional independently pinned source
ref, bounded payload hash and idempotency; inserts request+run+job+private outbox+
audit or rolls everything back. Policy/reference publication takes the same tenant
row lock as admission, so new versions do not race that validation. Keys are scoped
by tenant and actual test login. Same key/same command returns identical IDs;
different payload/policy denies. No 202 route, network capture or Worker exists.

SQL states/rows are explicitly TEST_ONLY. Outbox remains private and undelivered;
there is no external sender. Error messages and catalog dumps contain no raw HTML
or personal data. Idempotency/uniqueness and all mutation gates are checked in PG,
not an in-memory cache. The adapter returns only after its own transaction commits.

## References and immutable bytes

Trusted fixture bootstrap actually replays the original accepted native 404 and
200 sources through the unchanged D1/D2 builder. It binds complete target metadata,
Guard/policy/source/run/report/version, H0, full HTML/draft/editorial/layout/source
hashes and independent target/ref digests. 404 has one source-supported issue;
200 is coverage-only, zero/native-null. Neither can become APPROVED or shareable.
SQL rows cannot be overwritten; runtime cannot mint refs, while the migration-only
fixture seed uses independently held originals. Runtime commands compare the
expected ref hash to that protected row and refuse foreign/forged/stale refs.
Version tests create a new separately labelled native synthetic v2; they never
rewrite frozen v1 inputs/Guard or rebind evidence to make a case pass.

The stored metadata and synthetic-object key are NOT a verified object store or
proof of real-world truth. The private-object/verified-identity/transactional-human-
review production port is unimplemented and always denies. No native approve_version
or check_share call, ReviewDecision, APPROVED report, ShareGrant or external access.

## Queue and recovery

Actual FOR UPDATE SKIP LOCKED separates independent connections. Committed lease
token/sequence/owner/expiry are checked before finishing. A stale/expired token
cannot consume after another claimant; a completed same-token retry returns the
original event and does not double-consume the run. Delivery is at-least-once,
not exactly-once. Three failed leases become internal DEAD_LETTER. Side effects
and real Worker execution remain unimplemented.

Tests exercise real rollback, pg_terminate_backend, two concurrent connections,
actual clock expiry, committed queue across Docker restart on an owned volume,
and pg_dump/pg_restore retaining owner ACL/RLS and byte-equal canonical row data.
These are synthetic local/hosted engineering proofs, not production failover,
machine power-loss guarantees, real object durability or RA4A stage exit.

## Deferred and forbidden

P2/RA4B must supply verified identity/current authorization, protected actual object
bytes, transactional review decisions/CAS/audit/outbox integration, external broker/
Worker, production restore/failover/rotation and API contracts under another GO.
P1 adds no UI/API, HTTP 202, actual approval, ShareGrant, customer access, paid/live
model/site call, cross-product link or deployment. Human Gold remains 0/26.

Primary implementation references: [PG16 row security](https://www.postgresql.org/docs/16/ddl-rowsecurity.html),
[security-definer function requirements](https://www.postgresql.org/docs/16/sql-createfunction.html),
[session identity](https://www.postgresql.org/docs/16/functions-info.html),
[transactional locking](https://www.postgresql.org/docs/16/sql-select.html).

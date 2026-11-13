# RA4A P2A private bytes — synthetic PostgreSQL 16 contract

Entry: e9ec1bd7f36a0446af14f04b66b71e4d45ebfb97, freshly fetched and clean new
codex1/ra4a-p2a-private-bytes worktree. No Codex2 source or unmerged API imported.
This adds a private BYTEA store, not authentication, human approval or delivery.

Each exact tenant/source-run/report/version graph stores original complete draft
JSON, original HTML, complete source record, native evidence manifest/package,
Guard inputs, metadata, renderer version+CSS, target bytes, and every retained
source object. Original accepted fixtures and separately held SyntheticTrust pins
are replayed through the existing build_target/validate_target pipeline before
registration and after reads. None of the original native domain/Guard/producers
or test oracles change. Synthetic v2 uses the already accepted public producer;
it is explicitly a new test version, not a rewritten v1 capture.

The new ra4a_bytes schema is separate from P1. All three tenant tables use
ENABLE+FORCE RLS with USING/WITH CHECK; runtime app/worker/writer roles receive
no table SELECT/DML/TRUNCATE. Only app-role read_graph and a separate NOLOGIN
fixture-writer group register capability are granted. Per-test writer logins
are NONSUPERUSER/NOBYPASSRLS/NOCREATEROLE/NOCREATEDB and bound by the existing
protected SESSION_USER TEST_ONLY principal/tenant assignment, never JSON/GUC.
No real human identity or report-reviewer assignment is inferred from this.

register validates current policy/ref and holds the P1 tenant revision lock and
assignment locks. All parent+objects+one private registration event are atomic.
Stored SHA256 and lengths are PostgreSQL generated columns over actual BYTEA.
The complete graph and canonical sealed manifest are checked by a deferred
constraint at commit with fixed-search-path, non-BYPASSRLS owner execution.
Typed parts must exactly match original source components, not just equal JSON;
target/draft/HTML/source/CSS hashes bind the independently replayed P1 reference.
The graph/event seal forbids later object appends. Same key+same exact byte set is
idempotent, differing bytes/binding refuse. Composite FKs include tenant and
run/report/version. Each object/source/HTML is bounded by 8,000,000 bytes, target
by 65,536, complete graph by 64,000,000 and 137 typed objects. Oversize/incomplete
input is refused, never truncated.

Ordinary fixture-admin UPDATE/DELETE/TRUNCATE of stored records is refused, as
are runtime writes/reads of raw tables. Empty-schema test lifecycle resets are
allowed; disposable test databases may be dropped at teardown. This is not a
claim to resist a cluster superuser disabling triggers, changing DDL or destroying
its own volume. Such privileged fault injection is separately tested: regenerated
DB hashes do not replace independently held original content, and verified reads
refuse it. A fixture's transient process/DB role is not a production principal.

read_graph requires an exact tenant/ref/run/report/version/target locator and
current scope/policy/version; no listing/export/public link exists. The Python
read transaction holds authority/version locks while recomputing digest/length,
comparing the complete original byte set and replaying native validation using
outside provenance. It returns no verified result if any HTML/CSS/Guard/source/
target/object is absent, stale or altered. Old-version bytes stay immutable but
become unreadable through this port after newer reference publication. Read-only
verified data remains PRIVATE/NOT_APPROVED, including honest 200 native-null.

P2A schema drift is independently pinned in the ignored local lab state only
after trusted migration from empty schema; reapply checks migration SHA plus real
functions/constraints/triggers/RLS/ACL/generated-expression catalog fingerprint.
It does not bootstrap trust from a pre-existing server row or grant human rights.
The fingerprint is exported without credentials into raw catalog evidence.

P1 54 PG cases and 11 original pure cases remain unchanged. The new explicit P2A
files are selected outside P1's 54-case collection, with separate actual call IDs.
The full runner first executes P1-v1, applies v2 with reapply drift checks, runs
the unchanged P1 54 again against v2, then P2A. Original 11 and new 14 pure calls
are separately identified in JUnit even though the original pure runner collects
both files. Fresh per-case real PostgreSQL clones contain no prior byte graphs;
no test resets a populated immutable graph. Two-connection races, rollback,
mid-object pg_terminate_backend, native 404/200, stale/revoked/foreign refusals,
actual binary dump/restore and named-volume restart are mandatory, no skip/xfail.

P1 startup failure-before-STATE and idempotent cleanup tests are retained. The lab
only adds the authorized P2A evidence output directory; pinned image, SCRAM,
loopback publication, readiness and ownership cleanup behavior remain unchanged.
The PG workflow adds P2A execution/artifacts; four legacy jobs/Docker are intact.

Recovery certifies original held byte SHA/length, tenant and latest-version
refusal after logical restore into a fresh DB in the same isolated cluster and
actual container/data-volume restart. It is not cross-cluster DR certification.
Raw logs/audit events contain no customer data or report delivery; all retained
artifacts are accepted synthetic captures. DB administrator backup capability is
not public runtime raw access. This local bridge is not kernel egress denial.

Future RA4B ports need independently accepted authenticated human sessions,
protected object-service authority and transactional native/full ReviewDecision
CAS/audit/outbox. production_store_port and the original production port always
DENY. No approve_version/check_share, ReviewDecision, APPROVED report, ShareGrant,
real Worker/API/202/customer access, provider/model/site/paid/deploy calls are
implemented. Human Gold remains 0/26. Keep Draft and await Owner P2A FINAL PASS;
this is not RA4A FULL EXIT or RA4B authorization.

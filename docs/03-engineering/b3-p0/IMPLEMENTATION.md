# B3-P0 durable TEST_ONLY intent slice

Authority: [Owner exact code-entry decision](https://github.com/gloweaseco-leo/VRAE/issues/77#issuecomment-6867707779).
Accepted start: `cbcdb6f62d402861e8a12392f53061109a4a7d8b`.
New worktree/branch: `codex2/b3p0-testonly-atomic-review-intent`.

This implements a standalone disposable PG16 transaction core. It never creates a
natural-person ReviewDecision, APPROVED report, effective approval, ShareGrant or
external event. B4/PR83 and B5 UI mutation integration are absent. Full B3 remains
gated separately. The data/HTTP/error contract is in `contracts/b3_p0/README.md`.

## Additive database boundary

Explicitly apply accepted migrations 0001–0003 to a new disposable PG16 environment,
then apply `db/b3_p0/testonly_schema.sql`. Record that file's LF-normalized SHA256 in
`b3_p0.bootstrap`. Do not register it in `ra4a_private.migrations`: it is not a global
migration. The accepted P2A/P2B1 migration verifier runs after B3 bootstrap and must
still pass unchanged. A final canonical migration requires separate authorization.

Nine tables serve nine distinct purposes; receipt is stored with intent to avoid a
separate receipt table. No duplicate reviewer links replace accepted assignments.

| Table | Reason |
| --- | --- |
| bootstrap | Isolated B3 DDL fingerprint; original migration ledger unchanged |
| authority | Locked current tenant trust epoch, anchor status and expiry |
| witnesses | Immutable synthetic subject/SESSION_USER/Locator/epoch/deadline binding |
| states | Real SQL CAS, one terminal intent per report/version, sequence 0→1 |
| intents | Canonical command, immutable receipt, pins and permanently false effects |
| claims | Exact ordered canonical native Claim dispositions |
| sections | Exact ordered canonical required-section acknowledgements |
| audit | One immutable actor/command/receipt hash audit record per intent |
| outbox | One immutable stable internal-only event ID per intent |

All nine tables ENABLE and FORCE RLS. There is no PUBLIC or Reviewer raw table DML.
Only schema USAGE and EXECUTE on the two new SECURITY DEFINER entry points are
granted to the existing Reviewer group. Accepted object ACLs, role attributes,
memberships, function definitions and original source bytes are fingerprinted before
and after bootstrap. Runtime has an actual low-privilege Reviewer connection and
cannot receive admin, DSN, role, tenant or subject from an HTTP body.

`require_witness` uses accepted Reviewer load_target and current assignment/source
locking, followed by B3 authority/witness/state locks. It verifies actual SESSION_USER,
non-privileged role, current trust epoch, anchor status/deadline, witness deadline and
exact Locator; it rechecks source policy after authority lock waits. All SQL functions
use fixed pg_catalog search_path and schema-qualified application objects. Original
BYTEA is loaded and native ByteGraph/Guard/target/proposal verification runs inside
the adapter-owned transaction. SQL independently rechecks accepted byte pins and
closed Claim/section command structure. No old P2B1 receipt is promoted.

## Transaction and recovery semantics

CAS, intent, all Claim/section rows, receipt, audit and outbox COMMIT together. Deferred
constraints revalidate completeness and current authority at controlled commit-entry.
Actual write-stage failures and deferred COMMIT errors must leave no partial rows or
sequence advance. Same command/key/subject/actor/Locator returns identical receipt
bytes; fresh current witness/session is allowed. Conflicting payload/actor/subject/
version or a new key for an already closed version is refused.

All expiry checks use clock_timestamp(). A SECURITY DEFINER function cannot COMMIT.
An early SET CONSTRAINTS ALL IMMEDIATE can run deferred checks before physical
COMMIT; expiry can cross afterward. The explicit negative demonstrates actual
persisted intent/audit/outbox, a denied subsequent receipt and always-false approval/
external visibility. This is immutable TEST_ONLY history, **not a rollback**. The
normal adapter returns only after actual COMMIT and a new current-authority receipt
lookup. Unknown commit state never implies resubmission under a new key.

The SQL function's return value is a candidate byte sequence inside the caller's
transaction, including the fields that will be durable if COMMIT succeeds. Parsing
that candidate or inspecting its literal `durable` field is not evidence of COMMIT.
Only the adapter's completed transaction plus current-authority read may expose a
receipt over HTTP. Tests use an independent SQL observer after transaction exit to
distinguish persisted history from a rolled-back candidate.

The loopback test server retains opaque sessions in RAM and starts with empty
sessions. There is no IdP/login/provisioning endpoint. Private fixture provisioning
issues fresh synthetic witnesses. On database restart/restore, the private recovery
ceremony increments authority.epoch **before** new server sessions can be provisioned;
restored old witnesses are denied. Fresh matching synthetic subject/role can recover
exact historical receipts. A restore target must remain unserved until this ceremony.
This is an explicit disposable test procedure, not automatic production recovery.

Custom-format pg_dump/pg_restore uses a separate real PG16 container/volume/network,
with independently created accepted roles and private destination passwords. An
independent B3 schema/data/security fingerprint includes all nine new tables, functions,
constraints, triggers, policies, default ACLs, columns, schema ACL and actual effective
table privileges. The unchanged B7 observer checks all accepted business schemas;
it is not used as a substitute for the new B3 manifest. Both 404 and 200 originals
are independently reverified through the actual restored Reviewer read path.

Raw ACL arrays remain evidence. B3's nine-table comparator reuses the accepted ACL
expansion helper: NULL uses owner defaults; an explicitly empty ACL stays empty.
The initial real restore found explicit owner ACL arrays restored as NULL defaults.
Only semantically equal expanded entries compare equal; no permission check is
removed. Function/schema/column/default ACL and role inheritance checks stay separate.

Outbox is a real immutable PG ledger. The test consumes its stable event ID twice
into an independent private on-disk SQLite receipt ledger, reopens that ledger, and
observes one row. This demonstrates test processing deduplication, not B4 delivery,
an external queue, customer sharing or exactly-once business effect.

## Verification and retained failures

Run with existing locked dependencies only:

```
python -B -m integration.b3_p0.run <unique-run-label>
```

Use Python 3.11 and 3.13 separately. Each creates its own authenticated loopback PG16
source and an independent PG16 restore destination. Tests exercise native 404/six
Claims and 200/three coverage Claims; missing/malformed sections, Guard/Locator/
revision; stale CAS; actual separate-connection duplicate/conflicting races; wrong,
expired or revoked witness/anchor/assignment/principal/tenant/role; replacement source
policy; every write stage; actual deferred COMMIT failure; expiry/revocation during
observed PG lock waits; early constraints followed by real commit after expiry;
lost HTTP response; fresh-witness recovery; empty sessions after server restart;
DB down/restart; exact restore; truncated custom archive; raw SQLSTATE 42501 access.

Private logs, raw failure XML, archives, capabilities and credentials remain under
ignored `integration/b3_p0/.runtime`. Public exports contain bounded summary/source
hashes, passing native JUnit and explicit metadata-only SQL/restore observations.
Failures export bounded case IDs and original raw JUnit/log hashes, without traces.

The retained development run `dev-evidence-311-01` had 119 passes and two failures:
the raw ACL representation difference and Windows closing a request with an unread
body before rejecting an old session. The comparator retains raw ACL and compares
effective permissions; the server consumes the bounded body before session rejection.
The run also records source_unchanged=false because development continued during it;
it is not final acceptance evidence. A dedicated restore/lost-response rerun passed
2/2 before final frozen-source dual-minor runs. No assertion or old permission was
removed to obtain that result.

The first frozen 124-case runs passed on both minors. Four independent real-read
negatives were then added for HTML, SOURCE, GUARD and MANIFEST byte pin mismatch;
they reject malformed independent provenance while leaving original database bytes
and all B3 business counts unchanged. Expanded run 02 had 127/128 on both minors:
under concurrent full-suite load the one-second witness expired during the early
SET CONSTRAINTS check, correctly raising 42501 before the intended phase. The final
test uses a 20-second setup window and sleeps until the recorded database deadline;
it also asserts that the write function returned before the deferred expiry wait.
Runtime SQL, permissions, adapter code and all denial/completeness checks are unchanged.
Run 03 passed 128/128 on both minors. A final transport change consumes a valid
bounded body before Host/Origin/token policy denial too, consistently avoiding the
same unread-body reset across all refusal paths. Framing errors still fail closed.
Final acceptance uses `final-311-04` and `final-313-04`, not the earlier runs.
The native default-suite image tree predates only that new HTTP adapter refinement;
the changed adapter is covered by the final dual PG/HTTP suite and current full mypy.
All accepted implementation files and default test files remain identical.

An additional Windows default-suite attempt completed with 2446 passed, two failed
and 25 original host-isolation skips. It recorded an unchanged legacy collection
rate-timing assertion (31ms versus the 35ms minimum) and a GBK decode error in an
unchanged domain source scanner because that broad probe lacked PYTHONUTF8=1.
The timing case passed on retry and all 43 tests in that file passed; the domain
file is separately rerun with UTF-8 mode. The dedicated dual-minor B3 runner always
sets PYTHONUTF8=1. A first reused Linux image inherited VRAE_ISOLATED_LAB=1 without
the required firewall setup; that interrupted setup-red run is retained. Ordinary
default Linux runs explicitly use the original default marker (0), and the separate
kernel run uses the original entrypoint, NET_ADMIN setup and permanent capability
drop with marker 1. Slow Windows bind-directory attempts were interrupted when
moving the same test set to a container-local exact Git index snapshot. The native
copy is checked against every staged blob; Git archive's CRLF conversion is recorded
and only LF-equivalent text differences are permitted. No binary difference is waived.

Final exact results and hashes are in `evidence/*/summary.json`, native JUnit and
`observations.json`. The final report distinguishes default-suite host isolation
skips from the B3 PG/HTTP suite, which must have zero skips/errors/failures.

Only one new workflow adds two PG16/HTTP/restore jobs. The existing six workflows
remain unchanged: standard 4 + PG 2 + B2 2 + C3 2 + B7 2 + B5A 2 = 14; B3 adds 2
for a prospective total of 16. Hosted green is asserted only from actual first-cycle
results. Owner controls exact-SHA FINAL PASS and merge. No rerun, correction push,
merge, deployment or real identity/approval/share is authorized after that cycle.

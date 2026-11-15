# Specific L3 actions held; independent producer work continues

Entry: Owner Issue94 comment6893770402, main67acff97689514fdede01f2aab81dd5a7a96b9cd.
No proposed SQL below or in the diff has been executed. No db/ra4b_p2 source
has been installed, no migration0001..0004 changed, no old role/ACL/RLS/function
modified. This is not a request to suspend all independent C1 code.

## Actual port audit

Both native Linux Python minors in independently owned network-none PG16:
APP UID10001 gets HTTP202 only after COMMIT; a separate original UID10002 Worker
claims and completes that exact job. The original entrypoint emits DONE without
generating or persisting any report. `claim()` exposes exactly job_id, run_id,
lease_token, lease_seq, lease_until; no current source/epoch or result locator.

Actual `ra4b_test_a_worker` has only claim/finish in the accepted schemas.
Native attempts to read requests.source_ref, origin_epochs.epoch, call the old
read_graph or register all return42501. Actual p2b1_test_a_reviewer gets42501
for B4 status and origin reads. New authoritative source/commit/read functions
do not exist. Positive and negative IDs are in integration/ra4b_p2/audit_cases.py.
The strengthened audit has ten cases per minor, adding genuine APP/Worker UID
bootstrap-secret read denials after private-directory hardening. Earlier eight-
case results and the initial teardown ERROR remain historical records. This does
not turn absent S2 functionality into PASS.

## Minimum new transactional privileges requiring separate authorization

Proposed new SECURITY DEFINER ports, under `db/ra4b_p2/**`, owned by
ra4a_owner, fixed search_path=pg_catalog,ra4b_p2,pg_temp, PUBLIC EXECUTE revoked:

```sql
-- Precise proposed identities, not installed placeholder functions.
ra4b_p2.load_leased_source(text,uuid,uuid,integer)
ra4b_p2.commit_generated_result(text,uuid,uuid,integer,bytea,bytea,bytea)
ra4b_p2.read_assigned_generated_result(text,uuid,text,integer,text)

-- Proposed grants, only after real function implementations are reviewed:
GRANT USAGE ON SCHEMA ra4b_p2 TO ra4b_worker,p2b1_review;
GRANT EXECUTE ON FUNCTION ra4b_p2.load_leased_source(text,uuid,uuid,integer),
 ra4b_p2.commit_generated_result(text,uuid,uuid,integer,bytea,bytea,bytea)
 TO ra4b_worker;
GRANT EXECUTE ON FUNCTION
 ra4b_p2.read_assigned_generated_result(text,uuid,text,integer,text)
 TO p2b1_review;
```

load arguments are trusted tenant/job/current-token/current-seq; its locked DB
join must derive request/run/worker/expiry/epoch/policy/reference and return only
the exact authorized raw SOURCE bytes and hashes. No caller-supplied task ID,
reference, epoch or actor becomes authority. Recheck original require_run and
actual current lease, scope and origin under the genuine Worker SESSION_USER.

commit arguments add private canonical result/source-proof/HTML bytes. Within
one transaction, verify same-job current source/lease/epoch, persist the complete
result graph/locator/hashes/version plus unique audit/outbox, and call original
finish exactly once. Its deferred checks must still hold at COMMIT. Separate old
finish followed by a forged result must refuse: no LEASED current row means no
new result. No status-only or preseeded-report substitute. The original
ra4a_bytes.register is fixture-writer-only; no runtime Worker membership or raw
old-table GRANT may be added to bypass that42501. Any new narrowly bound sealing
routine that writes the original immutable byte graph/reference objects for
original B3 load_target therefore needs explicit Owner review/authorization;
a second private result table alone does not satisfy the business contract.

read arguments are server-held tenant/job/report/version/digest pins after
verified Reviewer identity. Verify actual current B3 assignment and original
load_target for the generated report before origin/job projection. Missing,
foreign, expired, revoked or stale records expose no private bytes. Neither
administrative runtime SELECT nor caller-supplied actor/UUID is acceptable.

## First protected-object delta, explicit and unexecuted

The two old origin policies in0004 lines42–51 use SESSION_USER restricted to
the four B4 APP/Worker identities. A new SECURITY DEFINER owned by ra4a_owner
does not change SESSION_USER. FORCE RLS remains active. Thus adding an owner
read wrapper by itself cannot establish current origin for a Reviewer. This is
the same protected boundary retained in the old Issue90 history; that old work
is not imported and its outcomes are not new-main acceptance.

Read-only review of the retained SCOPED_ROW_LOCK_STOP.md shows an authentic old
PG16 counterexample: SELECT-only policies expose rows but SELECT FOR SHARE/KEY
SHARE still return zero because locking SELECT also checks UPDATE USING. That
history is not rerun or asserted to be new-main PASS. A SELECT-only exception
therefore cannot be proposed as a complete current-authorization solution.

PROPOSED_ORIGIN_READ_LOCK.diff requests exactly two scoped SELECT policies and
one epoch UPDATE-USING policy WITH CHECK(false), only to enable the precise
epoch FOR SHARE lock. The immutable request binding can be read without its row
lock; the table's AccessShareLock still blocks TRUNCATE. No old policies or
WITH CHECK clauses change, no raw-table grants or membership change. A new
private INVOKER predicate current_generated_binding must first be implemented
in the approved new schema and independently reviewed: it binds an actual
Worker-produced committed result/native graph to the currently assigned report,
tenant/request/run/job/source/policy/versions/hashes, and does not query origin
tables recursively. It is not an installed stub or caller-controlled boolean.
The diff is an exact proposed policy delta, not an executable standalone schema
or a claim of passed row-lock/DML behavior. Definer UPDATE/DELETE/INSERT,
unassigned/cross-tenant visibility and exact concurrent epoch locks all require
native new-main verification before acceptance. This protected capability
extension remains held for Owner; no broad OR true, BYPASSRLS, SET SESSION
AUTHORIZATION, timeout or trust-list exception is proposed.

PostgreSQL16 command-specific policy semantics:
https://www.postgresql.org/docs/16/sql-createpolicy.html
https://www.postgresql.org/docs/16/ddl-rowsecurity.html

## Existing DB-name separation, to avoid an unnecessary protected edit

Original B4 store/Worker binds vrae_ra4a_p1; B2 IdentityBoundary and B5A profiles
require vrae_p2b1_<12hex>. Do not relax either original validator. Prefer a new
fixed-role S2 connection/Worker adapter in the authorized new namespace, using
accepted claim/finish SQL in the same isolated Reviewer database. No second
backend or second SSR. That future adapter and genuine signed Reviewer route
must be tested against the approved transactional seam; none is claimed here.

## Required future positives and negatives (NOT PERFORMED)

`test_real_worker_generated_commit_and_assigned_signed_read`,
`test_generated_result_idempotent_restart`,
`test_expired_foreign_replayed_lease_no_result`,
`test_forged_done_plus_report_denied`,
`test_source_guard_version_scope_mutation_denied`,
`test_revoke_epoch_cancel_race_before_commit`,
`test_sigkill_reclaim_no_half_persistence`,
`test_reviewer_raw_42501_and_no_approval_share`.

These require genuine dual Python PG16/low-UID Worker/signed Reviewer, unchanged
700ms/1s/8s/25s/30s/3600s bounds, original source/role/ACL/RLS fingerprints,
native XML/cleanup and new-head CI. Current pure producer PASS cannot replace
them. No Draft PR, new CI or S2 PASS is asserted before these ports are real.

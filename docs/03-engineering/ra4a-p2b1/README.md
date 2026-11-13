# RA4A P2B1 — private TEST_ONLY proposal transaction

Current acceptance generation is **V3 / 131 live PG cases**. Candidate 292b030
was withdrawn after a real raw-SQL/native Unicode blank-reason discrepancy.
See `UNICODE_NATIVE_PARITY_REPAIR.md`, `FROZEN_MATRIX_V3.json` and the V3
source/scope/result/archive files. Older 98-case results and the original local
archive remain historical evidence; their PASS is not a waiver of this repair.

Refs Issue #70. Entry main: `558d183624a0a36d1f4eaf9d3d75af73b9c88547`.

Every persisted outcome carries `TEST_ONLY_SYNTHETIC_DECISIONS_NOT_HUMAN_APPROVAL`.
This work does not create a natural person's approval, native ReviewDecision,
APPROVED report, ShareGrant, identity provider integration, HTTP endpoint or sender.
The production port always refuses, including purported verified actor/token input.
Human Gold remains 0/26; RA4 EXIT and RA5 live remain NO-GO.

## Transaction model

The additive `ra4a_review_test` schema has seven FORCE-RLS tables. Only three
fixture principals inherit the dedicated non-superuser, non-BYPASSRLS group.
Runtime can call two narrow SECURITY DEFINER functions; it cannot select or
mutate the tables. The migration owner is the existing NOLOGIN `ra4a_owner`.
Existing P1/P2A roles, function ACLs and schemas are unchanged.

`TestOnlyReviewCAS` only accepts PG16 loopback fixture databases whose names
match `vrae_p2b1_[0-9a-f]{12}` and an explicit TEST_ONLY mode. Authority is DB
SESSION_USER plus current tenant/report assignment and current P1/P2A policy,
reference and original byte graph. Client actor dictionaries and GUCs convey no
authority. Current report-version publication, revocation and reviews serialize
using the existing tenant lock; assignment/principal locks remain held.

The Python transaction reads original BYTEA, verifies each hash/length, replays
the full accepted P2A/native target producer against independently held expected
bytes and calls frozen `validate_proposal`. SQL independently checks the complete
source graph, target binding, claim identity/ceilings and all section acknowledgments.
Deferred commit validation rechecks authority, current bytes and policy expiry.

There is one first-writer transition per `(tenant, report, version, review_seq=1)`.
All three review outcomes close that version. A genuinely new current P1/P2A
version is required to begin another round at sequence 0→1; a separate monotonic
`report_event_seq` preserves history across versions. No command reopens a closed
version. A zero-finding target uses a separate coverage proposal, producing only
`SIMULATED_INTERNAL_SCOPE_ACK`.

The SQL CAS writes state, proposal, ordered claims and sections, one private audit
row and one undelivered private outbox row in one transaction. Append-only and
deferred completeness constraints prevent partial commits. The receipt is returned
after COMMIT. An exact current, authorised canonical-command retry returns the
same stored receipt bytes/IDs. The key is report-wide across actors/versions;
different payload, source or SESSION_USER refuses. Insignificant JSON whitespace
is canonicalized; actual payload values/order are not rewritten.

## Evidence and execution

`infra/ra4a/p2b1_run.py` defaults to a fresh-cluster full run: unchanged P1 v1 54,
P1 v2 54, P2A 86, original 25 pure tests plus separately counted P2B1 tests.
`--phase p2b1` is a development-only partial run, never evidence of the full gate.
Each invocation preserves raw stdout/stderr, command exit/time/hash, source
snapshots, true JUnit node IDs and actual call receipts. No skip/xfail is added.

Numbered live cases exercise native claim/section persistence, zero-case ceiling,
closed versions, idempotency/key collisions, runtime DML/role/tenant negatives,
assignment/policy revocation, malformed reasons and source ranges, substituted
targets, privileged clone-only byte corruption with recomputed DB hashes, rollback,
kill before/after commit, independent-connection races, controlled adversarial
commit order, schema drift, append-only sealing and actual backup/restore/restart.
Privileged fault injection explicitly occurs only inside disposable clone databases;
it is not a supported mutation API or resistance to a malicious cluster superuser.

The dedicated PG workflow retains startup-before-STATE failure cleanup, pinned
image/driver, original assertions and normal teardown. Its timeout is 30 minutes
to accommodate the full accepted prelude plus additional concurrency/recovery;
the four original workflows and Docker configurations remain unchanged.

## Remaining boundaries

No genuine reviewer identity/signature, native decision application, customer
access, production durability service or external outbox delivery is implemented.
Cluster administrators can disable triggers; held-source/native replay still
detects the tested corruptions. The tenant lock intentionally serializes reviews
within a tenant; throughput tuning is outside this acceptance package. Exact
current policy/assignment is required even for retry, so a revoked or stale caller
cannot retrieve an old receipt through the runtime port. Historical records remain
available to trusted fixture migration/audit tools.

Final source SHA, dual-runtime results, six CI runs, merge-ref parents, checkout
logs, raw artifact hashes and remaining risks will be recorded before Owner review.
Keep the PR Draft and stop for exact-SHA `RA4A_P2B1_FINAL_PASS`.

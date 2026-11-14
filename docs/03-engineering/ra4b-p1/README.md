# B4-P1 private runtime candidate — Issue #78

Scope: `TEST_ONLY_PRIVATE_RUNTIME_CANDIDATE`. G1/G2/G3 remain NO-GO.
No merge, deployment, public API, external identity authority, human approval or
ShareGrant is authorized by this implementation or its synthetic receipts.

The private loopback API durably admits one of two accepted synthetic source
references in PostgreSQL16 and returns HTTP 202 only after COMMIT. A separate
OS process uses its own restricted database identity to claim a persisted lease
and commit a guarded TEST_ONLY consumption receipt. GET reads persisted status;
cancellation explicitly returns 501. The runtime has no external network route.

## Accepted source and authority

Owner's [origin epoch GO](https://github.com/gloweaseco-leo/VRAE/issues/78#issuecomment-6850948205)
authorizes only additive 0004 and B4-owned paths. The subsequent
[accepted-main synchronization](https://github.com/gloweaseco-leo/VRAE/issues/78#issuecomment-6853164256)
requires accepted main `4fd1ce15f4bc2e596111aa2e8fe86a2a46ba640d`.
It was merged normally into this branch as
`f096f730384ed9dfe68c099ea00fbe67ed4f73f3`; its ordered parents are the previous
B4 preflight commit and that accepted main. B1/B2/C3 source is preserved.

0004 creates separate B4 roles with no legacy group membership or raw table
grants. Runtime credentials may execute only named B4 admission/status or
claim/finish functions. Those functions retain FORCE RLS, fixed search paths,
the original ten policies and the actual SESSION_USER tenant binding. The
original eight `ra4a_%` roles and eight `ra4a` tables remain unchanged.

An actual authorized APP initializes its monotonic epoch at first admission.
An immutable request binding records that actual APP and epoch. AFTER triggers
on original principal/assignment mutations use trusted OLD/NEW values and
transactionally advance only existing B4 epochs. They never copy grant flags
or let Workers read another actor's private rows. Tombstones survive disable,
re-enable, replacement, tenant moves and truncation. Old tasks cannot revive
on regrant; a new idempotency key is required for a new authorized task.

The bounded trusted fixture mutator is the actual `postgres` session; API and
Worker never receive its credentials. Unsupported source mutators fail closed.
Lock order is the actor's own authority, ordered origin epochs, tenant/policy
gate, then job. A trusted administrative transaction combining authority and
policy changes must mutate source authority/epochs before the tenant gate.
Transactions use the server's normal READ COMMITTED and initially deferred
commit guards. Current source/policy/version, origin epoch and lease/CAS are
checked before returning a claim and again on the effective mutation commit.

## Evidence and reproduction

`LOCAL_ACCEPTANCE.json` is generated only after all final native gates pass.
It records native JUnit counts, source hashes, protected-path checks, actual
catalogs, cleanup and privacy clearance. `accepted-main-*` folders are the final
fresh runs after synchronization; older runs remain diagnostic history.

Final local matrix: both Python minors pass staged P1 54/54, P1-v2 54/54,
P2A86, post-0004 P1 54/54, B4 46/46, P2B1 131/131, B2 crypto73 + PG30,
C3 29/29 and ordinary 2421 passed / 25 deliberately deferred (2446 discovered).
QA118 and Review127 pass without skips in each ordinary suite. Separate HTTP24
and actual browser16 cover those exact 25 deferred integration cases.
`accepted-main-runtime311-v3` and `accepted-main-runtime313-v3` pass the full
runtime and recovered phases, including observing the actual APP in COMMIT
before policy expiry and then a 403 with all admission rows rolled back.
All owned PG, runtime client and source-volume cleanup is verified.

Use an installed locked Python3.11 or3.13 environment from this worktree:

```text
python docs/03-engineering/ra4b-p1/run_full.py <unique-pg-label>
python docs/03-engineering/ra4b-p1/c3_compat.py <unique-c3-label>
python docs/03-engineering/ra4b-p1/unit_lab.py <unique-unit-label>
python docs/03-engineering/ra4b-p1/runtime_lab.py <unique-runtime-label>
python docs/03-engineering/ra4b-p1/legacy_labs.py <unique-isolated-label>
```

The frozen P2A seeder/verifier requires the ledger at 0001/0002, so the full
runner executes P1-v1, P1-v2 and P2A before adding 0003/0004, then reruns the
full frozen P1 suite after 0004. P2B1 and B2 follow. C3 retains its accepted
private bytes database at 0001/0002 while B4's canonical task database advances
to 0004; C3's original 29 tests, including actual restart, run unchanged.

Ordinary discovery intentionally defers exactly 24 original isolated HTTP
tests and one browser integration test. Those 25 are never counted as ordinary
PASS. `legacy-isolated-v1` executes all HTTP24 with the original TLS/firewall/
unprivileged setup and the unchanged browser supervisor's 16 actual scenarios.
The final acceptance joins these separate gates with both ordinary suites.

The runtime harness verifies different API/Worker UIDs, no child capabilities,
real SIGKILL/reclaim and three-attempt dead letter, response loss/idempotency,
HTTP parser/security negatives, HTTP expiry during COMMIT, genuine PG outage,
actual dump/restore/restart, persisted 404/200 metadata, and owned cleanup.
Only source-code volumes are used; private configuration stays in protected
tmpfs. Dump bytes stay inside the owned PG container and are destroyed on exit.

## Historical RED remains evidence

- `actual-311` / `actual-313`: original raw-table and unguarded-finish RED.
- `sql311-v4`: frozen role-count 53/54; `compat311-v1`: policy-count 53/54.
- `original-rls311-v1` / diagnostic: original **42501
  RA4B_ORIGIN_APP_DENIED**, with no business-state advance.
- `epoch311-v1`: incorrect harness stage attempted P2A after migration0003;
  `epoch-full311-v1`: one original five-second connection timeout, retained.
- `epoch311-v2`: a new test incorrectly expected an already leased job to
  raise on claim instead of returning no job. It now separately proves the
  actual held lease cannot finish after revocation; no frozen oracle changed.
- `epoch-final311-v1`: executed bytecode retained the old test's `CONSUMED`
  audit literal while linecache showed the subsequently corrected
  `TEST_ONLY_CONSUMED`. The resulting 43/1 is retained; final gates freeze code
  before launch and execute all 46 cases.
- Early runtime harness failures, ordinary Windows-bind runs stopped with
  explicit non-PASS status, and the original unit postprocessor's mistaken
  rejection of 25 deliberate discovery skips remain visible. Native JUnit was
  preserved and separately reclassified; later final full runs use the corrected
  classifier. This never converts an isolated case to ordinary PASS.
- `accepted-main-c3311`: original P2A migration-order precondition rejected the
  first new C3 wrapper. The corrected wrapper seeds at the original accepted
  stage before adding B4 to its own database.
- `accepted-main-runtime311` timed out awaiting the first Worker log;
  `accepted-main-runtime311-v2` returned a safe HTTP403 but did not observe the
  required COMMIT/PgSleep window under concurrent regression load. These
  are failures, not evidence of a successful full runtime gate. Their logs and
  cleanup remain; subsequent complete acceptance must pass unchanged bounds.

Historical STOP documents describe their own time and are not the current
decision. Privacy views in `PUBLIC_EVIDENCE_VIEWS.json` replace ephemeral
credentials and local user-home prefixes only. Exact originals remain under
ignored `.runtime/original-evidence`, with original/public SHA256 mappings.
Assertions, SQLSTATEs, failures and counts are preserved. Historical source
hashes describe their original version, not the current repaired source.

## Limits awaiting independent Owner acceptance

This is a bounded synthetic candidate. Legacy roles retain the historical raw
read/unguarded completion debt demonstrated by the original RED. An invalid
origin job can fail closed and block that tenant's bounded queue; no retirement
or cancellation workflow is claimed. The epoch protocol covers the authorized
private principal/assignment transaction path, not a production IdP or cluster
administrator lifecycle service. There is no runtime UI-to-human approval path.
Only a Draft PR and genuine CI evidence may follow complete local acceptance;
Owner independently decides acceptance. Never self-merge or deploy.

# Codex3 — current-main Beta integration (Issue96 / Issue97)

TEST_ONLY / NOT APPROVED. Component verification is not full end-to-end Beta PASS.
Human Gold remains0/26; B1/B2 remain2/7; G1/G2/G3 NO-GO.

Independent worktree `D:/Projects/VRAE-codex3-BetaIntegration-20261114`, branch
`codex3/beta-integration-20261114`, accepted base `447005b2951f43e8d8643632d663de268f278329`.
Only Owner-accepted main may be merged subsequently. No sibling Draft/A1/B7/Gold code or data imported.
Current authority is the latest body of Issue96 and Issue97, not old comments or withdrawn schedules.

## One runnable entry

On this Windows machine, use Docker Desktop, Node with built-in WebSocket, installed Google Chrome,
and Python3.11 or3.13 with `requirements-ra4b-p1.lock`. The current private host environments are
`integration/beta_review/codex3/.private/py311/Scripts/python.exe` and `py313/Scripts/python.exe`.
Native Linux runtime uses the existing dependency-only `vrae-ra4b-p1:311` / `:313` images by image ID,
with a NEW accepted-main source snapshot mounted read-only. No sibling image source is executed.

From the worktree root, in terminal1:

```powershell
& integration/beta_review/codex3/.private/py311/Scripts/python.exe scripts/beta_internal.py start --run operator-311-001 --minor 3.11
```

Keep this foreground controller running. It boots a fresh owned PG16 and original API, invokes real
APP admissions and independent UID10002 Worker, starts the original signed read-only SSR in a separate
restricted-profile process, verifies real HTTP reads and Chrome1280/375/320, then prints the actual
`http://127.0.0.1:<allocated-port>` URL. The API's original fixed8765 listener is inside the private
PG network namespace; it is not exposed as a new host API. PG publishes only an allocated127.0.0.1 port.
There is no public preview/tunnel or second website. The accepted bridge bootstrap does not establish
kernel egress denial; all diagnostic input uses the explicit in-memory synthetic transport, and Chrome
uses a deny proxy/DNS plus request interception. No real external audit request is performed.

In terminal2:

```powershell
& integration/beta_review/codex3/.private/py311/Scripts/python.exe scripts/beta_internal.py status --run operator-311-001
& integration/beta_review/codex3/.private/py311/Scripts/python.exe scripts/beta_internal.py open --run operator-311-001 --task 404
```

`open` obtains a fresh challenge and a genuine Ed25519 signed TEST_ONLY token through the accepted
identity/session endpoints, then opens an isolated interactive Chrome profile with the actual session
cookie. It does not create a natural-person identity or effective approval. Use `--task 200` for the
coverage-only counterpart. Raw tokens/keys/cookies stay private, not in command-line arguments or logs.
Close that Chrome window when finished. Alternatively `session` writes a private cookie document for
an Owner-controlled local HTTP client, without printing it. A bare browser URL initially shows the
original login page; it does not bypass authentication. Sessions/assignments expire normally.

Stop from terminal2 (or wait for the bounded30-minute auto-stop):

```powershell
& integration/beta_review/codex3/.private/py311/Scripts/python.exe scripts/beta_internal.py stop --run operator-311-001
```

The controller terminates only its own API/Worker and SSR, verifies exact Docker ownership labels,
removes its PG/network/data/source volumes, and checks the SSR port is closed. Keep the original
private outputs and sanitized RED/cleanup records. If the controller crashes, do not delete state or
remove arbitrary containers; use the exact ownership receipt under that run and the original Lab
cleanup routine, or the documented receipt to report a scoped cleanup failure.

For unattended validation with automatic teardown:

```powershell
& integration/beta_review/codex3/.private/py311/Scripts/python.exe scripts/beta_internal.py verify --run verify-311-001 --minor 3.11
& integration/beta_review/codex3/.private/py313/Scripts/python.exe scripts/beta_internal.py verify --run verify-313-001 --minor 3.13
```

Every run label is single-use. `verify` invokes real pytest with stop-on-first-failure, preserving the
native raw JUnit privately and publishing a sanitized projection with the raw SHA/CRC receipt.
`component-stages.xml` is the separate runner-stage assertion record; it is not mislabeled native
pytest output. Default protected pytest IDs are unchanged; these tests are explicitly invoked.

## What actually runs, and the first missing seams

| Edge | Current accepted implementation / real result | First missing interface and owner |
|---|---|---|
| SourcePolicy -> captured offline original | Existing Collector/SafeFetcher + explicit synthetic transport; only GET | No customer/network collection authorized |
| Evidence -> six-rule Execution -> Findings | Explicit `ra2b6-1.0.0`, six enabled and ten disabled; live404/200/DISC inputs | No invented future findings |
| Findings -> per-claim Guard -> report | Existing public producers replay actual new source; CTA404 one issue,200 zero | DISC finding is unsupported by current Guard/renderer: C1 Issue94 |
| POST -> request/run/job -> Worker | Original HTTP202, separately observed COMMIT, original low-role claim/finish DONE | Worker does not call Collector/rules/Guard/report and cannot persist new result graph: C1/Owner |
| Source/version -> report task | Original approved references and signed read-only original graph | No accepted B4 assigned-task/status bridge: C1 B4-P2 |
| Signed Reviewer -> PG original -> SSR | Original B5A identity/session/reader/SSR; real version/assignment checks | SSR uses independently seeded accepted original graphs, not the newly generated pipeline output |
| SSR -> durable per-claim TEST_ONLY intent | Original preview is unsaved, not native approval | PR89 pending Owner merge: C2 |
| Private versioned access -> delivery | Original guarded local report bytes; no enabled sharing | B6 PR92 pending after PR89; old missing share route returns501, not B6 EXIT |
| Cross-environment recovery / stale queue | Historical RED and MAX3 remain preserved and PAUSED | S4 new exact accepted-main safety GO required |

The live diagnostic outputs, B4 admitted source references and SSR sealed originals are three explicit
provenance lanes. Exact request/run/job UUIDs and epochs are in the private native linkage; public output
uses hashes. Never identify these lanes as a connected task-to-report chain. No handwritten task rows,
mock202 responses, admin runtime, SET ROLE/BYPASSRLS, alternate API or weakened Guard are added.

## S1 through S5 closure discipline

S1 delivers the running original components, live diagnostic pipeline, explicit missing-interface matrix,
actual signed read-only browser path, native tests and scoped cleanup. S2 merges ONLY newly Owner-accepted
main and verifies the C1 report/task bridges and C2 signed persistent intent when present; no import from
PR89, PR92 or B4-P2 Draft branches. S3 verifies accepted B6 exact-version/private/revocation/deny interfaces
when merged; a501 missing route today is not a completed delivery gate.

S4 stays in the final exit ledger: full PG16 three-DB/six-schema restore, SIGKILL/restart/lease, identities,
ACL/RLS/source hashes, stale old-first queue and unique audit/outbox, plus B historical handling. Restart
needs Owner's NEW exact-main authorization, including any deterministic TEST_ONLY seeded-ID exception or
protected RLS/operator permission change. MAX3 is not reset and no new sorting experiments are run.
Historical hashes are not restorable snapshots. No B7 recovery/SQL implementation is imported here.

S5 remains NOT READY until one Owner-accepted SHA genuinely connects all components, passes dual minor /
real PG/browser/restart/recovery/security/native JUnit/CI, and each original B1-B7 EXIT is independently
accepted. Final-only source changes to protected interfaces require separate Owner authorization.
Real identity, human Gold, ShareGrant, mail/VF delivery, paid models and production remain separate NO-GO.

## Privacy and evidence

`integration/beta_review/codex3/.private/<run>/` contains exact raw source/objects/Guard/report HTML,
UID process logs, UUID linkage, restricted Reviewer profile, test-only signer/cookies and original PG
state. `.../.private/pytest-<run>/raw-junit.xml` is the native pytest output. Only an Owner with local
workstation access or separately arranged private transfer can access these paths; they are not GitHub
artifacts. Do not upload this directory. Public per-run output under this document directory contains
source-file hashes, sanitized counts/statuses, dependency states, native JUnit projections and cleanup.
The publication gate compares all actual PG secrets against public files. CI job truth remains external
and must be read for the eventual exact PR HEAD; local results are not called hosted CI results.

## Preserved first-run observations

- `s1-native311-001`: live diagnostic pipeline ran; added internal-network Docker glue suppressed PG
  published-port metadata on Docker Desktop. Original loopback assertion stopped it. Owned resources
  were removed. The added configuration was removed; old source/assertions were not changed.
- `s1-native311-002`: real202/COMMIT/DONE twice; new harness incorrectly expected invalid bearer403.
  Original API and old runtime oracle require401 AUTH_REQUIRED; the NEW assertion was corrected exactly.
- `s1-native311-003`: API/Worker succeeded; NEW harness incorrectly expected stale-version403 while
  original SSR maps STALE_VERSION to409. Its immediate Windows port-closure check raced termination;
  the final cleanup now waits boundedly and continues other owned cleanup on any error. Separate
  followup-cleanup evidence confirms that run's PG/network/both volumes absent. Its RED is not overwritten.

These are recorded new glue / contract-mapping corrections, not original security-oracle changes or
new A1 random precondition experiments. Genuine RLS/tenant/Guard/lease/epoch/commit failures must STOP.

- `s1-pytest311-001`: native pytest6 cases, browser stage RED after preceding99-second signed-read replay; original90-second session lifetime was not extended.
- `s1-pytest311-002`: fresh genuine signed login before Chrome; native pytest6 PASS, zero skips; real1280/375/320, owned cleanup PASS. Later final-HEAD dual-minor receipts supersede this development result.

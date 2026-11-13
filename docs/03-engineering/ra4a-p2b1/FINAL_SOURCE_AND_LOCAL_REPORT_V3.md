# RA4A P2B1 V3 — actual engineering evidence, Owner decision pending

Draft [PR #71](https://github.com/gloweaseco-leo/VRAE/pull/71), Issue #70.
**TEST_ONLY_SYNTHETIC_DECISIONS_NOT_HUMAN_APPROVAL** throughout.

## Source and accepted-main integration

- Frozen repaired source: `8e99cb522a5c80faa3696a828fb199d4635e6407`.
- Latest independently accepted main: `51e2ff3f592c206fddf8193ad7346efbd2a70136` (Owner FINAL PASS / merged PR #68).
- Ordinary merge: `62bc478ff92bfbf9b894046b5c0b6a02954122b9`, ordered parents **8e99cb5 source, 51e2ff3 main**. No conflict, rebase, cherry-pick or force push.
- Latest main has 4,755 blobs; **4,752 protected blob/mode pairs unchanged**, exactly three minimal authorized infrastructure exceptions. All P2B1 frozen runtime/test blobs remain identical to the repaired source. Accepted RA4C2 app/tests and all reviewing/reporting/Guard/evidence/old QA/Gold/0001/0002 files are unchanged.
- `SOURCE_SCOPE_V3.json` and `INTEGRATION_SCOPE_V3.json` provide full leaf hashes and both baselines. Final evidence HEAD and its six new CI checks are posted in the PR after execution.

## Confirmed defect and stronger frozen matrix

Candidate `292b030...` was withdrawn after native rejected NBSP-only reason but
raw SQL committed a SIMULATED test event. Actual pre-fix **11 PASS / 1 FAIL**,
JUnit, original SQL/test snapshots and actual receipt/ledger counts remain in
`unicode-pre-fix/`. No genuine approval or sharing occurred.

New SQL now follows the complete frozen native whitespace semantics rather than
locale-sensitive POSIX whitespace. Coverage/section hashes use exact JSON values.
Original V2 **98 tests/source/assertions remain unchanged**; separate parity tests
add 29 whitespace blanks, one legal padded-text positive and three numeric hash
negatives: **131 real-PG cases**, no skip/xfail. Actual fix smoke **33/33 PASS**.
`FROZEN_MATRIX_V3.json`, `MATRIX_V2_TO_V3_CHAIN.json` and
`MIGRATION3_NATIVE_PARITY.diff` retain the old/new chain and SHA.

## Full actual hosted dual-Python / six CI

Repaired source's actual checkout was `2323684c8fe93fbb094fc8fc947d230cb26f6aa0`,
ordered parents **51e2ff3 main, 8e99cb5 source**. Every one of six checkout
`git log -1 --format=%H` lines identifies that exact commit.

| Actual runtime | P1 v1 | P1 v2 compatibility | P2A PG | Original/new pure | New P2B1 PG |
| --- | ---: | ---: | ---: | ---: | ---: |
| Hosted Python 3.11 | 54 PASS | 54 PASS | 86 PASS | 25 + 10 PASS | **131 PASS** |
| Hosted Python 3.13 | 54 PASS | 54 PASS | 86 PASS | 25 + 10 PASS | **131 PASS** |

P1 compatibility replay is not counted as 54 additional independent new cases.
Both are real disposable PG16 clusters with real migrations/RLS/ACL/CAS, exact
original byte replay, concurrent writers/adversarial commit order, rollback and
backend kill, lost-response idempotency, revocation/expiry, binary backup/restore,
container-volume restart, state/audit/outbox fingerprints and verified cleanup.

- [Four original CI](https://github.com/gloweaseco-leo/VRAE/actions/runs/43347838383): all SUCCESS; each domain **2,420 PASS / 25 existing conditional skips**, HTTP **2,444 PASS / 1 existing skip**, including accepted main's 96 RA4C2 tests. Actual frozen D1/D2 **127** and RA3C V2 **118** calls/source hashes and 24 HTTP network-negative records verified.
- [Both real PG CI](https://github.com/gloweaseco-leo/VRAE/actions/runs/43347838365): SUCCESS, actual **131/131 each**, no new skip/xfail. SQL catalogs show seven FORCE-RLS tables, least-privilege roles/grants, append-only/unique/deferred completeness constraints and private undelivered outbox.
- All three original downloaded artifact ZIP digests/CRC, source manifests, JUnit IDs, native 404/200 original bytes, recovery fingerprints and startup-failure/normal cleanup independently verified. Browser security retains 245 commands / 540 events / 16 cases, kernel controls, no unauthorized egress/writes and automatic exit before cleanup.

Raw API metadata, six decoded logs, three original artifact ZIPs and all audit
receipts are in `source-v3-ci-8e99cb5/`. The raw PR API still reported base SHA
558d183 while the immutable merge commit and all six actual checkouts already
used 51e2ff3. The initial old-base audit correctly refused the mismatch. It was
resolved using the preserved raw PR snapshot plus independent live Git main ref,
`git ls-remote`, immutable ordered parents and exact checkout lines; no API data
or test result was rewritten. Audit receipts disclose both base SHA values.

## Local Windows execution errors are retained as errors

Both local parallel runs passed the full P1 54 / v2 54 / P2A 86 / pure 35 prelude.
During the 131-case phase:

| Local runtime | Actual call PASS | ERROR | Planned cases not executed | Full local PASS |
| --- | ---: | ---: | ---: | --- |
| Python 3.13.13 | 92 | 1 setup ConnectionTimeout | 39 | **No** |
| Python 3.11.15 | 77 | 1 teardown ConnectionTimeout | 54 | **No** |

These results are not replaced by the hosted PASS. Subsequent diagnostics found
both containers running, unpaused, not OOM-killed, recorded ports matching actual
bindings, and reconnect successful. Exact local timeout root cause is unconfirmed.
Actual Docker state/port/log/stats and retry diagnostics are retained. No test,
timeout threshold, frozen assertion, native contract or SQL rule was loosened to
address the local error. Final primary full dual-runtime acceptance evidence is
the independently audited complete hosted PG runs above.

Failure traceback exposed disposable loopback PG fixture passwords. Exact
unredacted failure bytes remain privately under each worktree's ignored
`infra/ra4a/.venv/v3-local-failure-originals/`; public stdout/XML copies replace
only actual credential literals. Redaction mappings retain original and public
hashes. Original command hashes still refer to private originals. Outcomes,
error messages/counts and timings remain unchanged. Both labs were credential
scanned and their owned containers/networks/volumes removed, revoking the fixture
credentials. No password is published in the committed evidence.

## Exact hashes and public evidence bundle

| Artifact | SHA-256 |
| --- | --- |
| Original 98 tests, unchanged | `648f6efe4772304f11014b72a089abc215d47e68a3e4b33661d771c8fcaae964` |
| Additional 33 parity tests | `b2a10232834f5bcaccaec370610273d986781223748c61323340d70930bc68a5` |
| Repaired migration 0003 | `2be5dba988054de1a52e66b11ee68bd19f4d895c2537e3268ba1f5ea8e569547` |
| Frozen runtime/test source set | `bf50940e9aab3dfe57fe1e4b7881df15827de2743fb6c249ffb00d9fbb6dc595` |
| V3 public engineering ZIP | `edcc2e1ef86389ba3037b8233778c60142189928478636646f6f562da2ffaacc` |

`P2B1_V3_ENGINEERING_EVIDENCE.zip`: **1,304 members / 15,525,756 bytes**, CRC
verified; `RAW_MANIFEST_V3.json` / `ARCHIVE_RECEIPT_V3.json` pin all members.
Includes prior V1/V2 archive, all development RED/GREEN, real parity defect/fix,
local ERROR/redaction/cleanup, original hosted artifacts and source/audit evidence.
Private credential-bearing original tracebacks are intentionally not published.
`V3_ACTUAL_RESULTS.json` explicitly records hosted PASS and local ERROR separately.
The original strict local-success sealing path still refuses these local results.

## Risks and stage boundary

Local timeout cause remains an engineering diagnostic risk for Owner review;
additional exact-HEAD local rerun evidence, if executed, is posted separately.
Tenant-wide locking serializes review/revoke/publication; a review already holding
authority locks linearizes before a later blocked revoke, while subsequent revoked
commands/retries refuse. Expiry rechecks at deferred commit. This favors correctness
over throughput. Cluster superusers can disable triggers; corruption injections
are explicit disposable-clone faults, not a root-adversary protection guarantee.

404 remains one factual issue with separate conditional proposals and unchanged
machine status/original bytes. 200 retains three literal scope/limitation Claims,
zero issues, native fields null and only SIMULATED_INTERNAL_SCOPE_ACK. No report
is APPROVED and no real signature, native ReviewDecision, ShareGrant, real identity,
customer access, API/worker wiring, external sender, model call or deployment exists.
Human Gold 0/26; RA4 EXIT / RA5 live remain NO-GO. P2B2/RA4B need separate Owner
authorization. Keep Draft and wait for exact-SHA **RA4A_P2B1_FINAL_PASS**.

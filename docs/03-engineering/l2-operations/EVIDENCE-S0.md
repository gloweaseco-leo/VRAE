# S0 industrial L2 whole-app local candidate evidence

Both native Windows runs completed on executable source `731db81dbefb58097f0cbf0a0ad36dbacc50e360`. This is an A01?A04 synthetic internal Beta candidate, pending Owner independent FINAL PASS. The subsequent evidence-only seal adds this index, the receipt and raw artifacts; it does not change executable code. Local E2E is attributed to the executable SHA, not retroactively to the evidence seal. Natural CI checks the seal HEAD.

[Owner authorization](https://github.com/gloweaseco-leo/VRAE/pull/112#issuecomment-6923295040) ? [operator instructions](README.md) ? [complete refs, hashes and JUnit SHA receipt](s0-final-local-receipt.json) ? [cross-store design and historical RED](RUNTIME-WIRING.md)

## Source and accepted merges

Worktree: `D:/Projects/VRAE-codex3-L2Integration-20261116`; branch `codex3/l2-runtime-integration`; original Draft PR112. Normal merge history preserves prior local `6874c1f4c8fc3bd0e5f3aaf065618855fc9a9f1b`. No reset, rebase, force push or unmerged sibling source. Tracked state was clean throughout the frozen matrix; older untracked evidence directories remain untouched.

```text
commit b4801388d91d4764fc1c30cb006a1184a9fdb1ad
parents 6874c1f4c8fc3bd0e5f3aaf065618855fc9a9f1b a9604f570528e599a0b8215a8957208d76e47b89
tree 82122e68b423a838ce0b1b012cb216f14237502f
```

```text
commit d8d1313df7071d81b5c5948303278b89f94f961c
parents b4801388d91d4764fc1c30cb006a1184a9fdb1ad c25d5f5a27776c4cf494c98f4fb74f1d12ccdc2f
tree 7a438f0c9479dce09d13a3d5ac8f5324be718969
```

Accepted performance source: `a9604f570528e599a0b8215a8957208d76e47b89`; accepted docs main: `c25d5f5a27776c4cf494c98f4fb74f1d12ccdc2f`. Own diff against accepted main for protected `db`, original identity/application/evidence, C1 industrial package and C2 `vrae/l2` is empty. Worker lease remains 30 seconds with initial and mandatory pre-COMMIT replay.

Executable source root SHA256 (identical in both runs): `1f6da14a6f85c1b83996f07e70b78524ef9b4284e67a10f377c9092049aa764e`. Both actual source manifests are byte-identical and every listed file hash was checked against the frozen worktree.

## Actual native runs

| Run | Host / Worker Python | Native / restart | Chrome / live probes | PDF report / blueprint |
| --- | --- | --- | --- | --- |
| [taskbound311](taskbound311/acceptance.json) | 3.11.15 / 3.11.17 | 137/137 + 1/1 | 63/63 + 8/8 | 22 / 7 Chinese A4 pages |
| [taskbound313](taskbound313/acceptance.json) | 3.13.13 / 3.13.18 | 137/137 + 1/1 | 63/63 + 8/8 | 22 / 7 Chinese A4 pages |

PG16.15 (`server_version_num=160015`), locked image `postgres@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea`; Chrome 157.0.8103.52. Each browser JUnit has 63 real assertions plus one explicitly named archival-completion check (64 total); this is not 64 separate business actions. Native preflight is a component gate, not a substitute for actual Worker/browser E2E. Lint passed; mypy passed for 120 source files.

The matrix ran native `integration/l2_ops/verify.py --label taskboundpreflight --python311 <native311.exe> --python313 <native313.exe> --pg-image <locked-digest>`, then native `python scripts/beta_internal.py l2 app-accept --run taskbound311 --minor 3.11` and the corresponding `taskbound313 --minor 3.13`, sequentially with stop-on-error. The package uses original startup/unique SSR, actual Chrome/CDP, signed private login helper, real PG dumps before teardown and exact owned cleanup.

### taskbound311

- Fresh request: `0d67f4a9-d4fe-4265-ab5a-0ceff1a63ec9`; run: `a1194632-3a5b-4931-9057-b17239a2583c`; job: `5ba344d5-566c-4acd-96c3-e76f4f36b5e8`.
- Original Worker first lease: `lease_seq=1`; actual low-role result and finish event committed, with original Worker `M1_SQL_COMMITTED` logs. The stored row creation timestamp is not claimed to be the COMMIT timestamp.
- Pack: `ep-5f475e2cccb83c104c61161fe602d21923d422dde95363747e7152722412378d`; C1 complete native diagnosis SHA256: `4a4d7815f02040068aa9fe0055ce92293b124b1f678fe424fc54430ea0e5880a`.
- C2 report: `l2-native-dea0fc2f39d918b7a41a9b181ad8f359.v2`; version content hash: `983d6f62d01898eba6c1abf5d73e05bcb671fd9abddcada6e0c4de61ebf0a22b`; rendered display hash: `c7d47a15d8d3a218465e1648e8964ca1973a430c62fc853c77cfa964931fe58c`. These two hashes name different native artifacts.
- Controlled review: `review-37963c2824df46beb3386e254e4a9916`; SHA256: `44db9ce0745166d9abddec1c727e8a47fb4d3b28cb5ed3cb3ea0803167b62238`.
- Internal PG Brief: `rb-review-37963c2824df46beb3386e254e4a9916`; canonical SHA256: `4e1bb1367b3c4aa5dbac85d3213174a28123aea25def309356702c946459c282`.
- Different-task negative uses genuine second request/run/job: `0aa2ac4a-a82b-405b-9061-5128cc1f8535` / `326a31ad-3f4b-48b0-8f8a-92f94d434b94` / `d011dc98-a366-4062-a025-ed5bee98770d`. It is not a random-UUID retry. Both original Worker result locators are exported separately.
- [same-task source, diagnosis, versions and before/after refs](taskbound311/native-chain.json), [A to B to A isolation](taskbound311/real-task-switch.json), [browser assertions](taskbound311/browser-assertions.xml), [native JUnit](taskboundpreflight/native-311.xml), [PG restart JUnit](taskboundpreflight/restart-311.xml).
- [actual report PDF](taskbound311/s0-report-zh-A4.pdf), [blueprint PDF](taskbound311/s0-blueprint-zh-A4.pdf), [final Brief screenshot](taskbound311/s0-final-current-brief.png), [restart screenshot](taskbound311/s0-restart-readback.png).

### taskbound313

- Fresh request: `3469b242-5e1a-45f9-8244-53699b46dc0c`; run: `ef95224a-0223-4c87-8fea-7ec59eb4414c`; job: `539159e9-9fc6-4470-99b4-2f38dd2a7613`.
- Original Worker first lease: `lease_seq=1`; actual low-role result and finish event committed, with original Worker `M1_SQL_COMMITTED` logs. The stored row creation timestamp is not claimed to be the COMMIT timestamp.
- Pack: `ep-b480a2cdbfa02bff11beaf82c121093538f43b1423bb31a5d922c9a73d3576fa`; C1 complete native diagnosis SHA256: `6cf7f43a52ff30455b577364980767c1ae55dd312533c81ddad0fa019a1b9151`.
- C2 report: `l2-native-93859dc3f4bcc23f1aeefe43d8230fd7.v2`; version content hash: `5ef23cfe43a458390703ccdad798b5552676a58468cacd8808a2a1b2889684a9`; rendered display hash: `3cf8f7bc932b2e1574cc53b79ca8542aa7c8ad5c9f27d7d01ddbefee985fad26`. These two hashes name different native artifacts.
- Controlled review: `review-8b4551be4176423d8437fa35fc986b39`; SHA256: `7c0ec34c9ca2dcbf2fa643e8fa23004452d456fbded2b313c5d0ae83e19b814b`.
- Internal PG Brief: `rb-review-8b4551be4176423d8437fa35fc986b39`; canonical SHA256: `9c0a182a8bee79345bffbb678755738303a43af3d6126091dae9fd0b5e3772ec`.
- Different-task negative uses genuine second request/run/job: `d59f0a67-d09b-4177-9e65-1a8e6205c599` / `e953efc7-1d4b-47ef-88fd-b4f1aec354ee` / `90c36d17-8f1b-49a6-92aa-83a37eaa507e`. It is not a random-UUID retry. Both original Worker result locators are exported separately.
- [same-task source, diagnosis, versions and before/after refs](taskbound313/native-chain.json), [A to B to A isolation](taskbound313/real-task-switch.json), [browser assertions](taskbound313/browser-assertions.xml), [native JUnit](taskboundpreflight/native-313.xml), [PG restart JUnit](taskboundpreflight/restart-313.xml).
- [actual report PDF](taskbound313/s0-report-zh-A4.pdf), [blueprint PDF](taskbound313/s0-blueprint-zh-A4.pdf), [final Brief screenshot](taskbound313/s0-final-current-brief.png), [restart screenshot](taskbound313/s0-restart-readback.png).

## Business and authority acceptance

Each version creates a fresh real APP202 through the browser and original TaskClient, observes the independent original Worker, obtains the same new eight-page P40/V25 EvidencePack with URL/status/body SHA and signed low-role current Reader scope, executes C1 native analyze/full verify, and uses C2 NativeSource/current report/blueprint. The actual result has 19 assessments and seven blueprint packages. The driver does not copy sample reports or force these counts. Original unique SSR renders industrial procurement analysis, evidence, limits, blueprint, review and internal Brief; technical JSON/hashes remain secondary details.

Actual Chrome performs per-item Controlled review, saves the PG Brief, revises the native blueprint to report v2, observes valid unused old-form `409/L2_STALE_VERSION`, refuses an unreviewed current-version Brief, saves a new v2 review and Brief, refuses repeated nonce and wrong tenant/actor/report scope, then makes real task B and returns to A. Old A cookies/actions remain refused; fresh A authentication restores the same primary report/review/Brief. Actual PG and necessary services restart without result reseeding or rerunning migrations; version/content/display hashes, receipt and canonical Brief remain equal. Natural original M1 expiry is observed while C2 remains fresh; access is refused, and a new original challenge restores the same Brief. Runtime timing measurements may differ when the native analysis is re-executed; they do not change the stored report/Brief identity.

Both original current task authority and C2 current reviewer/version are checked through Brief commit, using the minimum original deadline. Original task/session locks and actual SQLite transaction blocking are directly observed. C2 SQLite and C3 PG are separate stores: no distributed atomicity is claimed. Immutable PG bytes without the completion fence remain `L2_BRIEF_PENDING_REVALIDATION`; public readback rechecks current source and review authority.

Each run has eight actual TEST_ONLY probes: same-byte PG idempotence; wrong tenant/run/job handles; own PG backend interruption with no committed row; lost original task connection; original C2 SQLite unavailability; changed review after context exit; competing original task/review locks and SQLite transaction; permanent C2 key revocation at the boundary. Partial rows remain explicit pending. Same-byte task-connection/SQLite compensation requires fresh original authority; stale/revoked rows are not served or silently repaired. [3.11 probes](taskbound311/live-dual-authority.json) / [3.13 probes](taskbound313/live-dual-authority.json). Original SQL/role contracts are unchanged; the explicitly injected C2 key revocation is not cleared.

## Preservation, cleanup and publication

For each run, both real custom-format PG dumps are saved BEFORE browser faults and again BEFORE final owned teardown. The final snapshot also contains the actual C2 SQLite, actual proof, eight fault receipts and Brief row completion states. Every private file SHA256 and SQLite quick-check was verified; public manifests expose hashes only. Cross-store snapshots explicitly say `multi_store_snapshot_atomic=false`. Raw dump/SQLite/token/profile/Chrome data remains ignored and private under `integration/beta_review/codex3/.private/<run>/acceptance-snapshot-*`; it is not published to this public GitHub repository.

- taskbound311: exact PG container `2062f06424ba9e9deec1c8bd490cff4e8f011f3cb99e8681ce394db4e98aac80` and recorded mounts absent; original client/SSR/loopback/source/routing resources closed. 37 public files and all private snapshot files verified; 17 actual credential values checked in memory, zero matches. [snapshot manifest](taskbound311/acceptance-snapshot-final-manifest.json), [row states](taskbound311/acceptance-snapshot-final-brief-row-states.json), [public file hashes](taskbound311/evidence-manifest.json), [cleanup](taskbound311/result.json).
- taskbound313: exact PG container `04ac9c11399f7703641a94eeb5212e606d745a226d5f019570b858f950ed4491` and recorded mounts absent; original client/SSR/loopback/source/routing resources closed. 37 public files and all private snapshot files verified; 17 actual credential values checked in memory, zero matches. [snapshot manifest](taskbound313/acceptance-snapshot-final-manifest.json), [row states](taskbound313/acceptance-snapshot-final-brief-row-states.json), [public file hashes](taskbound313/evidence-manifest.json), [cleanup](taskbound313/result.json).

Old unidentified anonymous volumes remain UNKNOWN_UNTOUCHED. No global prune, historical dump deletion or A1/MAX3 reset occurred. Historical REDs remain immutable, including CSP-blocked fetch, wrong driver 403 expectation for valid C2 409, earlier native C2 expiry, old Worker lease denial and old remote CI31/32. The earlier operator311 final dump remains UNKNOWN after the approved-tool delay outlived its sandbox; this receipt does not fabricate it. The new finite app-accept snapshots solve that lifecycle gap.

## Limits and Owner gate

Real consultation remains UNLINKED; customer approval, E2/E3, verified human labor, fee/rate/amount and invoice reconciliation are not invented. Actual runtime nanoseconds are recorded separately from unknown commercial cost. This is synthetic Controlled internal Beta only; not full five-dimension/AI capability, real-customer diagnosis, formal human review, external delivery or production. No third-party live website, paid model, CRM, Vey2GE production or L2M production call.

The one controlled push updates original Draft PR112 only after both actual local chains passed. The evidence seal must have a docs-only diff to executable731; CI and final receipt must state the exact pushed HEAD and enumerate every natural first-attempt workflow/job/artifact. No CI rerun is authorized to repaint historical RED. After the first natural CI reaches terminal state, stop and wait for Owner independent FINAL PASS; do not merge, deploy or mark ready.

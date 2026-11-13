# RA4A P2B1 source and local engineering evidence — awaiting Owner

Draft PR [#71](https://github.com/gloweaseco-leo/VRAE/pull/71), Issue #70.
Authority is **TEST_ONLY_SYNTHETIC_DECISIONS_NOT_HUMAN_APPROVAL**.

Functional source HEAD: `19caca8d3ebfcafda6e088a29fd6611f96214c24`.
Entry and latest accepted main: `558d183624a0a36d1f4eaf9d3d75af73b9c88547`.
All runtime/test files remain frozen from that functional source. The evidence
commit's exact final HEAD and its new six CI runs are recorded in PR #71 after
they execute; a committed file cannot contain its own future commit SHA.

## Actual fresh-cluster results

| Runtime | P1 v1 | P1 v2 compatibility replay | P2A PG | Original pure | New pure | P2B1 PG | New skip/xfail |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Python 3.11.15 | 54 PASS | 54 PASS | 86 PASS | 25 PASS | 10 PASS | 98 PASS | 0 |
| Python 3.13.13 | 54 PASS | 54 PASS | 86 PASS | 25 PASS | 10 PASS | 98 PASS | 0 |

P1 v2 is a compatibility replay, not another 54 independent new cases. All 98
frozen V2 cases execute SQL in real isolated PG16 databases; they are separately
counted from the original cases and pure tests. Complete JUnit, executed call IDs,
stdout/stderr, hashes and source snapshots are in `local311-fresh/` and
`local313-fresh/`. Their complete runtime manifests match committed Git bytes.

Both runs performed real transaction races, deterministic adversarial commit order,
pre-commit backend termination, post-commit lost-response retry, revoke/expiry,
exact source verification, binary pg_dump/pg_restore, named-volume container restart,
exact durable receipt and state/audit/outbox fingerprint recovery. Both current
and restored databases deny stale versions and foreign tenant access. Credentials
were scanned against all actual 11 lab secrets with no matches; owned container,
network and volume absence was verified after each run.

## Source / byte invariants

`SOURCE_SCOPE.json` audits all 4,569 entry-main blob/mode pairs: 4,566 unchanged;
only `.github/workflows/ra4a-pg.yml`, `infra/ra4a/lab.py` and
`infra/ra4a/p2a_run.py` have minimal authorized infrastructure changes.
Existing 0001/0002 SQL, D1/D2, RA3A/B/C/QA/Gold, report/Guard/evidence, original
four CI/Docker and operator-console/Codex-2 files remain unchanged.

| Frozen artifact | SHA-256 |
| --- | --- |
| New P2B1 tests | `648f6efe4772304f11014b72a089abc215d47e68a3e4b33661d771c8fcaae964` |
| Python transaction port | `a2af603bbee0b21fa928c9fade30f84cd68924fa194cccd7d469d821ccaa2557` |
| Migration 0001 (unchanged) | `0557738e22e83a6f1c991e8c2a796749ce43845ad80fec44d8dc4c891fd9b5e2` |
| Migration 0002 (unchanged) | `bffca8c3c205f018ea0ba87cfdb19c3d0bc0d919b3e5d9178be0cc7a434c9ba9` |
| Migration 0003 | `8ec4bc6110a180cc3ab425a83d892c2171b744d47747d893bae453cb67f69f9b` |
| All changed runtime/test sources | `00e070cb8a3b25608631965b076bd0ea95e573348cdaf8c29f8cccd5a86ec063` |
| Local raw evidence ZIP | `bb05d546ddf08f76330bbea10d38fa7e68f4fee6e70aca2b7a31ba7b8773ce3c` |

`P2B1_LOCAL_RAW_EVIDENCE.zip` has 813 members / 5,740,209 bytes. It includes
development RED/GREEN history, original binary backups, source snapshots, local
dual-runtime records and the independently downloaded functional-source CI evidence.
`RAW_MANIFEST.json` and `ARCHIVE_RECEIPT.json` pin its members and hashes.

## Already audited six functional-source CI

The functional HEAD's real merge-ref was
`be56eb0eb789d69a2695903172b02b91d5beee11`, with ordered parents
`558d183624a0a36d1f4eaf9d3d75af73b9c88547`,
`19caca8d3ebfcafda6e088a29fd6611f96214c24`.
All six checkout `git log -1 --format=%H` outputs identify that actual merge-ref.

- [Four original CI](https://github.com/gloweaseco-leo/VRAE/actions/runs/43343666223): SUCCESS. Domain matrix each 2,324 PASS / 25 original conditional skips; HTTP 2,348 PASS / 1 original skip. Actual frozen D1/D2 127 + RA3C V2 118 calls, source hashes and 24 HTTP network negatives verified.
- [Both actual PG CI](https://github.com/gloweaseco-leo/VRAE/actions/runs/43343666217): SUCCESS. Each original 54/54/86 plus 35 pure and 98 new PG calls, RLS/ACL/constraints/deferred-CAS catalogs, original byte replay, backup/restart and startup-failure/normal cleanup independently audited.
- Browser security ZIP: GitHub digest and CRC matched; 245 commands, 540 lifecycle events, 16 cases, positive/negative kernel controls, read-only root, sandbox preflight, automatic exit before cleanup, no unauthorized connections/writes verified.

Raw API records, six decoded logs, all three original downloaded artifact ZIPs
and derived audit receipts are in `early-ci-19caca8/`. These prove the functional
source SHA above; they are not presented as the later evidence HEAD's CI.
`audit_six.py` / `audit_hosted_*.py` recheck the final exact HEAD, latest main,
ordered merge parents, actual checkout lines, JUnit/source hashes and security
artifacts. Final-head original links and receipts are supplied in the PR.

## History and remaining risks / boundaries

`DEVELOPMENT_RED_GREEN.md` preserves the initial new-SQL alias error, harness
setup/format failures and unfrozen zero-Claim test assumption, with available
original logs/JUnit and explicit evidence limitations. V1 is retained; V2 keeps
the same 98 IDs with stronger SQL checks. No accepted assertion was weakened.

All three review actions close the current version. Each new authorized current
version begins at per-version sequence 0→1; a report-wide event high-water remains
monotonic. Exact authorised retry returns the identical stored receipt. Revoked
or stale callers cannot retrieve it through the runtime port. A review already
holding authority locks serializes before a later blocked revoke; a committed
revoke wins before subsequent commands. Policy expiry is rechecked at deferred
commit. The tenant lock favors correctness over throughput in this test substrate.

404 remains exactly one factual issue with separate conditional content; machine
statuses and all original bytes remain unchanged. 200 remains zero issues,
native fields null, literal scope/limitation Claims acknowledged, only an internal
SIMULATED scope ACK. Private audit/outbox contain no external delivery capability.

No verified human identity/signature, genuine native ReviewDecision, APPROVED
ReportVersion, ShareGrant, customer access, HTTP API, database service deployment,
outbox sender or real-model call is implemented. Cluster superusers can disable
triggers; privileged corruption tests are explicitly isolated fault injection.
No production HA/identity/security guarantee is inferred from disposable PG tests.
P2B2 / RA4B and any real reviewer path require separate Owner authorization.
Human Gold remains 0/26; RA4 EXIT and RA5 live remain NO-GO.

Keep Draft. Wait for exact-SHA **RA4A_P2B1_FINAL_PASS**. No self-merge or deployment.

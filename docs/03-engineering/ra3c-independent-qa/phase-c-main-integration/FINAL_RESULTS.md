# RA3C QA Phase C — explicit suite replacement and real isolation packaging

Ordinary pytest now discovers the exact frozen **64 business goals +54 denials**. The Owner-superseded original64 positive-request tests remain byte-identical, explicitly runnable historical RED. The isolated image now receives exactly the required23 QA docs through a closed allowlist, so its118 V2 calls execute for real. No production, Guard, schema, dependency, entrypoint, workflow or existing test assertion changed.

Final hosted verification targets accepted main **`a1321dac611ac2a38dca3b4785d71b0256d92136`**, per [Owner6821221274](https://github.com/gloweaseco-leo/VRAE/pull/48#issuecomment-6821221274). The exact final QA HEAD, genuinely new run/job IDs, original four checkout logs, ordered merge-ref parents and final status are supplied by the **post-freeze PR48 CI receipt**, not inferred from the inherited PR47 or failed first Phase C run. This committed report intentionally predates that final receipt.

## Authority and ordinary safe merges

- [Initial Phase C/governance and explicit V1-selection exception](https://github.com/gloweaseco-leo/VRAE/pull/48#issuecomment-6818714132).
- [Minimal Dockerfile/dockerignore repair authorization](https://github.com/gloweaseco-leo/VRAE/pull/48#issuecomment-6819258786).
- Clean original QA worktree ordinary merge61b88eb3: `be616511f42f337622963626c4542ef44fe70638`.
- Clean ordinary merge696d4ae6: `763a54b3a360a6362f2ed37860ae5b4584e6ee51`.
- Clean ordinary mergea1321dac: **`7e3ecfd49fb8584d1bf444cf75e9da857b0a307b`**, ordered parents `f3e26e6755516feebdde902c2527e2fc46c65720` +a1321dac. All merges were conflict-free; no rebase/cherry-pick/force push. No Codex2 worktree/branch was modified.

## Explicit disclosed selection

Exact configuration diff: `addopts = "-ra"` → `addopts = "-ra --ignore=tests/reporting/test_ra3c_independent_acceptance.py"`. `testpaths=["tests"]` stays unchanged. There is exactly one named historical omission and no V2 ignore/skip/xfail. [Version replacement protocol](PHASE_C_SUPERSEDED_V1_TEST_SELECTION.md).

| Execution | Historical64 included? | Of those, historical53 FAIL included? | V2 actually included? | Actual result/location |
| --- | --- | --- | --- | --- |
| Current ordinary default | **NO—all64 omitted by Owner version replacement** | **NO** | YES—all118 | local previous-base dadc19b:2061PASS/25 original hostSKIP each; fresh final-base result must be in final hosted receipt |
| Explicit V2 only | NO | NO | YES—all118 | Python3.11.15/3.13.13 each118PASS,0FAIL/ERROR/SKIP/XFAIL,exit0 |
| Explicit original V1, override addopts | YES—exact64 collected | YES—reported as53 FAIL | NO | each11PASS/53FAIL/0ERROR/SKIP/XFAIL,exit1 |
| Original archived Phase B combined | YES | YES | YES | original2072PASS/53FAIL/25SKIP/exit1 unchanged |

Thus default count2086 =1943 accepted passing regression +118 current V2 +25 existing host skips; the old11 passing and53 failing V1 nodes are both absent, openly, from current default. No historical failure becomes PASS by relabeling.

Final-source local explicit runs are pinned to **`57e865d8522a98347e64bd31a34412d677469087`**, whose accepted base was696d4ae6. Both V2 and historical JUnit/actual commands are in [py311](runs/57e865d8522a98347e64bd31a34412d677469087/py311/summary.json) / [py313](runs/57e865d8522a98347e64bd31a34412d677469087/py313/summary.json), with standard `v2/junit.xml` and `historical/junit.xml`. Every historical failure is exactly52 unsupported-prose and1 NOT_RUN Guard rejection. Original test blob `92ab4b2ef743abc0388866a2054952e56ba14a41` is unchanged. Explicit command: set the resolved legacy_transport.py path as `VRAE_RA3C_QA_ADAPTER_PATH`, then `python -m pytest -q -o addopts=-ra tests/reporting/test_ra3c_independent_acceptance.py`.

The complete local dadc19b default runs are separately preserved under that exact SHA/previous61b main, never called a132 runs. Owner6821221274 explicitly permits retaining completed work across the later docs-only base advance without restarting it. The actual final default full runs are the genuinely new ordinary hosted Python3.11/3.13 jobs on final HEAD+a132; no workflow modification is needed or permitted.

## Immutable business source and minimal portable inputs

Frozen V2 remains `00655091ac06ede0a26233feb6ff75da9fe642bb`, test blob **`43992a9084ee5f2c6bbd6f6b051a986da5c9a20c`**, canonical SHA256 **`9e60d3e307d3a4726adca62b79319b6a85f11a65453390b68a5003bd6a643e62`**. Original14 inputs and all original64 descriptors/54 rejection controls stay unchanged. The shim imports/aliases the exact original fixture/function objects; real collection/report receipts enforce all64+54 original IDs and118 passed calls. No copied business implementation or oracle wrapper is used.

The minimal profile validates24 fixed files, with the3 original test/fixtures already inside tests. Exactly23 extra docs include21 frozen runtime/source/provenance/referenced browser files and2 pinned transport files. Profile SHA256 **`f6d9f5432314e567016b3e09a84d753cc54fa6d6bd4543492fc1ee692b781294`**, transport SHA256 **`6f52e29f0da697df6caef2ef6c19440b683b4f5d3c409096df233c6dc0eef27e`**. The initial81-file broad integrity snapshot remains as historical evidence; unrelated logs/helpers are unnecessary image input, not dropped tests.

Trusted reporting-code fingerprints still reference the Owner-accepted e2f9466 implementation and fail if code changes. Only3 screenshot filesystem strings are relocated in its accepted browser dossier; reverse transport must equal the original data. Cached CI browser evidence is labeled as cached exact-renderer evidence, not a fresh CI capture. The actual GitHub checkout SHA is separate. [Two real integrity-negative collections](minimal-collection-integrity-probes/results.json) reject copied code/input drift with exit2 before business tests.

## Real Docker build, unchanged security, first failure retained

First [run43186042273](https://github.com/gloweaseco-leo/VRAE/actions/runs/43186042273) belongs to QA b743181+old main61b. Its isolated-http missing-docs failure and three successful jobs remain in [initial-ci-b743181](initial-ci-b743181/jobs.json); it is never counted as final4/4.

The authorized repair is [one COPY and exact allowlist](CI_CONTEXT_MINIMAL_AUTHORIZED.patch). Root `.env`, `.git`, cache exclusions remain; no broad `COPY . .`, open-ended docs inclusion or RA3D material. [Actual local Docker proof](local-minimal-docker/summary.json): buildexit0 and network-none runexit0; **2085PASS/1 existing browser-containerSKIP**, all118 real V2 calls PASS; all5 engineering gates exit0. Original readonly/network-none/128MiB tmpfs/512MiB memory/oneCPU/PID128/no-new-privileges/NET_ADMIN setup and unprivileged test execution are unchanged. All24 real network records show the existing verified-TLS/DNS/socket/egress controls. This local proposed-context experiment predates final docs-only main and is labeled accordingly.

Three exclusion sentinels were tested in a rebuilt context. Actual image enumeration shows exactly23 allowed docs, no sentinel; RootFS/config match tested image, while newly generated attestation manifest indexes differ. Full decoded build/run/inspect logs are retained. The [delivery source audit](source-audits/7e3ecfd49fb8584d1bf444cf75e9da857b0a307b/SOURCE_PROOF.json) confirms **every effective copied image input** is identical to that actually tested context, even after the two docs-only main advances.

## Whole-tree modes, replays and independent reading

Latest a132 main has1993 blobs. **1990 blobs/modes remain identical**; the only3 Owner-authorized exceptions are `.dockerignore`, `infra/ra1a/Dockerfile`, `pyproject.toml`. All1645 remaining prior QA blobs/modes and1557 original history-tree blobs outside these configuration paths are unchanged; all23 initial V2 blobs and V1/source/fixture hashes remain exact. [Exact accepted-main config diff](source-audits/7e3ecfd49fb8584d1bf444cf75e9da857b0a307b/accepted-main-exact-diff.patch). No `vrae/**`, schema, workflow, entrypoint, dependency, existing test or other Dockerfile edit.

Each Python on source57e865d actually completed19 prior replay commands, including forged-Gold exit1, all8 current sealed native RA3C build/load cases, and8 original renderer1.0.1 cases from exact6a7a3d3 Git blob bytes. Current renderer actually rejects stale old pins with `REPORT_PIN_VERSION`. Logs/results live in that source's `sealed-replays` and `prior-engine` directories. The initial CRLF export failure is retained and corrected only by explicit Git export settings, with strict blob equality preserved.

New actual native build/load/render in both runtimes produced identical HTML/refs and replayed original quoted bytes. Independent fresh Chromium source57e865d has **4 actual375/1280 views,18 successful citation clicks, privacy12px above fold, body14px, no horizontal overflow,0 observed page external requests/exceptions**. [Actual reading record](runs/57e865d8522a98347e64bd31a34412d677469087/independent-final-main-reading.json), [screenshots/raw observation](../owner-adjudicated-v2/runs/57e865d8522a98347e64bd31a34412d677469087/browser/browser-observations.json). These are new own captures, not Codex2 screenshots; unchanged deterministic pixels are not evidence reuse. Production/reporting inputs remain identical after the final docs-only base advance.

The one-issue report exposes one actual captured contact404 path, separates source fact, impact hypothesis, action and recheck; zero issues retain scope and limits. No invented qualification, rank, losses or customer story. This is credible bounded synthetic review, not measured customer conversion or real-world report approval.

## Evidence sealing and remaining boundaries

[Local manifest](RAW_LOCAL_MANIFEST.json): **365 members**, [raw ZIP](raw-phase-c-local-evidence.zip) **4,880,912 bytes**, SHA256 **`f466149c6f13aa9cd718aa7eacfede781770fd62de1d568a8d03d94c177874d1`**; every member/CRC/hash verified. It records completed local stages through57e865d/696, not a fictional later SHA. Later docs-only delivery-base preservation and final CI receipt are separately identified. [Invocation corrections](HARNESS_REVISION_1.md), Windows Chromium warnings, pip/cache notices and original CI failure remain unmodified.

[Final CI receipt policy](FINAL_CI_RECEIPT_POLICY.md): freeze the final evidence HEAD, obtain four genuinely new hosted SUCCESS, read all original logs/ordered parents, publish exact final receipt in PR48 without another HEAD-changing commit. Final-GREEN claim is valid only together with that external receipt.

Human Gold0/26 stays `QUALITY_GATE_NOT_EVALUABLE`. Fixed proposal vocabulary does not prove arbitrary semantics;0/1 synthetic defects/dedupe do not prove three distinct real defects or commercial ROI. No genuine customer/human/report/share approval, live site/model/provider call, expenses, deployment or RA3D production work. Keep Draft and STOP for separate Owner **PR48_FINAL_PASS**; no merge/auto-merge.

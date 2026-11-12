# Phase C: explicit superseded V1 selection and exact V2 discovery

Authority: [Owner comment6818714132](https://github.com/gloweaseco-leo/VRAE/pull/48#issuecomment-6818714132). Phase B substantive acceptance does not authorize a PR48 merge. Accepted main `61b88eb31d1dec668e7e05495b88fe2d8a5b25fe` was safely merged in clean original QA worktree with ordinary `git merge --no-edit origin/main`, producing `be616511f42f337622963626c4542ef44fe70638`, parents prior QA `48cd0052c0edfe09c0bc00791ecdd8e5f29888c2` + accepted main. No conflict, rebase, cherry-pick or force push.

## Narrow default-selection replacement

The **only config change currently authorized/applied** is this exact diff in `pyproject.toml`:

```diff
-addopts = "-ra"
+addopts = "-ra --ignore=tests/reporting/test_ra3c_independent_acceptance.py"
```

`testpaths = ["tests"]` is unchanged. The original V1 test remains at its original path, byte/Git-blob identical (`92ab4b2ef743abc0388866a2054952e56ba14a41`, canonical SHA256 `300f3a877684c3a174fec7c8e0feb2fcc7809479f4ccd201098fed6ed61afedc`), and its original 14 inputs/64 descriptors and all archived results remain unchanged. This is explicit Owner-authorized version replacement in **default selection**, not a change to any original assertion or historical outcome.

| Execution | Original V1 included? | Frozen V2 included? | Expected result, subject to actual execution |
| --- | --- | --- | --- |
| ordinary `python -m pytest -q` | **NO: all64 historical nodes deliberately omitted** | YES: exact64 primary +54 denials | 2061 PASS,25 existing host/container skips,0FAIL/ERROR/XFAIL |
| explicit V2 collection shim | NO | YES: all118 | 118 PASS,0FAIL/ERROR/SKIP/XFAIL |
| explicit V1 with addopts override | YES: all64, not zero/skipped | NO | 11PASS/53FAIL/exit1,0ERROR/SKIP/XFAIL |
| archived Phase B combined run | YES | YES | existing2072PASS/53FAIL/25SKIP/exit1 remains unchanged |

Actual standard JUnit, command, source head, return code and node tables will be appended under `runs/<qa-source-sha>/`. Expected counts in this design document are not execution success claims.

```powershell
# Default current contract, no command-line deselection:
python -m pytest -q
# The entire frozen V2 imported by ordinary test discovery:
python -m pytest -q tests/reporting/test_ra3c_owner_adjudicated_v2.py
# Named executable historical RED: explicitly override the default ignore:
$env:VRAE_RA3C_QA_ADAPTER_PATH='docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/legacy_transport.py'
python -m pytest -q -o addopts=-ra tests/reporting/test_ra3c_independent_acceptance.py
```

The runner sets that adapter to its resolved absolute path and records actual64-node collection and raw exit1. No marker, expected-failure plugin, source rewrite or zero-node command is substituted.

## Minimal exact-object collection shim and trusted input transport

New QA-only `tests/reporting/test_ra3c_owner_adjudicated_v2.py` imports and aliases the **same original function and fixture objects**, preserving all original parametrization IDs and assertions in frozen `test_acceptance_v2.py` (blob `43992a9084ee5f2c6bbd6f6b051a986da5c9a20c`, canonical SHA256 `9e60d3e307d3a4726adca62b79319b6a85f11a65453390b68a5003bd6a643e62`). There is no duplicated business implementation or wrapper around its assertions.

`collection_contract.py` verifies81 externally held evidence/source members against the **Owner-accepted QA snapshot48cd005**, using the literal `external-inputs.json` SHA256 `ebe61aac80ac81053b0758fe97e9ff8e8666f66a69cfc0a4e971315363b621f6`. The shim separately pins the transport source. Actual reporting fingerprints remain the old independently held e2f9466 bindings; changed reporting code must fail. No trusted ref is regenerated from current code, producer output or attacked JSON.

For hosted filesystems only **three screenshot path strings** in the original Owner-accepted Phase B dossier are relocated. A reverse transform must exactly equal the original dictionary; metrics, HTML hashes, business judgements, code identity, source refs and approvals are untouched. Source evidence code identity remains `e2f9466...`, not falsely relabeled as a fresh CI browser capture. The actual GitHub checkout SHA is separately reported. Source-integrity equivalence permits cached browser evidence for exactly unchanged renderer bytes. New independent merged-main browser checks are a separate actual execution, with their own source SHA/PNG/requests.

The added collection receipt fixture only observes actual pytest objects/reports. It enforces64+54 collected, exact fixture identity, all118 real call reports and no failed/skipped reports. Hosted stdout records original IDs/source fingerprints and actual calls; it neither selects nor changes a frozen outcome. Ordinary pytest still controls final exit/JUnit.

Collection performs no browser launch, source generation, network, subprocess or model call. It reads pinned files and writes an explicitly documented portable observation JSON/receipt to temporary storage. Missing resources or wrong hashes are errors, not bypasses.

## Container context constraint (not yet authorized to change)

Accepted `infra/ra1a/Dockerfile` copies tests/scripts/code/contracts but **not docs**. Accepted root `.dockerignore` also excludes `docs`. The new shim therefore correctly fails closed in that minimal layout. A one-line Dockerfile COPY plus a new Dockerfile-specific ignore file are proposed in `CI_CONTEXT_EXTENSION_PROPOSAL.patch`; they are **not applied** under the current narrow accepted-main preservation exception. No packaging copy of the frozen test is created to evade this constraint, and no CI-only branch disables118 cases. Local Docker daemon was unavailable; this is not claimed as a completed local container run.

Keep Draft. Human Gold0/26 and customer/model/site/spend/share/deploy/RA3D production NO_GO remain unchanged. Four new hosted GREEN jobs on final QA head remain mandatory; inherited PR47 green is not Phase C proof.

## Append-only Owner delta and applied final-main integration

Owner6819258786 explicitly extends the existing-file exception to `.dockerignore` and `infra/ra1a/Dockerfile` for minimal immutable QA packaging. The earlier pending-scope and81-member transport descriptions above are retained as the initial b743181 stage, not current final-state claims. `MINIMAL_PACKAGING_REMEDIATION.md` and `CI_CONTEXT_MINIMAL_AUTHORIZED.patch` document the implemented exact23-doc allowlist and24-member runtime profile. Frozen V1/V2, source/Guard/14 inputs and all64+54 oracles remain unchanged.

Latest accepted main696d4ae695041f0eeefa56d22039682a989380b2 was normally merged from a clean original QA worktree, without conflicts, at763a54b3a360a6362f2ed37860ae5b4584e6ee51 (parents f073262984103d2e6d546f724df50d8afa93d094 +696d4ae6). No prototype worktree or production file was modified. Exactly three existing accepted-main paths may now differ: pyproject.toml selection, Dockerfile one COPY and dockerignore explicit QA allowlist. Original workflow/entrypoint/dependencies/security/source files stay identical.

The final default complete suites are genuine new hosted Python3.11/3.13 ordinary pytest executions on final QA HEAD+696d4ae6. Final-source explicit V2-only118 and original V1 historical64 also rerun locally with standard JUnit in both versions. Earlier complete local source dadc19b/previous main61b records remain exact and separately identified, not called newer-main runs. No CI-only bypass or additional ignore is added.

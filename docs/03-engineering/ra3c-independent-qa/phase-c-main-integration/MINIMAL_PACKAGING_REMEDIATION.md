# Owner-authorized minimal isolated-image repair

Authority: [Owner6819258786](https://github.com/gloweaseco-leo/VRAE/pull/48#issuecomment-6819258786); final main coordination: [Owner6819198070](https://github.com/gloweaseco-leo/VRAE/pull/48#issuecomment-6819198070). These supersede the earlier pending-scope note; no further permission is required for the two explicitly named packaging files.

The original hosted failure is retained: run43186042273 on QA `b74318110ba14a23e6db6af393d4f8226ed33443` + previous main61b88eb3, three SUCCESS and isolated-http missing-docs FAILURE. Its four original logs remain in `initial-ci-b743181/`. It is never described as4/4 or as testing newer main696d4ae6.

`CI_CONTEXT_EXTENSION_PROPOSAL.patch` is the **unapplied initial broad proposal**. The implemented/tested replacement is `CI_CONTEXT_MINIMAL_AUTHORIZED.patch`: a single COPY in `infra/ra1a/Dockerfile`, and an exact file/parent-directory allowlist appended to `.dockerignore`. Root secret/cache exclusions remain. No new Dockerfile-specific ignore file, broad `COPY . .`, open-ended `!docs/**`, dependency, workflow, entrypoint or isolation change is used.

The minimal runtime profile has24 pinned members, of which three original V1 test/fixtures already arrive through existing `COPY tests`. There are exactly23 extra docs files:21 frozen runtime/source/provenance/referenced browser-evidence files and two explicit collection-transport files. `minimal-image-package.json` lists every path. The81-member initial profile/history stays unchanged in its old version; old CI/full-JUnit/unused authoring archives remain in Git but are unnecessary image inputs. No source facts,14 inputs,64+54 oracles or proposal/Guard data were changed or dropped.

- New profile SHA256: `f6d9f5432314e567016b3e09a84d753cc54fa6d6bd4543492fc1ee692b781294`.
- Minimal transport SHA256: `6f52e29f0da697df6caef2ef6c19440b683b4f5d3c409096df233c6dc0eef27e`.
- Frozen V2 source canonical SHA256 remains `9e60d3e307d3a4726adca62b79319b6a85f11a65453390b68a5003bd6a643e62`.

The shim changes only its transport filename/hash. It still aliases the same unmodified original fixture/functions; every64+54 original ID and oracle is executed. Trusted reporting fingerprints and browser source remain the independently accepted e2f9466 code identity, not values recovered from an attacker/current output. Final Git checkout/main provenance is separately audited.

## Actual local reproduction before applying to original worktree

An independent temporary context under the workspace was exported from exact QA `dadc19b421b79875c443284d60422dc28d422e73` with the proposed minimal shim/packaging applied. It does not touch Codex2 or any existing frozen source. This is explicitly a proposed-context experiment, not a false claim of a run on future final QA/main SHA.

Actual Docker build succeeded. Original network-none/read-only/tmpfs512MiB-memory/one-CPU/PID128/no-new-privileges/NET_ADMIN setup command then ran unchanged entrypoint and verify_ra1a runner. All five compile/ruff/mypy/pytest/pip gates exited0; **2085 PASS/1 existing browser-container SKIP**; **all118 V2 actual calls PASS**, with the exact64+54 IDs and pinned24-resource profile in stdout. Local image Python is3.11.17. `local-minimal-docker/` contains complete decoded CLI logs, actual24 network-evidence records, environment and receipt.

Three deliberately excluded sentinel docs were added before a cached rebuild. Read-only enumeration of the resulting image shows exactly23 allowed docs and no sentinel. The tested and sentinel-audited images have identical RootFS layers and config; manifest indexes differ due to newly generated build attestations. Both identities and original inspect JSON are retained rather than claiming identical manifest IDs.

Actual independent integration probes mutated a copied renderer file and a copied admissible-input file. Both ordinary pytest collections fail closed with exit2 before business execution; `minimal-collection-integrity-probes/` retains commands/logs. No production code or frozen test was modified to obtain those negative results.

The original local Docker daemon was unavailable and sandbox access to its config/logs was denied. The existing Docker Desktop engine was started with authorized escalation; no upgrade was performed. Build pip notices and runtime cache warning remain in raw logs. No live site/model/provider/expense/customer-share/deployment/RA3D production activity occurred.

## Final validation arrangement

The complete local dual-Python run on source dadc19b/previous main61b is preserved as that exact source, including V2-only118 PASS, explicit original V1 11/53/exit1 and default2061 PASS/25 existing SKIP. It is not mislabeled as newer main696.

After ordinary safe merge of696d4ae6 and minimal repair, final-source local commands rerun explicit V2 and V1 in both runtimes; all historical/sealed replays and independent merged-main browser checks are reanchored. The required final **default current full suites** run as the unchanged ordinary `python -m pytest -q` in the two genuinely new hosted Python jobs on exact final QA HEAD+696d4ae6. No workflow change or CI-only case bypass is introduced. Their original checkout/count/actual118-call logs are required, in addition to local standard explicit JUnit. Original historical53 failures are absent only from default current suite under the documented Owner-approved version replacement, and stay fully executable separately.

All recorded results and SHA anchors are stage-specific. PR48 remains Draft until separate Owner PR48_FINAL_PASS.

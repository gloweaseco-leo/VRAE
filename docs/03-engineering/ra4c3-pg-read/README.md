# RA4C3 — TEST_ONLY actual PostgreSQL read-side

Authority: [Issue #73](https://github.com/gloweaseco-leo/VRAE/issues/73), accepted entry main `51e2ff3f592c206fddf8193ad7346efbd2a70136`.

**Current status: Owner Option A transport/role gate passed; final verification pending.** [Owner continuation 6843166796](https://github.com/gloweaseco-leo/VRAE/pull/74#issuecomment-6843166796) explicitly authorizes the disposable ordinary-bridge trial and continuation of Issue #73 after its security gate. Actual host listener, non-loopback probes, authenticated SQL, wrong password rejection and restricted-role/RLS/assignment denials are recorded in `evidence/option-a-02`. This is not production isolation or a real reviewer session.

The accepted main `a17d02f16a16acd7214815fce02747509c31f7bd` was normally merged in `41a155b678cabe48d6508975eb10ba95102a8a9b`, ordered parents `c36fc696cd72ce68f9e5d97e1d56d25cda38a912`, `a17d02f16a16acd7214815fce02747509c31f7bd`. C3 does not use P2B1's CAS port.

## Read path and boundary

Existing console/task metadata → explicit trusted local restricted profile → accepted `TestOnlyPrivateBytes.read` → actual verified ByteGraph rows → native `ReportDraft.load`, Guard and ReviewTarget verification → existing SSR views and native `validate_proposal` → currentness check before delivering the response. Raw database bytes, not a rebuilt draft or in-memory source, feed the report. Accepted-main provenance and catalog pins are held separately from the database and HTTP input. Runtime has no writer/admin credential, raw-table privileges, native decision or proposal persistence. The default fixture preview still requires no DB.

The request retains native tenant/version/assignment locks; it checks raw byte hashes/lengths and outside-held provenance, policy currentness, runtime-role currentness and catalog identity before response. Concurrent raw-object write locks cause refusal, including a privileged fixture-admin mutation that later rolls back. Database failures return 503 with no fixture fallback; stale/source errors cannot deliver the partially rendered report. None of this confers real site permission or genuine identity.

Business facts/hypotheses and native H0/null semantics are preserved. PG-mode pages add expandable original-source/manifest hashes and collapse verbose coverage material; native content, selections and required acknowledgements stay intact. 403/UNKNOWN remain neutral. There is no second UI.

## Reproduce in the authorized synthetic lab

Install only the already-accepted locked dependencies (`requirements-ra1a.lock`, `requirements-ra4a.lock`). On an environment with Docker and these dependencies:

```
python -B -m integration.ra4c3.run_suite docs/03-engineering/ra4c3-pg-read/evidence/my-fresh-run --browser
```

Set `RA4C0_CHROMIUM` to the existing Chromium executable. The runner starts an exact-labeled PG16 fixture, executes original P1-v1/P1-v2/P2A suites and C3/full tests, runs actual PG-backed Chromium at 1280/375/320, and removes the owned container/network/volume and credential profile. It records exact Git head, ordered parents, source blob/mode/hash, commands, JUnit and raw logs. The browser records independent real API invocation/return spies, DOM/network/CDP, SHA-bound screenshots, policy revoke/restore and actual DB-stop refusal. The HTTP child is separate and never opens bootstrap/admin state.

Bootstrap state/profile and browser profiles remain ignored. The optional explicit `--option-a-local-trial` flag is confined to this synthetic C3 lab; default lab mode retains internal isolation. Ordinary bridge does **not** enforce egress denial and must not be copied to production or collection/browser sandbox topology. No daemon/global firewall, protected original lab, backend migration or original QA/Gold is edited.

The new isolated workflow runs two genuine C3-PG jobs in addition to the unchanged four standard and two original PG jobs. Hosted artifacts provide the exact checkout/head and merge-ref evidence; do not read an older run as final-head proof.

## Historical checkpoints and retained RED

The sections below describe the earlier blocked checkpoint. They remain as history, superseded only by the bounded continuation above. None of the historical failures is overwritten or relabeled GREEN. An initial Option A diagnostic assertion incorrectly equated the empty requested random port with the assigned effective port; it was corrected to check the two documented fields separately. Original RED and actual cleanup are retained in `option-a-01`. Initial DB tests exposed a fixture column-name mistake and a 400-versus-503 response mapping defect; original JUnit is retained. The first Chromium run completed 85 interaction assertions but ended RED because source changed during the run; its consistency check was preserved, requiring a frozen-source rerun.

Update after Owner bounded continuation: see [actual loopback comparison and network decision](LOOPBACK-COMPARISON.md). Random and explicit loopback port requests both yielded no effective host port while container password-authenticated SQL succeeded. Isolation was retained, all new owned resources cleaned, and no network-model change was made. Owner's specific network-change STOP now governs the next step; the original startup RED is preserved.

## Implemented, not yet integration-verified

The existing console has an explicit trusted local profile seam for a restricted synthetic PostgreSQL role, an original-byte read adapter using the accepted P2A API, native draft reconstruction from stored bytes, and request-scoped verification before response delivery. Default fixture mode remains selected without the explicit profile. An owned integration bootstrap was added because the original protected lab's output paths cannot be changed under this issue.

These are unverified implementation candidates. Original suite compatibility, catalog pin compatibility under the restricted role, race handling, all required denial cases and actual page provenance still require execution. The new contract test currently covers only rejection of an administrator profile; its name does not constitute remote-host coverage. The adapter and bootstrap need further review and tests before use.

## Genuine startup failure

The first PG bootstrap invoked the new lab with a pinned PG16 image, a uniquely labeled network/volume/container, and a loopback port publication request. Docker reported the container running, but `docker port <owned-container> 5432/tcp` returned exit 1:

```
no public port '5432/tcp' published for vrae-ra4c3-368de1e8269a
```

The Python wrapper raised `RuntimeError: OWNED_DOCKER_COMMAND_FAILED_port`. This description is a transcription of the execution result, not a stored raw traceback. Raw Docker diagnosis is preserved under [evidence/startup-01](evidence/startup-01/HARD_STOP.json), including state, empty published-port binding, command error and PostgreSQL log. The receipt hashes each raw diagnostic. The cause has not been established. The new lab's internal Docker network is a candidate to investigate; it has not been changed or retried after STOP.

The Owner issue explicitly says:

> Real runtime failures, source mismatch or production-like grant are hard STOP.

Accordingly, no functional development or PG retry was performed after this failure. Only read-only diagnosis, removal of this run's exact label-verified resources, and this reviewable checkpoint followed. The container, network and volume were individually confirmed absent; the receipt records each check. No migrations, fixture seed or HTTP server were started.

## Test status and missing proof

- Preserved initial genuine RED: [pytest.log](evidence/initial-red/pytest.log), [JUnit XML](evidence/initial-red/tests.xml), before the adapter module existed.
- A single pure profile-rejection test passed during development. Its successful run has no persisted raw log and is not offered as acceptance evidence.
- Required dual-Python original PG suites, full regression, new C3 security/race cases, real PG-backed Chromium at 1280/375/320, screenshots, read-spy proof and hosted CI are **NOT completed**.
- No new hosted workflow has been added. Any checks automatically triggered by the WIP Draft PR do not resolve the missing PG/browser proof.
- There is no fallback claim, native decision, ShareGrant, customer access, real-site capture, model invocation or deployment.

## Scope and resumption

Only `apps/operator_console/**`, one new `tests/operator_console/test_ra4c3_*.py`, `integration/ra4c3/**`, and this new documentation directory are changed. Existing persistence/reviewing/Guard/report rules, migrations, infra, old QA, dependency files and workflows are untouched. No unmerged P2B1 code was consumed.

Owner continuation is required to resolve the explicit runtime STOP. Proposed bounded next step: diagnose/fix only the new C3 owned lab's missing loopback port, without changing protected infrastructure or security rules, then resume Issue #73's original implementation and full verification gates. Keep this branch and Draft PR; no merge or deployment.

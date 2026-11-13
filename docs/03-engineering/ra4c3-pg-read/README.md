# RA4C3 — BLOCKED checkpoint, not an acceptance submission

Authority: [Issue #73](https://github.com/gloweaseco-leo/VRAE/issues/73), accepted entry main `51e2ff3f592c206fddf8193ad7346efbd2a70136`.

**Status: implementation incomplete; real-PG startup HARD STOP.** This checkpoint preserves work and genuine failure evidence. It is not a functional, security, browser or CI PASS. No real human review or release is implemented or authorized.

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

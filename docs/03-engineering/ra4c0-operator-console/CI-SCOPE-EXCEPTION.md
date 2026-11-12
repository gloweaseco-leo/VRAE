# Isolated HTTP image: one-line proposed exception (not applied)

Issue #60 allows only `apps/operator_console/**`, `tests/operator_console/**`, and this documentation directory. The existing `infra/ra1a/Dockerfile` copies all `tests`, but only `vrae` application source. The new read-only console tests import `apps.operator_console`, which is absent from that image. `pyproject.toml` also intentionally packages only `vrae*`; it is unchanged.

The console and its boundary tests now exist in the authorized directories. To run these exact tests in the genuine isolated HTTP job, the proposed minimum change is:

```diff
--- a/infra/ra1a/Dockerfile
+++ b/infra/ra1a/Dockerfile
@@
 COPY vrae ./vrae
+COPY apps/operator_console ./apps/operator_console
 COPY contracts ./contracts
```

This copies only this work package's Python read-side application and fixture pins. It does not change network/kernel rules, invocation, dependencies, test collection or assertions. It is an explicit `infra/**` exception requiring Owner authorization. We will not skip tests, duplicate application source into tests, dynamically copy source through fixtures, or weaken isolation to make the job green.

No other infrastructure or packaging exception is proposed. The existing worker image runs its own selected browser tests and does not require this interface layer.

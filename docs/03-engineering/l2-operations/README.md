# L2 C3 operator preparation and evidence

PR106 M3 is FINAL PASS and retained; this work does not redo it.

From the repository root using Python3.11 or3.13:

```
python scripts/beta_internal.py l2 source-check integration/l2_ops/fixtures/offline_synthetic.json
python scripts/beta_internal.py l2 source-check integration/l2_ops/fixtures/public_readonly_capture.json
python scripts/beta_internal.py l2 source-check integration/l2_ops/fixtures/client_provided.json
```

Each result is `SOURCE_VALIDATED_NOT_DIAGNOSED`, not a task/report. Three
manifests are synthetic examples of input capability; none claims a real public
site or customer authorization. They issue zero network requests. Changing
capture bytes requires an intentional updated expected digest.

Existing M3 `app start/status/open/restart-pg/verify/stop` is preserved. Do not
label its accepted L1 outputs L2. Full L2 task operation will be connected to
Owner-merged C1/C2 ports, as specified in
`contracts/l2_ops/INTEGRATION-v1.md`; current deep-port dependency is explicit.

Real PG16 validation, without changing any old SQL/RLS/Worker:

```
python integration/l2_ops/verify.py --label <new-alphanumeric-label> --python311 <native311.exe> --python313 <native313.exe>
```

Uses already installed postgres:16-alpine by exact local image ID, its own
container/network and loopback-only port. No real-site collector/model is run.
Private credentials remain under ignored `integration/l2_ops/.private/`.
Publishes native JUnit, actual restart readback, measured wall time and cleanup
facts under this directory. The upstream reader is explicitly a test fixture;
PG, transaction, role checks and restart are real. Automated test time is not
human labor and missing monetary rates are UNKNOWN.

Initial transport RED r1: Docker internal bridge did not publish host port;
no tests ran. Corrected to own bridge + loopback mapping. r2 passed both native
versions (before subsequent integrity/ingestion changes). The separately retained
Windows anchored-path RED was fixed by rejecting native and Windows anchors
before resolution. Subsequent evidence must name its tested source SHA; early
r2 is historical and not final-code acceptance.

No consultation receipt/rate supplied by Owner yet: consultation remains
unlinked or unverified, and costs unknown. This does not block offline analysis.
No new permissions, real customer claim, production deployment, external
handoff, E2/E3 achievement, or L2M execution is implied.

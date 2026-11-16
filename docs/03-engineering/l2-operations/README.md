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


r3 at 80e26d9 stopped on Python3.11: 36 passed, one test fixture error. The
immutability-conflict test changed consultation.reference while leaving its state
UNLINKED, so new business validation correctly refused before SQL. Corrected the
fixture to the valid UNVERIFIED_REFERENCE state, preserving the original conflict
assertion and all production validation. Python3.13 was not run after this RED.
Full raw JUnit/error and cleanup are retained under r3; no random retry.


r4 at 46df3aa: Python3.11 37/37 PASS, including real deferred-COMMIT rollback.
Post-restart native readback timed out; stopped before3.13. A separate single
transport-only probe proved Docker Desktop changes dynamic loopback ports on
restart (49677 ->56036). Fix: re-discover current mapping and reconstruct runtime
DSN before native readback. No authorization, database or application timeout
was increased. The failure repr contained a disposable test runtime password:
original raw files are retained privately with hashes, public copies redacted,
and the isolated database/container was destroyed. The verifier now privately
archives failure originals and redacts known disposable credentials from public
JUnit/error output automatically. These are new L2 package tests, unrelated to
paused old A1/B7 MAX3.


CI follow-up: see EVIDENCE.md and first-ci-red.json. New PG/Git operation tests
are explicitly executed from integration/l2_ops/runtime_tests, not silently
skipped in ordinary tests/. The default C3 unit suite has33 passing cases and
zero skips. Original exact25-skips/QA118/review127 assertions and all CI workflows
remain unchanged. Only the B5A publication documentation baseline is adjusted to
exact Owner-accepted PR108 blobs, with tamper negatives and truthful audit fields.


## Native source preparation

The versioned native input consumes an existing CaptureManifest archive, keeping
original quote bytes, capture timestamps and pack identity. The included new
industrial-native.archive is an actual accepted Collector/EvidencePack run over
an explicitly synthetic recorded transport:8 pages, all recorded200,9 offline
transport exchanges, zero network requests. Tenant was set to tenant-test before
collection; importer never relabels a foreign tenant or run. It contains no
report or diagnosis. All3 native-*.json wrappers remain synthetic scenarios.

```
python scripts/beta_internal.py l2 native-check integration/l2_ops/fixtures/native-offline_synthetic.json --reference industrial-native --pack-ref ep-735db2c276030e018f21ba7124fb61db6d46f3e922eca1b99df254512064582e --capture-run-id l2-industrial-capture-v1
```

Use native-public_readonly_capture.json or native-client_provided.json for the
other declared provenance channels. This verifies already held data locally;
no real site or customer authorization is implied. Raw supplemental materials
are listed as not in the native pack instead of manufactured HTTP observations.

All C3 checks are now outside tests/ and run explicitly: old ordinary discovery
has exactly its original2564 IDs. l2-ops.yml adds independent dual-version PG16
jobs; existing workflows and fixed inventory/classifier remain unchanged.
Hosted single-version entry is verify.py --label hosted311 --python-current
python --pg-image <held pinned image>; version mismatch fails before resources
are started. Local --python311/--python313 pair is still supported.


The final explicit suite lives in integration/l2_ops/checks plus runtime_tests;
the original tests/ tree and exact2564 IDs are byte-identical to accepted main.
Source checks produce no diagnosis, task or report. CurrentL2 now consumes native
diagnostic_depth/diagnosis_ref/expected_pack_ref scope, rejecting rehashed results
from a different tenant/run/pack/diagnosis. Its original authority deadline must
remain live through persistence: new-table deferred COMMIT expiry rolls back.

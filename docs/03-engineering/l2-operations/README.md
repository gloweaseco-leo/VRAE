# L2 operator preparation

PR106 M3 remains accepted. Its `app start/status/open/restart-pg/verify/stop`
operations are preserved. This Draft adds source preparation and internal
business handoff; full new-task L2 UI integration awaits Owner-merged PR110/111.
A successful source check does not create a task, diagnosis, report or grant.

From the repository root with the installed Python3.11/3.13 dependencies:

```
python scripts/beta_internal.py l2 source-check integration/l2_ops/fixtures/offline_synthetic.json
python scripts/beta_internal.py l2 source-check integration/l2_ops/fixtures/public_readonly_capture.json
python scripts/beta_internal.py l2 source-check integration/l2_ops/fixtures/client_provided.json
```

These are three declared source capabilities; all included examples are explicitly
synthetic. No website/client authorization is asserted or fetched. Extra raw
materials can be recorded locally; they are not manufactured as HTTP evidence.
Missing customer authorization does not stop offline preparation/analysis.

Native archive import reuses accepted EvidencePack.load and its complete replay:

```
python scripts/beta_internal.py l2 native-check integration/l2_ops/fixtures/native-offline_synthetic.json --reference industrial-native --pack-ref ep-735db2c276030e018f21ba7124fb61db6d46f3e922eca1b99df254512064582e --capture-run-id l2-industrial-capture-v1
```

The other wrappers are native-public_readonly_capture.json and
native-client_provided.json. industrial-native.archive is an actual Collector
run over declared synthetic recorded responses:8 pages all200,9 offline exchanges,
zero network requests. Tenant-test was set before capture. The importer keeps
original scope, bytes, times and refs. native-pins.json records the input pins;
these integrity expectations are not authorization. Results explicitly say
NATIVE_SOURCE_VERIFIED_NOT_DIAGNOSED with task/report fields unset.

Actual new-package validation:

```
python integration/l2_ops/verify.py --label <new-alphanumeric-label> --python311 <native311.exe> --python313 <native313.exe>
```

Single-interpreter hosted-equivalent entry:

```
python integration/l2_ops/verify.py --label <new-label> --python-current python --pg-image postgres@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea
```

The actual minor version must match; validation uses its own pinned real PG16,
loopback-only endpoint, dedicated role/namespace, actual COMMIT-expiry rollback,
PG restart and authenticated-role readback. Credentials/raw failed originals stay
in ignored integration/l2_ops/.private. Public JUnit/error copies are redacted.
Only owned containers/networks are removed. Existing CI/old roles/SQL/Worker and
original ordinary tests remain unchanged; publication metadata separately pins
Owner's exact accepted PR108 documentation blobs.

New checks are explicitly in integration/l2_ops/checks and runtime_tests, run by
new l2-ops.yml dual-version jobs. The original tests/ tree and exact2564 ID set
remain identical to accepted main; no classifier/inventory assertion is relaxed.
See EVIDENCE.md for actual results, historical RED, SHA and remaining integration.

CurrentReader must wrap original trusted signed/current-version access and C1
native verification. CurrentL2 binds tenant/run/native pack/diagnosis to the real
task and uses the original minimum authority deadline. Private brief saves use
that deadline through real deferred COMMIT checks. No snapshot hash, stored row,
APP DONE or imported archive becomes authorization. Consultation remains unlinked
or unverified until real evidence is supplied; absent rates/costs stay UNKNOWN,
automation is not human labor, and external delivery/L2M execution remain false.

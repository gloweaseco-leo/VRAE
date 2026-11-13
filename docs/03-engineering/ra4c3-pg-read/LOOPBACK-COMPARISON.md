# Owner bounded continuation: diagnosis complete, network decision pending

Authority: [Owner comment 6842716924](https://github.com/gloweaseco-leo/VRAE/pull/74#issuecomment-6842716924), not FINAL PASS. Original RED under `evidence/startup-01` is unchanged.

## Observed results, not a root-cause proof

Docker Server 29.2.0 runs Linux under Docker Desktop / WSL2, kernel `6.6.87.2-microsoft-standard-WSL2`. Two new owned reproductions retained the internal bridge, pinned PG16 image, SCRAM TCP password authentication and exclusively requested loopback publication. No daemon, firewall, protected lab, migration or foreign resource was modified.

| Actual operation | Random host port (`loopback-diag-03`) | Explicit host port (`loopback-diag-04-explicit`) |
| --- | --- | --- |
| Network inspect | `Internal=true`, bridge, IPv6 off | `Internal=true`, bridge, IPv6 off |
| Requested HostConfig binding | `127.0.0.1`, HostPort empty (allocate) | `127.0.0.1`, explicit allocated host port |
| Effective published port | `5432/tcp: []` | `5432/tcp: []` |
| `docker port` | exit 1 | exit 1 |
| Authenticated container TCP SQL | exit 0, `vrae_ra4a_p1\|160015\|postgres` | exit 0, same target/version/principal |
| Deliberately wrong password | exit 2, password authentication failed | exit 2, password authentication failed |
| Host authenticated SQL | NOT executed: no published endpoint | NOT executed: no published endpoint |
| Actual restricted app / tenant negative | NOT executed: migrations not run | NOT executed: migrations not run |
| Owned container/network/volume | individually removed, absence verified | individually removed, absence verified |

Each directory contains the original command stdout/stderr and `receipt.json` with command, exit code and SHA-256. The positive SQL is expressly **admin bootstrap readiness**, not an application-role test or UI proof. No restricted-role PASS is claimed. No arbitrary host port was probed in lieu of the missing endpoint. No migrations or HTTP process were started.

The initial non-elevated attempt `loopback-diag-02` failed to access the Docker named pipe before resource creation. Its raw failure is retained. Cleanup verification also could not access Docker, so that attempt has no cleanup receipt and is not described as successful. The authorized elevated reproductions used fresh resource names and completed cleanup.

## Read-only comparison with accepted P1

The unchanged accepted `infra/ra4a/lab.py` creates a dedicated labeled **ordinary** bridge (no `--internal`), requests `127.0.0.1::5432`, waits for authenticated TCP SQL inside the container, then reads the published binding. It explicitly records `kernel_egress_denial=False`. C3 added `--internal`; its requests for both dynamic and explicit loopback publication yielded no effective host mapping. P1's prior acceptance is historical evidence; no new non-internal P1/C3 lab was launched in this continuation.

Docker's [network-create documentation](https://docs.docker.com/reference/cli/docker/network/create/#network-internal-mode) describes internal networks as lacking a default route and filtering traffic to/from other networks. [Port publishing documentation](https://docs.docker.com/engine/network/port-publishing/) explains loopback binding. These documents explain a plausible mechanism; this two-variant reproduction does **not** establish that changing internal mode alone fixes this engine, prove an engine defect, or prove LAN isolation for a proposed replacement.

## Comparison proposals — neither implemented

| Option | Proposed change | Security difference and required proof | Current decision |
| --- | --- | --- | --- |
| A: match accepted P1 lab transport | Retain unique labeled private-purpose bridge/volume, pinned PG16, resource limits, SCRAM and explicit `127.0.0.1` publication; remove `--internal` only from the new C3 lab | Removes internal-network egress restriction; ordinary bridge is not kernel egress isolation. Needs separate Owner authorization and independent loopback binding, host authenticated SQL, non-loopback/LAN denial, restricted app/RLS/assignment tests and teardown/restart proof. No global firewall/daemon changes proposed. | STOP: security-model change not covered by this GO |
| B: preserve internal bridge with a narrowly scoped local transport | Keep PG on internal bridge; design an explicit loopback-only authenticated transport through a separately bounded process | New transport/trust boundary, credential forwarding, process lifetime, source consistency and fail-closed behavior need review; not a proven or authorized drop-in fix. No implementation or extra image proposed in this checkpoint. | STOP: design/permission required before implementation |

Recommended next decision is whether Owner permits a separately audited Option A under synthetic local-only conditions, explicitly accepting the egress difference, or requires preservation of internal-network isolation and a transport design first. Neither option may be treated as already approved by P1 acceptance.

The exact controlling Owner instruction is:

> 若修复必须改变 `--internal` 或信任/网络安全模型，先 STOP 并提交比较方案，不能自行放行。

No usable unchanged-isolation repair was verified by the bounded comparisons. We stop here instead of changing the network or asserting completion. C3 application implementation remains unverified and the original Issue #73 database/browser/CI gates remain outstanding.

## Cleanup hardening and test limits

The C3 start wrapper now uses its pre-state ownership receipt for cleanup when port lookup or connection fails. The migrate/seed CLI path tears down on an exception; resource names and exact labels are checked before removal, and state is removed only after successful cleanup. Existing state/output is rejected rather than adopted. No protected P1 cleanup code was changed.

Initial isolated failure-path unit tests covered pre-state startup cleanup, refusal to remove a foreign-labeled resource, and migration failure teardown. Python 3.11: 3 passed (`evidence/cleanup-unit-311.xml`); Python 3.13 first encountered sandbox temporary-directory permission errors (preserved `cleanup-unit-313.xml`), then 3 passed with an authorized-directory basetemp (`cleanup-unit-313-retry.xml`).

Actual wrapper execution `startup-05-auto-cleanup` uncovered a case-sensitive `No such` check that rejected Docker's lowercase absence message and interrupted cleanup. Its raw traceback is retained. The check was corrected to use lowercase matching; the separate bounded recovery verified labels before removing remaining resources and confirmed all absent (`startup-05-auto-cleanup/recovered-cleanup/teardown.json`). No earlier failure was overwritten.

A fourth unit test now covers lowercase absence and checks all three resource kinds. Final Python 3.11 and 3.13 each passed **4 tests**, with separate original JUnit files `cleanup-unit-311-final.xml` and `cleanup-unit-313-final.xml`. These tests use mocks and are explicitly **not** PG integration proof.

The corrected actual lab wrapper was then executed once (`startup-06-auto-cleanup`). The expected port error remained and the command exited 1; the wrapper automatically cleaned all three exact owned resources, wrote `failure-cleanup/teardown.json`, and left no state file. This is actual failure-cleanup proof, not startup/connection success. Raw console output is in `evidence/startup-06-auto-cleanup-console.log`. No network options changed.

No claim is made for actual restricted principal, tenant denial, database-backed UI, browser screenshots, hosted CI acceptance, real identity/approval, ShareGrant, external capture or deployment in this checkpoint.

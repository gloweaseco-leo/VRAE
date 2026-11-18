# R0 / R1-B private runtime candidate — issue 149

State: `R1B_PRIVATE_RUNTIME_CANDIDATE_DEPLOYMENT_GO_PENDING`.
Release state: `R1_ENGINEERING_CANDIDATE_NO_LIVE_SOURCE_NO_EXTERNAL_RELEASE`.
Accepted baseline: `89a5115e3b8c4ab782bc140d3d278ffc83e7cc7a`.
This is a runnable local OFFLINE_SYNTHETIC drill, with no public listener, cloud provisioning, VF binding, real source or model calls. It does not make the accepted local S5 workbench a production service. Owner retains merge/deployment decisions.

Run from a clean checkout with Docker and Python 3.11 or 3.13:

```sh
python -m pip install -r requirements-ra4b-p1.lock
python -B -m unittest integration.l2_launch.runtime.test_boundary -v
python -B -m infra.l2_launch.runner --label owner-local-001 --build
```

`--build` builds only the original dependency Dockerfile and digest-pinned base from `integration/ra4b/python-images.json`; the original PG16 pin is `infra/ra4a/image.txt`. Build can download pinned public dependencies. The runtime itself has no external route. Omit `--build` only when the exact accepted dependency image is cached locally. Host dependency installation is isolated in CI; do not install into a shared Owner environment.

Each label must be new: output directories are never overwritten. The runner snapshots tracked source into a read-only owned volume, records every file hash plus HEAD and tracked-diff hash, starts one PG fact database with no host ports, and shares only its network-none loopback namespace with the bounded supervisor. It reuses original UID10001 API, UID10002 canonical M1 Worker and UID10003 signed consumer, with original RLS/ACL and original fixed 30s lease. No second queue, report engine or fact database is created. The child processes receive only their original role/APP credentials and controlled test identity challenges; issuer private keys remain in the trusted supervisor. The root supervisor is a disposable test authority, not a production service identity.

The drill submits HTTP202 through the original TaskClient, retries idempotently (including a discarded HTTP response), checks mismatch409, pending queue/no invented progress, wrong tenant both at adapter/API and original low-role PG seam, expired PG policy, expired adapter, missing APP/Worker secret and unavailable cancel501/approved report. A fixture table lock stops load after the original lease transaction; the original Worker is SIGKILLed, the actual 30 seconds expire, and a fresh canonical Worker commits exactly one result at attempt/lease sequence 2. There are no lease edits, time warps or success stubs.

The original signed M1 reader verifies committed bytes; original C1 diagnosis and C2 NativeSource replay produce the seven-package draft. Original C2 ledger records only CONTROLLED synthetic review, denies wrong version and current revoked key. No Gold, formal human review or external delivery is claimed. After writers stop, actual PG custom-format dump/clean restore and SQLite backup restore reconstitute the same report/hash/version/receipt under fresh current test sessions. A second actual PG dump/restore retains revoked-policy denial. This retains cluster roles and source/evidence volumes; it is not new-host disaster recovery or atomic online multi-store backup. Old APP bearer is rejected after restart. Historical review receipt equality does not reinstate old identity or sharing authority.

All outputs are ignored under `infra/l2_launch/.private/<label>/`. Only `public/` contains CI artifact metadata: source manifest, image/ownership, check results, report/receipt hashes, measured durations/DB/dump bytes, privacy and exact cleanup receipt. Raw logs, credentials, PG dumps and SQLite bytes stay private. Known bootstrap and APP secrets are scanned out of successful public evidence. First failures stay in their original label. Cleanup verifies exact names and unique owned labels, removes owned containers/volumes only, and verifies none remain. No global prune. Local private backup/log retention is manual pending Owner evidence-retention policy; never attach the entire private directory.

Read [R0 decision](R0.md) and [interface gaps](interfaces.md). New CI adds both Python minors; all existing workflows and their bounds remain unchanged. No frozen source, contract, worker lease or chrome behavior is changed. Tests live outside the default `tests` inventory.

Local committed-source epoch and retained first REDs: [local-verification.json](local-verification.json). Subsequent final-head natural CI is authoritative for the latest source; no stale-head green implies final acceptance.

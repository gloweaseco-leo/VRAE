# G1 T0: actual offline HTTP vertical slice

Scope: a runnable T0 candidate for Issue #153's SPEED-TO-TEST release. **This is
not G1 final acceptance or a customer release.** Accepted base:
`7fdeeed0f427ce3b94677ab2a480eae1556e85ca`.

## What actually runs

A separate UID10004 VF synthetic HTTPS server calls a UID10003 loopback VRAE
facade using a server-only credential and the exact G0 media profile. The facade
uses the unchanged original APP/TaskClient endpoint at 127.0.0.1:8765. HTTP 202 is
sent only after original PG admission COMMIT, transport crosswalk COMMIT, and an
original current task read. All endpoints exist exclusively inside an owned
network-none container namespace; **no host port is published**.

The independent UID10002 entry claims the original 30-second M1 lease, reads its
original PG-authorized recording, then calls **R1A OfflineWorker -> original
Collector/RecordedTransport -> original M1 producer/replay/COMMIT** with that
new native request/run/job. The Worker cannot connect to the APP port. No old
P40 task/report bundle is used. The six neutral admission source templates are
explicitly input plans, never generated task results.

Original signed M1 reads/current_worker, original Guard/industry analysis and C2
NativeSource/Ledger produce the report. The same current_worker authority context
is retained while a whitelisted synthetic preview is written. All native C2
findings are preserved; page citations group their retained evidence rather than
truncate facts to one slot per dimension. Two normal industrial roles each yield
8 retained pages, 85 source facts, 22 C2 findings and seven native blueprint
packages. The normal report route stays HTTP403 even after controlled synthetic
review and a separately Owner-signed fixture preview permit. There is no formal
human approval or actual ShareGrant.

Source access is L1. Industry diagnostic depth does not broaden SourceAccess to
L2. `capture_live()` and every accepted frozen contract, R1A adapter, original
Worker/lease/SQL/Guard implementation remain unchanged. `X-G1-AI-State: NO_MODEL`
is truthful; #156's trusted post-COMMIT Provider integration is pending.

## Reproduce a new task

Use Docker Engine and native Python 3.11 or 3.13. Install the existing optional
lock without modifying it:

```powershell
python -m pip install -r requirements-ra4b-p1.lock
$base = (Get-Content integration/ra4b/python-images.json | ConvertFrom-Json).'3.13'
docker build --build-arg "PYTHON_BASE=$base" -t vrae-ra4b-p1:313 -f integration/ra4b/Dockerfile .
docker build --build-arg DEPENDENCY_IMAGE=vrae-ra4b-p1:313 -t vrae-g1:313 infra/l2_g1
python -B -m infra.l2_g1.runner --label my-t0-unique --quick --image vrae-g1:313
```

`--quick` creates one NEW manufacturer task and exercises the T0 denial gates.
Omit it to also run distributor, source403, robots-denied and timeout/UNKNOWN
through original independent Worker commits. Every invocation needs a new label.
For Python3.11 use its corresponding pinned base and image tags.

Public-safe receipts are under
`infra/l2_g1/.private/<label>/public/{source,ownership,http,t0,cleanup}.json`.
Full logs, bootstrap credentials and authority material are private siblings;
**never upload or share the whole `.private` directory**. CI uploads only `public`.
Source receipts contain exact per-file hashes, including an uncommitted local
candidate; a clean committed CI checkout provides the exact delivered SHA.

## Owner-operated local trial

Start the same command with `--quick --hold` in one terminal. It prints the exact
owned runtime name immediately. After its quick checks complete, it opens a
UID0-only Unix fixture console. In a second terminal, replace `OWNED_RUNTIME`
with that printed name:

```powershell
docker exec -u 0 OWNED_RUNTIME python -m integration.l2_launch.g1.owner_cli new manufacturer
# Copy the returned opaque audit_ref; the call really creates another PG task.
docker exec -u 0 OWNED_RUNTIME python -m integration.l2_launch.g1.owner_cli status AREF
docker exec -u 0 OWNED_RUNTIME python -m integration.l2_launch.g1.owner_cli work
docker exec -u 0 OWNED_RUNTIME python -m integration.l2_launch.g1.owner_cli status AREF
docker exec -u 0 OWNED_RUNTIME python -m integration.l2_launch.g1.owner_cli preview AREF
docker exec -u 0 OWNED_RUNTIME python -m integration.l2_launch.g1.owner_cli stop
```

`new` provisions a separate trusted synthetic invitation/consent and return grant,
then actually submits through VF HTTPS and exchanges the real secure cookie. It
never prints its service credential, return token, cookie or CSRF secret. `work`
executes one original low-role claim/collection/COMMIT. `preview` is an explicit
local Owner fixture operation: it performs controlled review and signs the exact
current preview hash, then reads it through VF HTTPS. Its output is **synthetic
and private**, never a customer report. The console is bounded to20 new tasks and
five predefined synthetic source kinds. It cannot accept arbitrary URLs.

Wait for `G1_LOCAL_OWNER_CONSOLE_STARTING` in the private supervisor output before
using the console. `stop` lets the runner copy receipts and verify exact cleanup;
Ctrl-C also invokes the runner's owned-resource cleanup. Permission fixtures and
sessions expire; this is a short local trial, not a hosted application.

## Authority and failure boundaries

The only task queue is original `ra4a.jobs`/M1 PG. Additive `g1_http` tables store
transport intent, immutable correlation, source plans, invitations and signed
session/preview custody. They never contain a second job-state machine. The
fixed fixture role has no original queue/result/raw-table grants. Separate
source/tenant and role checks precede business admission.

VF's signed request/audit IDs are external intent correlations; original APP
allocates the physical native request/run/job UUIDs. The immutable PG crosswalk
binds both without rewriting a signed request. HTTP accepted/status run_id is
the actual native run UUID. Worker input/capture/COMMIT and report pins use that
same native tuple, not the neutral input template's run.

G0 negotiation is exact: Accept and POST Content-Type are
`application/vnd.vrae.launch+json; profile="vf-vrae-r0.1-vfb.1"`.
Unknown Accept returns406; wrong Content-Type415. These are transport responses,
not new V1 domain error codes. Application errors use frozen safe bodies. Fixed
Host/Origin, duplicate-free bounded UTF8 JSON, bounded connections, actual TLS CA
verification and an exact certificate pin are enforced. Cookie exchange uses
HttpOnly/Secure/SameSite=Strict, a one-use challenge and CSRF. Protected reads
revalidate original current task, current invitation, realm and return session.

A tenant-wide transport lock and original-state quota serialize admission.
Identical full signed body/key retries preserve the same202 receipt; a distinct
valid signed intent under the same key returns409. No invitation/wrong tenant,
forged source, bare audit_ref, wrong CSRF and return replay are403. A pending
Worker is accepted/QUEUED, never completed. Draft status is running/UNPUBLISHED.

UID egress rules are installed only in the exclusively owned namespace: Worker
outbound TCP is restricted to PG5432; API and facade bypass are denied. No host
firewall, Owner UAT resource, cloud resource or other Docker resource is changed.
The runner verifies exact ownership labels before deletion and exact absence
rather than treating an arbitrary daemon error as successful cleanup.

## Deliberately pending after T0

- Full G1 restart/key rotation/revocation matrix, actual kill/lease reclaim and
  dead-letter evidence for this new HTTP task.
- Browser UI/Chrome viewports; this first trial uses the real server-side HTTPS
  CLI as explicitly released by the Owner.
- Report revision/re-approval flows and a richer consumer preview UI.
- Local VF inquiry retry/WAITING_ACK; no verified real VF business receipt exists.
- #156 trusted post-COMMIT AI integration and licensed real Provider evidence.
- C1/C2 independent tests against the exact Draft SHA and Owner final acceptance.

The sole final G1 terminal remains Owner-only:
`G1_INTEGRATED_OFFLINE_HTTP_E2E_PASS_LIVE_GATES_PENDING`.

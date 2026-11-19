# Persistent VRAE Linux/container service

Baseline: Owner-accepted main fbefba03 (PR163 + PR165 + PR166). This package
supervises those existing modules; it does not replace the queue, source policy,
Collector, Guard, report Ledger or Qwen provider. No customer site, paid model,
cloud account, public domain or production key is created by the package.

## Requirements and exact build

Use a Linux Docker host controlled by the user, Python 3.11+ for the host script,
and the original locked dependency image from infra/l2_g1. The existing PG image
remains the exact digest in infra/ra4a/image.txt. Work from a clean committed source
checkout and build the runtime using:

```sh
python -m infra.linux_service.build --base vrae-g1:313 --tag vrae-service:release
```

Only Git-tracked committed files enter the build context. Operator configs,
private exercise logs and untracked local keys cannot be baked into the image.
Use `docker image inspect --format '{{.Id}}' vrae-service:release` as the immutable
image ID. Its vrae.source_sha label must match the private deployment manifest.
Build the original dependency images using the unchanged locked delivery CI when
not already cached. No runtime pip install or floating provider dependency occurs.

## Private deployment inputs

Prepare a root-owned 0700 directory, e.g. /etc/vrae-service, with flat root-owned
0600 files. Production keys are supplied by the user's actual authorities; do not
copy the controlled exercise issuer or its generated keys. Runtime provisioning
copies these into a root-private operator volume and then UID-private tmpfs
configs. No Docker socket is mounted into the runtime.

| File | Content |
|---|---|
| manifest.json | contract=vrae.linux-service.v1; source_sha; immutable image ID; source_class; network_mode; explicit publish mappings |
| trust.json | existing root registry of pinned SOURCE_ADMIN / DEPLOYMENT_OWNER public keys and source class |
| deployment-intent.json | externally authorized signed intent described below |
| deployment-key | hex Ed25519 private key matching the pinned DEPLOYMENT_OWNER, used only by the root bootstrap to bind each new namespace |
| pg-password | administrator password, root bootstrap only; never passed to service UIDs |
| source-ca.pem | trusted source TLS CA bundle, normally system roots or explicitly licensed private source CA |
| client-ca.pem | trusted service client CA; each service bearer also pins its exact client DER SHA256 |
| server.pem / server-key.pem | server TLS certificate chain and private key with correct externally used DNS SAN |
| api.json | accepted AUTHORIZED_TARGET_V1 APP envelope, only ordinary APP bindings, explicit mTLS transport |
| worker.json | accepted WORKER envelope, only Worker bindings; workload={kind:AUTHORIZED_EGRESS_V2} |
| review.json | accepted report-authority APP envelope, only REVIEW bindings, original pinned Directory, explicit mTLS transport |
| ai.json | accepted APP envelope, only AI bindings; no provider credentials are provisioned by this release |
| provision.json | optional fresh tenant/actor/plan/invitation documents for the existing operator provisioner |
| authorizations.json | matching signed SOURCE_ADMIN envelopes for newly provisioned tenants |

Minimal manifest shape (replace every placeholder; this example is not a GO):

```json
{"contract":"vrae.linux-service.v1","source_sha":"<40-hex-commit>","image":"sha256:<64-hex-image-id>","source_class":"<pinned-source-class>","network_mode":"isolated-egress","publish":["<authorized-listen-IPv4>:8769:8769","<authorized-listen-IPv4>:8770:8770"]}
```

The host script supplies actual inspected network_id/network_internal facts. An
internal network is used only for the controlled non-customer exercise. Real
source egress uses an explicitly authorized isolated-egress network and the same
per-UID kernel default-deny rules. No API listener implicitly exposes PG5432.
No port is published unless its exact IPv4 binding appears in the manifest.

api.json and review.json use certificate/server-key **filenames**, not arbitrary
host paths. Their explicit `transport` contains bind, port, hosts, origins, mtls,
client_ca. Set bind=0.0.0.0, exact approved Host names/ports, origins=[] for service
requests without browser Origin, mtls=true. client_ca is replaced by the injected
read-only CA path. Every binding must include client_certificate_sha256. The
report service listens on its own 8770 transport; the old loopback-only default
and original report profile remain backward compatible.

Signed intent envelope uses the accepted key_id/document/signature scheme. Its
document contains contract=vrae.linux-service-intent.v1, source_class,
purpose=READONLY_DIAGNOSIS, current not_before/expires_at, authorization_hashes
(the canonical hashes of the exact signed source envelopes), destination_ips,
nameservers, deployment_go=GRANTED, source_network_fee_go=GRANTED and
model_fee_go=NOT_GRANTED. The root bootstrap verifies the signature/expiry/key,
installs the existing Worker egress rules, and signs deployment.json containing
the actual namespace inode/interfaces, exact kernel policy hash and source CA
hash. Service UIDs cannot read the deployment private key or change this proof.
A restart renews the namespace binding; it does not renew an expired legal grant
or turn a revoked source back on. Renewing a legal permission still requires its
actual authority. No report-by-report Owner signature requirement is introduced.

The existing configurable `integration.authorized_targets.provision.install`
shape is reused for optional fresh inputs. Existing tenants and revoked source
permissions are not overwritten or reactivated. Initialization checks and applies
only missing original migrations0001/001/002/003 and the additive004 narrow AI
result-discovery function. Runtime identities retain no raw PG table access.
An existing accepted PG volume may be restored as described below.

## Start, inspect, restart, upgrade and rollback

Run host operations as root. Docker access is restricted to this operator, never
provided to the API/Worker. Commands preserve volumes by default:

```sh
python -m infra.linux_service.control up --name vrae-primary --config /etc/vrae-service
python -m infra.linux_service.control status --name vrae-primary
python -m infra.linux_service.control restart --name vrae-primary --config /etc/vrae-service
python -m infra.linux_service.control upgrade --name vrae-primary --config /etc/vrae-service --image sha256:<new-image-id>
python -m infra.linux_service.control rollback --name vrae-primary --config /etc/vrae-service
python -m infra.linux_service.control stop --name vrae-primary
```

status reports process running state, not an invented external health result.
After start/upgrade/restart, a separate trusted caller must check the actual mTLS
health endpoints, source SHA and an authorized current task. Use the versioned
DIAGNOSIS-API.md and REPORT-API.md contracts; no web frontend is required.
Never put real bearer tokens in shell history or browser code. Load the service
client key and bearer from private files. Record status and response hashes,
not private evidence, session cookies, responsible JWTs or report text.

Docker restart policies keep PG/runtime running after host reboot. The root
supervisor restarts a failed child with a bounded crash budget. Worker claims
remain30s; a killed Worker cannot invent COMMIT. On a PG container restart use the
provided restart operation so the runtime joins the new PG network namespace and
re-signs its proof. An isolated PG failure surfaces safe503; do not restore an old
snapshot as current merely because a health check failed. For upgrades pin the
new immutable image and inspect health before resuming admission; rollback uses
the saved previous image and preserves all current data/permissions. Do not roll
back across incompatible future schemas without a separately tested migration.

Each service has a distinct UID: API10001, Worker65532, REVIEW10007, AI10008. The
Worker has only accepted PG/DNS/exact source443 egress. Other current service UIDs
have loopback PG and established response traffic only. REVIEW alone owns the
0700 persistent Ledger; the ordinary API cannot read its private config or DB.
The container root has only SETUID/SETGID/CHOWN/NET_ADMIN to initialize this owned
namespace, then child processes have no capabilities and no-new-privileges.

## Backup and independent restore

```sh
python -m infra.linux_service.control backup --name vrae-primary --config /etc/vrae-service --backup /secure-backups/vrae-2026-11-19
python -m infra.linux_service.control restore --name vrae-recovery --config /etc/vrae-service --backup /secure-backups/vrae-2026-11-19
```

Backup deliberately has downtime: stop runtime, cleanly stop PG, archive both PG
and report Ledger volumes, hash both archives, then restart the original service.
Backup directories/files are0700/0600. Keep the private operator inputs/keys in
the user's separately protected credential backup; they are not published in the
backup receipt. Physical PG backups remain tied to the pinned PG16 image and
architecture. Restoration verifies archive hashes before creating volumes and
refuses any existing data/ledger/runtime/PG target. It creates a distinct new
deployment, preserves PG identities/COMMITs and original Ledger revisions, then
rechecks all current/expired/revoked permissions. It never merges an old approved
report into a newer production ledger. Choose which deployment is authoritative
before admitting new work; this command makes no DNS switch.

## Qwen and report boundaries

The AI UID discovers committed results with the additive tenant-scoped function,
after the original lease expires. It invokes the merged C1 Adapter via the merged
postcommit port; operation ID is stable per job. Current PG/source authority is
rechecked in short transactions. No provider/key/fee authorization is created;
AI_UNAVAILABLE leaves deterministic evidence intact. The optional buyer_selection map in ai.json is keyed by tenant_id/target_id and
contains the explicitly selected model, subject_url and rule IDs. The daemon
rebuilds BuyerCandidatePins only from that task's current pack and projection;
missing or invalid selection stays unavailable, not a fabricated model result. Real qwen4-max dispatch
requires the separate actual provider/price/quota/fee GO and the existing C1
composition; this release does not silently unlock the exhausted budget.

The merged C2 profile remains CONTROLLED_NATIVE_REPORT_ONLY. Its current read,
revision/review/grant/revoke APIs persist in the private Ledger and are reachable
by external mTLS. The existing NativeSource/Directory/Ledger restrictions remain:
a controlled test approval is not formal human approval or customer release.
Unapproved customer report access stays403. This deployment package cannot turn
an unimplemented verified-human source consumer into formal report publication.

## Self-controlled exercise and current deployment evidence

```sh
python -B -m infra.authorized_targets.runner --label unique-linux-exercise --linux-service --image vrae-g1:313
```

This extends the accepted controlled actual HTTP/PG run, exports only test
credentials privately, then uses the **same control.py deployment operations**
to create persistent PG/Ledger/operator volumes, supervise all four service UIDs,
make actual external mTLS task/report calls, replace the Worker and whole runtime,
and cold-backup/restore into a new deployment. Public linux-service.json contains
only statuses/hashes/cleanup, never test signing keys or report/evidence bodies.
Existing runner resources and new service resources use separate exact ownership
labels. No global Docker prune or deletion of unrelated resources occurs.

The user requested local containers first. To retain the successfully restored
controlled deployment and publish only localhost ports, run:

```sh
python -B -m infra.authorized_targets.runner --label unique-local-deploy --keep-local --image vrae-g1:313
```

The retained controlled test permissions/certificates default to24 hours, adjustable
by the operator's --local-validity-hours on this local-only exercise. This does
not renew any customer license or impose a production validity limit.
The retained instance uses https://localhost:18769 (tasks/health) and
https://localhost:18770 (REVIEW). The caller certificate/key, session handoff and
file-configured mTLS probe are kept under the run's private caller directory;
local-deployment.json records its name and paths. Run the probe without putting
credentials on the command line:

```sh
python -m infra.linux_service.probe --config <private-caller>/probe-config.json
```

The optional controlled source is supervised only when the signed deployment is
CONTROLLED_NON_CUSTOMER on an inspected internal network. Its root-owned test
CA/key and test Directory issuer are never production credentials. Legal source
permissions, invitation sessions and TLS certificates expire according to their
actual configured times; the service does not auto-renew legal authority.
Stop/restart/backup the retained instance with control.py using the name/config
paths in local-deployment.json. Volumes remain after stop. To enable host boot
start on Linux install infra/linux_service/vrae.service after adapting the checked
out source/config paths; it invokes the same control script.

No remote SSH/VPS deployment was performed. An eventual external host requires
its own authorized access, DNS/TLS/network and target permissions. Local Docker
success is never described as a public deployment.

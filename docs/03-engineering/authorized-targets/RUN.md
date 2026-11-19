# Authorized targets: runnable BFF contract and local deployment

Run from a Docker-capable checkout, with the accepted original dependency image:

```powershell
python -m infra.authorized_targets.runner --label targets-local --image vrae-g1:313
```

The dependency image is built by the existing locked `integration/ra4b/Dockerfile`
then `infra/l2_g1/Dockerfile`. The new CI builds both Python 3.11 and 3.13 images.
The runner creates only labeled owned containers/volumes, no published port,
network-none PG16, read-only source volume and separate UID API/Worker processes.
It installs original migration 0001 plus `001_authority.sql`, provisions configured
tenants and runs actual HTTPS/PG/DNS/TLS/native diagnosis/current review checks.
All created resources are label-verified before exact cleanup. No global prune.

Results: `infra/authorized_targets/.private/<label>/public/targets.json`, source
manifest and owned cleanup receipts. Private raw evidence, CA/keys and review
ledger are kept under the ignored private directory, not uploaded by CI. Each
attempt has a new label; first RED evidence is retained.

## Server-only BFF contract

TLS host/origin is `https://127.0.0.1:8769`. Accept and POST Content-Type:
`application/vnd.vrae.launch+json; profile="vf-vrae-r0.1-vfb.1"`.
Authorization is a server-only Bearer mapped to one configured tenant DB role.
Never expose it or DB credentials to a browser. Request tenant cannot choose
another binding. No frontend/VEYFRONT repository change is included.

| Request | Authority and result |
|---|---|
| POST /v1/invitation-session | `{ "invitation_token": "..." }`, one-use unrevoked invite; 200, Secure HttpOnly SameSite=Strict __Host cookie plus X-CSRF-Token |
| POST /v1/audit-requests | Original frozen VFSubmit, current cookie and CSRF; independent signed source permission and diagnostic consent; 202 only after original PG admission COMMIT |
| GET /v1/audits/{audit_ref} | Current service binding, invite, cookie, CSRF and same subject; original task state and UNPUBLISHED, never invented completed |
| Any report/review/handoff subroute | 403; invitation/status access confers no report release |

Same subject/key/signed body reuses the original receipt. Changed intent gives
409. Missing/revoked/wrong subject/tenant/source permission gives safe 403.
Configured max_pending capacity gives 429/retryable; real Worker completion
restores capacity. Disconnected storage gives safe 503. No raw URL, evidence,
cookie, CSRF or credential is included in safe errors or server request logs.

## Minimal deployment inputs (local only in this PR)

1. Separate migration administrator runs original 0001 and target bridge on
   disposable PG16. Do not apply to Owner UAT or an existing production database.
2. `provision.install(admin, tenants)` accepts operator-held tenant arrays:
   tenant_id, expires_at, max_pending, actors, plans and invitations. Actor ports
   are APP, WORKER, and APP with port REVIEW; each tenant gets distinct login
   roles. Source plans contain origin/exact_paths/terms/limits/current SourcePolicy
   and authorization reference. Invites bind subject and allowed target IDs.
   Tokens/passwords must be generated privately. No runtime provisioning endpoint.
3. API config (0600, owned UID) contains kind APP, authority AUTHORIZED_TARGET_V1,
   server-held bindings including verifier public keys/service-token hashes,
   source_sha, certificate and certificate_key. Run
   `python -m integration.authorized_targets.http --config <private-path>`.
4. Worker config (0600, UID65532) contains kind WORKER, same authority, only its
   tenant bindings and workload. Run `python -m integration.authorized_targets.worker
   --config <private-path>`. Scheduler may run bounded parallel Workers; original
   PG SKIP LOCKED and resource capacity control work, never invitation counts.
5. Controlled test workload requires the unchanged R1A network-none, no-capability,
   no-new-privileges boundary and parent deny firewall; trusted DNS/CA are the
   accepted lab endpoints. It is not a public customer deployment template.
6. Separate REVIEW role uses `review.current_review` to hold current PG permission
   locks while the original signed Directory/Ledger reads and reviews exact
   versions/display hashes. It cannot be called by BFF or Worker DB groups.

Before any customer network: lawful authorization per target, reviewed parent
bounded-egress attestation/factory, current scope enforcement and deployment GO.
Before any customer report: verified-human source/review bridge, explicit C2
consumer profile, original ReportVersion/ReviewDecision/ShareGrant checks and
recipient-current access. Before C1 Qwen: same committed task/artifact adapter,
explicit allowance and spend controls. No cloud resources or model calls here.

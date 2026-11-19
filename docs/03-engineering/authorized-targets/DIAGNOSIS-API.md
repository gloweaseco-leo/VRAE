# Independent diagnosis API v1

The VRAE service accepts trusted server callers. No frontend, browser domain,
customer count or release schedule is selected. Business messages retain frozen
VF-B media/schema; `X-VRAE-API-Version: vrae.diagnosis-api.v1` identifies this
service contract. The authoritative schemas are `contracts/l2_launch/vf_b.py`
and the existing launch contract schemas. Fetch `/v1/openapi.json` for routes.

## Transport and identities

The accepted local-only endpoint remains unchanged unless the private APP config
contains `transport`. Explicit endpoints require mutual TLS and a certificate
fingerprint bound to **each** service bearer binding:

```json
{"bind":"0.0.0.0","port":8769,"hosts":["diagnosis.internal:8769"],"origins":[],"mtls":true,"client_ca":"/operator/service-client-ca.pem"}
```

This is the `transport` member of the original AUTHORIZED_TARGET_V1 APP envelope,
not a complete config. Each existing binding additionally has
`client_certificate_sha256` (SHA256 of DER certificate, 64 lowercase hex digits).
Keep the config UID-owned 0600, private key private, and pin the server CA and
hostname. A valid client CA certificate alone cannot use a different service
bearer. No `Origin` is required for mTLS service requests; an explicit Origin
must be configured. Host is exact. Cookies and CSRF remain required for task
operations. Never expose the service bearer, client key or permission issuer key
in browser code. mTLS does not replace current PG invitation/actor/source checks.

## Calls

Business Accept/Content-Type:
`application/vnd.vrae.launch+json; profile="vf-vrae-r0.1-vfb.1"` (use the exact `MEDIA`
constant from `integration.l2_launch.g1.http_server`; that constant is authoritative).
Health/docs/errors use `Accept: application/json`.

| Call | Required input | Result |
|---|---|---|
| GET `/health/live` | valid transport/client TLS | process LIVE/source SHA, independent of PG |
| GET `/health/ready` | bound service bearer | current APP scope + actual PG check, 200 or 503 |
| GET `/v1/openapi.json`, `/v1/errors` | bound service bearer | versioned contract / safe error catalogue |
| POST `/v1/invitation-session` | `{"invitation_token":"<private one-use token>"}` | Secure HttpOnly Strict cookie + X-CSRF-Token; replay403 |
| GET `/v1/source-plans/{target_id}` | cookie + X-CSRF-Token | current invitation-scoped policy and subject/invitation pins for request signing |
| POST `/v1/audit-requests` | signed VFSubmit, cookie + CSRF | 202 stable audit_ref/run_id after actual PG admission COMMIT |
| GET `/v1/audits/{audit_ref}` | same current subject cookie + CSRF | task/diagnosis/publication/access axes; DRAFT_READY is not completed |
| POST `/v1/audits/{audit_ref}/return-tokens` | current cookie + CSRF, optional ttl_seconds 1..900 | 201 private task/subject-bound single-use token, never report grant |
| POST `/v1/return-sessions` | `{"return_token":"<private token>"}` | restored current cookie/CSRF; replay/expired/revoked403 |
| GET `/v1/audits/{audit_ref}/report` | current report authority required | unapproved or unsupported customer-release profile403 |

Source-context reads issue no new license and do not change SourceAccess L1 into
diagnostic depth L2. The configured permission authority signs the existing
`permission_document(command, source_policy)` and `submission_document(VFSubmit)`;
the server verifies its pinned key, current invitation and original source scope.
The controlled external probe demonstrates this signing in its independent
container. Its temporary issuer is explicitly test-only, not customer authority.

Send exactly the same signed VFSubmit after lost ACK/reconnect to receive the
same 202 identifiers. A different valid signed intent under the same idempotency
identity returns409. Avoid regenerating proof timestamps on a retry. Different
subjects cannot query each other's status. 429 reflects queue capacity, not a
fixed number of invited customers. Business denials retain frozen safe_error;
health readiness uses the separate safe JSON error resource. 503 never implies
that a job did not commit: recover with the same original submission.

Example private service call (file permissions must protect all referenced files):

```powershell
curl.exe --cacert server-ca.pem --cert service.pem --key service-key.pem -H "Authorization: Bearer <service-token>" -H "Accept: application/json" https://diagnosis.internal:8769/health/ready
```

Never log command lines containing real credentials. Production callers should
load credentials from private files or a secret manager. The public drill records
only HTTP status/response hash; private cookie/key/pack data is excluded.

## Worker and post-COMMIT model port

Run `python -m integration.authorized_targets.http --config <private-app-config>`.
Run the original Worker as a separate UID65532 process using its own private
WORKER config: `python -m integration.authorized_targets.worker --config <path>`.
`poll_interval_seconds` enables bounded continuous polling (0.1..30 seconds);
omitting it preserves the accepted one-shot drain. Claims remain original30s.
Capture remains original Collector/Guard/EvidencePack/NativeSource with bounded
GET/HEAD, current source authorization, pinned DNS/TLS and kernel default-deny
per-UID egress. A failed capture cannot manufacture a completed report.

`postcommit.run(ai_binding, job_id, adapter=None, operation_id=...)` reads actual
PG committed authority only after the original lease ends. Default response is
AI_UNAVAILABLE with zero model dispatch. `CurrentCommittedAuthority.snapshot()`
returns detached actual COMMIT/artifact/task/deadline facts; `check_current()`
rechecks narrow current PG scope/source/hash in short transactions. No database
transaction spans the C1 adapter/model wait. Adapter input includes this object
and stable ai_operation_id; the saved receipt maps the provider operation ID.
Legacy migration002-only callers remain NO_MODEL-compatible, not admitted as a
new authorized model profile. No caller-supplied JSON is authenticated authority.
C1's PUBLIC_READONLY_CAPTURE→S3/REAL_QWEN adapter is a separate integration pending
its exact importable interface. Fake/replay results are never live Qwen success.

## Run and rollback

For the reproducible **non-customer** vertical run, use the existing locked image:

```powershell
python -B -m infra.authorized_targets.runner --label unique-api-run --standalone --image vrae-g1:313
```

The runner creates only label-owned local resources: internal network, loopback
PG, runtime, separate nonroot mTLS calling service, controlled DNS/TLS source and
private volumes. It actually stops/restarts PG and replaces the API process,
then verifies the same task IDs/session/idempotency. No host ports, Internet
customer site or model provider is used. Public receipts are under
`infra/authorized_targets/.private/<label>/public`; all keys, submitted bodies,
cookies, retained artifacts and private logs stay outside that directory.
`--serve` holds this disposable controlled namespace after checks and starts the
continuous Worker. It is a local exercise, with expiring/revoked test authority,
not a persistent deployment or production initializer. Ctrl-C cleans exactly its
owned resources. Never use test private signing keys for real customer sources.

For an authorized persistent deployment, supervise the same API/Worker entry
points with private per-UID configurations and the accepted PG volume. Apply
original RA4A schema, target migration001, delivery002, then additive003 in order
using the deployment administrator; provision current tenant roles/invitations
through the existing operator. Keep PG5432 loopback-only in the isolated network
namespace. Install exact signed namespace egress policy using the existing
root supervisor and trusted SOURCE_ADMIN/DEPLOYMENT_OWNER registry; configure
only individually licensed destinations and permission issuers. Use an approved
stable DNS/TLS certificate and restricted service network for the explicit API
listener. Allocate resources/fees and target access only after their separate GO.
The shipped registry contains no production customer authorization or cloud keys.

Before replacing a service preserve PG data and the separate report Ledger volume
under their retention policy. Read health/live+ready and source SHA after restart;
use original requests to resolve uncertain ACKs. To roll back, stop new admission
and replace API/Worker code with the previously accepted image/config. Migration003
is additive and can remain; do not drop task/session/COMMIT history or recover an
old approval as current. Revoking service actor/source authorization fails current
reads/captures closed. Report revision/review/revocation use the existing C2
Directory/Ledger authority; PR165 currently exposes CONTROLLED-only scope and is
not a customer publication profile. This PR does not silently remove that guard.

No actual cloud deployment, customer website access, paid model dispatch or
formal report release is performed by these instructions or the runner.


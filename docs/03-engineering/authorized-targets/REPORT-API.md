# VRAE report authority API v1

This service reads a new task's real committed EvidencePack/native report through
`target_v1.committed_input(..., HUMAN_REVIEW_INPUT)`. It keeps that PG authority
and the original responsible-person Directory lock through the actual HTTP
response. It uses the existing L2 Ledger for versions, decisions, directed grants
and revocation. It never accepts a submitted pack/report, caller-selected DB role,
tenant, reviewer name, approval flag or directory as authority.

**Current profile: CONTROLLED_NATIVE_REPORT_ONLY.** NativeSource's existing
`controlled_only` restriction and Ledger's external-access restriction are
unchanged. A controlled approval or directed read is not formal human approval or
customer release. This API does not enable the customer `/v1/audits/{ref}/report`
route. A verified-human/source consumer profile must be implemented compatibly
with those original authorities before customer publication. There is no
configuration flag that turns this profile into formal release. No new Gold
count, universal Owner reapproval step, frontend, CRM or delivery transport is
introduced.

## Transport and authentication

Run `python -m integration.authorized_targets.report_api --config <0600-config>`.
The config must be owned by the process UID. It uses the original
`AUTHORIZED_TARGET_V1` config envelope (`kind=APP`) and adds:

- `bindings`: distinct server-only service token hashes mapped to provisioned
  `port=REVIEW` roles. APP/Worker/AI service bindings cannot use this API.
- `report_directory`: original Directory issuer, audience, pinned public JWKS,
  expiry, `mode=CONTROLLED`, and server-configured Person entries. Each entry
  binds the actual actor/subject/tenant/role/report IDs. Private signing keys are
  never provisioned to this service. Use the existing signed Directory assurance
  format; a service bearer cannot create a responsible-person identity.
- `ledger_root`: an absolute, private, UID-owned 0700 durable directory. Each
  tenant/job uses its own original Ledger SQLite file. Preserve this volume to
  preserve versions/reviews/grants across service replacement; do not provision
  it on ephemeral storage for a persistent deployment.
- `max_inflight`: resource capacity, integer 1–8, default 4. This bounds active
  report operations and has no relationship to invitation/customer counts.
- `certificate`, `certificate_key`, `source_sha`: the existing TLS and exact
  source identity inputs.

Listener: TLS `127.0.0.1:8770`. No public port, cloud deployment, origin domain,
upstream TLS termination or caller UI is selected by this change. An externally
reachable deployment requires its own approved network/credential configuration.
The current listener checks exact `Host: 127.0.0.1:8770` and
`Origin: https://127.0.0.1:8770`; it follows no redirects or dynamic discovery.

Every request requires server-only `Authorization: Bearer <service-token>` and:

```text
Accept: application/vnd.vrae.report+json; profile="vrae.report-authority.v1"
Content-Type: application/vnd.vrae.report+json; profile="vrae.report-authority.v1"
```

Content-Type is required on POST. Bodies use the existing bounded JSON parser
(32 KiB); duplicate security headers and ambient Cookie authentication are
rejected. This is a new explicit profile, not a silent change to frozen VF-B.
Responses are `no-store`, include `X-VRAE-Source-SHA`, and explicitly retain the
controlled scope. Pin the configured CA/certificate and source SHA in the calling
service. Do not log credentials, responsible JWTs, session/action/access tokens,
private evidence or report text.

## Requests

All paths below are under `/v1/report-authority`. Job IDs are canonical UUIDs from
the original committed task. A job ID alone never grants report access.

| Method/path | Input and authority | Successful output |
|---|---|---|
| GET `/health` | REVIEW service identity, no person required | readiness and `customer_release:false`; DB connection is checked |
| POST `/challenge` | `{}` | nonce + CSRF, original Directory's 60-second one-use challenge |
| POST `/session` | `responsible_bearer`, `nonce`, `csrf` | `report_session`; original signed subject/nonce/JTI/expiry/key verification, tenant must match service |
| GET `/jobs/{job}/report` | `X-Report-Session`; current scoped OWNER/REVIEWER, or READER with directed grant | exact current report document, ReportVersion, display hash/ETag and non-release flags |
| GET `/jobs/{job}/history` | scoped OWNER/REVIEWER | original version/decision history; grant history remains Owner-only |
| POST `/jobs/{job}/actions` | person session, `{"operation":"decisions"}` (or revisions/grants/revocations) | one-use `action_token` bound to this session and exact operation path |
| POST `/jobs/{job}/decisions` | session + action + current If-Match; action, reason, items, attest | original Ledger review receipt, explicitly nonformal |
| POST `/jobs/{job}/revisions` | session + action + current If-Match; `{"changes":{"<blueprint-id>":"proposal text"}}` | next ReportVersion/display hash and `review_required:true` |
| POST `/jobs/{job}/grants` | scoped Owner + action + If-Match; `recipient_id`, integer ttl 1–1800 | original directed ShareGrant and one-time returned access token; controlled only |
| POST `/jobs/{job}/revocations` | scoped Owner + action + If-Match; `grant_id` | revoked original grant; subsequent reads are denied |

Mutation headers are `X-Report-Action: <action-token>` and
`If-Match: "<current-display-hash>"`. The server obtains version/content pins from
the actual current ledger; the caller cannot select an old version to approve.
A mutation consumes its action token. For an uncertain write/response failure,
read current report/history before acquiring a fresh action; do not blindly
replay a decision or grant issue. These endpoints do not claim idempotent write
semantics beyond the original ledger.

A reader additionally supplies `X-Report-Grant: <grant-id>` and
`X-Report-Token: <access-token>`. The original ledger checks current recipient,
issuing authority, review identity, version, decision, display hash, expiry and
revocation. Merely inviting a subject, completing a Worker or knowing another
subject's token cannot grant access. Reader sessions cannot review or change a
report. Responsible-person sessions are process-bound; after restart, log in
again with a fresh signed challenge. Persisted ledger versions remain intact.

## Request/response examples

These are protocol examples, not real credentials or an assertion of customer
release. The trusted calling service obtains the signed responsible JWT from its
configured authority; this API contains no issuer/private key endpoint.

```http
POST /v1/report-authority/challenge HTTP/1.1
Host: 127.0.0.1:8770
Origin: https://127.0.0.1:8770
Authorization: Bearer <server-service-token>
Accept: application/vnd.vrae.report+json; profile="vrae.report-authority.v1"
Content-Type: application/vnd.vrae.report+json; profile="vrae.report-authority.v1"

{}
```

Session body after signing that nonce:

```json
{"responsible_bearer":"Bearer <signed-responsible-JWT>","nonce":"<challenge-nonce>","csrf":"<challenge-csrf>"}
```

Read with the returned `X-Report-Session`. Selected response fields (the actual
response includes the full original report and full ReportVersion):

```json
{"contract":"vrae.report-authority.v1","scope":"CONTROLLED_NATIVE_REPORT_ONLY","formal_human_review":false,"external_release":false}
```

Review body must contain every existing finding and blueprint ID with its real
item acknowledgement; this abbreviated sample is not valid for a larger report:

```json
{"action":"REQUEST_CHANGES","reason":"Confirm the retained source and unresolved buyer input","items":{"<actual-finding-id>":"REQUEST_CHANGES","<actual-blueprint-id>":"ACK"},"attest":true}
```

`APPROVE` requires every actual item to be ACK, as already required by the original
ledger. Native source facts/evidence/UNKNOWN cannot be rewritten; only existing
proposal text is revisable. A revision requires a new review and new directed
grant. The API does not infer form submission, inquiry delivery or conversion:
unobserved results remain UNKNOWN in the original report.

## Errors, operation boundaries and recovery

| HTTP | Meaning and compatibility |
|---|---|
| 403 | current person/service/source/recipient/review/grant not authorized; identical safe denial, no task ownership disclosure |
| 409 | current display/version pin mismatch or obsolete grant after a newly reviewed version; obtain current authorized report before acting |
| 429 | configured active report capacity exhausted; bounded retry, not a customer-number restriction |
| 503 | bounded PG connection/lock/statement or report storage unavailable; preserve UNKNOWN and do not invent a successful read/write |
| 404/405/406/415 | unsupported route/method/profile/media type; no fallback to an old or unapproved report |

PostgreSQL current scope/actor/source policy/plan/invitation/source authorization
are rechecked by the accepted committed-input port while locks remain held.
Directory revocation and report operations serialize on its original lock.
Authorization withdrawal affects the next read, even if a service still has an
old cache or an active responsible session. The authority covers response write;
once a response has been sent, consumers must still avoid reusing cached content
as current authority. A network interruption cannot retract bytes already sent.

## Run, verify, roll back

The existing disposable runner adds one optional drill, requiring the accepted
delivery bridge (migration 002). It produces real local DNS/TLS captures and
original PG COMMITs before exercising this report API:

```powershell
python -B -m infra.authorized_targets.runner --label report-api-local --delivery-bridge --report-api --image vrae-g1:313
```

Use a new label each time. The original runner owns network-none containers and
volumes, no host ports, exact label-verified cleanup and private/sanitized evidence
separation. `report-api.json` records only probe IDs/statuses/hashes/elapsed time,
source SHA and non-release scope. The optional locked delivery CI runs the same
drill under Python 3.11/3.13; no new optional dependency enters default tests.

To remove this API, stop its service and revert its separate process/config and
caller route. No new PG migration or existing customer endpoint change is needed.
Retain/back up the original ledger volume under its authorized retention policy;
do not delete review history to roll back code. Never restore an old approved
view as current or reuse a grant for a different version. Other target/Worker/AI
ports keep their existing behavior. Real source-network, deployment/cost and
formal report release permissions remain separately controlled.

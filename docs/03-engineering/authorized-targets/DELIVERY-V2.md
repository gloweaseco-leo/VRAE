# Invited target execution and committed delivery v2

Base: Owner-accepted main cf1a67bd. Implements issue153 comment6997521017.
No invitation/client-count business limit is introduced. This is the next
runnable backend slice, not permission to operate on customer websites.

Run the actual controlled-noncustomer vertical:

```powershell
python -m infra.authorized_targets.runner --label delivery-local --delivery-bridge
```

It uses the accepted dependency image, original PG queue/30s claim/Collector/
SourcePolicy/Guard/NativeSource and exact owned cleanup. New independent CI
runs this path on Python3.11/3.13, plus the original target path separately.
Outputs are targets.json (accepted73 checks) and delivery.json (new ports and
source/AI records). No customer host, production deployment or model API is used.

## Trusted source execution

After original0001 and accepted001, install additive002_delivery.sql with the
separate migration administrator. Existing001-only deployments keep their
accepted controlled path. A v2 server-held plan declares execution_profile
ADMIN_TARGET_V2, authorization_kind ADMIN_AUTHORIZED_READONLY and source_class
CUSTOMER or CONTROLLED_NON_CUSTOMER. The signed plan digest includes its raw
retention setting, exact origin/paths, original SourcePolicy and resource limits.

Trusted administrator `operator.activate(admin_connection, signed_envelope)`
requires the postgres migration identity and an Ed25519 SOURCE_ADMIN key from
root-owned /run/vrae-targets/trust.json. It verifies the exact PG plan digest,
tenant/target, origin, exact paths including /robots.txt, READONLY_DIAGNOSIS,
GET/HEAD, original limits, TOS reference, legal reference, current start/expiry,
retention deadline and explicit public destination IPs before activating the PG
record. A browser, model or runtime APP/Worker cannot create/change that record.
A legal reference is the administrator's verified authorization record, not an
independent legal conclusion made by this software.

A DIFFERENT signed DEPLOYMENT_OWNER envelope is provisioned root-owned at
/run/vrae-targets/deployment.json. It binds authorization envelope hashes,
network namespace inode, interfaces, trusted DNS and CA hash, explicit deployment
and source-network-fee GO, and NOT_GRANTED model fees. Missing or invalid proof
raises LIVE_CAPTURE_DISABLED; booleans in the Worker config do not enable capture.
Shipped test keys are CONTROLLED_NON_CUSTOMER only and cannot sign CUSTOMER
permissions. No production key/permission/deployment proof is supplied here.

The separately inspected namespace parent calls infra.authorized_targets.
egress_policy.install BEFORE starting the UID65532, zero-capability,
no-new-privileges Worker. Kernel OUTPUT permits only PG127.0.0.1:5432,
approved targetIP:443 and explicit DNSIP:53, rejecting all other destinations
for IPv4/IPv6. Signed deployment proof binds this policy and namespace. The
parent must be an owned isolated namespace, never a host/default bridge or a
Vercel function. No Docker socket is available to Worker. This code does not
provision a cloud network or assert that a manually signed external deployment
was independently inspected; its trusted parent owns that attestation.

The versioned factory reuses original FencedAccess, full-answer DNS checks,
RecheckingResolver, PinnedTransport, SafeFetcher and Collector. Every request
rechecks current source authority, exact paths, source policy, lease and signed
deployment. Full DNS answers must fit signed IPs, with the complete answer
rechecked before numeric-peer connection. Robots/TOS, redirect/scheme/host,
GET/HEAD, pages/bytes/time/rate limits remain enforced. L1 source access is not
relabeled L2: diagnostic depth remains a separate field.

`operator.revoke(admin, tenant, target)` closes new admissions, future fetches,
commits and delivery inputs for that source. Original task history is retained;
VF-B access becomes WITHDRAWN instead of inventing task completion/cancellation.
One failed target leaves other invited subjects/targets usable. Worker failure
and actual COMMIT records retain authorization ref, safe reason, artifact hash
and retention deadline. Access after expiry is refused. The deadline is a
retention/audit record, not a claim that this patch has physically purged an
immutable evidence object; deployment retention/purge operations remain explicit.

## C2 / VF BFF actual consumption difference

Existing submit/session/status/profile remains vf-vrae-r0.1-vfb.1. Customer
report/review/handoff routes remain403. This patch does not clear controlled_only,
change a synthetic label, issue formal review, or create a ShareGrant.

New **server-only** POST /v1/internal/committed-input uses the same local TLS
transport/profile headers, with a separately configured REVIEW service Bearer.
Body: `{ "job_id": "<original-job-uuid>" }`. No caller tenant selector.
APP/customer Bearers and cross-tenant jobs are403. This input is not a report
read grant and must never be forwarded wholesale to the customer browser.

200 contract vrae.committed-target-input.v1 contains:
- purpose HUMAN_REVIEW_INPUT; original tenant/request/run/job/event/source tuple;
- actual PG transaction_id, committed_at and artifact_sha256;
- original30s lease bounds;
- same retained EvidencePack/objects, original NativeSource document/version,
  content_hash/display_hash, source authorization and current server source plan;
- publication UNPUBLISHED and grants_report_access=false.

`delivery.committed_input` holds original current PG source/invite/assignment
locks, verifies exact artifact bytes and current signature, and rechecks before
leaving the operation. C2 can build its verified-human review -> exact Owner
version approval -> current recipient ShareGrant flow on this authoritative
input. C3 does not duplicate those C2 components or pretend that controlled ACK
is human Gold. Actual human issuance/customer release still requires its GO.

## C1 Qwen4 minimal handoff

A separate target_v1_ai function-only actor receives POST_COMMIT_AI_INPUT using
`delivery.committed_input`. The original job must already be DRAFT_READY with a
real results COMMIT, and the original30s lease must have ENDED. Nothing extends
or borrows the Worker lease. C1 receives the same artifact/version/display hashes,
current source authority and exact task. PUBLIC_READONLY_CAPTURE is preserved;
it is not coerced into the old synthetic CompletionPins factory.

`postcommit.run(binding, job_id, adapter=None)` records AI_UNAVAILABLE with zero
calls by default. C1 supplies its own trusted adapter for the already merged
Session.run(mode='REAL_QWEN'), retaining its source-input compatibility, operator
allowance, strict qwen4-max, usage and fee checks. No Provider/Gateway framework
is reimplemented, no model configuration is accepted from HTTP, and no real
adapter/key/paid permission is enabled by this patch. AI receipts bind the same
artifact/report/display/task and cannot grant report access. Its candidate
output remains a human-review input; original report hashes are not overwritten.

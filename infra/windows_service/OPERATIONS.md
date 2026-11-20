# Windows public VRAE service

Actual controlled-source technical flow completed on 2026-11-19: external
sequential captures, actual Windows/password + phone MFA, human review,
directed recipient reads and Owner revocations. Owner subsequently approved formal customer
delivery, AI fees and credentials/delegations through 2026-11-30T15:59:59Z.
Each new site still requires actual legal consent and each report a fresh actual review.
The historical sample review remains limited to controlled acceptance and retains UNKNOWN.
See the single Issue153 handoff receipt for immutable artifact/version pins. The controlled public source is
operator-owned acceptance infrastructure, not a customer website. Health alone is insufficient.

## Actual listeners and authentication

- Diagnosis: `https://dong.tail27555e.ts.net:443`; raw TCP Funnel to loopback28769/API8769.
- Formal report: `https://dong.tail27555e.ts.net:8443`; raw TCP Funnel to loopback28770/REVIEW8770.
- Source used only with Owner permission: `https://vrae-owned-source.tail27555e.ts.net/`.
- Both services require a valid client certificate, its bound service bearer and correct hostname.
  Certificate/private-key and bearer handoff must use the private operator channel. They are
  server credentials: never embed them in a browser bundle or public artifact.
- Client CA, client private keys, signing keys, invitation tokens and pairing state remain in
  the root-owned Docker Desktop Linux/ext4 `vrae-windows-private` volume (0700/0600).
  The runtime has no engine socket; only the trusted local operator has it.

## Diagnosis protocol

`GET /health/ready`, `/v1/openapi.json` and `/v1/target-intake-contract` use
`Accept: application/json` with the certificate-bound API bearer. Inspect the returned
OpenAPI and intake contract for the deployed version and literal consent text.

All following diagnosis requests use the original frozen media type for Accept and POST Content-Type:
`application/vnd.vrae.launch+json; profile="vf-vrae-r0.1-vfb.1"`.

1. POST `/v1/invitation-session` with `{"invitation_token":"<private token>"}`.
   Retain the Secure/HttpOnly cookie and returned `X-CSRF-Token` in the calling server session.
   Invitations are single-use; use the original return-token protocol for recovery.
2. POST `/v1/target-applications` with the exact HTTPS URL, up to two additional exact paths,
   and consent: `{"version":"VRAE-READONLY-DIAGNOSIS-1","read_only_authorized":true,"model_data_notice":true}`.
   To explicitly enable model processing use version `VRAE-READONLY-AI-DIAGNOSIS-2`
   after presenting the deployed optional model consent text. It names Alibaba Bailian
   qwen4-max/cn-beijing, minimized typed evidence and no raw HTML/PII. Authorization
   binds the current invited subject to the signed plan hash; legacy notice does not enable AI.
   Send the task cookie and `X-CSRF-Token`. The server returns HTTP201 and an opaque application
   token plus DNS TXT proof instructions. Normal customer domains require actual domain control
   and explicit permission. The separately signed operator-owned acceptance origin is identified
   explicitly; it is never presented as proof of customer legal ownership.
3. POST `/v1/target-applications/authorize` with `{"application_token":"<returned token>"}`.
   HTTP201 authorizes only those paths. Private/mixed DNS, bad proof, expiry and revocation deny.
   Active capture returns429 when changing the kernel policy would conflict with its lease.
4. POST `/v1/diagnoses` with `url`, stable `idempotency_key`, current UTC `accepted_at`,
   `consent_version` and `language` (`zh` or `en`). Retain the entire request for retries.
   HTTP202 is admission, not completion. Same intent returns the same opaque audit reference;
   a changed request with the same key returns409.
5. GET `/v1/audits/{audit_ref}` with the same task session. Inspect `task.status`.
   `DRAFT_READY` remains unpublished. The original historical `/report` route stays403.

Worker concurrency is one; other invited tasks use the original bounded PG queue. Capture
retains the original 30-second lease, public DNS pinning, robots enforcement, exact path,
redirect, method, rate, page, time and byte bounds. No model fee authorization is inferred.
Without an authorized working provider, AI is explicitly `AI_UNAVAILABLE` and UNKNOWN remains.

## Reviewer and report protocol

Use `Accept` and POST `Content-Type`:
`application/vnd.vrae.report+json; profile="vrae.report-authority.v1"` and
`X-Report-Profile: VERIFIED_HUMAN_CUSTOMER_REPORT`, plus the REVIEW bearer and client certificate.
The report service rejects task cookies in the HTTP Cookie header.

Actual local Reviewer/Owner enrollment uses `pair_reviewer.py` (local Windows dependency: `qrcode[pil]==8.2`): a visible Windows credential
prompt checks the password with LogonUserW and matches its token SID to the enrolled account.
The phone uses Microsoft Authenticator Other account/TOTP. Root-protected SQLite stores the
pairing state and rejects reused TOTP steps, primary authentications and report nonces.
There is no username-only, test-signature or MFA bypass. Password and code are local UI inputs,
not shell arguments or chat messages. Refresh the staged signed directory only after enrollment
succeeds and no Worker job is active, using the original service restart procedure.

The original challenge/session/actions/decisions/grants/revocations API remains authoritative.
Only an actual enrolled Reviewer can review; Owner grants do not replace a Reviewer decision.
Current Owner/Reviewer report views identify `current_recipient.recipient_id` from the original
PG report binding. No user-supplied role or new recipient can replace that binding.

Customer report readers require neither Windows identity nor an Authenticator. The signed
`PG_INVITED_SUBJECT_AND_DIRECTED_GRANT_V1` delegation permits this read-only exchange:
POST `/v1/report-authority/recipient-session` with `audit_ref`, `task_cookie` (raw cookie value),
`task_csrf`, `grant_id`, `grant_token`. It checks the original current PG invited session,
the committed report, actual review, exact directed grant and current source/version.
It returns a maximum300-second opaque `report_session` with a distinct assurance label;
it does not claim MFA or grant a Reviewer/Owner role.

GET `/v1/report-authority/audits/{audit_ref}/report` with `X-Report-Session`,
`X-Report-Grant` and `X-Report-Token`. Revocation, expiry, changed recipient/session/source,
new report version or stale If-Match deny. Publication must be the approved version and its
current display/content hashes; no prior draft may be presented as released.

## Local operations and recovery

Use the existing immutable operator image and `infra.windows_service.private_host` commands
`status`, `up`, `stop`, `restart`, `backup`, `rollback`; provide `--image <immutable operator ID>`
and `--name vrae-windows`. The private input mount is resolved from its owned ext4 volume.
Backups are cold PG/Ledger archives and SHA receipts in the separate protected
`vrae-windows-backups` volume. Restore into a new owned deployment; never overwrite data volumes.
Runtime upgrades use the original `infra.linux_service.control.upgrade` and keep previous image/SHA.
Local invitation creation is `infra.windows_service.operator invite --subject <opaque-subject>`
in the trusted operator with the existing PG namespace; token handoff stays root-private.

Funnel uses only `--tcp`, never HTTPS termination. Windows Tailscale is a persistent service;
owned Docker containers use their configured restart policy. Docker Desktop must be running.
Windows shutdown, sleep, network loss and account/Funnel outages make this local service unavailable;
callers must honor failed health checks. Do not promise cloud availability. Renew expiring public
certificates and bounded operator/source/invitation authority through protected local operations.
Never disable the user's VPN or change global proxy, DNS or routing as a recovery shortcut.

External receipts record statuses, public peers, hashes and exact source SHA. Task cookies and
session state are sealed to an operator X25519 key before upload and decrypted only into the
private volume. Keep failed receipts. Delete temporary Actions client secrets after acceptance.
Migration to a future VPS preserves PG/Ledger and trust/revocation state, installs actual new
hostname certificates and tests external mTLS again; it is not a prerequisite for local acceptance.


## Actual local review operation

The enrolled Reviewer phone label is read privately from `pairing-label.json`.
Successful enrollment is established by the identity store transaction and signed
directory, not an expired browser pairing-page status. Do not enroll again to sign
a report. `review_browser` presents the exact committed native report and evidence
on a temporary loopback capability URL. It requires a human to read every item,
retain UNKNOWN, enter their own reason, and consent to the directed short grant
and its revocation test. Closing the page creates no approval.

After both reviews are staged, run `python -B -m infra.windows_service.review_operator
--operator-image <immutable trusted operator> --receipt <private operator receipt>`
in the actual Windows user's interactive session. It verifies the Windows account
password through the native credential API and the enrolled phone TOTP. It obtains
fresh original report challenges and signed VERIFIED_PERSON_MFA identities, then
compares the exact reviewed report/version/display/content hashes before recording
each decision and the current recipient's 900-second grant through the original API.
`--mode revoke` uses fresh actual Owner MFA to revoke those original grants.
Never pass passwords, OTPs, seeds, JWTs or grant tokens as command arguments.

The public report acceptance program returns an explicit incomplete state until
actual human decisions and directed grants exist. Once supplied privately, it
checks formal external reads, the exact committed report, subject isolation and
Reader role restrictions over the real public mTLS service. After actual Owner
revocation it first checks a still-live task session, then verifies grant rejection.
Do not count isolated regression fixtures as any of these public checks.

The current self-owned source scope is bounded to `/robots.txt`, `/`,
`/products/tx10`, `/contact`, 10 seconds per request and 24 seconds per capture,
inside the unchanged 30-second original lease. DNS uses signed container-scoped
TCP resolvers 223.6.6.6 and 223.5.5.5. This does not change Windows/VPN DNS,
proxy or routes; all original public-answer validation and preconnect pinning remain.
Missing scalar comparisons remain separate UNKNOWN assessments with distinct
identities; the original report's duplicate-ID rejection remains enforced.


## Live test modes and operating window

PRs run offline service boundaries. Real public tests require explicit dispatch of
`windows-public-service.yml`: `mode=health` checks current mTLS (and forbidden
clients), while `mode=full` additionally requires current source consent, task
sessions and actual human grants. A health artifact never proves a capture,
human review or customer release. `mode=ai` performs sequential capture only;
model invocation and success require separate current PG/usage receipts. All historical failures and full-flow receipts
remain evidence; they are not overwritten to make a later health run look complete.

The client CA/leaves, deployment/issuer delegation, verified directory and independent
model allowance now expire at **2026-11-30T15:59:59Z** (Beijing Nov30 23:59:59).
Client leaf serials/fingerprints rotated; existing keys, phone enrollment and role epochs remain.
The server certificate (valid until 2027-02-17) does not extend these authorities.
Historical invitations, revoked grants and expired source permissions were not revived.
The new self-owned AI scope has its own shorter expiry, recorded in the handoff evidence.

The isolated model runtime uses the canonical `vrae-local-ledger` volume subpath `qwen`.
Explicit shared-quota approval and its existing ownership label are required; a missing
ledger fails closed. Never copy/reset a ledger or chmod another deployment to fix access.
The existing global limit remains CNY5 per UTC day, including unknown historical reservations.
Both real calls retain provider-reported usage; their CNY0.05121 estimate is not an invoice.
One result was refused for GUARD_ANCHOR_REQUIRED and is not retried; one is an unapproved
human-review candidate. Model availability never creates report-release authority.

Docker Desktop already starts at this Windows user's login; owned containers use
`unless-stopped`. A bounded process wake request and this user's
`VRAE-TemporaryWake.lnk` remain effective only until the current temporary authority
window. Stop the wake request by creating the configured
`windows-power-guard-nov30.stop` file or ending its recorded PID; exiting releases it.
No power plan, global proxy, DNS or route was changed. Manual sleep, logout,
network/VPN outages and Windows shutdown can interrupt availability.


## Dedicated VF Preview identity (Owner 7026419809)

Current runtime c456312 adds root-configured `health_probe` expiry/exact GET-route
restrictions before application routes; normal mTLS certificate binding still applies.
Intake role selection excludes these temporary probes so they cannot disrupt the
original business binding. The unused GH probe identity was removed before export.

The separately issued VF Preview identity is a distinct APP actor/LOGIN role in the
same tenant, registered additively in the original principal/assignment/actor tables.
Do not rerun tenant install or reuse an old actor. Its certificate and PG login expire
at 2026-11-20T01:39:55Z; the invitation is unused and has the same short expiry.
Five DIAGNOSIS values and the new invitation were delivered as Sensitive variables
only to gloweaseco-1757s-projects/veyfront, Preview branch feature/vf-b-offline-g1-adapter.
No keys or invitation values are in this repository. Delete the invitation variable
after real consumption. Receipt metadata is not a claim of human acceptance or E2E.

Owner explicitly approved V4 invalidation and a no-model V5 for this self-owned site.
Its scope is now only /robots.txt and /, matching VF paths:[], with the original
2026-11-20T01:42:19.648899Z expiry. No new customer domain or automatic extension.
Windows AI allowance is withdrawn in both private and staged inputs; its observed
provider egress count is zero. Keep the canonical quota untouched (nine calls).

Owner chose the VF team to set the existing enable/session/target settings and
redeploy Preview. Do not enable/redeploy or change Production on their behalf.
Continue real Vercel BFF acceptance after their deployment and actual UI consent;
do not infer BFF success from credentials, local mTLS or GitHub receipts.

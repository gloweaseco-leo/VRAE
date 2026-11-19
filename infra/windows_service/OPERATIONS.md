# Windows public VRAE service

Current acceptance is NOT_READY until the external sequential capture, actual human review,
directed recipient reads and revocation checks all finish. The controlled public source is
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

# VERIFIED_HUMAN_CUSTOMER_REPORT

This explicit server profile releases the current original native report to its
signed, currently invited recipient using the existing ReportVersion,
ReviewDecision and ShareGrant authorities. It does not relabel NativeSource,
alter source facts/Guard/SourcePolicy/Worker leases, or promote a controlled
review. The default CONTROLLED_NATIVE_REPORT_ONLY profile is unchanged.

## Operator inputs

Apply additive `infra/authorized_targets/004_verified_reports.sql` after the
existing target migrations. The function-only REVIEW role reads current PG
COMMIT/source authorization and original invitation/subject. APP/Worker/AI gain
no new privilege. There are no new tables/queue/CRM/approval store. Preserve the
original Ledger volume, private config and separate REVIEW UID.

Set `report_profile: VERIFIED_HUMAN_CUSTOMER_REPORT`. A flag alone is insufficient:
the profile requires root-signed identity authority, signed MFA identity, current
original committed/source permission, version review and a directed ShareGrant.
Mount these operator-held files read-only, never from an HTTP request:

- `/run/vrae-reports/trust.json`: `keys` keyed by key_id, each with raw Ed25519
  `public` hex, `role: REPORT_AUTHORITY` and `revoked`.
- `/run/vrae-reports/authority.json`: envelope `key_id`, `document`, `signature`.
  Ed25519 signs `contracts.l2_launch.contract.canonical(document)` (sorted compact
  UTF-8 JSON). No private identity/config signing key is installed in the service.

Both files must be root-owned, regular, not symlinks, and not group/other writable.
Use root:REVIEW_GID 0750 for the directory and 0640 for files, so ordinary API
processes cannot read identity records. Revoked keys, invalid signatures, expired
or changed authority fail closed. Signed directory changes require service
reload/restart; routine grant revocation does not alter the directory.

The signed document uses this shape (replace placeholders with verified values):

```json
{
  "contract": "vrae.verified-report-authority.v1",
  "profile": "VERIFIED_HUMAN_CUSTOMER_REPORT",
  "reference": "<identity-verification and delegation record>",
  "not_before": "<aware ISO timestamp>",
  "expires_at": "<aware ISO timestamp>",
  "allowed_source_classes": ["<actual SOURCE_ADMIN-authorized class>"],
  "directory": {
    "issuer": "https://<trusted verified-identity issuer>",
    "audience": "<report audience>",
    "jwks": {"keys": ["<original Directory public Ed25519 JWK>"]},
    "mode": "VERIFIED_DIRECTORY",
    "expires": 1800000000,
    "people": []
  }
}
```

Directory expiry cannot exceed signed authority expiry. Person entries retain
the original actor_id/subject/name/tenant_id/role/verification_ref/report_ids.
Issuer keys and person verification must come from actual trusted identity
evidence, not a typed name, uploaded report, service bearer or claimed MFA flag.
Retain that verification evidence out of band. The runtime cannot issue it.

For repeatable tasks, signed Person entries may use
`report_ids: ["CURRENT_AUTHORIZED_TARGET_REPORTS"]`. This resolves only inside a
held current PG context: OWNER/REVIEWER stay within their signed tenant; READER's
signed subject must equal that report's original current invited subject. A
wildcard alone grants nothing outside this context. Static report IDs cannot
override the recipient binding. No new directory signature is needed per task.

Reviewer approval uses the original REVIEWER/OWNER permission. Directed grant
issuance/revocation keeps the original Owner **role** permission, which an
authorized release operator can hold. It is not a second content approval by the
user/Owner. No 26-Gold or universal personal-Owner approval gate is added.

## Transport and actual calls

Reuse [REPORT-API.md](REPORT-API.md) paths/media. The verified profile requires
the same operations under `/v1/report-authority/audits/{audit_ref}/...`, using
the opaque reference returned by task admission; a caller need not know PG job
IDs. Original `/jobs/{job_id}/...` paths remain compatible. The server resolves
the reference through a tenant-scoped REVIEW-only port and rechecks source and
person authority; knowing either ID grants no access. The verified profile uses
the accepted `transport` config with bind/port/hosts/origins/client_ca, mtls=true,
and client_certificate_sha256 on each REVIEW service binding. A wrong trusted-CA
leaf still gets 403. Keep REVIEW config/ledger separate from APP/Worker/AI.
Operator deployment selects the actual approved VRAE endpoint, not a caller UI.
Every verified request also sends:

```text
X-Report-Profile: VERIFIED_HUMAN_CUSTOMER_REPORT
```

Missing/mismatched expected profile gets 406, without controlled fallback.
Retain TLS trust, source-SHA/scope checking and no-store. POST `/challenge` with
`{}`; the trusted identity issuer signs the returned nonce in the original
Directory format: EdDSA/kid/typ=vrae-responsible-review+jwt, exact claims
iss/aud/sub/iat/nbf/exp/jti/nonce/acr, acr=VERIFIED_PERSON_MFA, maximum 300 seconds.
Exchange responsible_bearer/nonce/csrf through `/session`. Controlled acr,
invalid/expired signatures, role claims and replay are denied; roles come only
from the signed directory.

The Reviewer reads the actual committed report, obtains a one-use action token,
and posts `/decisions` with current `If-Match: "<display_hash>"` and actual item
acknowledgements. The original ledger binds version/content/display and reviewer.
An authorized release operator posts `/grants` for the original invited recipient
actor ID. TTL remains 1–1800 seconds, capped by current PG authority/directory
expiry. The recipient uses their own signed session, X-Report-Grant and
X-Report-Token. A service credential or another customer's token is insufficient.

Selected successful recipient response fields:

```json
{"contract":"vrae.report-authority.v1","scope":"VERIFIED_HUMAN_CUSTOMER_REPORT","formal_human_review":true,"external_release":true}
```

The full response has the original report, APPROVED ReportVersion, display hash
and actual review_decision. Original producer-document flags describe immutable
pre-review source; the separate current review/grant envelope authorizes release.
Evidence, locators, counterevidence and UNKNOWN remain intact. No form submission,
inquiry receipt, conversion or engineering certification is inferred.

Revision returns review_required=true/external_release=false. Old review cannot
release it (403); after re-review, old grants stay stale (409). Grant revocation
denies the next read. Wrong subject/report, expired/withdrawn source/invitation or
identity authority fail closed. PG/source/directory checks remain held through
actual output; verified writes recheck before Ledger COMMIT. Original 429/503
semantics remain. Health also checks the verified SQL port is installed.

## Verification, deployment and rollback

```powershell
python -B -m infra.authorized_targets.runner --label verified-local --delivery-bridge --verified-reports --image vrae-g1:313
```

Use a new owned label. Optional delivery CI also retains controlled API checks.
`verified-reports.json` contains completion/failure class, probe/status/hash/time
and exact source SHA, never report/evidence bodies, credentials or signing keys.
Cleanup is the original exact label-verified cleanup.

The drill uses two original invited subjects/targets, new PG COMMITs, isolated
signature keys and mTLS, and exercises review/read/revision/re-review/revocation,
wrong recipient/version and source withdrawal. This proves the same verified
identity **protocol**, not actual customer identity vetting or real human signoff.
Test verification references explicitly say so. Do not install test keys/records
in customer deployments or claim actual customer delivery from CI. Deployment
must supply actual trusted identity records, legal source permission and intended
recipients. This PR performs no live customer/provider/cloud action.

Rollback stops this profile/restores its previous service/config; retain original
ledger history and source data. The additive SQL grants no APP/Worker/AI access.
Never restore an old approval as current or reuse grants across versions.

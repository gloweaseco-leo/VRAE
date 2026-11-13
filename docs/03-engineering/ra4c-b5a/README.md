# B5A: signed TEST_ONLY session → current Reviewer SQL → original SSR preview

Authority: [Owner B5A ENTRY CODE GO](https://github.com/gloweaseco-leo/VRAE/issues/79#issuecomment-6859365279).
Entry is `6257ad3acb09d046d954301117134f6992c02d84`; branch is
`codex2/ra4c-b5a-signed-review-read-testonly`. Only new B5A paths are writable.

This connects the accepted operating console to actual PostgreSQL16 immutable
originals using a signed synthetic identity. Task metadata remains a labeled
synthetic fixture. A local cryptographic signer is not a natural-person identity.
The 404 report has one finding and six Claims. The 200 report has zero findings,
native-null, and three coverage Claims. All previews remain PRIVATE / NOT APPROVED.

## Implemented dependency contract

| Boundary | Actual implementation and data dependency |
| --- | --- |
| B2 identity | Accepted `IdentityBoundary.check` verifies the TEST_ONLY EdDSA Bearer, server nonce, issuer/audience and exact server-held Assignment/Locator. It connects as the actual p2b1 Reviewer and calls accepted `load_target`. |
| B5A session | One-use challenge produces an opaque, random server session bound to verified subject, exact tenant/report/version/locator, assignment and trust generation. Only a digest of the cookie identifier is retained. TTL is capped by token, anchor, binding and 120 seconds. |
| PG original reader | New `ReviewerReader` calls only accepted `ra4a_review_test.load_target`; actual session/current user must equal the configured nonsuperuser, non-BYPASSRLS Reviewer. No APP connection, raw table read, SET ROLE, grant or DDL modification. |
| Native and Guard | Returned BYTEA is checked against separately held target/manifest/object SHA and length pins. Accepted `NativeVerifier.load_original` and `ReviewTargetBridge.prepare` validate those returned original bytes. Runtime never calls draft generation and has no fixture-byte fallback. |
| Existing UI | The existing `ConsoleService` ports, `ConsoleInterface`, views and proposal composer render the verified read snapshot. Each protected request rechecks current authority and SQL originals before releasing its response. |
| Pure proposal | New adapter invokes accepted `validate_proposal` with exact per-Claim and section bindings. It produces only contract validation, including coverage acknowledgement previews. It does not bypass the old fixture-only preview constructor. |
| B3 and B4 | Genuine ReviewDecision, CAS/decision receipts, durable task API, API/Worker mutation and customer ShareGrant remain unavailable. B4 PR83 is not imported or assumed accepted. All effective mutation routes deny or return NOT_IMPLEMENTED with no business writes. |

## HTTP contract

The service binds exactly `127.0.0.1`. Host must match its actual bound port;
POST requires that exact Origin. Cross-site requests, injected role/DSN/tenant
headers, privilege-shaped form fields and duplicate/malformed inputs are denied.
No browser field selects authority, database identity or trust anchor.

1. GET `/b5a/login` supplies only a public bootstrap CSRF value and TEST_ONLY instructions.
2. POST `/b5a/challenge`, form `{task, _csrf}`, resolves an existing server binding
   and returns a short-lived server nonce/CSRF plus a path-scoped HttpOnly challenge cookie.
3. An **out-of-band** local fixture issuer signs that nonce. POST `/b5a/session`
   accepts only JSON `{}`, the Bearer Authorization header, `X-B5A-CSRF` and the
   actual challenge cookie. Successful B2 + original validation returns303 and
   sets only an opaque `b5a_session` cookie, HttpOnly, SameSite Strict, Path `/b5a/`.
4. Protected GETs use the existing pool/detail/review/target/evidence/proposal
   routes. Version/draft/target selectors must match the server binding. They
   cannot enlarge its scope. Authorized original reads are real SQL reads.
5. POST proposal-preview and logout require a one-use path/session CSRF nonce.
   Double submit denies. Logout destroys RAM state; it does not write to PG.

All responses use no-store, no CORS and a script-free CSP. Same-origin referrers
on successful HTML preserve native browser form Origin; external referrers are
suppressed. Bearers never enter a URL, HTML, cookie, telemetry or audit record.
Profile refresh is local provisioning, not an HTTP endpoint. Any changed or
unavailable profile invalidates prior sessions before accepting a replacement.
Restart generates a new boot generation/challenge state; old cookies and consumed
tokens cannot establish a session. Trust-key rotation also invalidates them.

This is disposable **loopback HTTP**, with no Secure cookie or TLS guarantee.
It is not a production login, IdP integration or deployable external service.

## Reproduction and acceptance

Use Python3.11 or3.13 and Docker with the accepted image pinned in
`infra/ra4a/image.txt`. Install the existing locked dependencies:

```text
python -m pip install -r requirements-ra1a.lock -r requirements-ra4a-p2b2a.lock
python -B -m integration.ra4c_b5a.run fresh-311
```

Set `B5A_CHROMIUM` to an existing Chromium executable when it differs from the
local Windows fixture path. Linux CI uses `/usr/bin/google-chrome` and Noto CJK.
Each invocation creates independent PG/network/volume resources and fresh keys;
use a fresh label, never adopt an earlier run. Runtime credentials, signer IPC,
raw XML/logs and profiles stay in ignored `integration/ra4c_b5a/.runtime/`.

The browser process receives signatures only through private test-controller
pipes. The HTTP child receives only a Reviewer profile/public JWKS, never admin,
writer or signer keys. Fixture mutation is performed outside the HTTP process.
This separation concerns inputs and responsibilities, not OS-user isolation.

Acceptance runs actual Chromium at1280/375/320, real hit-tested pointer and
keyboard selection, visible focus, Chinese glyph raster, exact six/three Claims,
pure preview, logout, profile revocation, PG assignment revocation and actual
HTTP-process restart. Real HTTP/PG negatives cover malformed/oversize bodies,
Host/Origin/CSRF, forged authority, token replay/signature/issuer/audience/nonce/
expiry, current anchor/binding/session, wrong tenant/locator/version, missing
source, original hash mismatch and DB-down. Independently held altered pins are
compared against actual PG originals; the immutable DB is not made writable to
manufacture corrupt rows. All13 private tables receive actual denied SELECT,
INSERT, UPDATE, DELETE and TRUNCATE attempts (SQLSTATE42501).

The accepted P1/P2A/P2B1/B2/C3 suites run from their existing source. The local
legacy adapter relocates only output/STATE constants and uses original public
lab APIs; it does not replace assertions, SQL or browser operations. C3's existing
APP reader is used only in its own legacy regression, never in the B5A runtime.

The new workflow adds two B5A jobs to the existing12; expected hosted total14.
Only after all local gates and publication scan may one Draft PR be pushed.
The first hosted cycle then stops for Owner FINAL PASS. No ready, merge or deploy.

## Evidence policy

Publish only bounded receipts, exact source pins, role/RLS/SQLSTATE facts, table
fingerprints, original XML/log digests, status-only XML and synthetic screenshots.
Raw JUnit and diagnostic logs are retained locally, never copied as public text.
The browser receipt field `actual_reviewer_rows` counts successful SQL-return
batches; the private audit event's `objects` field records each batch's actual
object-row count. Refusal proofs compare successful-return counts before/after.
The export allowlist and actual-credential scan must pass before staging or upload.
See `DEVELOPMENT-LEDGER.md` for retained development REDs; they are not acceptance
proof and are not silently overwritten by later runs.

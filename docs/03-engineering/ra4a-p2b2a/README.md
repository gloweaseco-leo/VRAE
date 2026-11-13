# P2B2-A: verified local TEST_ONLY reviewer identity

Owner authorization: [Issue #75](https://github.com/gloweaseco-leo/VRAE/issues/75), including the 2026-11-13 CI re-authorization. Entry is exactly `a17d02f16a16acd7214815fce02747509c31f7bd`. This is an engineering candidate pending independent Owner review, never authorization for real approval, sharing or deployment.

## Executable boundary

`vrae.identity.IdentityBoundary.check()` verifies a compact Ed25519 JWS with an exact, out-of-band issuer/audience and expiring, locally provisioned public JWKS. The profile requires `typ=vrae-test-identity+jwt`, `iss/aud/sub/iat/nbf/exp/jti/nonce`, at most 300 seconds token lifetime, and a server-held nonce. It rejects token-directed discovery/key URLs, every other algorithm, duplicate JSON fields, malformed/oversized encodings, invalid signatures, unknown/revoked keys, missing trust, clock rollback, invalid times and replay. No private signing key or issuer implementation is in the request module. The disposable signer exists only in `tests/identity/issuer.py`.

The separately held `Assignment` policy binds `(issuer, subject)` to one exact locator and fixed test DB role, with independent activity/expiration. Browser role, actor, user and tenant claims do not select this role. A trusted connection factory opens the existing local PG16 least-privilege session. The boundary checks `session_user`, actual PG major version and role privileges, then calls the unchanged `ra4a_review_test.load_target` function in a transaction. Existing P1/P2A/P2B1 authority enforces active principal, tenant assignment, report assignment, current policy and exact current reference. No schema extension is needed.

The returned `IdentityCheck` is an observation. It cannot be submitted to an authority API. Its native decision, approval and ShareGrant are `None`, external visibility is false, and production ports always deny. The boundary does not call `submit`, create an audit/outbox event, or change any review state. Tests compare actual database fingerprints before/after checks.

Claim/skew tests inject a trusted deterministic clock; the default boundary clock is real `time.time()`. DB policy expiration tests use the actual PostgreSQL clock. Signatures and database sessions are real in both cases.

## Deliberate compatibility limits

This is a constrained, signed local identity-token profile, not an OIDC authorization-code login implementation or an interoperable production IdP adapter. Issuer/JWKS, assignments, clock, connection factory and nonce are trusted provisioning inputs, never request configuration. There is no remote discovery, URL fetching, stale-cache fallback, real SSO/email, or customer credential support.

Replay storage is locked, bounded and process-local; a consumed JTI remains consumed even after a DB failure. Active entries are never evicted to make room. This supports only one disposable local boundary lifecycle. Restart must discard issuer keys and outstanding challenges/tokens. Multi-worker use, restart-persistent replay/revocation, production mapping and time-of-check-to-write integration are explicitly unavailable. A positive identity observation is never accepted as later write authorization.

Cryptography uses the isolated pinned `cryptography==50.0.2` dependency; original runtime/PG locks are unchanged. References: [JWT security BCP](https://www.rfc-editor.org/rfc/rfc8725), [Ed25519 API](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/), [upstream changelog](https://cryptography.io/en/latest/changelog/).

## Reproduce

Use fresh Python 3.11 and 3.13 environments, an available Docker daemon, and the accepted digest-pinned PG16 image in `infra/ra4a/image.txt`:

```text
python -m pip install -r requirements-ra1a.lock -r requirements-ra4a-p2b2a.lock
python docs/03-engineering/ra4a-p2b2a/run.py run unique-run-label
```

The runner invokes unchanged accepted fixtures with only their private state/output paths relocated into this directory. Each run owns a separate cluster/network/volume. It records native JUnit, stdout/stderr bytes and hashes, source byte/LF hashes, Python/dependency versions and Git HEAD/parents, and verifies owned-resource teardown. `--pg-only` omits the general legacy pytest invocation when that interpreter's unchanged general regression has already been recorded separately; it still executes both original PG migration phases, P2A, all P2B1 cases and new identity/PG cases.

The one added hosted workflow uses `--identity-only`: fresh accepted migrations plus the new crypto/identity-PG vertical. Original regression coverage remains in the unchanged four standard and two PG jobs, avoiding duplicate hosted full regressions. The workflow records actual merge-checkout HEAD/parents and always verifies cleanup; artifacts retain only the bounded run directory for three days.

Before and after destroying each final-profile lab, the runner checks public output against the actual disposable DB credentials, plus encoded bearer patterns. The added workflow uploads evidence only after this publication gate succeeds. Captured failure diagnostics are never printed before this gate. Native identity test counts come from JUnit; the reused P2B1 fixture's legacy call counter intentionally counts only `/p2b1/` paths.

New crypto cases are explicitly selected from `tests/identity/crypto_cases.py`; new PG cases are explicitly selected from `integration/ra4a/p2b2a/cases.py`. This follows the existing opt-in P2A/P2B1 test layout so frozen jobs do not acquire an uninstalled optional dependency. It adds no skip/xfail markers. General legacy pytest retains the repository's existing isolated-network/browser conditional skips; those jobs must run through their original dedicated CI environments.

```text
python docs/03-engineering/ra4a-p2b2a/red_control.py path-to-red-junit.xml
python docs/03-engineering/ra4a-p2b2a/audit.py
```

The RED control intentionally disables verification **in memory only** and must return nonzero. It is mutation evidence, not real cryptographic verification. Normal suites use actual Ed25519 signing/verification and actual PG16. `audit.py` validates permitted paths, scans public bytes for credential patterns and creates a disposable Ed25519 integrity seal over the byte/source/log manifest. The seal conveys no human identity, trust anchor or approval. Private runtime state is ignored and never uploaded.

Early failed/debug runs and original metadata containing local account paths remain in ignored `.runtime/private-evidence`. `PRIVATE_DEVELOPMENT_EVIDENCE.json` preserves original byte hashes and identifies any public metadata views with account-path redactions. Passing native JUnit is retained directly; originals are never silently rewritten or represented as green.

## Local acceptance evidence

Local results are in `LOCAL_RESULTS.json`. Each interpreter passed 73 crypto cases, 30 identity/PG cases, P1 v1 54 + P1 v2 54 + P2A 86 + P2B1 131. New/PG suites have zero skips. The intentional RED mutation produced three failures. Final hosted-profile rehearsals also passed 73+30 per interpreter, actual credential/token scans and owned cleanup.

The original general suite ran all 2,445 selected cases on each interpreter. First Windows runs recorded 2,418 passed / 2 failed / 25 existing isolated-lab skips (3.11), and 2,419 / 1 / 25 (3.13). Failures were the unchanged default-locale GBK source reader and one 3.11 local HTTP timeout under concurrent load. Both original failed nodes passed in UTF-8 corrective runs (2/2 on each interpreter), with source/assertions unchanged. Native first-pass failures and corrective JUnit remain recorded separately. Future child stages explicitly set `PYTHONUTF8=1`; complete exact-merge hosted regressions remain required.

## Next independently authorized step

P2B2-B should first obtain Owner approval for a bounded API/session design: server-issued challenge lifecycle, durable replay/revocation, an explicitly registered test IdP and tenant membership authority, and a transaction-bound identity-to-TEST_ONLY proposal adapter. Any persistent schema/protected API change needs a minimal separate decision request. Real human `ReviewDecision`, effective APPROVED, production tenant mapping, Worker/external delivery and ShareGrant remain gated beyond this increment.

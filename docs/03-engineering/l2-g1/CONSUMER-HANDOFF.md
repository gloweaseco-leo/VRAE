# Minimal C1/C2 handoff after normal main merge

Owner6995355794. Accepted main0b2c171b680e39ad8a410d7bc6708a9f82221072 is
normally merged, including #157/#158/#159. Existing G1 results/commits remain;
no rebase/force or Provider call. C3 does not edit C1/C2 client or test sources.

## Run your own isolated instance

Follow README's image build once, then use a new label:

```powershell
python -B -m infra.l2_g1.runner --label independent-UNIQUE --quick --hold
# In a second terminal use the exact runtime name printed by the runner:
docker exec -u 0 OWNED_RUNTIME python -m integration.l2_launch.g1.owner_cli new manufacturer
docker exec -u 0 OWNED_RUNTIME python -m integration.l2_launch.g1.owner_cli work
docker exec -u 0 OWNED_RUNTIME python -m integration.l2_launch.g1.owner_cli preview AREF
docker exec -u 0 OWNED_RUNTIME python -m integration.l2_launch.g1.owner_cli export AREF
# End the test and let the owning runner verify exact cleanup:
docker exec -u 0 OWNED_RUNTIME python -m integration.l2_launch.g1.owner_cli stop
```

`export` returns private file locations and byte digests only. The original
bundle, original PG row/count/COMMIT receipt and exact signed VFSubmit are under
`/evidence/.private-root/consumer-exports/AREF/`, UID0-only. Do not upload these
originals or config secrets. Source/body are the same newly created original
native task, not G0 examples. Exporting a snapshot grants no ongoing access.

C2 feedback6995605922/6995680836 identified two missing P0 inputs. Export now
also includes **private0600** `current-session.json` (actual Cookie map/header,
CSRF, expiry and same-session hash) and `changed-intent.json` (independently valid
permission/invitation/submission signatures, same durable key, different intent).
All values remain behind the UID0-only directory. Command output/public records
contain only locations and digests, never these credential values. Import the
session only in a trusted consumer process; do not print it or put it in URLs.
The exported session's first exchange is already consumed: importing it enables
real current-session P0 reads/CSRF tests, **not** a new first-exchange200 claim.
A case requiring a fresh exchange remains explicitly pending until that separate
fixture stage is arranged. Private signing keys and APP credentials are not
exported. The valid changed intent should receive409 without creating a new job.

Both real endpoints are inside this exclusively owned network-none namespace:

| Item | Actual interface |
| --- | --- |
| VF BFF | `https://127.0.0.1:8767`; does not accept caller Authorization |
| Private facade for a VF server consumer | `https://127.0.0.1:8766` |
| CA | `/tmp/g1-ca.pem`; export returns exact facade certificate SHA256 |
| Service identity | `Authorization: Bearer <service_token>` |
| Owner fixture identity | `X-G1-Fixture-Owner: <owner_token>`; separate credential |
| Private config | `/tmp/g1-facade/config.json`, owned UID10003/mode0600 |
| Host/Origin | literal endpoint host/port; Origin `https://127.0.0.1:8766` |
| Profile | frozen exact G0 media type on Accept and POST Content-Type |
| Source binding | `X-VRAE-Source-SHA` equals the clean archive's full Git SHA |
| Dirty local development | header is `UNCOMMITTED_WORKING_SOURCE`; never claim an exact-commit pass |
| CSRF | request and response `X-G1-CSRF` |
| Preview pin | `If-Match: <view_sha256>` |
| AI | single `X-G1-AI-State: NO_MODEL`; no provider execution |

Do not publish a host port or disable CA validation to fit the current client.
Execute the real HTTPS consumer inside your own namespace (or use an explicitly
owned TLS byte relay); no simulated response adapter. Inject secrets only into
the consumer process environment, never command-line values or public JSON.

## Specific differences from merged #158 client

The merged client is valuable but not yet directly wired to this service:

1. `owned_endpoint`/WireClient support HTTP only. This service uses TLS to make
   actual Secure cookies meaningful. A minimal C2-owned HTTPS/CA/certificate-pin
   transport change is needed, with the same actual requests/response checks.
2. Its CSRF name is X-CSRF-Token; ours is X-G1-CSRF. Its Owner alias always
   becomes Bearer auth; ours uses the separate Owner header. If-Match is not in
   its current four-header override allowlist. Do not treat these mismatches as
   valid CSRF/Owner-denial evidence.
3. Exchange requires actual GET `/v1/return-challenge` first. Its returned
   HttpOnly challenge Cookie and X-G1-CSRF must accompany the POST exchange.
   Exchange sets a session Cookie **and deletes the challenge Cookie**. The
   client must distinguish a Max-Age=0 deletion from a second live session.
4. The original private bundle preserves `REVIEW_REQUIRED`, plus the actual
   controlled ledger decision with formal_human_review=false. The current C2
   preview check requires APPROVED. Do not relabel the original version APPROVED
   or manufacture human/release authority to pass a consumer predicate. Keep
   real-release checks strict and handle the explicit synthetic-only fixture.
5. The fixed service identity is tenant-test. Wrong-tenant input is tested
   using that valid service identity and a foreign request tenant; there is no
   separately provisioned valid tenant-beta service token. Invalid auth403
   alone does not prove a current-session cross-tenant check.
6. Readonly `/work` intentionally has no Git metadata or writable C2 .runtime.
   A C2 driver may call its actual Consumer/report API and write sanitized results
   to its own evidence volume, retaining client/source byte hashes. Do not use
   its fake-wire selftests as actual HTTP acceptance.

Each of the23 cases must retain its actual PASS/FAIL/BLOCKED. In particular,
`inquiry_waiting_ack` has no implemented accepted handoff in T0; ordinary sales
handoff stays closed. Missing stage hooks/receipts must stay BLOCKED rather than
being replaced by an unrelated403 or another task's result. The existing Owner
fixture operations provide status, retry, deny/allow/expire, service-down/up,
actual original custody and controlled preview. PG restart uses `--recovery`.
C2 owns the minimal consumer compatibility changes/phase arrangement; C1 owns
independent P0 results. C3 fixes concrete backend defects they report.

Actual source provenance is the header plus source archive and Git blob hashes;
the header alone is not binary remote attestation. G1 full acceptance, real
human review, customers, targets, Provider costs and cloud deployment remain
closed pending the Owner's separate gates. These gaps do not block the Owner's
existing T0 CLI trial.

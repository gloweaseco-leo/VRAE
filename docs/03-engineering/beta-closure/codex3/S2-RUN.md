# S2 runnable consumer: real task status, provenance refusal, API restart

Accepted base: ea49547205c2ec8fdf6bcbd64e9fef90d7aa931a (Owner-merged PR89; PR99 #6890212776).
Branch: codex3/beta-s2-consumer-20261115. This change extends only the C3 runner.
Full processing/result binding remains BLOCKED; this is not full S2/Beta EXIT.

## Operate the actual accepted interfaces

Use the existing locked host environments and dependency-only native images described in README.
From this worktree, terminal1:

```powershell
$env:BETA_CODEX3_PRIVATE_EVIDENCE = '1'
& integration/beta_review/codex3/.private/py311/Scripts/python.exe -B scripts/beta_internal.py start --phase s2 --run owner-s2-001 --minor 3.11
```

This actually starts owned PG16, original low-role API/Worker and original signed SSR.
The independent diagnostic candidate still uses actual Collector/six rules/Guard/renderer.
The Worker remains the unchanged accepted claim/finish consumer.

Terminal2:

```powershell
& integration/beta_review/codex3/.private/py311/Scripts/python.exe -B scripts/beta_internal.py trace --run owner-s2-001 --task 404
& integration/beta_review/codex3/.private/py311/Scripts/python.exe -B scripts/beta_internal.py trace --run owner-s2-001 --task 200
& integration/beta_review/codex3/.private/py311/Scripts/python.exe -B scripts/beta_internal.py restart-api --run owner-s2-001
& integration/beta_review/codex3/.private/py311/Scripts/python.exe -B scripts/beta_internal.py trace --run owner-s2-001 --task 404
& integration/beta_review/codex3/.private/py311/Scripts/python.exe -B scripts/beta_internal.py stop --run owner-s2-001
```

Trace uses docker exec UID/GID10001:10001, reads only that APP's existing private config,
and performs GET against the original fixed loopback API. It has no DB query, new HTTP endpoint,
writer credential, SET ROLE, raw-table fallback or permission grant. Exact container labels
must match this run. Raw UUIDs remain private; CLI output exposes hashes and the explicit state.
--request accepts an actual request UUID; an unknown request is denied without record metadata.

restart-api is a once-only private test-supervisor signal for the exact own original API child.
It uses the already accepted same-UID signal/spawn helpers; it creates no new admission and
changes no SQL, role, policy, epoch or Worker code. It is not a runtime administration endpoint.
The original API reloads the same private role/config. This is API durability, not B7 restore.

## Meaning of the output

C3_S2_READ_TRACE_1 is an internal diagnostic output schema, not an accepted B4 producer contract.
request/run/job IDs and state are read from the real API. configured_reference_sha256 is an
out-of-band input-reference config pin validated by the original admission/status path.
report_version_metadata belongs to that pre-existing source reference; it is not generated output.

processing_result = BLOCKED_NO_ACCEPTED_LEASE_BOUND_RESULT_PORT
generated_report = null
origin_epoch = null
lease_token = null
reviewer_job_result_binding = BLOCKED
approval_status = NOT_APPROVED

The accepted status does not expose a current-lease result binding. Admin-observed epoch values
are not substituted into this consumer. Genuine separately generated draft bytes, a copied
job UUID, a caller's generated=true flag, or a matching pre-sealed reference cannot authorize
a job/result association. require_generated_result refuses all such candidates until an
Owner-accepted versioned producer/lookup contract is available. It has no fabricated positive stub.

## Native tests and exact C1 handoff

```powershell
$env:BETA_CODEX3_PRIVATE_EVIDENCE = '1'
& integration/beta_review/codex3/.private/py311/Scripts/python.exe -B scripts/beta_internal.py verify --phase s2 --run s2-311-001 --minor 3.11
& integration/beta_review/codex3/.private/py313/Scripts/python.exe -B scripts/beta_internal.py verify --phase s2 --run s2-313-001 --minor 3.13
```

The original nine task-lane tests remain unchanged in purpose: two actual committed-task reads, two pre-sealed-metadata association refusals,
two genuine independent live-report association refusals, one real unknown-request HTTP denial,
one explicitly consumer-envelope correlation mutation, one actual API restart/exact status reread.
Fresh PG/API/Worker and current pipeline inputs are used; no prior-run result is replayed as new.
All original product/API/Worker/SQL/CI and original tests remain unchanged.

C1/Owner must choose the exact accepted producer contract/version. Required consumer semantics:
- Authoritative tenant/request/run/job, current Worker identity and lease sequence/token/expiry,
  origin epoch, source/ref SHA and SourcePolicy/version, validated at read and COMMIT.
- Actual produced pack/execution/evaluator/package/Guard/version/report-content/HTML pins,
  durably bound by that producer to that admitted job, one audit/outbox and exact result lookup.
- Reviewer-assigned tenant/job/report/version locator after generation; no Worker lease token
  in SSR; current revocation/version checks; accepted PR89 TEST_ONLY intent and future PR92 ordering.
- Reject cross-tenant/actor, expired/replayed lease, stale/revoked epoch/policy, changed source,
  changed Guard/result, cancel-before-COMMIT, partial persistence and divergent retries.
- Same legitimate retry/restart returns the same durable result/receipt without duplicates.

These are consumer requirements, not authority to implement B4 functions, ACL, RLS or migrations.
Only normally merged Owner-accepted main is consumed. C1 DISC S1, the processing-result seam,
B4-P2 and PR92 remain explicit dependencies; PR89 is now accepted and consumed; no unmerged sibling source is copied.
A1/B7/MAX3 remains paused pending its later exact safety GO. Gold0/26; full Beta2/7, G1/G2/G3 NO-GO.

Raw source/config/trace/UUID/JUnit data stays under the ignored private integration directory.
Sanitized per-run receipts can remain under docs/.../codex3/.private via the environment flag.
The new native JUnit projection exports only safe suite/case fields and omits hostname/properties.

## Accepted B5-P0 lane on current main

start --phase s2 now provisions accepted B5P0 fixture capabilities and loads the
accepted b5p0_profile.load in the SAME existing SSR. No second UI/API is started.
The original CLI signed session/open command reads the sealed task and its
"internal rehearsal" link. Save is TEST_ONLY_REVIEW_INTENT / NOT APPROVED only.
The original B4 admissions and the sealed B5 tasks are separate provenance lanes.
B5 receipts do not authorize associating any report with a B4 job.

verify --phase s2 now runs 14 native cases: the original nine plus five B5 cases.
The accepted unchanged browser.mjs performs real signed original reads, per-Claim
pointer/keyboard saves and receipt reads on both sealed 404/200 at1280/375/320;
12 genuine form/receipt screenshots are private, with public SHA256 projections.
HTTP checks preserve exact version/receipt, deny cross-task and stale version,
then restart the SAME SSR child with the same strict private profiles, SQLite
recovery journal and PG B3 rows. Old cookies are denied; fresh Ed25519 login
rereads byte-identical receipt pages, with the same receipt SHA and no new
intent/audit/outbox. This is the accepted B5 process-restart path, not PG restore,
B7 recovery or a guarantee of old-session portability across processes.
Changing the exact private bridge bytes invokes the accepted loader's current
provisioning revocation and denies the receipt without any new business write.
No SQL, ACL, RLS, Guard or SourcePolicy changes are involved in that negative.

Accepted B5P0 Runtime/bootstrap, binding, verifier, IntentService and published
HTTP routes supply all authority. C3 holds fixture admin/signer only outside SSR;
SSR gets strict Reviewer/B3 witness profiles, never an admin profile. Original
B5/B3 sources and tests are unchanged. Raw receipt pages, cookies, keys, witnesses
and browser profile stay private. Full S2/Beta remains BLOCKED on the C1 result
producer/Reviewer assignment seam and later accepted PR92/S4 gates.

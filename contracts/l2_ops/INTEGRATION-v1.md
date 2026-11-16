# C3 L2 operations / business handoff v1

Baseline: accepted main `6a7c39b2bec48842de2236490aa6157a57606e08`.

This is the C3 composition contract, not a replacement C1 producer, C2 review
contract, task API, authorization grant or claim that L1 output is L2.

## Source input

`l2-local-input-v1` is consumed by `vrae.l2_ops.ingest.load_source(path)`.
Examples: `integration/l2_ops/fixtures/*.json`; all three examples are explicitly
synthetic and use the same controlled industrial catalog, not a real customer.
Access modes `OFFLINE_SYNTHETIC`, `PUBLIC_READONLY_CAPTURE`, `CLIENT_PROVIDED`
are independent of `diagnostic_level=L2`. Actual execution is offline capture
analysis; no URL fetcher is present. A receipt-shaped string enables no network.
Analysis basis and reuse permission references are declarations for subsequent
verification, not authorization grants. Source bytes are bounded, local and
UTF-8; descriptor SHA binds exact bytes. Bundle SHA binds all provenance.

## Normalization boundary for accepted C1 / C2 ports

C3's `CurrentReader.current()` context manager must be composed **on the trusted
server** from Owner-merged ports. It must perform the original signed session,
tenant/job assignment, expiry/revocation and locked current-version checks;
retain that context through business save COMMIT. No browser document, APP status,
static fixture, hash alone or user-chosen subject can implement this authority.
It yields `CurrentL2`:

- `pins`: tenant_id, request_id, run_id, job_id, event_id, source_ref, report_ref,
  report_version; report_sha256 (original complete report bytes),
  source_bundle_sha256 (C3 descriptor), industry_pack_sha256,
  payload_sha256 (complete canonical normalized deep payload).
- `payload`: accepted full deep result with diagnostic_level=L2. C1 owns analysis,
  evidence replay, IndustryPack and UNKNOWN semantics; C3 does not rerun/score or
  cap/expand findings. A payload SHA is distinct from the original report SHA.
- `review`: receipt_ref, receipt_sha256, report_version, report_sha256, decision
  normalized to APPROVE_INTERNAL / REJECT_INTERNAL / REVISE_INTERNAL. C2 owns the
  real receipt bytes and transaction; a DTO constructor is never proof of one.
- `blueprint`: accepted C2 blueprint including matching report_version and
  report_sha256, finding/evidence references, changes and verification criteria.
  Additional fields remain intact; C3 does not fabricate improvement proposals.

These are adapter outputs, not changes requested to the frozen APP202 SQL or
Worker lease contracts. C1/C2 may retain their native shapes; a small adapter
maps them after acceptance. No unmerged sibling implementation is imported.

## C3 result

`BriefService` produces `internal-rebuild-brief-v1`: exact report/task/source pins,
current internal review, intact blueprint, pending customer business goals,
product/market scope, material reuse rights, URL plan, acceptance and approval,
consultation reference, actual operation duration and optional priced estimates.
Rejected/revised reports remain REJECTED/REVISION_REQUIRED; internal approval is
not customer approval. Without a verified VF receipt the optional supplied
consultation reference is UNVERIFIED_REFERENCE, otherwise UNLINKED; neither
counts E2/E3. No VF authority or transport is invented.

`BriefLedger` is optional dedicated PG namespace `l2_ops_v1`, provisioned once by
controlled bootstrap with a **new dedicated runtime principal**, not old APP or
Reviewer grants. Runtime gets INSERT/SELECT only. Identical retry returns same
bytes; conflicting reference refuses. Success returns only after real COMMIT.
`save_current/load_current` recheck original current authorization; the ledger
itself must never be published as a read authority or browser endpoint.

`panel.render_current(service, document)` returns an escaped HTML fragment for
the existing unique signed SSR. It reauthenticates through CurrentReader. It is
not a new server and does not change existing CSRF/session/HTTP timeouts.
`render_verified` is a pure serializer and must not be exposed to browser input.

## Measurement

Integer monotonic wall nanoseconds, separately optional measured CPU nanoseconds;
no parent CPU is relabeled Worker CPU. Automated demo != human labor. Human
activity requires an explicit operator attestation reference. A declaration is
not independent verification. Missing rate/currency/records => UNKNOWN amount,
not zero. Supplied rates yield ESTIMATED integer monetary micro-units; no invoice
is asserted reconciled. No paid model call, production CRM, Vey2GE write or L2M
execution is performed.

## Current integration limit (must remain visible)

At initial C3 development baseline, accepted main has L1 M1 producer and M2
review only. No accepted live L2 producer/reader/review blueprint hook exists.
Tests deliberately use `TestOnlyReader`, explicitly not Worker E2E. This package
can validate sources and exercise real PG durability now; it cannot yet claim
operator-started L2 deep report/review/browser completion. C1/C2 coordination is
on Issues94/95. After their Owner merge, normally sync main and compose these
ports in original beta_internal / unique SSR; never replace with fixtures.

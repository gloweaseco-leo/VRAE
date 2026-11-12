# RA-3D offline sidecar contract v1

This is executable D1/D2 under Issue #57, derived from Phase0 DD01–DD14 without
editing that freeze. It does not implement the future authenticated application.
The implementation version is `offline-v1`, deliberately distinct from the
design's provisional `p0.1` and frozen native schemas.

## Inputs and trust

`build_target(document: bytes, html: bytes, source_raw: bytes, *, trust:
SyntheticTrust) -> ReviewTarget` requires ALL immutable bytes and separately held
accepted synthetic pins. `SyntheticTrust` must say
`TEST_ONLY_ACCEPTED_SYNTHETIC_SOURCE`; it holds the original source SHA,
ReportDraft payload SHA, native source pins, original rd-ref and HTML SHA. Its
policy snapshot and `synthetic-object://tenant/report/vN/htmlSHA` object ref are
explicit test-only stand-ins, never service authority. Missing inputs refuse.
`validate_target` rebuilds and byte-compares; direct construction is unverified.

The actual accepted EvidencePack, FindingPackage and public ReportDraft loader
replay all source/Guard/native bridges. Displayed claims (including positive
source quotations) also resolve against held objects and exact UTF-8 byte ranges.
No uploaded evidence ID or recomputed outer checksum creates semantic authority.
Accepted source facts describe captured website text/status only. Hypotheses,
actions and rechecks retain their original HUMAN_REVIEW_REQUIRED classifications.

Target covers the original native H0/id when present; SHA of full native object;
complete canonical ReportDraft payload and rd-ref; editorial/full raw HTML/layout
hashes; pack/execution/package/ordered Guards; complete source record and source
manifest (full pack plus sorted object byte hashes/lengths); Guard inputs; policy
snapshot/scope/run/report/version; evaluator/builder/Guard/reporter/editorial/
renderer versions; each interpretation's explicit null model provenance; immutable
synthetic artifact ref; all displayed claim identities/types/source ranges;
coverage and limitations digests. Rule identities/versions/proof details are bound
inside the complete package/source bytes. Exact production Git provenance is
independently recorded by D1 and final source-scope audit.

Target canonical JSON limit: 64 KiB. Proposed command: 128 KiB. Native source,
draft and HTML retain their original maximum 8,000,000 bytes, never enlarged.
JSON objects reject duplicate keys, NaN/Infinity, floats, unsafe integers, wrong
types, non-UTF8 and depth >32. No Unicode/newline/URL normalization. Ordered arrays
remain ordered. SHA256 uses `vrae.ra3d.<kind>.offline-v1\n` plus sorted compact
UTF-8 JSON excluding its own digest. SHA is not a signature or fact authentication.

A four-entry memo retains only successful replay for the complete immutable input
tuple including policy/object/pins and current renderer asset hash. Changing a byte
misses it. Failed inputs are never cached. Accepted engine/schema source is fixed
by D1; this is not a hot-reload service. Actor, current authority, clock, latest
and review sequence never come from the memo.

## Proposed commands and simulation

`ReviewCommandProposal` permits APPROVE_CANDIDATE / REQUEST_CHANGES / REJECT.
`CoverageAcknowledgementProposal` is a different type and kind. It must preserve
the exact coverage and remaining-unknown digests. Every displayed claim must have
exactly one disposition keyed by guard_ref/binding_ref/pointer; no omitted,
duplicated or foreign identities. Appropriate accepts are ACK_LITERAL_FACT,
ACCEPT_AS_HYPOTHESIS and ACCEPT_AS_PROPOSED_ACTION. A rejected/changed claim cannot
be approved. Changes/rejection require 1–2000 nonblank safe characters and at
least one specifically located CHANGE_REQUESTED/REJECTED claim. Review sections
coverage, limitations, full preview and business boundaries each acknowledge the
exact target; no fake Guard binding is fabricated for fixed text.

`prepare_production_review` always refuses
`D_AUTHENTICATED_PRODUCTION_REVIEW_NOT_IMPLEMENTED`, regardless of arguments. It
has no permissive default or production adapter. Actor dictionaries, free text,
report creators, worker/model/service roles confer no human authority.

`InMemoryReviewSimulation(simulation_label='OFFLINE_TEST_ONLY_NON_DURABLE')`
accepts only explicitly marked `TestOnlyActor` fixtures, appropriate synthetic
role/tenant/report assignment and injected aware UTC. `publish` builds a target;
`submit` checks identity shape before lookup, synthetic clock, immutable bytes,
complete proposal, latest version and first-writer-wins round sequence. It returns
only SIMULATED_APPROVE_CANDIDATE / SIMULATED_CHANGES_REQUESTED /
SIMULATED_REJECTED / SIMULATED_INTERNAL_SCOPE_ACK. The receipt explicitly has
native_decision=null, native_approval=null, share_grant=null, durable=false and
external_visibility=false. The original native Draft remains unchanged.

The sequential round key is (tenant, report, version, target_digest, expected
review_seq=0); success records seq=1 and closes the round. Idempotency scope is
(tenant, synthetic actor, report, key). Same command returns the identical immutable
receipt; a different payload conflicts, a second key cannot overwrite a decision.
Old identical retries may return history with effective_current=false after a new
version. Publication is monotonic: no equal-version changed target or rollback;
restoring old text still needs another new version. Invalid mutated upload is
rejected and never replaces the already stored legitimate immutable object.

Competing proposals are explicitly interleaved sequentially in tests. There is
NO claim of real parallel execution, thread safety, transaction, persistence,
recovery, outbox or verified authorization. The clock/high-water is test-only and
lost on restart. Fresh instances do not recover or authenticate old receipts.
No actual APPROVED ReportVersion, ReviewDecision or ShareGrant is created. Neither
approve_version nor check_share is called. No UI/API/DB/worker/login added.

## Remaining gates

Real verified human/session/assignment and revocation, current policy authority,
immutable object store, trusted persistent clock, transactional CAS/audit/outbox,
and customer access remain NOT_RUN / NO_GO. D3/RA4 need another explicit Owner GO.
Human Gold is 0/26; no accuracy, comprehension or commercial outcomes inferred.
No live website/model, paid call, customer report send, deployment or production
install is part of this work.

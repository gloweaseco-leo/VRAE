# RA3C bounded report contract 1.0

## Entry and replay

Public API: `vrae.reporting.build_draft(pack, package, guard_inputs, metadata, **pins)`;
`ReportDraft.load(document, html_bytes, pack, package, guard_inputs, metadata,
expected_draft_ref=..., **pins)`; guarded `render(...)` returns exact replayed bytes.
A direct dataclass constructor is storage, never verification or approval authority.

Input pins must have the exact key set defined in `draft.PIN_KEYS`: independently held
pack, execution, package, builder/evaluator, scope, guard version/ordered refs,
metadata SHA, reporting version and renderer version. Caller-held expected draft ref
is separate on load. Never take these trust anchors solely from the object being loaded.
Only one verified CaptureManifest source is accepted: separate captures cannot be
blended to manufacture a three-issue report.

The original C3 package is replayed by RA3B catalog/GuardResult.load; every displayed
source fact must match a complete current catalog fact, individual binding pointer,
text, binding hash and replayed SOURCE_FACT_BINDING_VERIFIED status. IDs in a global
list confer no semantic authority. Each CTA-02 native bridge also passes original
`validate_evidence_graph`; source→target and actual 404/410 response must match.
UNKNOWN, blocked, 403, 500, unretained and positive signals do not become defects.

Only fixed bounded Chinese provisional prose in `editorial.PROPOSALS` is accepted,
and only with its own individual HUMAN_REVIEW_REQUIRED binding to the same fact.
This intentionally denies arbitrary model prose even when its IDs and Human guard
are well formed. This is a deterministic editorial projection, not semantic inference.
All provider model/token metadata must be null in SYNTHETIC_PRIVATE_PREVIEW mode.

## Distinct findings and report state

Distinct groups are `(CTA-02, final target URL or target URL, HTTP status)`; repeated
links to one endpoint do not inflate the issue count. A deterministic sorted representative
is selected for each group, then at most three. An explicit nonempty unique selection
may contain 1–3 actual eligible findings, but not duplicate endpoint groups. Omitted
eligible groups are counted, other unsupported failure rules are separately disclosed.
Selection cannot create a finding or mix captures. No severity/confidence/score/ROI.

Zero issues => PRIVATE_COVERAGE_SUMMARY, native_report_version=null. One to three =>
L1_REPORT_DRAFT with original schema-valid native ReportVersion REVIEW_REQUIRED,
actual finding IDs and `report_content_hash`, approved_by/approved_at null. Every
RA3C object is private, NOT_APPROVED, unshareable and semantic_approval=false.
No ReviewDecision, ShareGrant, access API, DB, mail or deployment is implemented.

## Full content integrity

Canonical UTF-8 sorted compact JSON hashes use SHA-256. Reporting, editorial and
renderer versions are explicit. Renderer asset hash binds version plus complete CSS.
The editorial digest binds all manifest content before output hashes: metadata/time,
scope, exact claims/proposals/citations/native bridge, original input pins and guard
bundle hash, actual coverage, limits, private flags and layout asset/version. The HTML
includes this digest. html_sha256 binds every rendered byte; final rd-ref binds the
entire manifest including both digests. Native RA0 content_hash remains separate and
retains its existing meaning (manifest + findings; not full editorial HTML).

Loading rebuilds from independently pinned original inputs and compares full canonical
manifest plus exact HTML bytes plus independently expected rd-ref. Rehashing edited
copy, layout, timestamp, status or private flags does not make it legitimate. Draft
bytes are immutable and document reads detached. Version two creates new refs; old
version one can still replay under its own old pins, without being overwritten.

## Rendering and scope

HTML is Chinese-first, five buyer tasks, actual captured paths/statuses, 0–3 issue cards
with observed fact, possible impact, proposed action, recheck method, limitations and
disabled future discussion affordance. Hypothesis/action/recheck remain labeled pending.
Literal website quotes are expressly source self-description, not authentication.

No scripts/assets/forms/remote navigable links. Every anchor is a known internal ID.
Untrusted text passes length/control/bidi checks and HTML escaping; source quote is
inert plain text. CSP default/script/connect/img/font/object/frame/form none, only
exact hashed inline CSS allowed. It is defense in depth, not a substitute for replay.
The maximum payload/HTML is 8 MiB, text/URLs explicitly bounded. Failures emit fixed
REPORT_* codes without echoing untrusted source. Local preview files have no auth
server; confidentiality depends on keeping the private files private. No customer
access control implementation is claimed.

Desktop and mobile form one continuous HTML report; evidence panels expand only on
internal navigation. Print presents the report summary on one A4 page; detailed
evidence remains in paired HTML/JSON, not silently truncated into a PDF assertion.
Three-issue print uses denser typography; optional positive-source sidebar is omitted
in that print layout, while all three facts and all provisional proposals remain.

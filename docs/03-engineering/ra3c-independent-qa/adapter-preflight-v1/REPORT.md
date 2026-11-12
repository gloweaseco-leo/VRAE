# Read-only adapter preflight V1 — QA_MAPPING_NOT_BOUND

Authority: [Owner instruction](https://github.com/gloweaseco-leo/VRAE/pull/48#issuecomment-6814793175).
QA Phase A accepted source is `fa645b58549dfd21a6b80656d403f672b790acd8`,
with evidence HEAD `1db13d4fd025bd6c354d51fb26f3dd5acbbfac15`.
The separately inspected **provisional**, not final, PR #47 HEAD is
`6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2`. It is newer than the provisional
SHA cited in Owner's earlier comment. No final-candidate claim is inferred.

Only five production reporting files were read from exact Git objects. No
candidate test, fixture, demo, screenshot or generated report was used to alter
QA expectations. No reporting module was imported, no build/load/render was
executed, no business pytest case or browser was run. **0 substantive feature
cases executed here; no GREEN, independent visual PASS or production bug count.**

Original sources at this exact provisional commit:
[public exports](https://github.com/gloweaseco-leo/VRAE/blob/6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2/vrae/reporting/__init__.py),
[build/load/render and claim checks](https://github.com/gloweaseco-leo/VRAE/blob/6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2/vrae/reporting/draft.py),
[canonical encoding](https://github.com/gloweaseco-leo/VRAE/blob/6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2/vrae/reporting/common.py),
[proposal vocabulary](https://github.com/gloweaseco-leo/VRAE/blob/6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2/vrae/reporting/editorial.py),
[actual HTML locations](https://github.com/gloweaseco-leo/VRAE/blob/6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2/vrae/reporting/renderer.py).

`adapter_draft.py` is an auditable, deliberately **unbound draft** under Codex-1
docs only. It contains real public-call wiring, actual JSON origins and the
native digest recipe. Its bind/build/load entry points raise a QA MappingNotBound
error until representation/input boundaries are adjudicated. That QA error is
not listed as a production rejection type and cannot make an attack PASS.
Helper call sketches must not be mistaken for calls already executed.

## Actual public API and immutable output

At the inspected SHA, `vrae.reporting.__init__` exports `build_draft`, `render`,
`ReportDraft`, `ReportError`. The production `draft.py` defines:

```python
build_draft(pack, package, guard_inputs, metadata, **pins)
ReportDraft.load(document, html_bytes, pack, package, guard_inputs, metadata,
                 *, expected_draft_ref, **pins)
render(document, html_bytes, pack, package, guard_inputs, metadata,
       *, expected_draft_ref, **pins)
```

ReportDraft exposes actual `.document`, `.html_bytes`, `.ref`; the QA artifact
can preserve these exactly. Render replays through load rather than accepting
untrusted naked JSON. Existing source pins map without recomputation, with the
held singular expected_guard_ref wrapped into expected_guard_refs=[held_ref].
Original interpretation, bindings and guard.document can be structurally wrapped
into one guard bundle. The adapter must not drop NOT_RUN, missing-information or
other claims, insert guard-approved candidate prose, or rebuild attack pins.
The package embeds its RuleExecution, whose separately held ref is forwarded.

Native reference recipe: `_project` first hashes editorial content, renders HTML,
stores exact HTML SHA256, then sets `draft_ref='rd-'+digest(document)`. Thus the
existing frozen independent canonical-doc recipe can exclude **only /draft_ref**;
editorial_content_sha256 and html_sha256 remain in the hashed document. The actual
`.ref` is returned unchanged. No replacement QA digest is manufactured. This is
static algorithm compatibility, **not an executed round-trip integrity PASS**.

Direct actual roots include /issues, /native_report_version, /private,
/approval_status, /shareable, /scope, /metadata/version, /recorded_coverage,
/limitations, /examined_pages/0/captured_at, /renderer_version,
/renderer_asset_sha256 and /pins/expected_guard_refs/0 where present. Issue facts
and proposals map to /fact_claim/text and /proposals/{impact,action,recheck}/text;
their statuses remain the real guard statuses. Finding ID and buyer task come
from /finding/finding_id and /finding/buyer_task, not synthesized UI labels.
Actual source pointers and digest recipe are in the adapter and static audit.

## Unresolved boundaries — no oracle weakening

| ID | Real source observation | Frozen contract boundary / disposition |
| --- | --- | --- |
| M01 REQUEST_METADATA | Native metadata requires report_id, version, created_at, created_by, mode, finding_selection, plus separately held metadata/reporting/renderer pins. Frozen contexts do not supply the full caller request. | A separately reviewed caller-request fixture/pin source is needed. Do not invent a reviewer ID, report output or recompute held metadata hashes inside mutated tests. The draft takes explicit metadata/request_pins; supplies no defaults. |
| M02 PROPOSAL_VOCABULARY | `_claims` accepts HUMAN_REVIEW_REQUIRED only when `(claim_type,text)` exactly matches the three candidate `PROPOSALS`; `_issues` requires all three matching proposal bindings. Frozen QA has its own impact/action/recheck text and one MISSING_INFORMATION statement; all four differ. | Passing preserved input reaches a different admissible-input boundary by source inspection. Replacing text, rebinding or removing the missing-information claim is forbidden. Owner must adjudicate the intended valid-input contract; this preflight does not label it a confirmed functional defect. |
| M03 LANGUAGE_MUTATION | Language exists as actual `<html lang="zh-CN">`; there is no document language key. | Frozen D07 requires a native JSON mutation path. Adding a language field to returned JSON fabricates production output. An HTML source mapping can read language but cannot satisfy D07's JSON-only mutation helper. Needs Owner adjudication. |
| M04 EVIDENCE_MUTATION | Quote/byte span/citation live under actual nested fact/source/citation objects; pack/scope/target/binding have other actual origins. | Frozen C02/C03 can use the permitted object projection, but D04 requires `issue.evidence` to be one native JSON object with flat keys. No single native object has that shape. Do not inject a flattened evidence field. Needs Owner adjudication of extraction/mutation mechanics. |
| M05 OBJECTIVE_COLLECTIONS | Objective claims live in actual issue.fact_claim and positive_source_claims objects; text/binding arrays are not native document fields. | Frozen field() supports scalar JSON/HTML or object projection, not list projection. Mapping objects to expected string lists would require an explicit extraction mechanism; do not append fake arrays to document or exploit string iteration. QA_MAPPING_NOT_BOUND. |
| M06 ABSENT_SCORE | Native document has no site score field. | Frozen scores check permits None/[]/{}, but field() cannot express audited absence except native_report. Mapping an unrelated null field to scores would manufacture semantics. Lack of a native score is not itself a defect. Needs Owner adjudication. |
| M07 EMPTY_GUARD | Native `_claims` rejects supplied interpretations whose status is NOT_RUN; it permits an empty guard-input list. The frozen raw_absent context has no facts/bindings and NOT_RUN. | Do not silently drop that guard or alter expected_guard_refs to obtain a zero-issue artifact. Record input/cardinality mapping boundary, pending Owner's decision. |
| M08 MULTI_PAGE_SINGLE_FACT | Frozen duplicate_contact source has two native CTA findings but prepare_context binds one canonical fact. Native `_issues` demands exactly one bound objective match for each native CTA finding before deduplication. | Do not generate a second binding or replace the input with candidate fixtures. Static compatibility gap for T10, not an executed bug verdict. Owner must resolve admissible input/selection expectations. |

HTML-only roles main_text, privacy_text and service_scope_text have actual DOM
locations `main#report`, `div.private-bar`, `section.next`; there are no claimed
node indexes or captured observations yet. A future extractor must resolve
unambiguous nodes from exact candidate HTML, including different zero/one issue
layouts, rather than using made-up source positions. Source time is distinct
from report creation time; /examined_pages/.../captured_at is the source role.

These gaps are separated from business truth standards. No request is made to
weaken 0–3 genuine issues, exact evidence, no fabricated credentials/rank/revenue,
HUMAN_REVIEW_REQUIRED, approval isolation or no-external-request requirements.
Some frozen extraction assumptions cannot be satisfied honestly by this actual
representation. **Owner adjudication is required before a fully bound adapter;
all original test/input bytes remain unchanged.** No corrective production
request is sent to Codex-2 on this static basis.

## Reproducible scope and next steps

`audit_static.py --out static-py311.json` (or a new nonexisting output name) reads
the pinned five Git objects with AST and hashes them. It checks all 1,400 accepted
main blobs and all 11 original freeze-added blobs against current QA HEAD,
records real signatures/versions and the independent/candidate proposal mismatch.
It compiles only the new QA helpers, never executes candidate source.
Separate 3.11/3.13 static outputs are audit runs, **not dual-Python Phase B results**.

On Owner's contract decision and the formally released exact final functional
SHA, re-read actual API hashes, audit the adapter/request metadata and run detached
no-push Phase B with unchanged 64 cases/14 inputs. Genuine defects require actual
minimal reproduction on PR #47; self-contradictory oracles go to Owner. Actual
375px/1280px local screenshots, citation clicks, zero external requests and
substantive business reading remain mandatory and currently unverified.

PR #48 remains Draft. No candidate branch/source edits, merge, RA3D, live source/
model calls, customer sharing, spend, deployment or Gold acceptance.

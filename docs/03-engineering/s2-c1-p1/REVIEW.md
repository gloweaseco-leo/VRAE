# C1-P1 batch 1: static paths and response candidates

Authority: [Issue118 Owner CODE GO](https://github.com/gloweaseco-leo/VRAE/issues/118#issuecomment-6964181971).
Base: accepted main `a5b8c30ccefb656c266d75e66f9f20ceb7df1080`.
Isolated branch `codex1/s2-c1-p1`. This is an independently reviewable first
batch, not completion of all six C1 rules or S2 EXIT.

## Version and admission

Call `evaluate_s2(pack, expected_pack_ref=held_pack_ref, trusted_scope=server_scope,
projection_version=STATIC_PROJECTION_VERSION)`. Verify with the independently held
`expected_projection_ref` and `expected_projection_version=STATIC_PROJECTION_VERSION`.
The default remains P0 `s2-projection-1.0.0`; P1 is `s2-projection-1.1.0`.
Input scope validation, original execution replay and accepted browser v1 binding
remain in the sole S2 composition entry point. No C2 Draft source is consumed.

`static_projection.rows` contain validated Observation **candidates** plus original
source locators and byte citations. They are not admitted facts. The containing
envelope stays `s2p-`, never `rx-`. Original FindingPackage and Guard are unchanged
and reject this envelope. No fact-promotion bridge is implemented in this batch.

Rule version: `s2-static-1.0.0`; source extraction version:
`s2-static-http-1.0.0`. All 16 catalog IDs and the six legacy enabled flags remain
unchanged. Only three S2 capability entries gain `BOUNDED_READ_ONLY_CANDIDATE`.
Legacy `readiness.GAPS` remains unchanged.

## Supported conclusions

| Rule | Enabled subset and PASS meaning | UNKNOWN / blocked / counterexamples |
| --- | --- | --- |
| DISC-03 | Captured lexical APPLICATION path has an explicit text anchor to a same-site lexical PRODUCT path, whose retained captured final product response is HTTP 200. Both original bodies are cited. | No application page, no supported anchor, unsupported HTML, redirect outside product role, unretained/unvisited/error target all UNKNOWN. Captured blocked source/target yields ACCESS_BLOCKED. URL roles do not establish industry relevance. |
| SEO-02 | Captured lexical PRODUCT HTTP 200 source has body text outside an anchor and an explicit text anchor with a same-site HTTP(S) href. | JS/template/noscript text, missing text, fragment/query/dynamic/cross-site href, base URL, duplicate attributes or ambiguous structure do not establish PASS. No rendered, visibility, indexing, ranking or crawler health conclusion. |
| TECH-01 | Exact HTTP 200 metadata is bound to a real retained OBSERVED HTTP_BODY and original byte citation. Redirect trace is copied exactly from the verified CaptureManifest. | Metadata-only 404/410/500 remains UNKNOWN with exact source pointer; ACCESS_BLOCKED remains ACCESS_BLOCKED. No fabricated ev-ref, defect Observation or current availability assertion. |

No FAIL_WITH_EVIDENCE is emitted by this conservative version: metadata-only
negative responses cannot support an admitted negative Observation. No
NOT_APPLICABLE is emitted: industry applicability requires a separately held,
versioned configuration, which this batch does not invent.

Every citation uses a genuine `ev-` resolved from the verified pack and includes
source/snapshot refs, source locator, body SHA256, UTF-8 byte start/end and exact
original quote. Response metadata carries a source pointer, never an ev-ref.
Sources are bounded to 131072 retained bytes, strict UTF-8, explicit body structure,
512 elements, 64 nesting levels and 128 anchors/text segments. CSS visibility and
language semantics remain unassessed. No network/model calls occur in projection.

## Buyer view

For the synthetic water-application archive, the output answers: “The saved
application page contains a P40 link, and the saved P40 product response was 200.
The product source contains descriptive text and a static product link.” A 403
instead says “Access blocked”; a recorded 404 with no retained body says
“Response metadata reports 404; evidence is insufficient for a defect finding.”
These statements help inspect the saved purchase path without claiming supplier
qualification, engineering fit or SEO performance.

`example.json` records actual output from this archive. Validation receipts and
raw initial RED JUnit/logs are preserved in `runtime/`; see `receipt.json` for
hashes and final native/CI results.

## Remaining independent C1 work packages

INFO-02 model/technical-material coverage, TRUST-02 source-declared proof context,
TRUST-03 independently cited identity/contact conflicts, and incremental
IndustryPack version/applicability/model/unit/condition handling remain pending.
Existing six industrial rules are not counted as these generic implementations.
No claim of 10/10, 16/16, engineering fit, certificate authenticity, real human
Gold or precision is made. Real human Gold remains 0/26.

## First natural CI RED and test portability repair

The first head `4c72b03554d34cb69060e1d31c4031cbb8903489` exposed two new-test
packaging dependencies: importing P0 test helpers pulled `integration` into the
unchanged minimal HTTP image, and the P0 oracle used Git history unavailable in
shallow checkouts. Both full native CI jobs reported exactly one failed historical
oracle test; the image failed at collection. Raw logs are retained in `runtime/ci-first-*`.

The repair only makes the new P1 tests self-contained. The oracle is exact
accepted `a5b8c30:vrae/rules/s2/contract.py` bytes, pinned by original Git blob
`3df95cb5cefb1840ad3b145d1eade2d8cb4fd067`; it is checked before execution.
Original frozen source checks also compute the Git blob hash without requiring
Git inside the isolated image. No original assertions, image, permissions or
production rule source changed. Both local full runs at `4c72b03` remain recorded;
the repaired native tests and final-head natural full CI provide follow-up checks.

## Boundaries

Frozen original execution blob: `c183970fd90ec69729221a4174c38d193f4b054b`.
Frozen EvidencePack blob: `8d45d5882103323e62bc4bd61a4379899e759966`.
No permissions, SSRF/collector/Worker, old Guard, SQL/RLS, lease, original outline,
C2 UX modules or C3 Gold tooling are changed. Draft only; Owner review and merge
are required. No deployment, third-party real site, paid model or production
outbound action is performed.

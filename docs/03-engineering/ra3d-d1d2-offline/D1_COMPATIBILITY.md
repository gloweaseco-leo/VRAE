# D1 compatibility gate, accepted main e40201b

Authorization: [Owner Issue #57](https://github.com/gloweaseco-leo/VRAE/issues/57).
Only the three authorized new path trees are used. The original worktree was
clean at creation from e40201bf399cc8c5d11a708fcbe33c31f01e67b2.

Before D2 existed, `compatibility.py` actually replayed accepted source fixtures
and independently held caller pins through EvidencePack.load, FindingPackage.load,
every GuardResult.load, build_draft, ReportDraft.load, and render. The 404 quote
was compared to its original byte range. No approval/share helper was invoked.
`D1-python311.json` records exact Git blobs, API inputs, outputs and H0. The
Python 3.13 run independently repeats the gate; results are runtime-labelled.

| Binding / actual source | D1 outcome | Scope and missing authority |
| --- | --- | --- |
| ReportDraft document/ref/HTML, reporting/draft.py | PASS | Direct construction is unverified; public load must replay |
| H0, domain/reviews.report_content_hash | PASS for 404; null for 200 | Original algorithm retained, not an HTML or semantic hash |
| 404 draft | PASS, one issue, native REVIEW_REQUIRED | Synthetic source, captured HTTP failure only |
| 200 draft | PASS, no issues, native=null | Internal coverage candidate only, never native APPROVE |
| Claim facts/types/pointers/Guard refs | PASS | Exact native Guard replay; HUMAN_REVIEW_REQUIRED stays unchanged |
| Pack/objects, rule execution/package, scope | PASS | Independently held accepted fixture pins; not an uploaded self-certification |
| HTML/editorial/asset/renderer hashes | PASS | renderer ra3c-html-1.0.2, not old Phase0 provisional 1.0.1 |
| Native ReportVersion/ReviewDecision/ShareGrant schema | COMPATIBLE, read only | additionalProperties=false; no schema edits or native decisions/grants |
| Request-changes status | COMPATIBLE sidecar only | Native enum unchanged; simulated round closes |
| Real policy snapshot / current revocation | BLOCKED | Capture retains policy id/version, not an authoritative current policy repository |
| Model gateway/prompt provenance | NOT_RUN / NOT_RECORDED | Native inputs explicitly synthetic/null; do not manufacture gateway provenance |
| Verified human/session/assignment | BLOCKED | Always-denying production port, no actor dict accepted as identity |
| Immutable object store and trusted clock | BLOCKED | Only explicitly TEST_ONLY immutable-bytes references and injected synthetic UTC |
| Durable transaction/CAS/audit/outbox | NOT_RUN | In-memory reference has no production concurrency, durability or recovery guarantee |
| Share/customer/UI/API/deployment | NOT_RUN / NO_GO | No such implementation in D1/D2 |

No severe canonicalization, Guard or source incompatibility was found. D2 may
proceed for explicitly synthetic preparation/simulation only. The missing trust
services remain explicit production refusals. Phase0 DD01–DD14 and A01–A48 are
preserved unchanged; this document does not turn future production cases PASS.

The copied `tests/reviewing/fixtures/{404,200}.json` contain the original accepted
source records and held pins, plus an independently replayed payload SHA. They
are included in existing `COPY tests` without Docker/CI/ignore changes. Tests
must not depend on this new documentation directory being present in the image.

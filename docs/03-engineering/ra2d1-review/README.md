# Private offline human review — all 26 units are still unsigned

Start with [reviewer.md](reviewer.md) / [reviewer.csv](reviewer.csv).
Full immutable source/target evidence bindings: [packet.json](packet.json).
Editable JSON template: [review-input.json](review-input.json).
Every real human verdict, rationale, identity, time, conflict decision and Owner
approval reference is **blank**. Nothing here is an actual approval or public report.

## Human workflow

1. Inspect the original fixture body and bound href/target HTTP status/error/trace
   in `tests/benchmark/samples/<site_id>.json`. Use packet unit_ref/observation_id/
   evidence locators to find the exact record. Inspect evidence **before** considering
   the candidate expectation. An unknown unit does not prove a missing feature.
2. Copy reviewer.csv or review-input.json to a separate offline review file. Never
   edit the seven sealed samples, old report or immutable CSV evidence columns.
   JSON/CSV must retain exactly 26 unique unit identities and evidence-binding hashes.
   This permits partially completed files; unresolved units remain pending.
3. An actual independent human fills `status` (UNREVIEWED / REVIEWED / REJECTED /
   CONFLICTED), `human_verdict` (PASS / FAIL_WITH_EVIDENCE / UNKNOWN / ACCESS_BLOCKED),
   `rationale`, `reviewer_identity`, timezone-aware `reviewed_at`, `conflict_decision`
   (NO_CONFLICT / RESOLVED / UNRESOLVED), and an actual `owner_approval_reference`
   when available. Missing/invalid verdict or missing metadata stays pending.
   A REVIEWED row with unresolved conflicts is ineligible. Human verdicts **may
   disagree** with the diagnostic observation; valid disagreement is scored, not
   rejected for failing to echo a candidate. Rationale is attributed reviewer text,
   never an automatically generated objective website claim.
4. For actual human input, set JSON origin=EXTERNAL_HUMAN, or use CSV CLI flag
   `--csv-origin EXTERNAL_HUMAN`. This is only an origin claim, **not authority**.
   Run `python scripts/verify_ra2d1.py --reviews <offline-file.json-or.csv>`.
   Without independently verified Owner authority the result remains pending.
5. Owner independently checks reviewer identity, actual evidence inspection,
   scope and conflict resolution outside Codex. Only Owner can provide an external
   signed attestation and establish the signing key's trust. There is no signing,
   key generation, approval button or Gold promotion operation in this tool.

Default replay is **read-only**: `python scripts/verify_ra2d1.py`.
The minimal isolated-HTTP image omits docs/: the tool reconstructs the complete
old report from sealed inputs and checks the same fixed canonical report SHA.
When the archived report file exists it is additionally compared; no pin is relaxed.
Explicit `--export` only writes identical blank artifacts; if a review file has
changed it refuses to overwrite it. All reviewer input is separate from candidates.

## External verification contract (no attestation is supplied here)

Owner's separately supplied UTF-8 JSON attestation has exactly these fields:

| Field | Owner-supplied meaning |
| --- | --- |
| schema_version | 1.0 |
| purpose | VRAE_INDEPENDENT_HUMAN_REVIEW_ATTESTATION |
| review_set_sha256 | canonical SHA256 of the exact imported review document; CLI outputs it |
| packet_ref | exact packet ref below |
| owner_identity | Owner identity matching the externally trusted OpenSSH allowed_signers entry |
| independent_human_review_confirmed | true **only if Owner actually verified independent human review** |
| owner_verified_at | actual timezone-aware Owner verification time |
| approved_rows | unique `{unit_ref, review_row_sha256}` records for the exact externally verified rows |

Canonical SHA256 uses existing `document_hash`: sorted keys, compact separators,
UTF-8, ensure_ascii=false, no NaN. Row hashes bind the actual imported row, including
verdict/identity/time/conflict/Owner reference. Editing any review field changes
the review-set hash and requires a new external attestation; old approvals cannot
silently authorize a revised file. No attestation/signature/key is generated or
committed by Codex. The supplied detached SSH signature must cover the **exact raw
attestation file bytes**, namespace `vrae-human-gold`.

Verifier options, all supplied together by Owner:
`--owner-approval FILE --owner-signature FILE --trusted-owner-signers FILE
--trusted-owner-sha256 SHA256 --owner-identity ID`.
The allowed_signers public-key file must be external to this checkout and its raw
file SHA256 must match privileged, out-of-band Owner configuration. It is never
taken from the review input. A path, hash, identity or signature string alone does
**not** establish who owns a key; Owner must independently establish that trust.
Verification uses installed OpenSSH `ssh-keygen -Y verify`, fails closed on missing
tool/key/valid signature, and checks exact approved-row hashes. Owner's verified
signature attests the independent-human prerequisite; code cannot itself prove
that a person inspected evidence. No real authorized attestation exists yet, so
actual positive human authorization has **not** been exercised in this package.

## Scoring boundaries

Three separate concepts are reported: candidate/test agreement, provisional
**Owner-verified human synthetic** scoring, real-world performance (NOT_ESTABLISHED).
Only complete REVIEWED rows explicitly authorized by the verified external
attestation are eligible. Names/Owner reference strings, templates and tests never
authorize a row. REJECTED/CONFLICTED/incomplete/unverified rows remain pending.

Positive means a bounded per-href defect. TP/FP/FN/TN requires explicit binary
verdicts on **both** sides; UNKNOWN/BLOCKED never become TN or default FN. Coverage,
abstentions, unresolved expected defects, unsupported facts/passes and disagreements
are separate. Fewer than 5 binary units or fewer than 3 site-condition types means
sparse support: metric counts/rates stay N/A. Precision/recall with empty individual
denominators stay N/A. Partial review keeps the overall gate NOT_EVALUABLE, with
provisional false-fact warnings separate. Once all 26 rows are externally verified,
any false-fact flag fails the gate; even complete
supported review leaves QUALITY_GATE_OWNER_DECISION_REQUIRED, never automatic
QUALITY_PASS, RA-2D FINAL PASS, production readiness or RA-3 authorization.

`SIMULATED_NOT_HUMAN_GOLD.json` is clearly labeled **fake test disagreement input**:
two rows deliberately create demo FP/FN. Its placeholder identity/time/reference
are not people, reviews or approvals; simulation diagnostics never enter actual
Gold metrics, even if signature verification were simulated as successful.
Reserved `SIMULATED_*` reviewer identities or Owner-reference values are never
eligible, even after an adversarial origin relabel or simulated positive verifier.
`negative-forged-gold.json` is an intentionally invalid, likewise simulated stamp
and must be rejected. Actual reviewer templates remain untouched and blank.

Current state: HUMAN_REVIEW_READY / GOLD_LABEL_PENDING / QUALITY_GATE_NOT_EVALUABLE.
Packet ref: `review-packet-f47c45fbe0a9362f7181bf708d644b9f1b4af420e8fadd237e5772e78d139f16`.
Seven original sample pins and the old benchmark report are unchanged. No rules,
production code, INFO-01, safety architecture, review UI, DB or RA-3 work is added.

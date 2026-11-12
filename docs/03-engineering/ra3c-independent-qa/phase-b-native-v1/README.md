# First executed Phase B — NOT READY / CUSTOMER_SHARE_NO_GO

Authority: [Owner M01–M08 adjudication](https://github.com/gloweaseco-leo/VRAE/pull/48#issuecomment-6815157266).
Exact functional SHA: `6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2`.
Original QA freeze: `fa645b58549dfd21a6b80656d403f672b790acd8`;
test blob `92ab4b2ef743abc0388866a2054952e56ba14a41`.
Native adapter/request source: `a848036953fdf539eed2bec032d05ba7f972c990`.
Separately pinned positive/negative controls: `360973d119e65e76306279b9b704a26c9197916a`.

## Original 64, actually executed without changes

| Actual raw pytest outcome | Python 3.11.15 | Python 3.13.13 |
| --- | ---: | ---: |
| Passed | 11 | 11 |
| Failed | **53** | **53** |
| Fixture/adapter errors | 0 | 0 |
| Skip / xfail | 0 / 0 | 0 / 0 |
| Total | 64 | 64 |

All 64 original nodes were selected and ran through the real native adapter;
these are not the earlier setup-only attempts. Both raw exits are 1. Full JUnit,
stdout and exact file SHA are under py311/py313, with every node retained.

The 11 passed nodes are rejection paths (T11/C08 plus designated hostile-input
refusals), **not eleven report-generation or visual passes**. The original source
facts, four independent proposal/missing-information strings, bindings and held
refs are forwarded unchanged. The actual producer refuses 52 normal requests
with REPORT_UNSUPPORTED_PROSE (M02) and the no-raw NOT_RUN bundle with
REPORT_GUARD_NOT_VALIDATED (M07). Thus **53 raw failures need Owner input-boundary
adjudication**. They are not relabeled PASS or presumed to be 53 production bugs.
There are zero reached representation-error nodes in this run: the M02/M07
boundary stops them before the known M03–M06 extraction restrictions are reached.
Those latent restrictions remain documented, not counted twice or silently fixed.

The detached candidate worktree contains all **1,506 unchanged candidate blobs**
and only three added frozen QA files. Results record before/after proofs and
actual source hashes. No push or production edit occurs there. All 1,400 accepted
main blobs and all 11 original QA freeze-added blobs remain unchanged on the QA
branch, including the original 14 synthetic scenarios and Phase A RED history.

## Executed M01–M08 findings

| Gap | Actual evidence and remaining decision |
| --- | --- |
| M01 metadata | New Owner-authorized request-pins.json holds 28 deterministic offline caller requests, revisions1/2, explicit operator, mode and external metadata/version hashes. No fake reviewer/approval. Mutated boolean revision is actually rejected as REPORT_METADATA. Adapter never recalculates held pins from submitted mutation. |
| M02 vocabulary | Original broken404/healthy200 requests actually reject REPORT_UNSUPPORTED_PROSE. Separately pinned whitelist-vocabulary requests on the same independently captured sources actually build/load/render one/zero issues on both runtimes. These separate controls do not replace original inputs or count as original-case PASS. Owner must adjudicate the original suite's reportable-HUMAN_REVIEW_REQUIRED precondition before any versioned oracle change. |
| M03 language | Separate real HTML lang byte mutation is rejected by actual public loader. No invented JSON language field. Original D07's JSON-only mutation helper remains incompatible; no rewrite or PASS claim. |
| M04 evidence | Actual nested citation evidence_ref is changed and only the outer draft_ref resealed. Loader rejects with both original caller ref and attacker-resealed ref. Source/guard pins stay original. Native mutation input is retained under diagnostic-*/outer-resealed-nested-evidence-attack.json. Original D04 still has its flat-object helper gap. |
| M05 collections | Diagnostics read actual fact_claim/positive_source_claims text and binding refs verbatim, with native JSON pointers; no fields added to report. Frozen field() cannot consume this list projection. Owner's versioned adapter/protocol decision still needed if that helper is reached. |
| M06 score | Diagnostic negative membership over actual native keys finds no site-score/ROI/rank/sales-loss fields. No unrelated null substituted. Original extractor has no audited absence origin. |
| M07 no raw | Original NOT_RUN bundle rejects. Explicit separately held empty guard list + empty trusted refs produces a truthful zero-issue coverage summary, native_report_version=null. Adapter does not silently drop the original bundle. Original T07 combines a noneligible submitted guard with a required-output oracle; request Owner's versioned precondition adjudication. |
| M08 duplicate | Original duplicate request first hits M02. Controlled supported-vocabulary request with one actual fact rejects REPORT_MISSING_OR_AMBIGUOUS_FACT; a separately pinned per-finding two-guard request selects one issue and validates its exact source. No missing second citation was fabricated. This is an executed caller-completeness/representative-selection product boundary for Owner, not evidence of a security bypass. |

Minimal original-node reproduction is available directly from the preserved
JUnit and full-suite command in py313/results.json; B02 is a report-required
impact-classification node blocked by M02, T07 is the no-raw/M07 node. The same
production succeeds on the separately pinned valid request. Any QA V2 adjustment
requires Owner approval, separate versioning and retained V1; none has been made.
The unimplemented representation proposal and executed one-node questions are
in PROTOCOL_AMENDMENT_PROPOSAL.md.

## Additional native security diagnostics

diagnostic-py311/py313 each record ten actual bounded native rejections:
false certificate with genuine source ID, instruction, cross-tenant scope,
malformed metadata, forged guard status with resealed guard container,
HTML-language byte change, nested-evidence change with old/new outer ref,
forged APPROVED/private/share flags, and forged review/share authority fields.
No actual approval/share API or RA3D implementation was used. All are separate
diagnostic requests; they do not inflate the frozen 64-case pass count.

The first auxiliary run_controls.py stopped after the false-certificate rejection:
it incorrectly expected REPORT_UNSUPPORTED_PROSE, but RA3B had already classified
that objective fabrication REJECTED and production returned REPORT_CLAIM_REJECTED.
The original script and partial results remain unchanged and **are not marked
completed/successful**. A diagnostic continuation records actual outcomes rather
than changing that expected code or the frozen tests. Its safety outcome is a
denial; the auxiliary exact-code discrepancy is disclosed for Owner review.
That auxiliary console trace was emitted in the tool session, not separately
captured as a raw file; no fabricated complete stderr file is supplied.

## Actual independent browser and business reading

ui-supplement contains **new outputs from real public build/load/render** on
our original broken404/healthy200 source routes with separately pinned supported
proposal control requests. Source quotes were independently resolved against
the held EvidencePack and exact byte span before capture. Both Python versions
produce identical supported404/200 native refs and HTML hashes. This does not
make the original four proposal strings reportable or turn F01–F08 into PASS.

Codex-1 independently launched Chromium156 over private CDP pipe, using a fresh
profile, retained browser sandbox and only exact local files. No Codex-2 screenshot
was reused. Four actual viewports (375 mobile/touch, 1280 desktop), **10 physical
mouse evidence clicks**, zero observed external target-page requests, zero runtime
exceptions. Four main screenshots and four evidence expansions, HTML SHA, browser/
driver version/hash, viewport/scroll metrics and actual requests/clicks are retained.
Network evidence is target-page interception plus disabled DNS/blocked external
schemes, not a claim of an independent kernel egress certification.
Chromium stderr reports a Windows executable sandbox-access warning and a
network-service restart; it is retained verbatim. Capture completed, but no
claim of clean browser-process diagnostics or sandbox certification is made.
No --no-sandbox switch was used.

| Actual native-control UI | Client / scroll width | Body | Privacy | Evidence clicks |
| --- | --- | --- | --- | --- |
| 404 375 mobile | 375 /375 | 14px | **11px** | 4 |
| 404 1280 desktop | 1265 /1265 | 14px | 12px | 4 |
| 200 375 mobile | 375 /375 | 14px | **11px** | 1 |
| 200 1280 desktop | 1265 /1265 | 14px | 12px | 1 |

All private labels are above fold; one main heading, no horizontal overflow.
However mobile private/not-approved text is 11px, below the unchanged F04 12px
independent readability heuristic. It is a **measured UI acceptance gap**, not a
WCAG verdict. Initial reproduction was submitted to [PR47 comment6815316159](https://github.com/gloweaseco-leo/VRAE/pull/47#issuecomment-6815316159);
the same result is now independently reproduced on actual public-call output.
Codex-2 owns any fix and new final SHA. No silent threshold reduction is allowed.

Actual reading: the 404 preview offers one bounded contact-path observation,
source URL/time, an explicitly provisional “可能需要额外绕行…仍需人工核实”,
a “候选·待批准” repair proposal and authorized recheck. It gives a credible
next discussion about this path without promising conversion or delivery.
The zero case visibly says “0 项可报告问题”, shows scoped 200 pages and the
unverified product-source quote “Gearbox NX-40”; it does not pad three defects,
vouch for factory certification or infer successful inquiry delivery. Desktop
hierarchy is clear. Phone wrapping works, but five stacked task cards delay the
specific finding and the privacy typography misses the frozen gate. These are
QA observations, not a customer response, report approval or proven sales impact.

The earlier independent render of the developer's own demo is separately archived
under phase-b-initial-6a7a3d3a (4 views/18 clicks). It is **not added** to the new
4-view/10-click count and is not substituted for our own native-control output.

## Exit and limitations

First-round conclusion: **INDEPENDENT_64_CASE_QA_NOT_READY_PARTIAL /
CUSTOMER_SHARE_NO_GO**. Raw tests are RED. Original frozen-input visual nodes
remain not accepted; actual browser observations have been made and include a
font-gate gap. M02/M07 oracle preconditions and latent M03–M06 representations
need versioned Owner adjudication, M08 needs the product/input-boundary decision.
Do not force arbitrary model prose into the report to achieve GREEN.
Current independent captures exercise zero/one distinct genuine issue; they do
not establish a three-distinct-real-issue positive case or unrestricted model
semantics. Rejection-only passes must not conceal those coverage limits.

PR #48 remains Draft. Stop after submitting this round for Owner's decision.
No self-merge, deployment, real site/model/provider/spend/customer report/share,
RA3D or Gold claim. Human Gold remains 0/26 / QUALITY_GATE_NOT_EVALUABLE.

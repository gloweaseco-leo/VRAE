# Qwen4 buyer candidate acceptance — 2026-11-19

**REAL_QWEN4_BUYER_CANDIDATE_PASS** on code
`302ed8f216fc1163f2469a452c9898676b75d3c8`, accepted main base
`98ec330579be3eb1e0be7862da9bfea4e7b5ce2c`.
Authorization: issue156 comment7002712356, separately added **at most 2
dispatches / CNY3**. This batch made **1** actual supplier dispatch, no retries,
and stopped. No second request is needed or automatically scheduled.

## Observed result

- Original controlled noncustomer source → original 30-second Worker COMMIT →
  expired lease → original current-PG authority → S3 Session → native Qwen4 →
  original Guard → original PG `ai_record`, followed by independent PG readback.
- Real HTTP200, exact model `qwen4-max`, `finish_reason=stop`, complete valid JSON.
- Provider-reported input/output/total usage: **1208 / 333 / 1541** tokens.
- One UNDERSTAND buyer hypothesis; explanation, one uncertainty, seller question
  and rebuild action. All four original Guard claims are HUMAN_REVIEW_REQUIRED.
- Current source/task/report/display pins verified after dispatch. The durable
  PG receipt equals the returned receipt; original deterministic report is intact.
- Estimated CNY **0.022070**, using official Beijing input10/output30 per million
  tokens, checked at https://help.aliyun.com/zh/model-studio/qwen4-max.
  Actual invoice, account balance and discounts remain **UNKNOWN**.
- Original five quota rows (old three UNKNOWN plus prior two recorded usage) and
  original policy are unchanged. A new explicit authorization batch holds the
  new sixth row, USAGE_RECORDED. No quota reset, replacement or legacy refund.

The actual candidate asks which variant and fixed/configurable specifications
the listing covers. Its uncertainty explicitly says withheld source text and
an UNKNOWN review card cannot establish descriptive completeness. This is a
model hypothesis requiring human review, not a new verified website defect.
Guard verifies binding/safety, not business truth. Independent Gold remains 0;
no human approval, customer report publication or UI change occurred.

## Two distinct fixes and their evidence

Prompt1.1 removes interchangeable duplicate anchors and repeated instruction/
gap wrappers, while keeping typed confirmed facts, UNKNOWN rule coverage, all
configuration conflicts and counterfacts. Wire/local compact validation allows
at most two claims, 220 characters per prose field and one item per list. The
original full local schema still validates first. The original **2048** output
token ceiling is unchanged. This real request used 1208 input tokens versus
3490 in the previous experiment; the contexts are different captures, so this
is an observed experiment comparison, not a deterministic compression ratio.

PG checks use the original readers over ordinary password-authenticated TCP
short transactions in a separate trusted POSIX caller. An owned internal TCP
forwarder relays only PG wire bytes to the original DB. There are no Docker-exec
snapshot/record RPCs in the authority or receipt path. Original AI-role/RLS/table
privilege checks run unchanged; an independent read-only admin transaction audits
the disposable test receipt. The source Worker retains its internal network,
kernel firewall and original 30-second lease. Provider egress runs in the separate
caller, with the unmodified allowlisted NativeTransport. DPAPI-decrypted credentials
travel only via anonymous stdin, never args/env, repo files or provider input.

`execute` never calls a failed PG receipt a successful candidate: it clears claims,
returns AI_UNAVAILABLE, preserves known provider usage, and records receipt UNKNOWN.
No automatic redispatch/refund occurs after an uncertain commit.

Before this real dispatch, actual controlled PG/fake Provider exercised success,
invalid schema, truncated output, forged REF and real post-dispatch withdrawal.
It verified no PG transaction spans provider I/O, original pins unchanged,
durable receipt readbacks, and usage retained when revoked authority forbids a
candidate receipt. See `pg-fake-result.json`. Separate `direct-pg-preflight.json`
proves NO_MODEL preparation and original PG receipt write over this caller's
direct route, with zero provider calls.

## Files and boundaries

`buyer-request.json` is the exact minimized request body (no raw HTML, customer
identity, URL, workspace or key). `buyer-response-safe.json` preserves the real
model/usage/choices and exact generated JSON string, replacing only request ID
with SHA256. The private raw-response hash is in `provenance.json` and the summary.
`buyer-receipt.json` contains original Guard proof and source bindings;
`pg-live-readback.json` is the independent durable PG readback. `manifest.json`
pins the exported files. No SQLite, DPAPI ciphertext or raw response is uploaded.

This is one controlled synthetic acceptance, not customer-data/model readiness,
Gold acceptance, an invoice, a public launch or automatic report approval.

## First REDs retained

- Initial pytest temp setup: Windows sandbox denied its global pytest directory;
  JUnit retained privately. Explicit workspace temp directories resolve it.
- Initial schema test expected the old broad wire schema. The test now verifies
  a stricter compact subset while the original local capacity/uniqueness remains.
  The intermediate run (170 pass / 1 stale expectation failure) remains retained.
- Mypy initially required an explicit dict annotation for the copied compact
  schema; corrected, then 143 modules passed.
- First owned PG run hit the parent harness's 120-second wait while serially
  draining multiple distinct 30-second Worker jobs. Private Worker log and cleanup
  evidence remain in `infra/authorized_targets/.private/c1-qwen4-buyer-batch3-run2`.
  Only the multi-job test wait changed to 300 seconds; no Worker lease changed.
  A fresh controlled run passed the PG positive/negative gate before any model call.
- The C1-only standalone wrapper then hit a final artifact-collection assertion:
  the generic runner expected `api.json` from the deliberately bypassed unrelated
  full API exercise. This happened after the real candidate, independent PG
  readback and all acceptance pins passed. Cleanup absence receipts passed. The
  hook now emits an explicitly labeled C1-only artifact, never a full API PASS.
- First remote Qwen protocol run [44490615700](https://github.com/gloweaseco-leo/VRAE/actions/runs/44490615700),
  exact SHA302ed8f, attempt1: both versions 419 pass / 3 failed. The new unit tests
  imported the PG port in a deliberately psycopg-free protocol environment.
  The tests now substitute only that port; actual original PG coverage remains
  in the separately passing real-PG workflow44490615555. No runtime dependency or
  production authority was weakened; no model call repeated.

No prior evidence or CI failure was deleted or rerun to erase a RED.

Local complete regressions on Python3.11 and Python3.13 each passed **422** tests,
0 failures/errors/skips. Ruff passed and mypy passed143 modules. Exact-head CI
and its raw artifacts are checked separately from these local results.

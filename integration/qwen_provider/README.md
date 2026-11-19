# Trusted post-COMMIT Qwen Provider

## Current buyer-output repair (#156 comment 7002712356)

The legacy preflight/NO-GO narrative below is historical. PR168 already recorded
two real Qwen4 HTTP200 responses, including real usage; the second was truncated
and did **not** pass buyer-candidate acceptance. See the immutable batch2 evidence
under `docs/03-engineering/qwen-live-smoke/20261119-batch2`.

The new single-dispatch buyer acceptance passed with real 1208/333 tokens,
original Guard/current-PG pins and durable PG readback. See
`docs/03-engineering/qwen-live-smoke/20261119-buyer`; CNY0.022070 is an estimate,
not an invoice, and all candidate text still requires human review.

Prompt 1.1 keeps the original 2048 output-token bound, selects one representative
Guard anchor per task (plus every conflict and counterfact), and asks for one
valuable hypothesis, at most two. Wire and local compact validation cap prose at
220 characters and each uncertainty/question/rebuild list at one item. The full
original local schema remains a prerequisite. No truncated JSON is repaired or
accepted, and usage persists before content/Guard validation.

`committed.execute(binding, job, adapter, operation_id=...)` wraps the original
post-COMMIT PG API. Its `pg_receipt_status=RECORDED` requires the original final
current-authority check and receipt transaction to succeed. Failure returns
AI_UNAVAILABLE with no candidates, preserves any known usage, and marks the PG
receipt UNKNOWN (an interrupted commit cannot be called definitively absent).
It never retries, publishes a report, or refunds a reservation.

`buyer_drill` and `buyer_live` are explicit operator-only controlled acceptance
harnesses, not public APIs. A separate POSIX caller uses password-authenticated
TCP to the owned PG; original readers run short transactions without Docker
control RPCs. The source Worker retains its original internal network, firewall
and 30-second lease. Only the multi-job parent test wait is longer. Native egress
runs separately from that Worker. No key belongs in arguments, env, files or CI.

The comment explicitly permits a **new** batch of at most two synthetic Beijing
Qwen4 dispatches with a CNY3 cap. This is not standing product authorization.
`buyer_live` is deliberately one-shot, appends to the retained original ledger,
verifies all five old rows unchanged, and stops after its result. No automatic
second call is implemented. A successful acceptance additionally requires
nontruncated schema/Guard candidates, current task/report pins, real provider
usage, and an independent durable PG receipt readback. Invoices remain UNKNOWN.

Refs #156 / PR161 Owner comment 6995853239. Original engineering base:
`7fdeeed0f427ce3b94677ab2a480eae1556e85ca`; smoke-fix base:
`0b2c171b680e39ad8a410d7bc6708a9f82221072`.
The sole current model is **qwen4-max**. Shipped tests and examples use
**PROTOCOL_FAKE_NOT_REAL_API**. Qwen4 real calls: **0**. Three historical Qwen3.7
failed attempts are retained unchanged under `docs/03-engineering/qwen-live-smoke/20261119`.
Supplier availability and candidate quality are unverified; Gold=0, no invoice evidence.
Initial review terminal: **REAL_PROVIDER_INTEGRATION_READY_LIVE_CALL_PENDING**.
It is never `REAL_QWEN_LIVE_CALL_PASS`.

The original `ModelGateway.run`, synthetic Ledger, NO_MODEL/FIXTURE, 30-second
Worker, Guard, SourcePolicy, RLS and report/sharing authority stay in place.
The existing Session adds an explicit trusted `REAL_QWEN` branch, replaying the
unchanged ModelGateway's original NO_MODEL input/minimization path before the
bounded native adapter. No HTTP parameter can supply a provider,
key, URL, model, permission or quota path. C3's HTTP/PG/Worker is not modified.

## Native protocol and privacy

Server-held `Config(workspace_id)` constructs exactly
`https://{workspace}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions`.
The only model is `qwen4-max`. The response must confirm that exact
model; no alias/model fallback is automatic. Native body uses top-level
`enable_thinking=false`, `max_completion_tokens=2048`, `stream=false` and strict
JSON Schema. No SDK, agent framework, search, tool calls, retries or redirects.

Protocol choices follow the official [Chat Completions API](https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions)
and [structured output](https://help.aliyun.com/zh/model-studio/qwen-structured-output)
documentation checked 2026-11-18. The documented output-token rounding tolerance
is reserved (2048+10); an actual permitted response must still verify compatibility.

Every dispatch replays the original `prepare_request`. Only its minimized
provider projection and a strict typed task/ref/status/conflict table are sent.
Source quotations, URLs, raw HTML, identities, contacts, private pins and local
provenance are withheld. No numeric source fact is invented to compensate.
This limits semantic specificity: the first provider can reason about observed
information organization and follow-up questions, not unseen engineering details.

At most eight autonomous prose claims contain explanation, uncertainty, seller
questions and Rebuild suggestions, each with known same-task refs and at least
one original Guard literal anchor. Known same-task configuration conflicts and
their counterfacts cannot be omitted. UNKNOWN/NOT_APPLICABLE are not defects.
Strict local schema/reference checks precede original Guard binding validation;
every hypothesis, question and recommendation must return HUMAN_REVIEW_REQUIRED.
Guard verifies binding and instruction safety, **not semantic correctness**.
No new native Finding or fact is admitted. The local review result contains
original source bindings for verification; these are not sent to the provider.
All outputs remain private, NOT_APPROVED, not reports, and not shareable.
Existing unreviewed-report 403 authority is not bypassed or newly implemented here.

## Spend and failure behavior

`Permission` is an internal record of a separately granted operator allowance,
not a signed permission token or substitute for service authentication. The
default has no allowance, pricing, key or live network grant. A trusted caller
must supply current Beijing approval, a bounded synthetic-only call count and
fee cap, a valid operator-verified price snapshot and server-held key. The
fictitious sample permission/prices/key are explicitly refused by NativeTransport.
There is no environment key autoload; key repr is suppressed, and it is never
written to quota, receipt, argv, environment or logs.

The native adapter in `infra/qwen_provider` is deployed with the repository
infrastructure, not a standalone pure-domain wheel. It runs in a separate short-lived stdlib-only subprocess via
anonymous pipes. It constructs its sole allowed host/path itself, rejects any
nonpublic/mixed/translated DNS set, pins a numeric peer, verifies TLS hostname
and certificate, ignores proxy environment and suppresses remote errors. Parent
timeout/cancellation kills and waits for it. This is an application allowlist
process, **not a claim of kernel egress isolation** or a change to R1B's isolated
NO_MODEL container. Deployment must keep the original trusted service boundary.

`Quota(path, create=True)` explicitly creates one exclusive operator-owned SQLite
quota store. Reopen with `Quota(path)`; never recreate/restore it to retry an
unknown dispatch. It is not a business job queue or Worker. Atomic reservations
bind approval/config/price/fake-vs-native policy, operation and scope. Maximum
16 calls per allowance and 100 CNY fee cap; stricter operator limits apply.
Reserve conservative input capacity 65536 plus output 2058 tokens before dispatch;
these are reservation ceilings, **never supplier usage measurements**. A valid
response records supplier prompt/completion/total tokens, hashed request ID,
exact model, time, prompt version, CNY estimate and pinned price. No byte count
becomes a measured token. Costs remain estimates, never invoices.

Timeout, cancellation, malformed/missing usage, 429/5xx, failed TLS/DNS or invalid
content return AI_UNAVAILABLE while the deterministic report remains unchanged.
Unknown dispatch retains its full reservation, has no automatic retry/refund,
and native real_model_calls is unknown rather than falsely zero. Valid usage is
persisted even if later JSON/Guard/content validation refuses candidates. Restart
or concurrent duplicate cannot dispatch the same operation twice. Results are
in-memory Session readbacks; durable quota stores safe usage, not candidate prose.
Session authority is checked before dispatch and after response; expired results
cannot be read. New sidecar states do not extend AuditRun enums.

## Offline reproduction

```
python -X utf8 -m pytest -q tests/intelligence/qwen_provider_cases.py tests/test_domain.py::test_no_network_or_unauthorized_framework_code tests/intelligence/s3_offline_cases.py tests/intelligence/test_gateway.py tests/intelligence/test_accounting.py tests/intelligence/test_request.py tests/interpretation/test_guard.py tests/interpretation/test_fixed_replay.py
python -B -m integration.qwen_provider.demo --output integration/qwen_provider/.runtime/demo-local
```

The demo requires a new output directory. Its single same-source context yields
NO_MODEL, protocol-fake candidate text and missing-key fallback. Network/DNS and
subprocess tripwires forbid API calls. Protocol fake example usage is deliberately
137 input / 83 output tokens, independent of UTF8 size, and fictitious price is
clearly labeled. `first-red.md` preserves initial local failures. CI runs both
Python 3.11 and 3.13 and uploads only synthetic JSON/Markdown/JUnit, never quota DBs
or secrets. New explicit cases remain outside the original default inventory.

## Pending separately authorized synthetic live smoke

No live call can be signed off until Owner specifies all of: Beijing/workspace
permission; key hookup through the trusted server secret channel (never issue/chat
body); fee cap and maximum number of requests; verified current price and expiry.
After that, the trusted caller initializes its retained quota, configures the
native provider, and calls only after original Worker COMMIT and lease end:

```python
# Internal server pseudocode; values come from the separately authorized operator.
p = QwenProvider(Config(workspace_id), retained_quota, permission=owner_allowance,
                 price=verified_price, key=server_secret)
result = await existing_session.run(operation_id, mode='REAL_QWEN', provider=p,
                                    timeout_ms=120000)
```

This increment intentionally accepts only the original OFFLINE_SYNTHETIC
CompletionPins/NativeSource context for the first pure synthetic live smoke.
Do not relax those pins for live sources. C3 keeps authenticated task ownership
and original report authorization; it can run its T0 NO_MODEL flow independently.
Actual model usage, exact returned version, text candidates, Guard review and
sanitized egress receipt remain required future live evidence. Real customer
sources, public capture, human approval, sharing, cloud deployment and production
access remain outside this task's current authorization.

The independent provider wait is capped at 120 seconds; this does not change the
original 30-second Worker lease. A timeout keeps usage/cost UNKNOWN and retains
the reservation. Supplier strict Schema omits its unsupported `uniqueItems`
keyword only on the wire; the original full local schema still rejects duplicates.
See `docs/03-engineering/qwen-live-smoke/20261119` for the first authorized attempt
receipts. None of those failed attempts establishes a successful live integration.

Per PR161 Owner comment 6995853239, no further live HTTP model dispatch is
currently authorized. Do not reset, clear or recreate the exhausted legacy
quota. Prior actual spend and account balance remain UNKNOWN; retain the old
CNY 0.442608 maximum unsettled reservation as occupied, not paid or available.
The new official Qwen4 public list price is CNY 10 input / 30 output per million
tokens, sourced from https://help.aliyun.com/zh/model-studio/qwen4-max. Price
objects are model-bound and require this exact source; they do not prove an
account-specific effective quote, account balance or invoice.

After separate user GO for at most two additional calls AND trusted price,
balance and cumulative CNY 6 checks, use `probe.minimal_probe_body()` for only
the first pure-synthetic call (64 output tokens, thinking disabled, strict JSON).
Verify exact reported qwen4-max model and supplier usage. If either is missing,
STOP without a second call. Only a genuine first success with clear fee/error
checks permits a second same-source Session diagnostic + original Guard review.
There is no loop, retry or live launcher in the probe-body builder. Protocol-fake
tests and DNS/TLS preflight are not live model evidence. See the separate
`qwen4-preflight` evidence directory for current no-fee checks and missing gates.

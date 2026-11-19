# Qwen4-only no-fee preflight — live dispatch remains NO-GO

Owner PR161 comment [6995853239](https://github.com/gloweaseco-leo/VRAE/pull/161#issuecomment-6995853239)
supersedes the legacy Qwen3.7 selection. The current single provider now pins
`qwen4-max` in both parent and isolated egress process. It accepts only the exact
documented reported model; there is no legacy fallback, prefix acceptance or
guess at an undocumented snapshot alias. Model-bound Price objects reject the
legacy model/source. The old three attempts and their files remain unchanged.

The old exact SHA `d0805df8891f6eef8bd405d16353a7082000ee27` finished
**21/21 natural workflows, 43/43 jobs SUCCESS, all attempt 1**. Its detailed
receipt is `closed-d080-ci.json`. This closes compatibility engineering only,
not real model quality, Qwen4 execution or G1 service acceptance. Old RED runs
remain retained; none was rerun to obtain this result.

The official [Qwen4 model page](https://help.aliyun.com/zh/model-studio/qwen4-max)
documents Beijing Chat Completions and JSON Schema support, default thinking
enabled, and public list prices CNY 10 input / 30 output per million tokens.
The request explicitly sets enable_thinking=false, stream=false and a bounded
max_completion_tokens. `price-snapshot.json` records the checked public quote;
it is not an effective account quote, account balance or invoice.

No-Key/no-HTTP diagnostics on the existing approved Beijing host passed TLS
verification using the original SystemRoot-only child environment. They sent
**zero HTTP requests and zero model dispatches**. Before/after hashes of the
original quota DB match; its three DISPATCHED_USAGE_UNKNOWN rows and occupied
CNY 0.442608 were not reset, cleared, refunded or replaced.

No authenticated Alibaba billing connector or aliyun CLI was available. Previous
actual spend, account balance and effective account price remain UNKNOWN. The
conservative Qwen4 token-cap reservation is CNY 0.717100 per call. The JSON also
shows the two-call arithmetic plus occupied legacy budget, but that calculation
**does not guarantee cumulative actual billing below CNY 6 or authorize calls**.

There is no new native launcher or automatic retry in this revision. The pure
`integration/qwen_provider/probe.py` builder prepares only the first minimal
synthetic request; FakeTransport tests exercise the native response/model/usage
mapping without sockets. The full local schema, duplicate/reference checks,
original Guard and unchanged 30-second Worker lease remain in place. Native
waiting and timeout termination stay independently bounded at 120 seconds.

Any future sending requires explicit additional user GO, a trusted effective
price, and account balance/previous-spend plus occupied-budget checks. Until
then, keep all dispatches stopped. If those gates are met, the only permitted
sequence is:

1. First call: `minimal-probe-request.json`, qwen4-max, 64 output tokens, strict
   JSON `{ "ok": true }`. Record genuine exact model, supplier usage, hashed
   request ID and estimate. Missing model/usage or another error means STOP;
   do not spend a second call to guess at parameters.
2. Only after a genuine first success and clear fee/error checks, a second call
   may use the same-source S3 diagnostic context. Preserve refs, counterevidence,
   UNKNOWN and original Guard/HUMAN_REVIEW_REQUIRED. No native facts, report
   approval, public sharing, customer capture or cloud deployment is authorized.

Local Python 3.11/3.13 each passed all 103 explicit provider cases with networking
tripwires. These include both model pins, legacy/undocumented return rejection,
model/source-bound pricing, a minimum protocol fake, per-request output limits,
pre-reservation parameter refusals, schema projection, cancellation and timeout
cleanup. They are **PROTOCOL_FAKE_NOT_REAL_API**, never a Qwen4 live-pass receipt.

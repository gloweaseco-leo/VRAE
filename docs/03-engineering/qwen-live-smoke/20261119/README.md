# First authorized synthetic live smoke: NOT PASSED

Owner chat authorized Beijing, at most three synthetic attempts and a total
CNY 6 ceiling. All three persistent dispatch reservations have been used.
Model calls are stopped. No successful completion, supplier usage, confirmed
returned model version, AI candidate or semantic quality evidence was obtained.
The native deterministic report stayed unchanged in each attempt. No live-pass
or production/G1 integration approval is claimed.

| Attempt | Code SHA | Observed result | Supplier usage |
| --- | --- | --- | --- |
| 1 | `62f9f0966a089074abdf2a68f91469efee28217b` | EGRESS_FAILED; no HTTP status | UNKNOWN |
| 2 | `6fa914d59861301498e314e673412a9f024aff9e` | HTTP 400 / PROVIDER_HTTP_ERROR | UNKNOWN |
| 3 | `59ef1e803e750422ce8a076970dda90d4a67f27b` | TIMEOUT after 30 seconds | UNKNOWN |

The private credential was never printed or transmitted to GitHub. The public
export was checked against the actual key, DPAPI ciphertext and workspace ID;
only a workspace hash and endpoint shape are published. Public files contain
synthetic inputs, fixed error codes and hashes, not credential files, SQLite or
untrusted server error messages. These are canonical JSON request bodies, not
HAR/packet captures. Manifest hashes cover the JSON evidence files.

## What was fixed

Before attempt 1, the local credential gate incorrectly excluded legal opaque
Bearer characters. Both gates now follow the header-safe token grammar in
[RFC6750 section 2.1](https://www.rfc-editor.org/rfc/rfc6750#section-2.1), retaining
the length cap and whitespace/header injection rejection. This local refusal
did not reserve a call or reach the network.

After attempt 1, credential-free/no-HTTP diagnostics reproduced Windows DNS
error 11003 with an empty child environment. With only SystemRoot retained,
the same approved host passed TLS1.3 certificate/hostname validation. The
adapter now inherits only that required Windows system value; it still does
not inherit a key, proxy or PATH.

Attempt 2 sent uniqueItems in the strict output schema. The official
[Bailian strict-keyword table](https://help.aliyun.com/zh/model-studio/qwen-structured-output)
lists this keyword as unsupported with HTTP400. It is removed only from the
supplier schema projection; the full local validator still enforces uniqueness,
reference bindings and all original Guard restrictions. This is an identified
documented incompatibility, not a quoted vendor diagnostic: the old adapter
discarded the HTTP400 body, so its empty-body hash does not represent the original
server error. Bounded error bodies now return only through the anonymous pipe
for protected local retention, never through public exception messages.

Attempt 3 reached the client deadline without a response/usage. The independent
provider deadline is now bounded at 120 seconds; the original Worker lease is
still exactly 30 seconds. The 120-second change has not been live-tested under
this exhausted allowance. It does not reset calls or refund unknown dispatches.

## Cost and authority

All three quota rows remain DISPATCHED_USAGE_UNKNOWN. Their combined retained
reservation is **CNY 0.442608**, a conservative token-cap reservation using the
public undiscounted Beijing snapshot rate, **not actual spending or an invoice**.
Actual cost cannot be asserted to be zero. Timeout/disconnection does not prove
that a provider performed no billable work. Price evidence is the official
[Qwen3.7-Plus page](https://help.aliyun.com/zh/model-studio/qwen3-7-plus); account
discounts and actual billing were not verified. No extra call is authorized by
the unused monetary headroom because the three-attempt ceiling is exhausted.

The service identity is CODEX1_OWNED_LOCAL_PROVIDER_SMOKE. Contexts come from
the accepted synthetic fixture, whose task explicitly says offline-job-not-worker.
The fixture lease pins are simulated. These receipts do not prove an actual
Worker lease, PostgreSQL COMMIT, G1 HTTP run, human approval, ShareGrant or
customer-site capture. All Gold/quality and Guard candidate-validation results
remain unevaluated because no model candidate was received. No original Guard,
native fact/report authority, SourcePolicy, ModelGateway or R1B isolation was changed.

Each pre-call code revision had its first dual-Python protocol CI pass:
322 tests on 62f9f09 (run 44425663466), 326 on 6fa914d (44426544120),
332 on 59ef1e8 (44427378576). Original artifact SHA/CRC/JUnit checks were retained
locally. These are protocol-fake CI results, separate from the failed real
attempts above. The subsequent 120-second revision needs its own independent CI.

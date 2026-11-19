# Authorized Qwen4 batch: two genuine supplier responses, STOP

Owner authorization: issue156 comments
[7000206811](https://github.com/gloweaseco-leo/VRAE/issues/156#issuecomment-7000206811)
and [7000543676](https://github.com/gloweaseco-leo/VRAE/issues/156#issuecomment-7000543676).
Base main fbefba03c393bd1a0013f4a42d8e5765248fe2bb; dispatch code
36c66f8e8bce0654d80066180219d37e789c7167. Region Beijing, sole qwen4-max,
pure synthetic inputs, max 2 new dispatches / CNY6 conservative reservation cap.
Both authorized dispatches are consumed. **STOP: no retry or third dispatch.**

| Request | Actual supplier result | Input/output/total tokens | Public-price estimate |
| --- | --- | --- | --- |
| 64-token synthetic probe | HTTP200, qwen4-max, finish_reason=stop, JSON ok=true | 115 / 6 / 121 | CNY0.001330 |
| Original synthetic PG -> S3 Session | HTTP200, qwen4-max, finish_reason=length | 3490 / 2048 / 5538 | CNY0.096340 |

Both usages are PROVIDER_REPORTED, not protocol fakes. New-batch token estimate
totals **CNY0.097670**. Actual invoices, effective account discounts/free quota and
balance are UNKNOWN. The [official Beijing price](https://help.aliyun.com/zh/model-studio/qwen4-max)
was checked at execution: CNY10 input / CNY30 output per million tokens. Original
Provider INPUT_CAP65536 / OUTPUT_RESERVE2058 reserves CNY0.717100 per dispatch,
maximum CNY1.434200 for two. This is a token-based cap calculation, not an invoice
or a claim about the old unknown charges.

The same persistent quota.sqlite retains its original policy and three old
DISPATCHED_USAGE_UNKNOWN rows exactly. Additive authorization_batches/call_batches
associate the two new rows with the explicit new approval. Both new rows contain
genuine settled usage; the second also records INCOMPLETE_OUTPUT. A unique
approval_ref prevents relabeling the same approval as another batch. Old rows
cannot be settled/rewritten through the new batch. Original history SHA256 before
and after matches b239c9000f444fa28e905a190dc030e2fcc2c7f4fc06c9c6bd0d6c74a739f8e2.
Old Qwen3.7 usage and actual costs remain UNKNOWN; old+new invoice total is UNKNOWN.

## What the second experiment did and did not establish

The original controlled Collector/PG queue produced synthetic TX10 evidence and
a genuine committed NativeSource, with original lease start/end and transaction
1250. The original V3 completion_facts/current source signature/assignment checks
passed; source mode remained PUBLIC_READONLY_CAPTURE. The actual original
Adapter/Session produced the minimized native request saved in pg-request.json.
Input was never a customer page or private customer information.

To keep the credential in the owned DPAPI Windows terminal, PG reads and receipt
writes used a narrow local Docker exec control pipe to the ORIGINAL server-side
CurrentCommittedAuthority/delivery readers and ai_record function. Host-side
authority _read/current_input/connect were delegated to those real original
readers; no snapshot or fake database response was manufactured. This is an
experiment-specific transport, not a production mTLS API success claim. The key
never entered the isolated PG container. Actual vendor I/O delegated to the
unchanged original Windows NativeTransport, with only a recording observer.
The exported harness sources make that distinction reviewable.

**End-to-end candidates/Guard success was NOT achieved.** The genuine response
hit the existing 2048 output limit and finish_reason=length. Original Provider
settled genuine usage first, then rejected the incomplete response. No candidate
could enter Guard validation or native report facts. Subsequently, the final
original PG current check through the control pipe timed out at 30 seconds; a
captured reader error also reports the original PostgreSQL statement timeout.
The final AI receipt was not inserted in PG. Do not describe this as a completed
PG AI receipt, a candidate success or verified post-call current authority.
pg-recovered-result.json is explicitly a recovery from the durable real provider
ledger and original response, not a fabricated successful service receipt.

The first actual call succeeded before the second was permitted. Initial local
setup errors incurred no model dispatch: an approval URL failed the existing
fixed-ID validation, and an experimental pause prevented the standalone harness
ready signal. The latter was cleaned and replaced with the original controlled
delivery drill plus the accepted 003 completion-facts migration. No production
authority/timeout, ModelGateway, Guard, Provider or endpoint was weakened. After
the second actual call failed, it was not retried or salvaged as candidate output.

Both owned runs have cleanup receipts verifying absence of every exclusively
labeled resource. The subsequent original controlled drill uses its own FAKE
protocol checks; those are separate from these two genuine Windows supplier
dispatches. Its hardcoded model_calls=0 describes that drill process and must not
be used as the count for this experiment. No customer report was published,
no ShareGrant was issued for these AI results, and no cloud deployment occurred.

## Evidence handling

Original response bytes remain in the private owned terminal, with SHA256 hashes
in the exported receipts. *-response-safe.json are explicitly safe subsets and
are not claimed to be the original response bytes. Requests, exact model/usage,
finish reasons, billing estimates, original PG preflight pins, recovery details
and cleanup records are exported. No credential or encrypted DPAPI blob is
exported. Workspace identifiers in harness source copies are redacted; source
copies are for audit and are not a turnkey live-call command.

The minimal production patch only appends explicit grant batches to the original
ledger. It does not increase output limits, change prompts, invent a successful
candidate, reset quota or dispatch again. Output-volume and control-transport
limitations remain identified for later work; a future real experiment requires
a separate explicit allowance.

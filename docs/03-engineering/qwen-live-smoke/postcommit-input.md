# Same-run post-COMMIT input replay (offline only)

Historical PR162 boundary below. Accepted PR164 now supplies the current PG
handoff. See [committed-api.md](committed-api.md) for the new server adapter and
separate capture-mode S3 compatibility path; the original offline gate stays intact.

Base: accepted main `cf1a67bdab7c2acadff6cedbbe7be64357fb51be`, including
PR162 HEAD `994c0372b2b3b8fd30ad60d3a7f2dc5cad236b33` and accepted PR161.
Scope: Owner #156 comment 6997245247 and PR162 comment 6997493678.

`integration/qwen_provider/postcommit.py::replay_input` reconstructs the original
EvidencePack and NativeSource from the PR162 producer's envelope, against a
separately held NativeTask, exact artifact SHA256, report content hash and display
hash. It verifies the original industry/Guard-backed NativeSource replay and the
complete original report/version. It keeps `PUBLIC_READONLY_CAPTURE`, L1 source
authority, L2 diagnostic depth, NO_MODEL and unpublished/unapproved state distinct.
It returns only `(pack, source)`, never an S3 Context, permission or model request.

The pins and artifact must come from C3's authenticated, committed current-source
authority. They are internal expectations, not credentials. Constructing both
from arbitrary JSON would only test self-consistency and would not authenticate
a task. This helper performs no database query and cannot prove COMMIT visibility,
current authorization, an unexpired invitation, assignment epoch or revocation.
The source-bundle hash is matched to the held task; no absent bundle bytes are
invented or claimed to have been replayed.

## Exact integration boundary still pending

The accepted PR162 `review.current_review` retains PG locks and performs a fresh
`review_source` check after the ledger operation. Its source replay is useful
precedent, but it yields a ledger rather than the complete S3 input pin contract.
`review_source` returns the retained artifact; that artifact lacks the original
lease-start/lease-expiry, independently held completion time and current authority
expiry required by `s3.offline.CompletionPins`. `loaded_at`, source `created_at`
and a result-table timestamp generated before transaction completion are not
substitutes for evidence of actual successful COMMIT.

Separately, original CompletionPins explicitly accepts only OFFLINE_SYNTHETIC.
PUBLIC_READONLY_CAPTURE remains rejected, even with internally consistent
timestamps. Changing its label to synthetic would change the original task and
report. This PR leaves that gate intact and tests both refusal paths.

C3 must expose a reviewed post-COMMIT current-authority handoff with independently
held same-task/report/evidence pins and actual lease/completion/deadline facts.
Any capture-mode S3 admission needs an explicit reviewed compatibility design.
Do not keep the 30-second Worker lease or the review PG transaction open for a
potential 120-second model request. Current authorization must be checked around
dispatch and result/read without treating a copied artifact or callback label as
authority. This change neither implements nor claims that database/model flow.

## Reproduce

```
python -m pytest -q tests/intelligence/qwen_postcommit_cases.py
```

The synthetic business sample reuses the accepted P40 EvidencePack/diagnosis and
original NativeSource projection, with the producer envelope shape above. It is
not a real captured customer, actual PG COMMIT receipt, legal source permission or
live Qwen response. Cases cover separately held task fields, artifact/report/display
hashes, evidence bytes, invalid base64, diagnosis/report/version edits, authority
promotion, mode rewriting, duplicate JSON, nonfinite JSON and byte bounds. Socket
creation and DNS resolution fail the tests. The Qwen protocol workflow executes
these cases explicitly on Python 3.11/3.13 alongside the existing Guard, protocol,
usage, failure and offline-session suites; default core test discovery is unchanged.

Canonical JSON byte comparison preserves JSON types: replacing a report's false
with 0 or its version 1 with true is refused. Both regression cases first failed
against the initial Python object-equality implementation, then drove this fix.

Live Qwen4 calls remain zero. The original three Qwen3.7 attempts remain exhausted;
actual cost, account balance and effective account price remain UNKNOWN. No secret,
quota database, network/Server/SourcePolicy/Guard implementation or customer report
release is changed. Existing protocol fakes remain simulation evidence only.

# VRAE committed capture -> existing Qwen4 Session

Built on accepted main cc10b3a15dcb45d0cd57668f2d3ba949957cc5fb (PR164).
Owner scope: PR163 comment 6998498673. This interface belongs to VRAE's trusted
server composition; VEYFRONT UI or release state is not an input or dependency.

```python
from integration.qwen_provider.committed import Adapter
from integration.authorized_targets.postcommit import run

# All arguments below are independently held by the authenticated server.
# projection and buyer_pins come from the original S2 factories over the exact
# committed EvidencePack, selected subject and server IndustryPins configuration.
adapter = Adapter(ai_binding, original_job_id,
                  projection=s2_projection, buyer_pins=buyer_candidate_pins,
                  provider=existing_qwen_provider_or_none, timeout_ms=120000)
receipt = run(ai_binding, original_job_id, adapter,
              operation_id=stable_server_operation_id)
```

Use a synchronous service worker (or invoke this synchronous entry in an ASGI
worker thread). Reuse the per-task Adapter and the existing QwenProvider/Quota;
do not reconstruct a real quota, fee allowance or operation ID for a retry. A
concurrent call on the same Adapter returns AI_UNAVAILABLE/OPERATION_IN_FLIGHT.
The existing Session owns cached operation results and the original persistent
provider quota prevents duplicate dispatch across restarts.

The AI binding is the original function-only target_v1_ai actor. It is never a
customer/Worker Bearer or a browser-selected tenant. Each current read uses
delivery.committed_input(..., purpose='POST_COMMIT_AI_INPUT'), which verifies the
original PG source/invitation/assignment/policy and current source signature.
No new HTTP endpoint, Provider, fee issuer, source authority or Agent framework
is introduced. Customer report access and formal review remain independent.

The adapter compares the caller's handoff to a fresh original current read. It
replays the exact artifact hash, NativeTask, EvidencePack, diagnosis, report and
display hash, preserving PUBLIC_READONLY_CAPTURE. CommittedCompletionPins is a
separate internal compatibility path; original offline CompletionPins remains
synthetic-only. The context hash additionally binds original transaction_id,
artifact hash and full current-input descriptor. A copied dataclass/callback or
JSON object does not grant access; the trusted server must use the original PG
reader and its existing signature trust configuration.

Original lease bounds must span exactly 30 seconds and have ended. PG's
committed_at is the result insertion timestamp; the inherited timing slot uses
it for lease consistency only. It is not asserted to be an exact physical COMMIT
instant. Reading the row through the original current port proves visibility of
the completed COMMIT. Local plan/policy/source deadlines are checked, and fresh
PG checks also enforce earlier invitation/assignment expiry or withdrawal.

Every context check reopens the original current port. The injection point closes
its first read transaction before calling the adapter and reopens it before
recording a receipt. The adapter also rechecks before dispatch, after usage,
after Guard binding, and before cached result use. Provider I/O holds no original
PG transaction or Worker lease. A source change refuses candidates; original
quota usage already recorded by the provider remains intact.

Original ModelGateway preflight, minimization, Guard binding, strict qwen4-max,
supplier usage validation and durable reservation/settlement all remain in use.
Provider/Permission/Price/key/endpoint cannot be supplied through the handoff.
The adapter maps original Session status to AI_UNAVAILABLE or
AI_CANDIDATES_FOR_HUMAN_REVIEW and preserves the stable operation ID. Candidates
stay private/unapproved, never overwrite report hashes and grant no report access.
Invalid input uses fixed errors. After an unknown dispatch/usage outcome, cost is
UNKNOWN; settled usage survives candidate or current-authority rejection. Early
input refusal with a configured provider does not invent zero historical cost.

With provider=None the source/context path remains usable and returns
AI_UNAVAILABLE/PROVIDER_GO_NOT_GRANTED with no dispatch. An existing provider
without current fee permission is refused by its original authorization check.
This does not consume or replace the exhausted historical allowance.

Verification:

- Explicit qwen_committed_cases.py covers current-port stubs, original Session,
  usage, Guard, invalid output, timeout, expiry, cross-task pins, withdrawal,
  operation cache and concurrency. It supplies no actual PG authentication proof.
- The original authorized-delivery controlled drill now invokes pg_check.verify
  over the actual committed TX10 capture. It exercises default NO-GO, original
  Session candidates with protocol FAKE usage, schema-failure usage retention,
  unchanged input hashes, and actual pg_stat_activity during fake provider I/O.
  Its c1-committed.json receipt identifies FAKE_NOT_REAL_QWEN explicitly.

No live Qwen4 call or new fee authorization is enabled. Historical three Qwen3.7
attempts remain exhausted; actual cumulative billing/account price/balance remain
UNKNOWN. Synthetic fake ledgers used by tests are unrelated to the real ledger.
Old M1 Docker RED remains historical evidence. The builder now emits only fixed
cause codes plus stderr hash/size when its captured stderr proves a known cause;
otherwise it reports CAUSE_UNDETERMINED. Images, locks, exits and old gates remain.

# Same-service Qwen4 runtime

Refs #156 Owner comment7005266142; accepted baseline bedc9fa. The feature
assembles the existing Qwen4 Provider/Quota/Session/Guard in the existing durable
AI discovery loop. It creates no Agent framework, model gateway, Worker, CRM or
frontend. Real-model HTTP200 evidence from PR170 is not runtime acceptance.

## Isolation and original authority

The original CONTROLLED_NON_CUSTOMER source proof requires a physically internal
namespace. Adding an Internet NIC to its PG/Worker namespace would violate the
accepted source authority. `isolated_model_runtime=true` therefore relocates the
**sole original AI loop** to this deployment's `-ai` container, UID10008. The
primary supervisor stops spawning its AI child; Worker/PG/REVIEW remain unchanged
on their original namespace, with the same volumes, source signatures and fences.
The AI container has its own outbound bridge and private access to the original
network. No AI port is published. Two fixed bounded TCP forwards carry ordinary
password-authenticated PG wire traffic; original connect/role/RLS checks and short
transactions execute normally. These are not Docker snapshot/record control RPCs.

The old source `model_fee_go=NOT_GRANTED` remains correct for that source proof.
A **separate signed operator AI allowance** authorizes Qwen4. No browser/request
can supply it, a key, Provider, endpoint, model or ledger path. The root verifies
the pinned DEPLOYMENT_OWNER signature, source class, immutable image source SHA,
expiry, exact qwen4-max/Beijing, minimal data scope, one-dispatch/task, 2048 output
ceiling, no retries and explicit daily CNY budget. Permission is rechecked before
each dispatch. An ordinary legacy synthetic Permission cannot enable customer data.

The AI parent resolves only the fixed official workspace hostname, rejects
nonpublic answers, and pins its IPv4 answers in a root-owned0440 runtime file. Only those
IP443 destinations plus local PG are allowed for AI UID10008. The native adapter
still checks public IP/peer/TLS hostname and the exact endpoint/model itself.
Its bounded stdin carries these trusted pins to the existing egress child;
standalone callers retain the original DNS resolution path. This avoids writing
Docker's read-only `/etc/hosts` and grants the AI child no DNS access.
AI requires no outbound DNS after the root pin; SSH/LAN/metadata/other HTTPS/DNS
remain kernel-denied. If DNS rotates, restart to repin; do not open all443 or retry
an unknown dispatch. AI children have zero capabilities/no-new-privileges and
cannot read root signing secrets. Source Worker/PG/REVIEW egress is unchanged.

## Operator materials — names only, never publish their values

Existing trusted deployment: manifest, root trust registry, deployment signing
key, actual source authorizations and AI-role PG bindings. New model material:
`model-permit.json`, `model-key`, retained original Quota and explicit fee approval.
Use the existing Windows DPAPI secret only through a trusted local stdin operation
into the Docker/WSL ext4 operator volume. Do not write plaintext keys to NTFS,
argv/env, GitHub/CI, logs or VEYFRONT. Root operator key is0600; runtime key is
root-owned0440 with AI10008 group access, under a root-owned0750 directory. AI
cannot chmod/replace it. Grant uses the same pinned operator key, not a CI issuer.
The runtime Dockerfile has its own build exclusions for local `.private`,
`.runtime`, environments and worktrees; ignored operator/test materials must not
be copied into image layers. Only runtime volumes/tmpfs carry operator material.

The offline `qwen_provision` command reads only a bounded private stdin envelope:
explicit operator_fee_go, fee approval reference/expiry (max24h), daily cap,
operator-verified price upper bounds, workspace/key, authorized source hashes,
and the retained SQLite plus its logical table-row digest. It refuses absent fee
GO, invalid price/signature and absent historical rows. This is an explicit local
operator action, not a runtime secret autoloader or new HTTP endpoint.

Run it in an owned one-use `--network none` container, with root-only operator
volume RW, existing REVIEW Ledger volume RW, tmpfs temporary/trust paths and only
CHOWN/DAC_OVERRIDE for that offline copy. The running AI never has these DAC
privileges. The helper imports the old nonempty SQLite once and verifies all old
table rows exactly; it never replaces an existing destination or recreates a lost
counter. Seal the former Windows quota read-only **before** starting AI so there
is only one active counter. Later key/permit renewals do not import another quota.

For an already running C3 deployment, `control activate-model --name <existing>
--image sha256:<committed-image>` uses the existing Linux-private operator volume,
updates only image/topology metadata there, and keeps the same PG and Ledger.
It never exports private operator files back to Windows/NTFS and does not invent
a fee/source permission. Staging the signed model allowance and retained quota
is still a separate explicit operator action.

The canonical quota is `/ledger/qwen/quota.sqlite` in the existing persistent
Ledger volume, mounted by subpath as `/model-ledger`. Only AI can write it; REVIEW
can read usage metadata for the original cold-backup path (no key/prose is stored
there). Thus original cold backup/restore includes the current quota, not a new
empty store. A copied backup is not permission to consume an exhausted operation.

## Budget, consent and failure behavior

Proposed local default: **CNY5 per UTC day**, one dispatch per original job,
original2048 output cap, no automatic retry. It becomes active only after explicit
operator fee approval/signing. This is a resource budget, never an invitation limit.
New per-task authorization batches append to the original ledger; stable original
job operation IDs prevent restart/day/permit rotation from redispatching a task.

Reservations atomically aggregate across all runtime batches. Every unknown
reservation remains occupied, including old experiments; known old usage on the
same UTC day is counted too. Settled supplier usage replaces only its own reserve.
Daily rollover never refunds an unknown attempt. Original old3 UNKNOWN, prior2
supplier usage and PR170's1 recorded usage are not reset/reclassified. Day budget
reports occupied/reserved/estimated values, **not an invoice**; actual bill remains
UNKNOWN. Price must be at least the current official or higher account quote.

Exact source authorizations can be explicitly allowlisted for a controlled trial.
For repeatable newly invited targets an operator may explicitly sign
`allow_signed_model_consent=true`. Then the current SOURCE_ADMIN-signed plan hash
must include `model_processing` with provider=aliyun-bailian-beijing,
region=cn-beijing, data_scope=MINIMIZED_TYPED_EVIDENCE_NO_RAW_HTML_PII,
consent=EXPLICITLY_ACKNOWLEDGED and a bounded consent_reference. C3 owns actual
legal target issuance/consent capture; a browser flag alone never qualifies.
The original minimized request withholds raw HTML, URLs, identities, contact
details and secrets. No per-customer prompt/Agent is created.

`ai_loop` discovers original COMMITs after lease expiry and supplies the real
Provider to the original Adapter. Missing license/key, budget refusal or model
error records AI_UNAVAILABLE while preserving deterministic evidence. Genuine
usage persists before schema/Guard checks; a final PG failure clears candidates
and returns receipt UNKNOWN. There is no report approval/publication side effect.
The receipt includes actual provider/model/usage, REAL_QWEN configuration and
sanitized day-budget state. The old deterministic report remains authoritative.

## Acceptance and current limits

The Linux-service natural CI first tests real signatures and shared SQLite budgets,
then the original continuous PG/Worker/mTLS service. Its explicit test entrypoint
relocates only AI and exercises six fresh HTTPS tasks: no fee permission, missing
key, valid candidate, invalid schema, timeout, exhausted budget. This uses only
FakeTransport, a marked synthetic key and a disposable FAKE quota. Native HTTP is
tripwired and kernel AI egress remains denied; fake proof is never live proof.
Raw actual PG receipts/usage, original pins and resource cleanup are exported.

Actual native acceptance must use C3's **same ongoing local service**, a current
authorized source/caller, an independently approved finite fee allowance and
private DPAPI import, then one fresh task. Do not repeat supplier probes or reuse
PR170's result as this run. Keep the service/data running afterward; no VEYFRONT
change, customer-data upload or human approval is implied.

The 2026-11-19 local acceptance used C3's retained `vrae-local` controlled service,
the same PG/Ledger volumes and ports18769/18770. The initial caller403 was traced
to expired sessions. A new30-minute invitation for the existing controlled subject
and already signed source was issued through the trusted operator and exchanged
through the original mTLS API; old sessions and source permissions were untouched.
This retained controlled instance is not represented as C3's new customer runtime.

Six fresh HTTPS fake tasks passed positive/negative PG receipt checks. The actual
AI UID passed official TLS1.3 and kernel denials. Exactly one newly authorized
native dispatch returned1218 input/578 output tokens, estimated CNY0.029520,
actual invoice UNKNOWN. JSON/compact schema passed; the unchanged candidate
validator refused `GUARD_ANCHOR_REQUIRED` before original Guard binding. Its
durable original PG receipt is AI_UNAVAILABLE with no claims/access/publication.
The original deterministic report survives. **Real candidate acceptance FAILED**;
PR170's older success is not substituted. No further paid dispatch was attempted.

See [sanitized acceptance](qwen-local-20261119/acceptance.json) for exact task/report
pins, signed-runtime SHA, usage and daily budget. The original six historical
rows remain unchanged; canonical storage now contains seven calls (three old
UNKNOWN, four provider-usage rows). Key/permit live only in root-private Linux
volumes/tmpfs; the former Windows quota is read-only archival material. The same
operator24-hour expiry was retained through image renewal, without quota reimport.

The supplier's rejected prose is not retained, so no exact generated-reference
repair is claimed. Do not weaken Guard, manufacture an anchor or replay a paid
call to make this result green. Additional real candidate acceptance requires a
new explicit single-call allowance. C3 still owns customer source consent/identity,
public connectivity and integration of the reviewed PR into its customer runtime.

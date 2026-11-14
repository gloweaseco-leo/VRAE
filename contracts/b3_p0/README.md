# B3-P0 standalone TEST_ONLY contract

Owner authorization: Issue #77 comment 6867707779. Base `cbcdb6f62d402861e8a12392f53061109a4a7d8b`.

`Command.payload` is the exact canonical UTF-8 accepted `ReviewCommandProposal` or
`CoverageAcknowledgementProposal`, with the original closed shape, native target
digest, tenant/report/version, expected_review_seq, idempotency_key, every guarded
Claim disposition and every required section ACK. No browser actor, witness,
subject, role, DSN, trust epoch, authority or approval flag is accepted in this DTO.
The current native Python validator and accepted SQL validator both execute.
The immutable Locator is the server-held six-tuple
`(tenant, ref_id, source_run, report, version, target_digest)`.

`Witness(token: UUID, location: Locator)` is an out-of-band **synthetic** fixture
capability. A private administrator provisions a row bound to actual Reviewer
SESSION_USER, `TEST_ONLY_*` subject, Locator, trust epoch and expiry. Runtime has
no administrative connection, witness provisioning endpoint or raw table access.
This does not validate a human identity or implement an IdP. Opaque 120-second
maximum HTTP sessions retain the witness exclusively on the server. New server
instances begin with empty sessions. A restart/restore ceremony rotates the DB
authority epoch before issuing new sessions; never expose a restored DB directly.
Fresh witness + same synthetic subject may recover historical bytes; a fresh
session is not itself authorization, and every SQL access rechecks current rights.

Only `POST /test-only/intents` and `POST /test-only/receipts` exist on an ephemeral
127.0.0.1 listener. The latter accepts exactly `{idempotency_key: string}`.
Host must equal the exact loopback authority, Origin is forbidden, Authorization
is one server-provisioned opaque Bearer token, JSON is bounded to 131072 bytes.
There is no UI integration, public route, natural-person login or production route.

Receipt is immutable canonical bytes (`Receipt.document` enforces a closed field
set). `authority=TEST_ONLY_REVIEW_INTENT`, `durable=true`, `review_seq=1`, status
`REVIEW_INTENT_TEST_ONLY` or `COVERAGE_ACK_TEST_ONLY`; native_decision, person_id
and share_grant are NULL; effective_approval and external_visibility are false.
It includes exact Locator, original source/HTML/manifest SHA256, actual db_actor,
synthetic subject, command_digest, key, stable intent_id and event_id. The native
v1 ReviewDecision DTO is unchanged. A 200/zero-finding target still has three
coverage Claims and never becomes an approval. The 404 has six guarded Claims.

Same report/key, subject, actual DB actor, Locator and canonical command returns
the exact prior receipt with no extra audit/outbox. Witness token and session are
excluded from the semantic digest to permit authenticated recovery. Different
payload/subject/actor/version is a conflict; another key for a closed report/version
fails CAS. Unknown receipt returns UNKNOWN_COMMIT, never implicit resubmission.

The adapter owns its transaction, forbids ambient transactions, loads original
BYTEA via accepted Reviewer load_target, runs native byte/Guard/proposal checks,
then performs SQL CAS and inserts intent, Claims, sections, audit and internal
outbox together. Deferred constraints check completeness and current authority at
controlled commit-entry. Locks follow accepted assignment/source-parent then B3
authority/witness/state. Authority uses clock_timestamp, not transaction-start now().
No function claims to COMMIT. Physical COMMIT may cross expiry: immutable history
can exist even if post-commit revalidation denies the receipt. Denial is not proof
of rollback. History is always non-effective. Database/connection ambiguity after
write is UNKNOWN_COMMIT; fresh current authority may look up the same key.

SQLSTATE 42501 means current authority/access denial; 40001 stale CAS; 23505 key
conflict; 22023 malformed native command; 23514 incomplete transaction. HTTP
contains bounded error codes only. Production review/share adapters always DENY.

B4 durable task interfaces, real IdP/person bindings, native decision persistence,
APPROVED reports, ShareGrant and B5 UI mutation integration remain unimplemented.
No PR83 implementation is imported. The internal outbox is an immutable durable
event ledger for at-least-once test processing, with no sender or business effect.

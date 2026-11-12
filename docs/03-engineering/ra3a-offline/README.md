# RA-3A offline ModelGateway

Issue [#39](https://github.com/gloweaseco-leo/VRAE/issues/39), under offline entry
[Issue #38](https://github.com/gloweaseco-leo/VRAE/issues/38). New independent
`feat/ra3a-offline-model-gateway` worktree starts at accepted main
`91d408bcdbe0a6667c1e356723e3385465cdd6ae`. Unmerged QA PR #37 is not imported or
claimed merged. Only new intelligence modules/tests/demo/evidence are added;
interpretation, findings, rules, contracts, security/CI and historical fixtures
remain unchanged.

## Business demonstration

Run `python scripts/verify_ra3a.py`. No network/model credentials/dependency install
is needed beyond the existing project environment. It loads the **unmodified**
accepted C3 positive fixture with literal independent EP/RX/FP/evaluator/builder
pins in `tests/intelligence/synthetic.py`. New output is sealed separately in
`tests/intelligence/fixtures/ra3a-offline-demo.json` and compared on every replay.

The gateway prepares a bounded request describing six confirmed source-level
checks separately from UNKNOWN/BLOCKED catalog entries, then explicitly dispatches
only to a deterministic fixture. This gives the later L1 interpretation stage a
usable request and auditable admission/usage foundation without sending raw
customer/source text or approving generated claims.

| Scenario | Actual behavior |
| --- | --- |
| Default | NO_MODEL / NOT_RUN, no tokens/claims or calls |
| Explicit Fake Provider | Bounded opaque output; usage ESTIMATED and synthetic |
| Same operation replay | No new dispatch; same usage identity and no second fee |
| Unknown rate | Refused before reservation/dispatch; never priced as free |
| Missing usage | UNKNOWN, output discarded; maximum reservation held, run quarantined |
| Retry after unknown | Refused; no new dispatch or release of uncertain liability |
| Pre-dispatch cancellation | Reservation released, no dispatch; old operation remains non-reusable |

The demonstration uses an explicit **synthetic** CNY 1.00 cap and fake 0.01/0.02
per-1000-byte-unit rates; these are not market prices, executable live approval
or the planning-only CNY 2 target. Real model calls and real token charges are 0.

## Interfaces and boundaries

- `prepare_request`: exact C3/B6 pin and caller tenant/run/policy checks plus full
  independent FindingPackage source replay; the separately supplied execution
  must equal the verified embedded execution. No bare URL, raw HTML or detached
  prepared wrapper is accepted for execution.
- Redaction is an allowlist projection, not a fragile email regex: **all source
  free text, raw elements, company/product names, addresses, contact strings,
  URLs, local tenant/run/policy IDs and provenance IDs are withheld from the
  provider by default**. Fixed rule/outcome/kind/status fields enter a capped
  data section with a fixed system instruction. Provenance bindings and recorded
  source scope remain local in the private request envelope. Unknown is not a
  defect. Excessive data is rejected instead of silently truncating evidence.
- `OfflineProvider` is the typed replacement seam; only the exact deterministic
  `FixtureProvider` implementation is runtime-allowlisted now. Foreign adapters,
  provider/model names or supplied credentials are disabled. No SDK/HTTP client,
  environment secret reading, network/metering service or live tokenizer exists.
- `BudgetPolicy` and `PriceSnapshot`: explicit positive finite decimal strings,
  supported CNY/USD without FX, fixed rate ref, integer micro-unit accounting
  rounded upward, strict per-request tokens/per-run money/tokens/operation bounds.
- `Ledger`: one invocation-local thread-safe journal. RESERVE → START → COMMIT
  (synthetic ESTIMATED) or UNKNOWN; RELEASE is only allowed before dispatch.
  Operation and request replay are guarded. Unknown usage preserves liability
  and blocks new dispatch. Trusted checkpoint restore replays transitions;
  **all unfinished reservations recover as UNKNOWN**, not a free retry.
- `verify_accounting_audit`: independently pinned request, latest ledger and
  record time, exact usage recomputation and opaque output hash binding. It
  does not validate meaning of model claims. Schema-valid UsageRecord alone is
  insufficient; no estimate can be promoted to RECONCILED or an external invoice.
- Fake output always remains UNVALIDATED outside AIInterpretation. The native
  AIInterpretation is NOT_RUN with empty hypotheses/recommendations and null
  model/tokens; RA-3B per-claim validation is explicitly still required.

## Real evidence and exceptions

- `red.log`: new gateway missing before implementation (expected first red).
- `typing-red.log`: one missing local list annotation; fixed with explicit types.
- `lint-first.log`: multiline demo import's E402 marker was on the wrong line;
  corrected. No lint rule was disabled beyond the established script path import.
- `accounting-first.log`: 51 passed. `focused-first.log`: 105 passed;
  `focused-final.log`: 108 passed after checkpoint/cancellation/demo additions.
- `audit-time-red.log`: a genuine negative initially failed because a modified
  usage timestamp could be rechecked against itself. Audit now requires the
  independently supplied original record time, plus strict timezone-aware time
  formatting. `focused-green.log`: final 110 passed, including that counterexample
  and verified-but-overbound request refusal.
- `decimal-context-red.log`: an additional real negative exposed inherited
  Decimal exponent limits. All money operations now use an independent fixed
  high-precision context, so caller rounding/precision/exponent settings cannot
  alter reservations. Final 111-case and full regressions include this case.
- `demo-first.log` and `demo-final.log` preserve the corresponding actual offline
  replays. Neither rewrites any accepted source fixture. A transient patch-tool
  path-read error was retried after confirming the file existed; no code/data
  loss or scope expansion occurred.
- `regress.py` records full actual stdout/stderr and exits for Python 3.11/3.13:
  compile/Ruff/mypy/pytest/pip check, every historical sealed replay, RA-3A demo,
  simulated Gold and required forged-Gold rejection (expected exit 1). Raw
  summaries/logs for the initial run are retained in `python311/` and `python313/`;
  these started before the Decimal hardening and are not final acceptance proof.
  Final source regressions are in `python311-final/` and `python313-final/`. Full regressions
  run in the already approved environment to avoid the previously proven Windows
  pytest-temp sandbox denial; tests/skips and existing CI are not weakened.
  Both final full pytest runs passed 1419 tests / 25 host-only lab skips. Each
  final version completed all 23 commands with expected exits, including the
  required forged-Gold exit 1. There are 111 RA-3A tests in the final full suite.
  The final Python 3.13 Ruff command also emitted two optional cache-write
  permission warnings; checks passed and exit was 0. They are preserved verbatim.
- PowerShell UTF-16 diagnostics are normalized to UTF-8 and diagnostic whitespace;
  original sealed source bytes and refs are never normalized or overwritten.
  Final HEAD/base and all four hosted job links, checkout/merge parents and raw
  browser security artifact digest are recorded in the Draft PR after commit.

All named raw logs and four regression directories are stored losslessly in
`engineering-raw.zip` to keep repeated historical outputs out of the source diff.
`evidence-index.json` contains the archive SHA256, each original relative path /
byte count / SHA256, and all actual command summaries. Verify the archive digest,
then use `python -m zipfile -l docs/03-engineering/ra3a-offline/engineering-raw.zip`
or open a specific entry with `zipfile.ZipFile.read`. No accepted historical
file was archived, removed or edited; this archive contains only this worktree's
new RA-3A diagnostic outputs. `regress.py` reproduces the original directories.

## Actual risks and unfinished work

1. No live adapter, provider pricing, real tokenizer, paid execution, credentials,
   production authorization or invoice reconciliation is implemented/authorized.
   Byte units and synthetic estimated money are not measured model billing.
2. There is one authoritative **local** ledger, not distributed/persistent billing.
   Caller must protect the latest checkpoint pin. The system cannot prevent a
   trusted caller deliberately cloning ledgers or choosing stale checkpoints;
   it makes no production exactly-once billing claim. Unknown requires later
   authorized reconciliation, not an optimistic refund/retry here.
   Output accounting audits use terminal (committed/released/unknown) checkpoints;
   unfinished checkpoints deliberately recover to UNKNOWN rather than attest a
   still-running receipt. This stage does not finalize concurrent pending work.
3. Privacy minimization deliberately withholds source quotes/names. Output can
   explain controlled rule facts only; it cannot substantiate new source-specific
   prose or prevent hallucinations by a future live model. This is a supported
   offline-provider boundary, not a sandbox for arbitrary third-party Python.
4. RA-3B per-claim evidence/semantics validation, RA-3C page/report and RA-3D
   reviewer/share workflow are not implemented here. No output is VALIDATED,
   approved, customer-ready, public or shareable.
5. Human Gold remains Owner-deferred 0/26, QUALITY_GATE_NOT_EVALUABLE with
   precision/recall N/A. CI/Fake outputs do not replace human or Owner review.

Stop at Draft PR for Owner independent acceptance; no merge or deployment.

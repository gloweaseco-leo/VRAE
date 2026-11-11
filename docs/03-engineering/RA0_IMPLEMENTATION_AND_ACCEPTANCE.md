# RA-0 implementation and acceptance record

## RA-0F current verdict — 2026-11-10 America/New_York

**LOCAL_ENGINEERING_VERIFIED / PASS. GitHub CI: CI_INFRA_BLOCKED. Overall: PARTIAL
(local acceptance complete, hosted CI and Owner sign-off outstanding). RA-1 execution:
NO-GO in this authorization.** No merge, deployment or RA-1 implementation performed.

Remote branch checked and fetched at start: `feat/ra0-contracts-domain-foundation`,
HEAD `791be66d09b4d35d029fe7fb825adb53cfec42cf`, identical to supplied baseline.
Main remains `43817d1cd0badf2c2223f98bc8fe322e4f1419c7`.
All work stays in [Draft PR #1](https://github.com/gloweaseco-leo/VRAE/pull/1).
Source manifests in the acceptance summaries identify the tested working tree byte-for-byte;
their `head` is the original checkout parent, not a claim that repairs existed in that parent.
The containing RA-0F Git commit identifies the delivered tree. Timestamps in logs are UTC;
2026-11-11 UTC is still 2026-11-10 in the requested America/New_York reporting day.

| Work package | Current status | Evidence / limits |
| --- | --- | --- |
| RA-0A | PASS locally; contract freeze awaits Owner | 17 JSON Schemas, 19 valid/36 invalid fixtures, OpenAPI 3.1; strengthened draft report/HTTP contracts |
| RA-0B | PASS for pure domain | Policy, scope, role, state, evidence, approval, sharing, currency/budget and business guards; no real identity adapter |
| RA-0C | PASS for synthetic contract baseline | 25 URL syntax cases, 48 generic expectations across 16 rule candidates, additional adversarial tests; not a RA-2 rule engine or real-site accuracy benchmark |
| RA-0D | PARTIAL | Both clean local Python environments pass; hosted matrix blocked before runner; runtime Docker/Worker isolation is not built or claimed |

### F1 — actual checkout, clean complete verification

Both venvs were newly created with `include-system-site-packages=false`, then installed using
`python -m pip install -e '.[dev]'`. No reconstructed source or host-environment dependencies.
Python 3.11.15 was already available; 3.13.13 was installed separately using uv.
Both run the original `tests/test_domain.py` and `tests/test_contracts.py`, plus new regressions.

| Check | Python 3.11.15 | Python 3.13.13 |
| --- | --- | --- |
| Editable dev install | exit 0 | exit 0 |
| `python -m compileall -q vrae` | exit 0 | exit 0 |
| `ruff check vrae tests --select E4,E7,E9,F` | exit 0 | exit 0 |
| `mypy vrae` | exit 0; 12 source files | exit 0; 12 source files |
| `python -m pytest -q` | **272 passed, 0 failed, 0 skipped**, exit 0 | **272 passed, 0 failed, 0 skipped**, exit 0 |
| `python -m pip check` | exit 0; no broken requirements | exit 0; no broken requirements |

Versions in both environments: pytest **9.2.0**, jsonschema **4.26.0**, Ruff **0.17.4**,
mypy **1.20.2**, PyYAML **6.0.3**. No Linux runner execution is claimed.

Evidence index:

- [3.11 complete commands, timestamps, exits and source SHA-256](ra0f-evidence/acceptance-311-summary.json)
- [3.13 complete commands, timestamps, exits and source SHA-256](ra0f-evidence/acceptance-313-summary.json)
- [3.11 pytest log](ra0f-evidence/acceptance-311-4-pytest.log), [3.13 pytest log](ra0f-evidence/acceptance-313-4-pytest.log)
- [3.11 install](ra0f-evidence/311-install.log), [3.13 install](ra0f-evidence/313-install.log)
- Adjacent `acceptance-*-{1..5}-*.log` files retain complete output and exits for every gate.
- `acceptance-*-freeze.txt` captures resolved dependencies; the editable line names the Git parent,
  so use the source manifest/containing commit for repairs, not that line as the repaired revision.
- [runtime/dev constraints](ra0f-evidence/constraints.txt) permit version-pinned repetition;
  they are not a wheel-hash lock or an OS/build-tool reproducibility guarantee.
- [runner script](ra0f-evidence/verify.py) uses the checkout root, records every gate even after failure,
  and exits nonzero if any gate fails. Run `python docs/03-engineering/ra0f-evidence/verify.py <label>`.

Reproduce in a new venv on each Python version:

```sh
python -m venv .venv
# activate .venv (Windows: .venv/Scripts/Activate.ps1; Unix: . .venv/bin/activate)
python -m pip install -e '.[dev]'
python -m compileall -q vrae
ruff check vrae tests --select E4,E7,E9,F
mypy vrae
python -m pytest -q
python -m pip check
```

To reproduce resolved runtime/dev versions, add
`-c docs/03-engineering/ra0f-evidence/constraints.txt` to the install command.
No dependency conflict from the earlier shared moviepy/pillow environment is attributed to VRAE.

### F2/F4 — failures first, minimal fixes, full regression

Original exact baseline result: **236 passed / 4 failed**, pytest exit 1; other four gates exit 0.
See [baseline summary](ra0f-evidence/baseline-311-summary.json) and
[full failure traces](ra0f-evidence/baseline-311-4-pytest.log).
The fixture loader overwrote OBSERVED/FETCHED examples with later UNKNOWN examples sharing the
schema name. Select the first canonical example; all 55 original contract fixtures remain tested.
No test was removed, safety constraint relaxed or exception suppressed.

New red evidence: [18 failures / 1 pass](ra0f-evidence/red-regressions.log),
[4 additional failures / 27 passes](ra0f-evidence/red-second.log),
[OpenAPI write-header failure](ra0f-evidence/red-openapi.log).
The first scoped-finding probes exposed the old set-only interface with TypeError, not a domain refusal;
the repaired interface now consumes actual scoped records and raises DomainError. During repair an
incorrect sibling-test import caused one harness failure; it was corrected to `tests.test_domain`.
All intermediate output is retained; only `acceptance-*` is the final local verdict.

| Finding / invariant | Repair and test evidence |
| --- | --- |
| UNKNOWN/ACCESS_BLOCKED cannot become objective failure | Original graph tests now use correct correlated fixtures; explicit new blocked/unknown negative tests and `classify_rule(None, evidence)==UNKNOWN` |
| Nonexistent, cross-tenant or cross-run evidence is refused | Original graph/AI tests plus unresolved nested observation evidence, UNKNOWN AI citations and scoped report finding tests |
| Schema does not prove natural-language truth | Documented structural-first/domain-second contract; RA-3 semantic support remains unimplemented |
| Content changed but old hash retained | Recompute hash over immutable report manifest and exact finding contents during approval/share; tests mutate IDs, statements, run and approval attribution |
| L0 report mislabeled by caller | Required `ReportVersion.audit_mode` participates in hash; share caller must match approved mode; L0 always refused |
| Future share grant/policy | Reject future issued_at/created_at; revoked/expired cases retained; naive share clock raises domain refusal |
| Token format and approvals | Reject nonhex token hashes; approved_by/approved_at must match review decision; unauthorized roles still refused |
| Business confirmation | Qualified verifier must match confirming Owner; service cannot confirm E3; unauthorized roles cannot override via booleans |
| Policy host entries containing paths/query | Require bare host entries before syntax checks; does not implement DNS/SSRF protection |
| Non-JSON financial values | Reject NaN/Infinity before JSON Schema validation; Decimal boundary and same-currency/unknown-cost tests retained |
| Idempotency scope delimiter | Encode a structured tenant/key pair; defensive even outside valid tenant grammar |
| OpenAPI V1.1 mismatch | Restore authenticated health; require Idempotency-Key on all writes with conflict responses |

Compatibility: this unpublished draft adds required `ReportVersion.audit_mode` and changes review/share
function inputs from trusted bare IDs to scoped records. Fixtures and tests are updated together;
no live consumers exist. Full manifest format and adapter prerequisites are in
[contract notes](../../contracts/v1/README.md).

Trust boundary: domain actors, repository records, `receipt_verified` and `qualification_confirmed`
remain caller-supplied preconditions. Hash equality is integrity binding, not identity authentication,
source ownership, persisted revocation, actual VF receipt verification or AI semantic validation.
`validate_existing_grant` alone is not report access authorization. URL checks are syntax/policy
only; RA-1 must implement DNS binding, redirect and network-layer protection. RA-4 must supply
authenticated identities, atomic storage/queues/budgets and authoritative business receipts.

### F3 — CI evidence and precise blocker

Workflow `413356026`, run **42840530620**; branch/head match the baseline. Jobs:

| Job | Matrix | started_at / completed_at (UTC) | steps | runner_id |
| --- | --- | --- | --- | --- |
| 129914229311 | 3.11 | 2026-11-10T15:04:18Z / 15:04:20Z | 0 | 0 |
| 129914229937 | 3.13 | 2026-11-10T15:04:18Z / 15:04:20Z | 0 | 0 |

Check-run failure annotation explicitly states:
> The job was not started because recent account payments have failed or your spending limit
> needs to be increased. Please check the 'Billing & plans' section in your settings

Evidence: [raw jobs](ra0f-evidence/baseline-ci-jobs.json),
[raw annotations](ra0f-evidence/baseline-ci-annotations.json),
[job-log fetch failure](ra0f-evidence/baseline-ci-log-fetch.txt).
An Ubuntu-label migration annotation is only a notice, not the failure cause.
The provider identifies a billing/spending-limit category, but does not identify which account
condition or amount; do not claim a precise unpaid balance or outage.

Workflow review: push to this feature branch + pull_request events; ubuntu-latest;
3.11/3.13 matrix; contents:read; 12-minute timeout; same six commands as local; no secrets or
production dependencies. Both push and PR may create runs for a commit. YAML/trigger/installation
steps did not cause this pre-runner rejection. No retries, dummy commits, disabled tests or gates.
Owner must inspect Billing & plans, resolve payment or explicitly authorize an appropriate limit;
then run the existing workflow on the accepted SHA. No account change or spend is authorized here.

### F5 — admission recommendation

See [RA-1 work packages and security matrix](RA1_ADMISSION_AND_WORK_PACKAGES.md).
L2M source candidate/actual dependencies are recorded; license/usage right remains unconfirmed.
The complete clean local suite is sufficient substitute engineering evidence for Owner to review
RA-0 independently of CI, not authority to waive CI, merge or start RA-1 automatically.

Unresolved: hosted CI/account blocker; Owner contract/security sign-off; L2M use rights and future
RA-1 authorization. RA-0C generic fixtures are not domain-specific rule accuracy measurements;
real browser/network/DB/identity/model/commerce verification remains explicitly later-stage work.
No HTTP crawler, browser collection, LLM, Supabase, API/Worker service, VF modification, customer
message, production data, merge or release was introduced. Changes stay in the RA-0F allowlist.

## Historical records below (superseded by RA-0F verdict above)

## Scope / authority
Baselined from `main` SHA `43817d1cd0badf2c2223f98bc8fe322e4f1419c7`.
Authority: Product Charter V1.1 > accepted ADR-0001/0002 > current architecture V1.1 > master plan.
RA-0 permitted: JSON Schema/OpenAPI, pure-domain constraints, synthetic fixtures and CI only.
Forbidden: website access, DNS fetch, Playwright, LLM calls, customer data, DB, production deployment,
marketing/lead contact, Vey2GE live connection, L2M code reuse, RA-1.

## Contract decisions
- 16 named JSON Schema 2020-12 definitions; one OpenAPI 3.1 contract-only document.
- Version is required: `schema_version=1.0`, separate from report content version and policy version.
- Opaque string IDs intentionally used; UUID/ULID finalization deferred without changing V1 invariants.
- Null usage amount/token/provider/price means unknown, not zero.
- L0/L1 `PUBLIC_READONLY_RESEARCH`; L2 requires owner authorization, non-expired bounded policy.
- AuditRun execution stops at REVIEW_REQUIRED. ReportVersion approval requires precise human
  ReviewDecision bound to version/hash; ShareGrant separately grants distribution.
- External E2 requires VEYFRONT saved inquiry receipt; E3 human qualification evidence.
- JSON Schema is shape authority, Python functions implement cross-entity checks.

## Security caveats
The RA-0 `syntax_host` gate is syntax-only and **is not a complete SSRF defense**.
No DNS lookup, IP binding, redirect interception, Chromium network policy, egress firewall or robots
enforcement exists yet. Even accepted syntax MUST NOT be used to fetch real URLs.
Reviews/shares/queues are pure, in-memory contract operations without persistent authorization,
atomicity, secure token generation, authentication or crash recovery.
AI reference checks verify IDs, **not semantic support**; RA-3 will require factual/human validation.

## Reproduce
Use Python >=3.11,<3.14; local reference 3.13.5.
```sh
python -m pip install -e '.[dev]'
python -m compileall -q vrae
ruff check vrae tests --select E4,E7,E9,F
mypy vrae
python -m pytest -q
python -m pip check
```
CI tests 3.11 and 3.13. A local run and CI run must separately report real exit codes.
No Mock PASS substitutes for real collection/database/browser/API validation.

## RA-1 prerequisites (not authorized)
1. Architect/sign off RA-0 contracts and validate any policy-mode changes.
2. Audit L2M candidate read-only module license, exact source SHA and dependency graph.
3. Design isolated Worker with DNS pinning, redirect per-hop/asset policy, IPv6, egress firewall;
   test actual DNS rebinding and browser subrequests in disposable sandbox.
4. Define robots/terms and specific permitted test domains before ANY live network sample.
5. Keep evidence hashes immutable and budgeted access within tenant and L0/L1/L2 authorization.

## Documentation observation
The planning documents describe future/past phase statuses as of 2026-11-10. This file and
the Draft PR are the execution record. These plans must not be interpreted as deployed capability.

## Current validation status / infrastructure blocker

- GitHub Draft PR: https://github.com/gloweaseco-leo/VRAE/pull/1
- GitHub Actions run 42830253941 and later run 42830780239: **FAILURE BEFORE RUNNER START**.
  Jobs have runner_id=0 and no executed steps; job-log endpoint returned BlobNotFound.
  This is an infrastructure block, not passing or failing pytest assertions.
- Separate schema shape/enum/pattern fixture inspection on the exact GitHub
  branch returned **41/41 expected** (16 legal, 25 illegal) using an independent
  in-memory validator, which is **NOT official jsonschema / Python pytest**.
- No local Python test process on the exact branch has yet produced a verified
  exit code. RA-0 final engineering acceptance remains **BLOCKED**, not PASS.
- Never infer full correctness from structurally valid fixtures or a draft PR.


## Latest independent source audit (RA-0, branch only)

- 12 Python production/domain source files inspected for imports and calls indicating
  external HTTP/Playwright, database clients, LLM, shell execution and email.
  **0 flagged patterns**. This is static pattern analysis, not a network isolation proof.
- 38 pytest test functions declared across two test modules; these include parametrized
  URL, role, policy, state, evidence, approval, share and cost cases.
- 25 synthetic URL syntax cases; 19 legal contract JSON cases; 36 illegal contract
  JSON cases = 55 contract fixtures; plus 48 generic rule expectations. Contract-only independent checker
  yielded **41/41 expected outcomes**, not the pytest/CI result.
- Added conditional schema constraints for deep policy consent, AI NOT_RUN, human
  ReportVersion approval and SalesHandoff receipt/evidence.
- Explicitly reject L0 report distribution. External E2/E3 receipt/confirmation in RA-0
  are caller-supplied preconditions; authentic VF receipt verification is RA-4.
- Actual Python pytest, mypy, Ruff and compileall results on this exact branch remain
  **unverified** due absence of a runnable GitHub-hosted runner and inaccessible
  private repo from the local execution container.
- **Acceptance: BLOCKED / NO-GO for RA-1 until real Python test execution and review.**

## RA-0 supplemental local validation: 2026-11-10 (offline, not original CI)

### Exact source material and methodology
- Domain Python modules were read from the private GitHub Draft PR and rebuilt in an
  independent local validation working directory; schema files also originated from GitHub.
  New test harnesses are **independent**, synthetic and local-only, not the repo's two
  original test modules. The final semantic schema rules were applied to the local copies
  and checked for equivalent JSON contents.
- Environment: local Python 3.13.5, pytest 9.0.2, jsonschema 4.26.0.
- Exact local command: `python -m pytest -q tests/test_independent_ra0.py tests/test_independent_schemas.py`
- Observed result: **165 passed in 1.22s, exit code 0**. This includes 81 domain
  guards and 84 structured schema/checksum and cross-field checks.
- `python -m compileall -q vrae` -> **exit code 0**.
- All **17** schema documents passed `Draft202012Validator.check_schema`.
- The pre-patch `0.10 + 0.20 <= 0.30` budget test surfaced floating-point false
  blocking (`LIMIT_EXCEEDED`); branch now uses Decimal and same-currency checks.
- Latest branches include conditional status/ref invariants and explicit `UNKNOWN`
  evidence/snapshot nullable hashes, while `FETCHED`/`OBSERVED` still require hashes.
  **19 VALID / 36 INVALID** hand-authored contract fixtures, **25** URL syntax
  examples, **48** versioned generic candidate-rule expectations (these are fixtures,
  not RA-2 implementation).
- No real website, model, browser, production data, DB or external contact used.

### Remaining gates (do not claim complete RA-0 PASS)
- GitHub Actions latest head still FAILS before a runner starts (no executed
  pytest, ruff, mypy or compileall steps). Runner allocation/cause is unknown.
- Original repository `tests/test_domain.py` and `tests/test_contracts.py` have
  **not run to completion on this exact PR head**. The independent 165 passing tests
  are useful evidence but **cannot** replace repo-original full-suite results.
- Ruff and mypy were not installed in the offline local container. The shared
  environment `python -m pip check` exited 1 on unrelated preinstalled
  moviepy/pillow versions; rerun in a clean isolated environment.
- No live SSRF defense exists; URL validation is **syntax only**, RA-1 tests are
  separately gated and not authorized.
- Final RA-0 acceptance: **PARTIAL IMPLEMENTATION / BLOCKED ACCEPTANCE**.
  Keep Draft PR, never merge/deploy, and do not enter RA-1.

## Final independent QA supplement (same RA-0 scope, 2026-11-10)

- GitHub implementation head before this record: `13d6160584d771effa852908b08d4c8a5fa285a1`.
- Exact source equivalence was verified against GitHub for **all 12 domain Python
  modules** (byte-level FNV-1a) and **all 17 JSON Schemas** (canonical JSON
  FNV-1a). This shows the independent offline tests inspected actual PR content.
- Python 3.13.5 / pytest 9.0.2 / jsonschema 4.26.0 / PyYAML 6.0.3.
- Local independent command:
  `python -m pytest -q tests/test_independent_ra0.py tests/test_independent_schemas.py`
  -> **168 passed, 0 failed, 0 skipped, exit code 0**.
- `python -m compileall -q vrae` -> **exit code 0**.
- All 17 schemas checked with `Draft202012Validator.check_schema`.
- Hand-authored repository contract fixtures now contain **19 valid and 36
  invalid** cases. Other checked-in input fixtures: **25** syntax-risk URL cases,
  **48** generic rule expectations across the versioned catalog of 16 rules.
- Defects fixed in this RA-0 branch: float rounding false budget block
  (Decimal and currency equivalence); impossible UNKNOWN snapshot/evidence hashes;
  observed facts wrongly permitted from ACCESS_BLOCKED/unhashed snapshot.
- Enforced valid `ACCESS_BLOCKED -> UNKNOWN` but refusal for
  `ACCESS_BLOCKED -> OBJECTIVE`; an OBSERVED fact requires a hashed fetched page
  and hashed evidence.
- GitHub Actions latest head still failed before runner execution (e.g. run
  `42839994182`); runner steps did not start. The precise provider-side cause is
  **unconfirmed**, do not claim it is a source-code test failure.
- **Original repo test suite has not completed on the exact PR head**;
  Ruff/mypy not installed in the isolated offline environment. `pip check`
  on a shared environment failed for an unrelated preexisting
  moviepy 2.2.1 / pillow 12.3.0 incompatibility; this is not proof of
  a VRAE dependency conflict.
- **Gate remains BLOCKED**, PR stays Draft, no merge, no deployment, no RA-1.

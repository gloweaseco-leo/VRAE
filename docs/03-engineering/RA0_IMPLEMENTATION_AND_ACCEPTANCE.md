# RA-0 implementation and acceptance record

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
- 25 synthetic URL syntax cases; 16 legal contract JSON cases; 25 illegal contract
  JSON cases = 66 structured fixture cases. Contract-only independent checker
  yielded **41/41 expected outcomes**, not the pytest/CI result.
- Added conditional schema constraints for deep policy consent, AI NOT_RUN, human
  ReportVersion approval and SalesHandoff receipt/evidence.
- Explicitly reject L0 report distribution. External E2/E3 receipt/confirmation in RA-0
  are caller-supplied preconditions; authentic VF receipt verification is RA-4.
- Actual Python pytest, mypy, Ruff and compileall results on this exact branch remain
  **unverified** due absence of a runnable GitHub-hosted runner and inaccessible
  private repo from the local execution container.
- **Acceptance: BLOCKED / NO-GO for RA-1 until real Python test execution and review.**

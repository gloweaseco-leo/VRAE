# B5A local acceptance results

Entry main: `6257ad3acb09d046d954301117134f6992c02d84`.
Branch: `codex2/ra4c-b5a-signed-review-read-testonly`.
All results below are actual executions. This is local acceptance, pending the
single Draft PR's first hosted cycle and independent Owner FINAL PASS.

| Gate | Python3.11 | Python3.13 |
| --- | --- | --- |
| New real PG16 / signed session / HTTP security |57 passed|57 passed|
| New actual Chromium1280/375/320 |81 assertions,18 full-page screenshots|81 assertions,18 full-page screenshots|
| New business DB state |21 table fingerprints unchanged|21 table fingerprints unchanged|
| P1 original v1 / v2 |54 /54 passed|54 /54 passed|
| P2A original |86 passed|86 passed|
| P2B1 original |131 passed|131 passed|
| B2 original crypto / real PG |73 /30 passed|73 /30 passed|
| C3 original real PG / actual Chromium |29 /105 passed|29 /105 passed|
| Ordinary current full suite |2443 passed,25 original host-only isolation skips|2443 passed,25 original host-only isolation skips|
| Included native Review / QA V2 |127 /118 passed|127 /118 passed|
| Compile / Ruff / mypy / pip check |PASS,70 typed source files|PASS,70 typed source files|

No new skip or xfail was introduced. The25 unchanged default markers prohibit
running isolation tests on the host. Separately, the original disposable Linux
namespace/firewall entrypoint executed all24 network/TLS/kernel cases, and the
original sandboxed Chromium/Worker supervisor passed all16 adversarial scenarios,
including automatic browser termination. Original sources, seccomp, capabilities,
checks and dependency locks were unchanged; only owned image tags were selected.
See [isolated receipts](evidence/isolated-gates.json).

The22 new default boundary tests also passed with PG and cryptography imports
explicitly blocked, preserving the original dependency-light default CI.

Final B5A runs are `sealed-311-01` / `sealed-313-01`. Their drivers verified
source-at-start equals source-at-end before exporting evidence. Native XML SHA256:

- 3.11: `4d053b1e3129dfe96a471c41ee400686b585d71ed0ad0ffed169ddc5d4a41544`.
- 3.13: `17e726832b252cacab7980c3ffbfd84ceef2ad99ff22bf0b7126ee8c592b65ff`.

Local execution used the uncommitted working source, with HEAD still at the entry
main. The sealed source manifests pin the actual added code by LF SHA256; the
commit is subsequently checked against those blobs. After sealing, only the
unused result classifier `local_report.py` was corrected to preserve the original
25 skip records and link the successful original C3 retry. It was then executed
against both native result sets. Runtime, security tests, browser flow, SQL and
accepted files were unchanged. The precise reporting-only delta is recorded in
[reporting-source-delta.json](evidence/reporting-source-delta.json).

Actual Reviewer reads returned original BYTEA for both cases; source SHA256:

- 404: `3931962da536faa57f975b751ebdeff8141737feed5d15a3aeee52bd50e5e01a`.
- 200: `f679bb4bf463e788775b2e2c163e0b424187fab6098e8df9a0e66c00e780c614`.

The negative gates observed real SQLSTATE42501 for revoked authority, wrong exact
locators, and65 direct private-table operations across13 tables. Altered held
content/HTML pins were checked against actual PG originals; immutable constraints
were never disabled to manufacture corrupt records. DB-down produced denial with
no fixture fallback. Token replay, anchor/binding invalidation, expiry, forged
authority, Host/Origin/CSRF, malformed/oversize wire input and effective mutations
were denied. No ReviewDecision, approval, ShareGrant or B4 API was created.

Bounded evidence is in [3.11](evidence/sealed-311-01/),
[3.13](evidence/sealed-313-01/), and the original-suite
[3.11](evidence/legacy-311/) / [3.13](evidence/legacy-313/) receipts.
Raw XML, logs, credentials, private profiles and original BYTEA remain in ignored
local runtime storage. Public export contains sanitized status XML, raw digests,
actual role/RLS/ACL facts, fingerprints and synthetic screenshots.

Development failures and environment retries remain in
[DEVELOPMENT-LEDGER.md](DEVELOPMENT-LEDGER.md). No accepted guard, grant, DDL, old
workflow, rule, Gold or frozen charter was modified. Real identity, real decision,
customer sharing and deployment remain outside this slice.

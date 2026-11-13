# B5A development evidence ledger

Entry: accepted main `6257ad3acb09d046d954301117134f6992c02d84`.
Authority: Owner Issue79 comment6859365279. No accepted source/grant/DDL edits.

- Initial probe import failed while the independent locked target installation
  was still finishing (`_cffi_backend` unavailable); no PostgreSQL access occurred.
  Both installs subsequently exited0 and the explicit imports passed.
- Actual entry public-API probe passed for both404/200: accepted signed B2 check,
  real `p2b1_test_a_reviewer.load_target`, immutable Native load, one/zero finding
  and six/three Claims. No APP read and no migration/grant widening.
- Actual signed-session HTTP-to-existing-SSR probe passed for both404/200.
- `development-311-01`: 55 JUnit records including teardown errors (52 collected
  cases); raw JUnit SHA256
  `fdf4b0d20b12c0715dc4d18c25f125a0882d9725aa3eddfcfc3ca67ec04bedd5`.
  Two presentation assertions used `NOT_APPROVED` where the existing frame uses
  `NOT APPROVED`. DB-down negative passed, but the fixture's restart recovery
  incorrectly reused the old dynamic port, causing later connection/teardown
  cascades. Corrected only the new tests and owned transport re-discovery.
  The old private zero-write receipt from that RED is **not valid zero-write
  evidence**: its finally block previously marked success even after incomplete
  verification. New receipts require the actual full fingerprint assertion to
  complete before any success flags are set. Original RED files are retained,
  not rewritten or used as successful acceptance.
- `development-311-02`: 52 cases, 51 passing. Raw JUnit SHA256
  `ca21f3ea152eeb110744ca9c0a10255bc3c1c4359b4a212169c3a290d3081122`.
  The private-SQL test's setup used a regclass cast, which PostgreSQL correctly
  denied for the private schema before the65 intended statements ran. The new
  test now obtains a column name from public pg_catalog joins, without a grant.
  No accepted permission failure was bypassed.
- `browser-dev-311-01`: actual separate-process Chromium PASS,81 assertions,
  18 screenshots at1280/375/320. Actual mid-page PG denial42501, profile anchor
  revocation, real HTTP restart and consumed-token rejection passed. All21
  business-table fingerprints were unchanged. This is one minor's browser
  evidence, not the entire dual-minor acceptance declaration.
- `legacy-311-01` / `legacy-313-01`: original P1 first stage passed; then the new
  output-relocation adapter failed when the old lab CLI recreated its module as
  `__main__` and reset its output root. Resources were cleaned. The new adapter
  now calls the original public bootstrap API directly, leaving accepted guards,
  test assertions and files unchanged.
- `security-311-03` / `security-313-01`:56/56 each, no skip/xfail. Protected
  native JUnit SHA256 respectively
  `f4cdf92c74b33acf42d3ca6300972578588c722684633181b42e85834caae037`
  and `942d366931d6593689942b1aa9c460f7d705e0e66d949881c9c648e8e23cfe47`.
- `browser-313-01`:81/81 actual Chromium assertions and18 screenshots passed;
  independent PG16 and unchanged21-table fingerprint proof, including42501.
- Additional code review identified stdlib HTTP parser errors that can precede
  the application and reflect malformed request lines. Added a constant error
  response and real Socket negative. First targeted wire runs found the stdlib
  HTTP/0.9 sentinel suppressing headers (fixed body was already non-reflecting).
  Emit a fixed HTTP/1.0 error including no-store even for invalid version syntax.
  Original RED XML hashes:
  `8f8ae61247148f1dcae4235e5568cf378bb0f05f79a2ae15aec8bef1f8bdc116`
  and `8dd26b55b35da871d3baf3b3d767dbea1731b30f36261310e339b9956261853c`.
  The final dual-minor driver repeats the complete security and browser gates
  after this transport change, with full-page screenshots at each tested width.
- `review-311-01` / `review-313-01`: original P2B1 executed131/131 passing in
  each minor. The following B2 stage initially selected its directory, which has
  no default `test_` files, and correctly exited5 with0 collected. The new runner
  now selects the original explicit `tests/identity/crypto_cases.py`. Separate
  `identity-311-01` / `identity-313-01` stages passed73 pure and30 real-PG cases
  each. No zero-collection stage is counted as passing evidence.
- `local-final-311`:57/57 security passed, native XML SHA256
  `d42e12db73155820a2337d392f7d5a9906f2a8b7306638c5b85dfe0921c2ac9d`.
  `local-final-313`:56/57; native XML SHA256
  `ef3651f0fd38cd062dc1986b04443e30288f826eac0f73e25e7c3078e58d5fa5`.
  The one oversize24577-byte request was denied without a source read, but
  closing with unread request bytes produced WinError10053 before the client
  received413. The test expectation was not relaxed: the new HTTP adapter now
  consumes at most BODY_LIMIT+1 transport bytes, never sends excess bytes to the
  application, then returns its fixed413. Full final drivers are rerun as
  `sealed-311-01` / `sealed-313-01`, with source-at-start and source-at-end equality.
  The earlier311 browser run overlapped this new transport fix; its later source
  snapshot is not an exact-source acceptance receipt. Earlier development exports
  are retained privately, not committed as final proof.
- `sealed-311-01` / `sealed-313-01`: complete final57/57 security,81/81 actual
  browser assertions,18 full-page screenshots each, actual42501 and unchanged
  21-table fingerprints. Start/end source equality and bounded export passed.
- Original full suites completed2468 records each:2443 passed,0 failures/errors,
  25 unchanged host-only isolation skips. An initial summary treated these skip
  records as RED; corrected the reporting classifier, not the original markers
  or expectations. Dedicated original isolated gates subsequently passed24 real
  network/kernel cases and16 Chromium/Worker scenarios with actual termination.
- `legacy-311-02` original C3 browser initially timed out before any assertion or
  PG read. Chromium stderr recorded Windows sandbox executable access denied
  0x5 and network-service crash. Approved execution outside the tool sandbox,
  with Chrome's own sandbox and exact test source intact, passed105/105 in fresh
  PG (`c3-retry-311-01`). Original3.13 C3 browser passed105/105 in its first run.
- The obsolete initial driver's later P2B1 selector named a nonexistent
  `security_cases.py`, causing0 collected/exit4. This stage is not counted as
  evidence. The explicit accepted `cases.py` + `parity_cases.py` executions in
  `review-311-01` / `review-313-01` independently passed131/131 each.
- Only the result classifier changed after the runtime seal: it now preserves
  original skip status and links the successful independent C3 retry. Both
  actual result aggregations passed. Exact old/new hashes are published in
  `evidence/reporting-source-delta.json`; sealed runtime/test/browser code did
  not change. No original RED/XML/log was rewritten.

This ledger is history, not a final local/hosted PASS declaration. Raw logs/XML,
credentials, profiles and original source objects remain private and uncommitted.

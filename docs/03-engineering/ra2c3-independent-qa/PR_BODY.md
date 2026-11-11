Independent black-box QA for #35. Production C3 builder is owned by Codex-1 (#34).
This Draft contains only the exclusive Codex-2 test, independently authored
synthetic inputs, frozen historical pins and QA documentation/actual records.

Contract/test source commit: `5dcb09526c1dc08a2d7060866ab96bdfc3fe017d`.
Accepted base: `4b5ebe689f048ba20d38354ae7c03d4bbaf37c6a`.
Test file SHA-256: `2c35973cd9e811961a8e68109e37a1db2d00908fabdaeb565f5c2331118fb110`.

139 tests cover source-only TRUST proof, two separately pinned positive and
captured CONTACT 404/410 packs, UNKNOWN/ACCESS_BLOCKED scope, source/execution/
package tampering, authorization/time/location/pins, private-unapproved-
unshareable invariants, genuine CTA native bridge and C0/C1/C2 sealed replay.
Every mutation requires real successful C3 build/load/verify first: unsupported
version rejection cannot masquerade as attack-defense success. No skip/xfail/stub.

Actual accepted-main runs on Python 3.11.15 and 3.13.13 each returned exit 1:
**23 passed, 1 failed, 115 prerequisite errors, 0 skipped**. This is
**PRE-IMPLEMENTATION EXPECTED RED**, because main lacks `ra2c3-1.0.0`.
It is neither a candidate vulnerability nor GREEN CI. Raw stdout/stderr, JUnit,
commands, timestamps and hashes are committed under the QA `runs/` directory.
Ruff E4/E7/E9/F passes on owned Python files.

Owner clarification is enforced: real captured CONTACT 404/410 can yield one
bounded CTA-02 defect while TRUST remains UNKNOWN; it cannot yield TRUST PASS
or a TRUST defect. A separate full positive pack proves the positive groups.

**Candidate gate completed:** Codex-1 Draft #36 exact functional HEAD
`995325203be1385b98cc888f8b2dd7cc9e85ddcf` ran the **unchanged** frozen tests in
an isolated archive. Python 3.11.15 and 3.13.13 each returned exit 0:
**139 passed, 0 failures, 0 errors, 0 skipped**. Import paths prove the archived
implementation was used; original candidate file hashes were unchanged.
Actual commands, JUnit, stdout, hashes, archive manifest and separately pinned
scenario refs are committed in `docs/03-engineering/ra2c3-independent-qa/runs/`.
No genuine implementation failure was exposed, and no production repair or
test weakening was performed. Functional HEAD was read back unchanged after
the runs; any subsequent functional revision requires another exact-HEAD run.

Four hosted CI jobs on #36 for this HEAD were independently read back as real
success (raw metadata and direct links in `RESULTS.md`). These do not turn this
QA PR's baseline-based expected RED CI into green. No CI changes were made.

Keep Draft. Do not merge while main is incompatible. Owner acceptance remains
pending. No Gold, real website diagnosis, sharing/report generation, deployment,
self-merge or RA-3/4/5/6 work.

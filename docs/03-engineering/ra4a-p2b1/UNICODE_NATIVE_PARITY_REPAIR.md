# Native/SQL parity repair — candidate 292b030 withdrawn

The 98-case source and evidence commits remain preserved, including their actual
dual-Python PASS and six hosted SUCCESS results. Those results did not cover the
following new self-review finding and are not sufficient final acceptance.

On real PostgreSQL16, POSIX `[:space:]` differs from frozen native Python
`str.strip`. The read-only classification probe observed U+00A0, U+1680 and
U+202F as nonblank in PG while blank in native. Actual minimal transaction repro:
take accepted 404 proposal and change only reason to U+00A0. The native Python
port rejects `D_UNTRUSTED_TEXT`; direct SQL committed a SIMULATED test receipt.
Actual pre-fix regression: 11 PASS / 1 FAIL, first failure U00A0.

Full original failure stdout/stderr, JUnit, source SQL/test snapshot and actual
receipt/ledger counts are in `unicode-pre-fix/`. The earlier read-only probe and
its source/metadata are under `post-ci/292b030.../`. The committed test receipt
has native_decision/native_approval/share_grant=null and external_visibility=false.
No authentic approval, access or sharing was created. The discrepancy is still
a defect in the new SQL validation boundary, not a contradictory test oracle.
It was reported on [PR #71](https://github.com/gloweaseco-leo/VRAE/pull/71#issuecomment-6841326537).

The repair touches only new migration 0003 and the new harness/tests. Replace
locale-sensitive blank classification with the exact native whitespace repertoire
using Unicode character-set trimming; preserve C0/bidi and size restrictions.
Use exact JSON value comparisons for coverage/section hash pins to avoid text
coercion. Frozen native validation, 0001/0002 and all accepted contracts/tests
remain unchanged. Dispose old fixture DBs; never rewrite an applied migration
ledger in place. All final validation begins from fresh v1→v2→v3 clusters.

`integration/ra4a/p2b1/cases.py` remains byte-for-byte the frozen V2 98 tests.
Add separate `parity_cases.py`: all 29 native Unicode whitespace blank reasons,
one legitimate padded-text positive and three numeric JSON hash-pin negatives.
Frozen V3 is the original 98 plus 33 actual database cases = 131, no skip/xfail.
The prior original 98 assertions are never removed, loosened or rewritten.

`FROZEN_MATRIX_V3.json`, `SOURCE_SCOPE_V3.json`, `LOCAL_DUAL_ACTUAL_RESULTS_V3.json`
and `ARCHIVE_RECEIPT_V3.json` version the stronger candidate/evidence separately.
Old V1/V2 source, RED/GREEN, SHA and raw archives remain historical evidence.
The final exact V3 HEAD must obtain six new hosted SUCCESS checks and full raw
checkout/artifact audit before submitting for Owner FINAL PASS.

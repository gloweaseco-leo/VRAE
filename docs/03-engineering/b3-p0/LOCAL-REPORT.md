# B3-P0 pre-push local receipt

Owner authorization: [6867707779](https://github.com/gloweaseco-leo/VRAE/issues/77#issuecomment-6867707779).
Accepted main at start and final fetch: `cbcdb6f62d402861e8a12392f53061109a4a7d8b`.
This is an independent TEST_ONLY transaction slice, not full B3 or a human decision.

| Actual run | Result |
| --- | --- |
| Python 3.11.15, fresh PG16 + separate restore PG16 | 128 passed, zero failures/errors/skips |
| Python 3.13.13, fresh PG16 + separate restore PG16 | 128 passed, zero failures/errors/skips |
| Each B3 suite | 106 transaction cases + 17 HTTP/recovery cases + 5 contracts |
| Native Linux default full suite | 2448 passed, 25 original isolation skips, zero failures |
| Original namespace/firewall/capability-drop full runner | 2472 passed, 1 browser-lab skip; all five compile/lint/mypy/pytest/pip gates exited zero |
| Final current mypy | 74 source files, success |
| Windows legacy pipeline/domain follow-ups | 43 passed / 162 passed, unchanged tests |

Final B3 run labels: `final-311-04` and `final-313-04`; both record source_unchanged=true.
Raw native JUnit SHA256:

- 3.11: `8bd33f805acbeb2f3ec2819f6c4c6ed79fe9e4e580f6924d2c0476457465fb94`
- 3.13: `12f217e90533971c77433fea7ae5c85740d5e728111f23190403aa4f145606ce`

DDL LF SHA256: `20389c5d7be68a00f61cbb2509b3954f91fbaacaed928c270f10c395ea0c4185`.
All nine B3 table/data/schema/security restore roots match source, as do the accepted
business manifest roots. All nine raw table ACL representations differ after restore
but all expanded permission sets match; raw arrays are retained separately. NULL and
empty ACL are not collapsed. Actual restricted SQL returns 42501 where required.

The original 6,730 accepted files retain every Git blob and mode. Only the authorized
new namespaces and one new workflow are staged. The original migration ledger stays
at exactly 0001–0003; B3's standalone bootstrap ledger is independent.

Native full-suite source tree and newline audit: `NATIVE-TREE.json`. The only later
runtime change was the new B3 HTTP bounded-frame refusal ordering; the final dual
PG/HTTP suite and final current mypy cover that change. No accepted/default test
source changed. Native image/archive, credentials and dumps remain local/private.

Original red runs are retained, not counted as acceptance: development 119/121;
expanded deadline run 127/128 per minor; broad Windows default 2446 passed, 2 failed,
25 skipped; and an interrupted Linux lab-environment setup run. `IMPLEMENTATION.md`
explains each correction. Raw JUnit/log hashes and case IDs are in `LOCAL-RECEIPT.json`;
raw failure traces remain private. No assertion, ACL check or frozen QA was removed.

The YAML matrix is 14 unchanged hosted jobs + 2 new B3 jobs = prospective 16.
Hosted CI has not yet been claimed green. One controlled push and one Draft PR may
follow this receipt, then the first hosted cycle must be recorded and work stopped
for Owner exact-SHA FINAL PASS. No rerun/correction push/merge/deployment is authorized.

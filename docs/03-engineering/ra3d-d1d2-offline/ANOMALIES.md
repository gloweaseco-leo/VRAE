# Actual anomalies and versioned corrections

## Initial candidate 6c6275f

The first 93-test local iteration passed with four standard pytest warnings:
record_property under default xunit2. The next 123-case suite passed. Final local
JUnit uses explicit legacy format for those properties; no test assertion changed
because of the warning. Original JUnit is preserved.

The initial candidate completed four real hosted CI jobs in run 43210583446:
both Python jobs 2184 PASS / 25 existing SKIP, isolated HTTP 2208 PASS / 1 existing
SKIP, original isolated browser SUCCESS. Original logs and all four checkout
records are under initial-ci-6c6275f. This earlier success is not final acceptance.

Self-review independently reproduced two initial-sidecar strict-type defects:
Python dict equality allowed policy_version=True to equal integer 1; expected
issue count True likewise equalled 1. `diagnose_policy_types.py` and the original
strict-type-initial-probe.log retain actual ACCEPTED outputs and both digests.
These are defects in this new initial D2 code, not RA3C/Guard or test-oracle faults.
No real approval, grant or authority was ever produced: production port still
always denied and all outputs were synthetic/nondurable.

Correction: compare canonical scope bytes; strictly type/bound held issue count
and SHA fields; reject unknown source envelope fields; suppress reflective native
exception contexts. Four new dedicated regression cases are added. Original 123
cases and both source fixtures remain intact; final count is 127, no skip/xfail.
The exact source revision and Git diff are retained by ordinary additive commits.

Two redundant local full runs on initial 6c6275f were deliberately interrupted
after the complete initial hosted full runs had already succeeded, to advance
the independently confirmed correction. Exact commands, partial stdout/stderr,
elapsed 977.812 / 974.402 seconds and termination code 4294967295 are retained in
runs/6c6275f.../py11 and py13. These are INTERRUPTED, never PASS, no completed full
JUnit or invented test count. Their dedicated 123-case JUnit had actually passed.
Only owned children with command line matching this task's full.xml were stopped;
an initial Stop-Process call raised a PowerShell host NullReferenceException, also
outside sandbox; using -Force -Confirm:false then stopped the two verified owned
children. No other process or filesystem state was removed.

Final-source local runs explicitly use regress.py --targeted: compile/ruff/mypy,
all 127 reviewing cases with full JUnit, pip check and deterministic native replay
scenarios/refusal codes on both Python versions. Full default regression on the
final source is required in both fresh hosted Python jobs and unchanged isolated
HTTP. This is an execution-location distinction, not skipped/xfail test cases.

## Raw evidence byte preservation

Git on this Windows workstation normalizes text line endings. The raw-local ZIP
is authoritative for exact original stdout/stderr/JUnit bytes and hashes; its
member manifest is verified before committing. Git text copies remain convenient
readable views. The original redirected D1/probe logs retain their actual Windows
encoding in that archive; they are not reconstructed success logs.

Existing historical RA3C V1 exclusion and previously accepted default test skips
are unchanged. No new reviewing case is skipped or xfailed. Existing CI/dependency
warnings are retained rather than remedied by unauthorized dependency/CI edits.

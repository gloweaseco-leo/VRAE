# PR #37 accepted-main integration

Authority: [Owner integration instruction](https://github.com/gloweaseco-leo/VRAE/pull/37#issuecomment-6799233828).
Accepted main: `91d408bcdbe0a6667c1e356723e3385465cdd6ae`.
Prior QA HEAD: `10b09efad8d198fda83f23f747169e891a95f99f`.
Normal merge commit: `bb4e007a501efd10cbfbf6eba17f55b5638ce827`.
No conflicts, rebase, force-push, cherry-pick or production edits.

The original 29 exclusive QA files, including all original run records, were
checked individually by Git blob against prior QA HEAD. All are unchanged.
Frozen test blob remains `004b1b7bedbe2478361a52e2668586502164d63a` from contract
commit `5dcb09526c1dc08a2d7060866ab96bdfc3fe017d`. Production paths match main.
New integration records live only in this additional directory.

`regress.py` runs both full-repository tests (with JUnit), verifies all 139
independent cases actually passed without skip/xfail, and runs the compile,
Ruff, mypy, pip and fixed historical RA-2A/B/C/D replay commands. It reads the
accepted synthetic/forged Gold verifier inputs solely as historical regression;
it neither changes labels nor performs human Gold review. A forged Gold exit 1
is an expected rejection, not an unexpected regression.

Each numbered log corresponds to its command in the runtime's `summary.json`.
The full pytest JUnit records preserve passed, failed, error and skipped cases.
Host-only isolation skips, if present, are distinct from the frozen QA suite;
real isolation is checked by the unchanged hosted HTTP/browser jobs.

`audit_ci.py` verifies actual hosted run/job success, exact run HEAD and each
job's `git log -1 --format=%H` checkout SHA. It also verifies the GitHub-generated
merge commit has exactly the held main and final QA HEAD as its two parents.
Final hosted logs are retained locally under ignored `.venv/qa37-final-ci/` and
linked in the PR's final audit comment, avoiding a post-CI change of final HEAD.

Environment exception: the initial fetch encountered sandbox Windows
`SEC_E_NO_CREDENTIALS`. The shell continued and merged the locally cached
`origin/main`, which already pointed to the exact Owner-provided `91d408b...`.
Fetch was immediately repeated with approved access and succeeded, independently
confirming the remote main was exactly that same SHA. No stale or unreviewed
code was integrated. This command sequencing exception is recorded explicitly.

## Retained Windows exceptions

Both first sandbox full runs reported 1442 passed, 25 pre-existing host-isolation
skips and 5 `tmp_path` setup errors (`WinError 5`, access to `pytest-of-liu`).
Both still passed all 139 frozen QA cases; no case was weakened or skipped.
All other 21 command expectations in each 22-command regression were satisfied.

The approved parallel reruns removed those setup errors but encountered file
I/O exceptions on existing historical tests: Python 3.11 had 5 `Invalid argument`
fixture reads (1442 passed / 25 skipped); Python 3.13 had the same 5 and one
transient `AuditRequest.schema.json` read failure (1441 passed / 25 skipped).
These failures remain in `python311-approved/` and `python313-approved/`.
The referenced files were independently checked present and unchanged.
An unchanged targeted Python 3.13 command:

```text
python -m pytest -q tests/findings/test_ra2c3_integration.py tests/findings/test_seo01_integration.py -k historical --tb=short
```

returned **5 passed, 197 deselected in 3.19s**, exit 0. This diagnostic is not a
substitute for full regression. Serial full reruns are recorded separately;
no specific root cause of the Windows I/O anomaly is asserted without proof.

## Final local full-regression result

The unchanged full test suite passed in the subsequent serial approved runs:

| Runtime | Passed | Failures / errors | Existing host-isolation skips | Frozen QA |
| --- | --- | --- | --- | --- |
| Python 3.11.15 | 1447 | 0 / 0 | 25 | 139 passed, 0 skipped |
| Python 3.13.13 | 1447 | 0 / 0 | 25 | 139 passed, 0 skipped |

See `python311-serial/` and `python313-serial/` for the full commands, raw logs,
JUnit and summaries. These local runs test the normal integration commit
`bb4e007a501efd10cbfbf6eba17f55b5638ce827`; the final PR commit adds only new
integration documentation/records/helpers. Hosted full regression must then
check the exact final PR HEAD and merge-ref, as independently recorded in the
final PR comment. No claim that earlier failures never occurred is made.

RA-3B issues #40 and #38 were read. No RA-3B code, worktree or branch is created
here. Its separate development remains conditional on Owner FINAL PASS and
actual merge of #37, followed by independent read-back of new main.

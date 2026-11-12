# Actual baseline results and pending candidate gates

Accepted main: `8379e5f63d3feaa66a646d8a19d866a693162c99`.
Final frozen tests/inputs: source commit `68336821bb2b8c919b0d04bd86400c165329d9a6`,
manifest commit / final local test HEAD `0c1fc1c2be98058c15d5fad7041c02099ef231fb`.
Later commits add only QA documentation and raw records, not frozen tests/inputs.

| Runtime | Final independent QA pytest | Final full pytest | Other actual checks |
| --- | --- | --- | --- |
| Python 3.11.15 | exit 2; one collection error; zero skip | exit 2; one collection error; zero skip | All 22 other expected command exits matched |
| Python 3.13.13 | exit 2; one collection error; zero skip | exit 2; one collection error; zero skip | All 22 other expected command exits matched |

Both are **PREREQUISITE_RED_CONFIRMED**, `feature_qa_pass=false`. Genuine error:
`ModuleNotFoundError: No module named 'vrae.interpretation'`. No feature tests
executed on main; 224 is the static planned-case count, **not** a pass count.
No skip/xfail/stub or changes to CI hid the collection failure. The recording
runner's successful exit certifies expected RED recording, not feature success.

Each runtime's 24 recorded commands independently verify:

- 14 newly generated synthetic captures through original EvidencePack and C3
  replay, including independently expected positive and UNKNOWN/BLOCKED outcomes;
- compileall, Ruff, mypy, pip dependencies;
- genuine RED of frozen independent QA and combined full pytest;
- all 15 historic RA2A, B0-B6, B6 execution, C0-C3, D0/D1 fixed verifiers;
- accepted RA3A offline Fake/NOT_RUN demo, with no real calls/costs;
- expected forged-Gold refusal exit 1, without human label changes.

Initial V1 baseline runs were on `82c08e282853d104ee3ae40afb8881c63d8ef138`.
Both also recorded the same expected import RED and all 24 expected exits.
They are historical records, not evidence for the final amended mutation source.
Final runs explicitly pin the final freeze; both old and new records retained.

`baseline-raw.zip` contains all **108** original log/JUnit/summary files from the
four runs, ZIP SHA256
`c2e2a7512bff7d2f483dbcc49970698d80cc1e1414697cbfa6885b40b9cb366a`.
`evidence-index.json` records each entry's size/SHA256 and complete summaries.
Archive contents were reread and independently checked against that index.

## Pending, not implicitly passed

Last read-only GitHub check: main still exact accepted SHA above; PR #42 still
development HEAD `336bad8cd3a4573dbd18d360cefbff80fd33a979` with no final-ready
notification. That source has **not been executed**. No candidate GREEN record
exists; no implementation defect is inferred from main's missing module.
Owner/Codex-2 final-ready notice and exact SHA are required by Issue #43 before
the throwaway candidate execution. The frozen source remains unchanged then.

Both candidate Python results, all 224 QA outcomes, genuine RED/GREEN against
functional code, full combined regression and four successful hosted jobs on
latest combined accepted main remain **PENDING**. Current Draft's hosted CI RED
must be retained and must not be presented as a functional candidate failure.
Actual hosted job links/checkout merge-ref parents are posted in the Draft PR's
audit comment after the run, without a new source commit changing its HEAD.

## Retained exceptions and limits

- Input generation found a missing structured introduction/contact prerequisite
  in the uncommitted sample; corrected before first input freeze. No production
  code/expected semantic ceiling changed.
- Pre-candidate locator audit corrected mutation destination `element.path` and
  `snapshot.captured_at`. Original freeze, old test commit and old records retained;
  all final-baseline tests rerun with final freeze. No candidate-driven oracle edit.
- Matrix intended API-declarations-only inspection; Git output included the full
  production `guard.py` module. Disclosed broader read; matrix predates that read;
  no functional tests, fixtures or helper samples were read/copied/executed.
- Diagnostic attempts to inspect a guessed accepted helper filename found it
  absent. One direct fixture inspection selected an execution without citations
  and raised IndexError. These were inspection errors, not regressions; no source
  data was changed to suppress them.
- A read-only GitHub main/PR lookup failed under sandbox socket permissions;
  approved-environment retry succeeded and confirmed exact main/PR head. No
  stale/unapproved source was integrated. Expected pytest import errors and Gold
  refusal exits are preserved separately from environment/inspection exceptions.
- Working-tree LF/CRLF conversion warnings are retained as Git diagnostics.
  Freeze SHA256 uses canonical Git/LF bytes and additionally verifies Git blobs;
  captured source object bytes are never newline-normalized.
- Finite synthetic QA does not prove universal semantic entailment, production
  security, legal authenticity, actual business outcomes or current authorization.
  Candidate API compatibility/oracles have not yet been exercised against the
  final implementation; any QA compatibility issue must be disclosed/refrozen,
  never silently treated as a production bug or watered-down PASS.

Draft only; no self-merge. Human Gold 0/26 deferred is quality N/A. No real model,
paid call, customer report sharing, real-site fetch, deployment or RA3C/D.

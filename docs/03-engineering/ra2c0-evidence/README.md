# RA-2C-0 actual evidence

Baseline `70fa445ab094b01f3e84c50030c19d6c79f4cae3`; production scope is
only new `vrae/findings/*`, no accepted code or contract changes.

- `red.log`: actual initial module-absent collection exit2, not a semantic
  assertion failure. The initial baseline has no FindingBuilder.
- `fixture-failure.log`: actual intermediate **1 failed / 43 passed**, caused by
  the new naked-record test helper indexing a missing package_ref before calling
  the API. Corrected to supply the trusted package pin directly; no guard weakened.
- `green.log`: **46 passed**; final full regression adds the sealed diagnostic
  example test (47 new cases total).
- `python311/` and `python313/`: each **629 passed / 25 environment skips**;
  compileall, Ruff, mypy, pytest, pip check and all four fixed demos exit0.
  Commands, versions, exits and full outputs are retained.
- The skips remain 24 dedicated HTTP-isolation tests + one Browser-isolation
  function, executed in the required hosted jobs.

Re-run: `python docs/03-engineering/ra2c0-evidence/regress.py python311` (or
python313). Independent business replay: `python scripts/verify_ra2c0.py`.

The sealed fixture produces exactly one bounded contact-href HTTP404 issue,
two checked positive steps and 14 UNKNOWN items (one actual blocked RFQ plus
13 deferred rules). No recommendations, hypotheses, guessed severity or padded
issues. Source HTML remains in the pinned EvidencePack; target status/error/trace
are inseparable from each verified Finding row and the embedded full execution.
Exact native-ID bridge invokes the unchanged RA-0 guard. Unknown scope projections
carry no native or observed fact IDs.

Focused cases cover all three supported broken-link rules, 404/410, missing raw,
unvisited/blocked/WAF/robots, source/target/trace/ID tampering, wrapper resealing,
old/wrong pins and versions, scope/cross-site drift, whole-site overclaim, false
severity/approval/sharing, immutable replay, input size and the sealed example.

Hosted run/job links, skip counts and downloaded raw Browser artifact audit will
be attached to the exact final SHA in a new Draft PR after actual completion.
See `../RA2C0_VERIFIED_FINDINGS.md`. Stop for independent Owner acceptance; no
automatic merge, full-stage completion or RA-2D work.

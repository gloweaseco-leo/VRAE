# RA-2B-1 actual evidence

Baseline: `8a1b1aca9da5a00c1f3f252f207c7a7b57d3e558`.

- `red.log`: baseline evaluator lacks the two new rules; actual **8 assertion
  failures / 2 passes** against captured 200/404/410/403/500 paths. It returned
  UNKNOWN where new-rule PASS/FAIL/BLOCKED was expected. This is feature admission
  red→green, not a claim that the accepted legacy version violated its scope.
- `green.log`: first complete focused rules run, **98 passed**. Three subsequent
  metadata-edge/fixture replay cases are included in the final full regression.
- `python311/` and `python313/`: final full suites each **582 passed / 25 skipped**;
  all eight commands exit0 (compileall, Ruff, mypy, pytest, pip check, RA-2A,
  RA-2B-0 and RA-2B-1 fixed-example replays). Versions/commands/exits retained.
- The 25 host skips remain 24 dedicated HTTP-isolation cases + one Browser
  isolation function, executed in their required hosted jobs.

Replay all gates: `python docs/03-engineering/ra2b1-evidence/regress.py python311`
(or python313). Demo: `python scripts/verify_ra2b1.py`.

The new evaluator is explicitly selected as `ra2b1-1.0.0`; the legacy default and
old expected files remain unchanged. New DISC-02/CTA-02 cases include real captured
P/F/UNKNOWN/BLOCKED, missing source/target raw text, unvisited/missing roles,
robots/WAF, redirects, individual good/bad paths, no POST, wrong pins/versions,
cross-site/run/blob rejection and recomputed-hash response/trace/metadata tampering.
The full path cap is 256 with explicit truncation.

See `../RA2B1_BUYER_JOURNEY.md` for the updated 16-row matrix and exact evidence
edges. Raw target response metadata is mandatory for 404/410 judgment; future
Finding consumers must preserve it. No visibility, form-delivery or production
diagnostic claim. Original collectors/contracts/security gates remain unchanged.

Hosted run/job links and raw Browser artifact verification will be attached to
the exact final SHA in the independent Draft PR after completion. Stop for Owner
independent acceptance; no automatic merge or later-stage implementation.

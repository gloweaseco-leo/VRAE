# RA-2B-0 actual local evidence

Baseline main `cf99cfdc09f7355c98fd6e1c52bd1f401f3b7d98`.

- `red.log`: before implementation, actual collection exit2 / module absent
  (`vrae.rules`); **not** a passed/failed semantic assertion.
- `fixture-failure.log`: intermediate actual 1 failed / 16 passed; duplicate
  `limits` kwargs in the new offline test fixture, corrected without collector changes.
- `green.log`: final focused rule suite **36 passed**.
- `python311/` and `python313/`: each full suite **517 passed / 25 environment
  skips**; compileall, Ruff, mypy, pip check, pinned RA-2A replay and pinned RA-2B-0
  replay all exit0. Commands and interpreter versions in `summary.json`.
- Skips are the existing 24 dedicated HTTP-isolation tests and 1 Browser-isolation
  function. Hosted isolated jobs execute them in the required containers.

Replay: `python docs/03-engineering/ra2b0-evidence/regress.py python311` (or
python313). Business demo: `python scripts/verify_ra2b0.py`, using committed
`tests/fixtures/rules/industrial-navigation.json`. No network or browser required.

One enabled bounded rule, DISC-01: static homepage nav href target 200 → PASS;
captured target 404/410 → per-link FAIL_WITH_EVIDENCE; unvisited/missing original
content → UNKNOWN; blocked → ACCESS_BLOCKED. Other 15 rules are explicitly UNKNOWN.
All five original tasks/16 rule versions are retained; details and limitations in
`../RA2B0_RULE_READINESS.md`. No independent non-applicability proof is available,
so no NOT_APPLICABLE is emitted. No Finding or AI output is created.

Hosted CI job/run links and raw artifact verification will be attached to the
exact final SHA in the new Draft PR after completion, without an extra evidence-only
commit. Engineering completion does not replace independent Owner acceptance.

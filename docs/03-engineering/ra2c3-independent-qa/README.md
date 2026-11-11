# Independent RA-2C-3 adversarial QA

Contract frozen from Issues [34](https://github.com/gloweaseco-leo/VRAE/issues/34),
[35](https://github.com/gloweaseco-leo/VRAE/issues/35) and the
[Owner clarification](https://github.com/gloweaseco-leo/VRAE/issues/35#issuecomment-6798752310),
before examining a C3 candidate implementation. Accepted baseline:
`4b5ebe689f048ba20d38354ae7c03d4bbaf37c6a`.

Only the reserved independent test, `ra2c3_codex2_*.json` inputs and this directory
are owned here. No production, CI, dependency, historical fixture or Gold edits.
All collection uses an in-memory transport and fixed resolver. No real websites,
email, contact submissions, reports, deployment or RA-3 execution.

## Matrix and rejection oracles

| Area | Independent proof / failure condition |
| --- | --- |
| Positive source proof | Own industrial HTML; name line/column/path, decoded text, raw element and SHA checked against retained bytes; full execution provenance and separate TRUST group required |
| Cross-rule meaning | Separate positive pack and genuine captured CONTACT 404/410 packs; latter must preserve CTA-02 source+target defect and TRUST UNKNOWN, never TRUST PASS/defect |
| Missing/blocked scope | Brand alone, absent name/intro/link/raw, conflict, same brand/different legal names, JS only, unvisited, robots, WAF, 403, 500 remain UNKNOWN/ACCESS_BLOCKED, with no unsupported defect |
| Quoted claims | Claimed legal registration/certification/factory text remains quotation; cannot become authentication or scoring metadata |
| Package attacks | Tamper source text/href/label/raw/location/URL/hash/time/version/refs/scope, wrapper fields and privacy flags; recompute self-hash; load AND verify must reject |
| Execution attacks | Reseal fabricated provenance/execution and caller execution pin while retaining real evidence pin; build/load must replay and reject |
| Contact attacks | Genuine broken-link positive control, then mutate target response and native bridge; a captured 200 cannot be relabelled 404 |
| Trusted boundaries | Wrong/absent held pins, another valid run, altered raw bytes, tenant/policy/authorization/coverage substitution, unsupported builder/evaluator combinations reject |
| Object safety | Detached immutable package, naked Finding not proof, oversize and NaN reject |
| Historical C0/C1/C2 | Entire canonical fixture digest and pack/execution/package refs frozen from baseline Git objects, then actual historical build/load/verify |

Each mutation requires successful real C3 build/load/verify first. Unsupported
C3 on baseline is **PRE-IMPLEMENTATION EXPECTED RED**, not a security rejection
and not GREEN CI. No skip, xfail or implementation stub is used. Actual pytest
exit codes, JUnit failures/errors and raw output are retained by `run_qa.py`.

Example (use the desired Python 3.11 or 3.13 interpreter):

```text
python docs/03-engineering/ra2c3-independent-qa/run_qa.py --label baseline-311 --target-sha 4b5ebe689f048ba20d38354ae7c03d4bbaf37c6a
```

Candidate tests must use an isolated archive of its precise Git HEAD, overlay
only these independent test inputs, record both candidate and QA source SHA,
and repeat unchanged tests against any final revised HEAD. Genuine failures go
to Codex-1 for repair in its own branch. This QA PR stays Draft pending Owner
review and demonstrated compatibility; baseline expected RED cannot be merged.

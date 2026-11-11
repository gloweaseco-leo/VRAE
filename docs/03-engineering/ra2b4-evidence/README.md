# RA-2B-4: captured homepage search-entry facts

Issue [#26](https://github.com/gloweaseco-leo/VRAE/issues/26). Started in a new
worktree/branch from accepted main `214321551034a98239cc6a6586ec9d788ba3769a`.

The new business capability is a caller-pinned, replayable SEARCH_TECHNICAL
Observation: the retained original HOME-request HTML contains one explicit,
nonempty Title and one unambiguous same-site Canonical href. Optional description
is independently observable. This helps a reviewer inspect what search-entry
metadata a synthetic B2B supplier actually supplied, alongside the existing
buyer-path and product-information evidence.

Explicit opt-in only: `execute(pack, expected_pack_ref=pin,
evaluator_version='ra2b4-1.0.0')`. Original bytes remain in EvidencePack; source,
snapshot, evidence references, response metadata, capture time, raw elements,
decoded values, character ranges, line/column, body SHA and recorded policy scope
remain inspectable. `verify_execution` recomputes the complete result from the
trusted pack pin, including the added SEO fields. No network is used by evaluation.

## Replay and limits

Run `python scripts/verify_ra2b4.py` (read-only; no fixture generation flag).
`tests/rules/fixtures/seo01-static-signals.json` seals nine packs and complete
new-version executions, plus pinned references for each historical evaluator.
`replay.log` is the initial successful replay; `py311/11.log` and `py313/11.log`
are the final full-regression replays.

| Synthetic case | Bounded result |
| --- | --- |
| Industrial homepage: clear title + same-site canonical + description | PASS |
| Title only | UNKNOWN; observed title remains inspectable |
| Conflicting canonical links | UNKNOWN; both candidates retained |
| External canonical | UNKNOWN; no external target fetched |
| JS-only title | UNKNOWN; no rendered-state claim |
| Original body not retained | UNKNOWN |
| HTTP 403 / robots denied / WAF | ACCESS_BLOCKED |

PASS means original static tag presence only. It does not establish canonical
target response, SEO quality, crawler access, Google canonical selection, actual
indexing, ranking, multilingual correctness, rendered visibility or whole-site
completeness. Missing, empty, ambiguous, malformed, cross-site, unsupported or
oversize input never becomes FAIL_WITH_EVIDENCE or NOT_APPLICABLE. Bounds are
131072 retained body bytes, 128 relevant head elements, 512 title/description
characters and 2048 href characters. UTF-8 (optional BOM) source is supported;
explicit head structure is required. No attempt is made to reproduce browser
HTML error recovery. Robots response metadata alone lacks a resolvable body;
robots and uncaptured sitemap facts therefore remain UNKNOWN.

## Actual checks and retained failures

PowerShell's UTF-16 redirected logs were converted to UTF-8; diagnostic line
endings/trailing whitespace are normalized. Test outcomes, source fixtures and
recorded command exit codes are unchanged.

- `red.log`: before implementation, accepted default evaluator returned UNKNOWN
  for the proposed positive example. The final test explicitly selects the new
  evaluator; the accepted default intentionally remains unchanged.
- `parser-red.log`: prototype collided with HTMLParser's `offset` integer;
  renamed the helper to `char_offset` without weakening the positive test.
- `ambiguity-red.log`: nested title markup initially produced PASS; raw title
  markup is now conservatively UNKNOWN on both supported Python versions.
- `initial311.log`, `initial313.log` and their summaries retain the first full
  attempts. An unsupported marked declaration was not yet rejected, and five
  existing tmp_path tests hit the sandbox's denied Windows pytest temp directory.
  The marked-declaration hook now returns UNKNOWN; complete reruns use the
  approved environment outside that filesystem sandbox. No test was skipped or
  altered to accommodate the permission error.
- `marked-section313.log`: the next Python 3.13 run classified that malformed
  declaration as a bogus comment instead of calling `unknown_decl`. The original
  source prefix is now checked in the comment callback too. Python 3.11's
  corresponding full run passed; both versions are rerun after this correction.
- `py311/summary.json` and `py313/summary.json`: final actual command exit codes
  for compile, Ruff, mypy, full pytest, pip check, all historical RA-2A/B/C/D
  replays, the new SEO replay, simulated review and forged-review rejection.
  An exit of 1 for the last forged-Gold command is the required rejection.
  Both full pytest runs passed 908 tests with 25 host-only lab skips (24 HTTP
  cases and one browser case); those isolated labs run in the hosted CI jobs.
- The 65 dedicated SEO tests include partial/optional signals, duplicate and
  conflicting attributes, dynamic/template/body tags, malformed head structure,
  UTF-8/BOM/entities, parser bounds, body corruption, forged title/canonical,
  source URL, target href, locator/hash, version, tenant/run/policy, claim/coverage
  and recomputed outer execution SHA. Both old FindingBuilder versions reject
  the new evaluator. Full hosted CI links and exact final SHA are recorded in
  the Draft PR, after these files have been committed.

Only the new SEO module, minimal execution dispatch, dedicated tests/fixture,
one replay script and this evidence directory change. Historical evaluator
outputs, C0/C1 Finding packages, catalog/schema, collector/security and all Gold
samples/reviews remain unchanged. Historical replays still report
`GOLD_LABEL_PENDING` and `QUALITY_GATE_NOT_EVALUABLE`; this work supplies no human
labels or quality-accuracy claim. TRUST-01 files are untouched.

Draft PR only; Owner acceptance and merge remain pending. No RA-3 or deployment.

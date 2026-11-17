# S2-C1-P0: derived projection Port

This contract supersedes the rejected native-executor candidate at be6cb990.
Owner ruling: https://github.com/gloweaseco-leo/VRAE/pull/121#issuecomment-6953113824
Accepted integration main: 94a58b9867d96f104941874e07a2c4a4c84ec27f, merged normally.
Original RED evidence and commits remain in branch history; no history rewrite.

## Authority and versions

The unchanged vrae/rules/execution.py is the only accepted native RuleExecution
dispatch/recompute authority. Exact Git blob: c183970fd90ec69729221a4174c38d193f4b054b.
Original execute defaults, supported ra2b0/1/3/4/6 results and rejection of
unsupported ra2b2/5 are byte-compatible. No S2 evaluator is added to that file.

New output kind S2EvaluationProjection has projection_version=s2-projection-1.0.0
and projection_ref=s2p-<canonical document hash>. It has no top-level rx execution_ref
or evaluator_version. Its baseline_execution is the original ra2b6 result, verified
by original verify_execution. The derived document separately binds
baseline_execution_ref, baseline_evaluator_version, baseline_catalog_version,
baseline_catalog_sha256, same pack_ref and tenant/run/policy_id/policy_version.
It is neither authorization nor a report/fact engine. It cannot enter the old
FindingPackage/Guard as a native execution; this rejection is explicitly tested.
P1 assertion publishing requires a separately reviewed S2 evidence/promotion bridge.

## Executable public interface

```python
from vrae.rules.s2 import evaluate_s2, verify_s2_projection

projection = evaluate_s2(
    pack, expected_pack_ref=held_pack_ref, trusted_scope=held_scope,
    browser_pins=held_browser_pins_or_none)
verify_s2_projection(
    projection, pack, expected_pack_ref=held_pack_ref, trusted_scope=held_scope,
    expected_projection_ref=held_projection_ref,
    expected_projection_version='s2-projection-1.0.0',
    browser_pins=held_browser_pins_or_none)
```

trusted_scope is exactly the four independently held server scope fields above;
types match strictly, including rejection of bool as policy_version. Verifier
regenerates original native execution, all inputs and optional C2 projection;
changing content and self-rehashing does not replace independent pins.

Caller must already hold valid signed current-task/Policy/expiry/version authority
and enforce original access checks. Comparing scope never grants permission.
Never derive those authority pins from submitted JSON or browser form values.

## C2 accepted-main integration

The optional browser_pins is the actual accepted vrae.rules.s2_ux.BrowserPins:
tenant_id/run_id/policy_id/policy_version/pack_ref, exact source_refs tuple and
timezone-aware observed_after/before. It is independently held by the trusted
service. Port checks strict scope/pack equality then calls unchanged
project_browser(pack, held=browser_pins). It never synthesizes source/time pins.
No pins means browser_projection=null, NOT_REQUESTED_NO_BROWSER_PINS_INFERRED.
Foreign/stale/unselected sources fail through accepted C2 binding checks.

C2 returns read-only source-text candidates/UNKNOWN/ACCESS_BLOCKED, not new
rule PASS/FAIL or approval. No ordinary DOM extension can establish href, alt,
geometry, occlusion, accessibility or visibility. It retains its own version.
The historical ReadOnlyAdapter Protocol is reserved only and never invoked;
it is not the accepted C2 callable or a way to admit arbitrary native rows.

## Retained read-only input DTO

```python
adapter_request(pack, *, expected_pack_ref, rule_id, expected_scope) -> dict
verify_adapter_request(request, pack, *, expected_pack_ref, expected_rule_id,
                       expected_scope, expected_request_ref) -> None
resolve_input(request, pack, *, expected_pack_ref, expected_rule_id,
              expected_scope, expected_request_ref, evidence_ref) -> dict
```

contract_version=s2-readonly-1.0.0, input_ref=s2i-<canonical hash>.
Four reserved C2 rule IDs: INFO-03 / CTA-01 / CTA-03 / TECH-02.
Only original OBSERVED retained HTTP_BODY/BROWSER_DOM/BROWSER_SCREENSHOT ev-refs
resolve via the original same pack. DOM fields, blob SHA, snapshot-ref, arbitrary
JSON and response metadata never become evidence_ref. Source src-/page-/ev-
namespaces are not APP source catalog IDs. Snapshots retain original location;
response_metadata retains original CaptureManifest status/redirect/error and
explicitly states METADATA_NOT_AN_OBSERVATION_EVIDENCE_REF.
recorded_coverage is recorded capture only; coverage_denominator=null.
It is not a whole-site scope_manifest or extra provenance/authorization authority.
Missing evidence remains UNKNOWN; semantic language requires human review.
NOT_APPLICABLE requires explicit versioned applicability, never lack of capture.

## P0 capability limits

16 catalog IDs remain unchanged. Baseline 6 bounded rules remain native; 4 C2
and 6 C1 future rule capabilities remain NOT_IMPLEMENTED_P0. A successfully
composed C2 read-only projection does not count as implementing four evaluators.
C1 P1: DISC-03/INFO-02/TRUST-02/TRUST-03/SEO-02/TECH-01, after Owner P0 merge.
Industrial IND six are separate, never counted toward 16 generic rules.
No model/network/form submission/real site/real approval; Gold still 0/26.

## Reproducible checks and historical preservation

tests/s2_contract/p0_cases.py plus accepted integration/s2_ux/test_projection.py
exercise old five versions x five source classes against accepted Git source,
exact HEAD/worktree executor blob, independent s2p replay, forged input/ref/scope,
cross-run and browser-pin consistency, altered C2 results and native admission denial.
Original tests, B5A allowlist, RA3B archived SHA/fixtures, pack.py, Guard, old
FindingPackage, SQL/RLS/Worker/SSRF/authentication/30s lease are unchanged.

local-receipt.json records historical pre-remediation results; do not mistake
that historical IN_PROGRESS value for this revision's final status. Original
be6cb990 CI 29/38 (9 RED), first local GBK/source failures and raw JUnit remain
retained. Final remediation results are separately recorded, never overwritten.

integration/s2_contract/demo.py reuses accepted offline synthetic eight-page
bytes, calls evaluate_s2/verify_s2_projection and exports projection.json.
example.json is the real current summary, not a new APP/Worker COMMIT or S2 E2E.
The whole projection's canonical SHA is recorded to compare both Python minors.

# S2-C1-P0: native execution and read-only adapter inputs

Authority: [Issue118](https://github.com/gloweaseco-leo/VRAE/issues/118),
[S2 coordinator Issue117](https://github.com/gloweaseco-leo/VRAE/issues/117).
Accepted base: `84276325befdcf858852a1ec791e8b0695a515eb`.

## Executable dispatch, phase and compatibility

```python
from vrae.rules import execute, verify_execution
from vrae.rules.execution import S2_VERSION  # 's2-1.0.0'

execution = execute(pack, expected_pack_ref=held_pack_ref, evaluator_version=S2_VERSION)
verify_execution(execution, pack, expected_pack_ref=held_pack_ref,
                 expected_evaluator_version=S2_VERSION)
```

execution.py remains the sole dispatch/recompute interface. Its S2 branch uses
the unchanged ra2b6 evaluations and adds deterministic versioned capability and
adapter-input metadata. The original catalog has the same 16 IDs and hash.
Six legacy bounded rules remain enabled; **ten new rules are NOT_IMPLEMENTED_P0**,
not implemented merely because they return UNKNOWN. Six pending slots belong
to C1, four to C2. Industrial IND six are independent and are not added to the
generic implementation count. GAPS is unchanged; each S2 capability retains
its historical gap separately from the actual per-version implementation state.

All supported old versions (ra2b0/1/3/4/6), their default, and rejection of
unsupported ra2b2/5 keep their prior behavior. The new suite compares canonical
bytes against the actual execution.py Git object from the accepted base on
observed, 404, blocked, unretained and browser-containing native packs.

P0 does not enable or import C2's future module. C2 may implement the callable
below in its owned `vrae/rules/s2_ux.py` after this contract is accepted; C1's P1
dispatch integration will consume only accepted-main implementations and must
validate/replay their native rows. No arbitrary callable or browser result can
be registered through execute(). Do not copy this Draft into a sibling tree.

## Actual read-only input API

```python
from vrae.rules.s2 import adapter_request, verify_adapter_request, resolve_input

request = adapter_request(pack, expected_pack_ref=held_pack_ref,
                          rule_id='CTA-01', expected_scope=held_scope)
verify_adapter_request(request, pack, expected_pack_ref=held_pack_ref,
    expected_rule_id='CTA-01', expected_scope=held_scope,
    expected_request_ref=held_input_ref)
resolved = resolve_input(request, pack, expected_pack_ref=held_pack_ref,
    expected_rule_id='CTA-01', expected_scope=held_scope,
    expected_request_ref=held_input_ref, evidence_ref=actual_ev_ref)
```

`held_scope` has exactly tenant_id/run_id/policy_id/policy_version, independently
held by the server in the original current-task authority context. These
functions verify consistency; they do not create identity, signed provenance,
source access, current version, expiry or business approval. Keep those contexts
and their original checks alive independently.

| DTO field | Meaning / authority |
| --- | --- |
| contract_version | Exact `s2-readonly-1.0.0`; no caller-defined extension fields. |
| rule_id | One of INFO-03/CTA-01/CTA-03/TECH-02. |
| expected_pack_ref, scope | Caller pin and exact verified recorded scope; not live authorization. |
| snapshots | Detached original pack snapshot refs/source locators/times/modes/viewports/status. |
| evidence | Only real OBSERVED retained HTTP_BODY/BROWSER_DOM/BROWSER_SCREENSHOT pack entries. `resolve_input` revalidates the complete request and resolves an actual ev-ref through original pack.resolve. |
| response_metadata | Same-pack CaptureManifest HTTP status/redirect/error, source locator and snapshot_ref. Explicitly NOT an Observation evidence_ref. No fabricated ev-identifier. |
| recorded_coverage | Existing captured/unvisited/blocked coverage; never the whole-site denominator. |
| coverage_denominator | null until an independently held, applicable sampling manifest is implemented. No invented production budget. |
| input_ref | Deterministic input fingerprint, independently replayed against held pack/rule/scope/ref. Self-rehashing altered fields is rejected. |
| state / limitations | P0 input consistency only; explicit unsupported/human-review/authorization limits. |

The DTO never copies arbitrary DOM keys into EvidencePack fields. DOM strings,
object hashes, metadata locators and snapshot refs cannot resolve as ev-refs.
The native source verifier establishes consistency, not an independent browser
attestation or a screenshot's semantics.

## Reserved C2 callable and four slots

```python
def evaluate(pack: EvidencePack, *, expected_pack_ref: str,
             request: dict, expected_request_ref: str) -> list[dict]: ...
```

This matches the real `ReadOnlyAdapter` Protocol. Return native RuleExecution
observation rows: original Observation schema, same scope/rule/catalog version,
real pack citations and bounded claims. P1 must independently recompute them;
this P0 does not yet accept adapter output or grant Guard authority to it.

| C2 rule | Allowed existing input and limit |
| --- | --- |
| INFO-03 | Retained text/DOM bytes can support source-text observations. Semantic language quality is UNKNOWN with reason HUMAN_REVIEW_REQUIRED; that string is not a new Observation.result enum. |
| CTA-01 | Static HTML href and original DOM visibility are distinct. Original DOM does not establish CTA href/geometry; arbitrary extra DOM keys cannot fill the gap. Inadequate linkage stays UNKNOWN. |
| CTA-03 | Approved recorded viewport/screenshot/DOM refs only. No native overflow/occlusion geometry is supplied by this P0. Missing browser or geometry stays UNKNOWN, never a fabricated mobile PASS/FAIL. |
| TECH-02 | HTML image/heading candidates and original browser refs. Individual resource metadata has no new ev-ref or accessibility/ranking authority. Uncaptured resources remain UNKNOWN. |

NOT_APPLICABLE requires explicit versioned applicability evidence; absence of
capture is not proof of inapplicability. Existing blockers remain recorded
ACCESS_BLOCKED, not website defects. No network, RFQ submission or model occurs.

## Preserved boundaries requiring later review

The unchanged FindingPackage maps exact legacy builder/evaluator pairs and
rejects S2. That refusal is tested. Existing S0/C1/C2/Guard paths continue using
their accepted legacy versions; this P0 does not wire S2 into report, Controlled
review or Brief. P1 must propose an explicit versioned bridge without changing
old Guard authority. Metadata-only TECH-01 objective claims remain HOLD if they
would require a protected evidence contract change; P0 exposes metadata only.

execution.py is also an original ENTRY frozen file. The required new dispatch
changes its blob; original B5A source protection is deliberately unmodified and
must retain its actual ACCEPTED_SOURCE_CHANGED outcome. Owner must review the
exact executor diff/blob before any separate exact compatibility authorization.
No broad source exemption, pack.py change or unreviewed Guard bridge is included.

The unchanged `tests/interpretation/test_fixed_replay.py` also reads
`preserved-history.json` through the original `scripts/verify_ra3b.py` and pins
the executor's normalized file SHA. Candidate inspection finds exactly one
historical mismatch: execution.py, expected
`35b50fcf233e5566d5669af5f59ed6cf92eb3c147764081c29dcb373f8d5809d`,
candidate `0b07631dcacecdec8a4c7f2c7a309648dd156087ddcbcc240e2f64b0ff1537f4`.
Neither old fixture nor guard script is changed. This protected source-pin
compatibility is HOLD for Owner's exact-blob review; native old-output byte
comparisons passing cannot override that source freeze. The rest of P0 remains
reviewable and independently executable; a failed full/hosted gate is not PASS.

## Reproduction and truthful phase result

```text
python -m pytest -q tests/s2_contract/p0_cases.py --junitxml=<new-output>/native.xml
python -m integration.s2_contract.demo --out <fresh-output-directory>
python -m pytest -q --junitxml=<new-output>/full.xml
```

The example genuinely calls execute/verify on the accepted eight-page offline
industrial source, checked by a fixed canonical fixture SHA. It is not a new
APP202/Worker COMMIT or S2 E2E. Summary shows the actual old six observations,
pending ten, original pack/source refs and unknown coverage denominator. Raw
execution and JUnit stay in ignored .runtime; bounded receipts are published.
Gold remains pending: no precision, human labels, second report engine, external
site, paid model, production budget, approval or deployment is claimed.

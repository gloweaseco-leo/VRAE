# S2 buyer-task report candidate slice

Authority: [Owner product-loop CODE GO](https://github.com/gloweaseco-leo/VRAE/issues/118#issuecomment-6966540568).
Exact accepted base `95ed55321775223e95cf0a1585220951cc692648`. One isolated small
Draft adds a read-only view over **INFO-02 and TRUST-02**. It adds no rule engine,
fact store, review authority, production endpoint or native fact-promotion bridge.

## Runnable vertical path

The existing authenticated server selects its current pack/task/profile and holds
the source projection ref plus one or two observation selections. It calls:

```python
from vrae.reporting.s2_candidate import (
    BuyerCandidatePins, ObservationPin, build_candidate,
    verify_candidate, render_markdown,
)

# held is server state from the authenticated current task, never a UI request.
candidate = build_candidate(current_pack, supplied_s2_projection, held=held)
verify_candidate(candidate, current_pack, supplied_s2_projection,
    held=held, expected_candidate_ref=server_held_candidate_ref)
markdown = render_markdown(candidate, current_pack, supplied_s2_projection,
    held=held, expected_candidate_ref=server_held_candidate_ref)
```

`BuyerCandidatePins` holds tenant/run/policy/version, pack ref, projection ref and
version, IndustryPins (tenant/profile/ref/version), subject model/current HTTP
snapshot and an immutable tuple of ObservationPin. Each ObservationPin fixes
observation ID, rule/source version and the exact source snapshot set. The public
builder replays the **whole original** S2 projection against these pins before
selecting any row. The selected rows must share the pinned subject snapshot and
model; a source-less rule-wide configuration exclusion is allowed only when
already replayed as NOT_APPLICABLE. Cross-product/source splicing is rejected.

Pins are consistency/selection constraints, not a replacement for current signed
task authorization, expiry, ownership or the original access controls. The caller
must retain those existing controls and the actual current pack independently.
This module has no lookup that can infer a trusted current task from UI payloads.

Run `record.py --examples-only` to replay four saved synthetic server fixtures
and their candidate outputs. It does not recollect or overwrite existing source
archives. `buyer-complete.md` is the procurement report example; accompanying
UNKNOWN/NOT_APPLICABLE/ACCESS_BLOCKED examples and `SOURCES.md` show limited cases
and exact original byte excerpts. Server fixture files are offline test state,
not a production authentication mechanism or a new operational data store.

## Exact candidate DTO

`kind=S2BuyerTaskCandidate`, `reporting_version=s2-buyer-candidate-1.0.0`,
`candidate_ref=s2br-*`, `authority=READ_ONLY_REVIEW_CANDIDATE`.
Source input stays `s2-projection-1.2.0`, IndustryPack 1.1.0; selected rule version
`s2-industrial-context-1.0.0`, source version `s2-industrial-source-1.0.0`.

Each card contains buyer task/title, unchanged result/reason, model,
observation/rule/source versions, `source_replay`, `observed_fields`, original
`source_excerpts`/`source_pages`, `limitation`, configuration locator and a fixed
`review_hypothesis` explicitly typed HYPOTHESIS_REVIEW_REQUIRED. The hypothesis
points only to its selected observation; caller prose is not accepted.

- SOURCE_BYTES_AND_RULE_REPLAY means saved bytes and the bounded S2 check were
  replayed. It does not mean a legal/business claim is true or old Guard-approved.
- CONFIGURATION_OR_RESPONSE_METADATA_ONLY means no material content quote can
  be asserted; no ev-ref is invented. Blocked material is not displayed as fact.
- UNKNOWN preserves unresolved fields/associations. NOT_APPLICABLE preserves the
  pinned explicit configuration exclusion. ACCESS_BLOCKED preserves capture
  limits. None becomes an asserted website fault.
- INFO-02 can show the source-declared revision and conditions; it never approves
  engineering fit. TRUST-02 shows source proof kind/date context; authenticity,
  validity and compliance are unassessed.

`native_fact_admission=NONE`, original Finding/RuleExecution/Guard remain unchanged
and reject this envelope. It is not native ReportDraft. There is no approve/share
action or report publication state machine; external delivery is unauthorized.
An actual native promotion would require its own precise contract/negative cases
and Owner review, which this read-only slice does not need.

C2 can display this DTO after Owner acceptance, using text/escaped rendering for
all original `source_excerpts.quote` values. Do not insert source HTML into DOM or
infer pins from the DTO. The Markdown formatter uses human labels and escaped
text; technical byte locators remain in the separate source details. C2/C3's
already-merged source DTO handoff is [posted here](https://github.com/gloweaseco-leo/VRAE/issues/118#issuecomment-6967103221)
and retained in HANDOFF.md; no Draft source copy is required.

## Validation and boundaries

The explicit mandatory S2 suite adds 37 new tests, including self-rehash forgery,
cross-model/source/snapshot selection, source projection forgery, version/profile
and tenant/run rebinding, all four result states, configuration-only exclusions,
escaped display, directional text rejection and native admission rejection.
Original default discovery remains exactly 2564; original frozen assertions and
CI inventory are unmodified. CI strategy/Chrome diagnosis remain separate in
Issues129/126; no old 3.11 failure or font/browser step is rewritten here.

Frozen execution blob `c183970fd90ec69729221a4174c38d193f4b054b` and EvidencePack
blob `8d45d5882103323e62bc4bd61a4379899e759966` stay exact. No existing reporting
engine/Guard/rules/industry source, SourcePolicy, Worker, SQL/RLS or C2/C3 code is
changed. Existing reporting canonicalization/display helpers are reused.
Initial RED, real JUnit and source/evidence hashes remain in runtime/receipt.json.
S3 real AI, S4 external customers, model calls, real third-party sites, production,
merge and deployment remain unauthorized/unperformed. Real human Gold stays 0/26.

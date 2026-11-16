# Synthetic industrial buyer-task execution

Private NOT_APPROVED business data; not engineering approval or a shared report.

- Source: eight local HTML pages; fixed recorded transport, no live domain request.
- Models: P40 pump equipment and V25 industrial valve component.
- Native refs: rx-e87afcd9c27b775e82a1cf0b31fd750fe696cd9a72e0c42a67b98a3a139af620, cg-f51bc7d3f71fba08677790a0b6a3d4ee3e737bfc52e8c409ccc2d687d2e249a5, cg-bb59577abe92a8af31db30add072046127d327e44374e518acf1e659ca4ebdaa, cg-35db813a5e056e08b7dff627481ea4eb60debb86ade294ff314413d0fe5976b7, cg-f493d4640e7fbb0a7b9a051af94dcbfa9da2cc777b5e2b56ba33989e90a06c67, cg-e54c00d14d9184715ec977f8bdb3b22950732fa18e7b0974d20ca09cfa361779
- Diagnosis: l2-8d6d6a404ed7d01f89e6f031a969c68716cbf462f5d24cd6c8490d69dbdf86d8
- Result counts: {"PASS": 10, "FAIL_WITH_EVIDENCE": 4, "UNKNOWN": 4, "NOT_APPLICABLE": 1}

## Evidence-backed comparisons and unresolved questions

- P40 / IND-SELECTION / PASS: A replayed category-to-product path reaches this source-declared model and family. [obs-7942f7e088c5b1f8d7a29dfd2b8f8cf5653cce5de5873b6ba114f5b499bf3d92]
- P40 / IND-SPEC / PASS: Configured procurement attributes have source values and supported units where required; correctness is unverified. [obs-02f6c455ba506720d7620ee1f20eb33c89fa638423374f3e96c806af61365918]
- P40 / IND-DUTY / PASS: Source-listed flow 12 m3/h meets the configured scalar comparison to scenario 10 m3/h; this is not engineering fit confirmation. [obs-8d531ecba35b48f64c450043ab02f370e3c357b16d2bbfc8c1eaed1efc223ca3]
- P40 / IND-DUTY / PASS: Source-listed head 30 m meets the configured scalar comparison to scenario 25 m; this is not engineering fit confirmation. [obs-086e47569b77bd77b202f00e5a2cae0e821afcc0f3a2a30292c273ba4f6de82c]
- P40 / IND-DUTY / PASS: Source-listed voltage 400 V meets the configured scalar comparison to scenario 400 V; this is not engineering fit confirmation. [obs-043b20cdc2791f0cafa02bfa78e0bec759404721cbffb6af065737ce74b9f50e]
- P40 / IND-DUTY / PASS: Source-listed frequency 50 Hz meets the configured scalar comparison to scenario 50 Hz; this is not engineering fit confirmation. [obs-8c68db1cc5f2e56bdea8f70e30be5a4f001ea38a5253e58921806718dfe76775]
- P40 / IND-DUTY / FAIL_WITH_EVIDENCE: Source-listed pressure 10 bar does not meet the configured scalar comparison to scenario 18 bar; this is not engineering fit confirmation. [obs-fc90665111127112e97c620a87961c2d51ab37027755838e517c87f9d282e6e3]
- P40 / IND-DUTY / PASS: Source-listed temperature 80 degC meets the configured scalar comparison to scenario 60 degC; this is not engineering fit confirmation. [obs-dd813aca27519a3c48d328d2bad3a0a90d1290f2703b5ad1da0672c31f60c22d]
- P40 / IND-FIT / UNKNOWN: Catalog values do not establish application suitability or safe operation. [obs-91c3e6b0097bfff4ba6e63f015fbb0a594f96b14ab2db3fba79e82bcb37c7f80]
  - Verify: pump curve at the required flow/head; NPSH and inlet conditions; seal/medium compatibility; duty cycle and installation conditions
- P40 / IND-PROOF / FAIL_WITH_EVIDENCE: The supplier-stated validity date precedes the capture date; neither certificate authenticity nor actual supplier qualification is established. [obs-93af3df30c329db64cc749479ec3d1046f97ddb8e69508709323e1d05b56ee16]
- P40 / IND-RFQ / UNKNOWN: The RFQ packet has unresolved buyer inputs or route coverage; no failed inquiry or website defect is asserted. [obs-90de67a1f95e5fde720783466e60ec2b48b336b30a8300a1731dca38ceb7e615]
- V25 / IND-SELECTION / PASS: A replayed category-to-product path reaches this source-declared model and family. [obs-56615e92dfe02934ae8a229207cd5e258ea4cdc75d8329a351a70875915f57b5]
- V25 / IND-SPEC / PASS: Configured procurement attributes have source values and supported units where required; correctness is unverified. [obs-97a461d7edd16d52ce3553a9a70916e784688b5a7a62bf8700dcb1957a86de98]
- V25 / IND-DUTY / FAIL_WITH_EVIDENCE: Source-listed pressure 16 bar does not meet the configured scalar comparison to scenario 18 bar; this is not engineering fit confirmation. [obs-39bca9d12bbb104324df87b4c6ab1e528bb5450538791b784f7d39d2e2614f97]
- V25 / IND-DUTY / PASS: Source-listed temperature 120 degC meets the configured scalar comparison to scenario 60 degC; this is not engineering fit confirmation. [obs-4a09b98c5ca11fee036987549422789fb6ea5d23f14d387f499d9dc81fda062b]
- V25 / IND-FIT / UNKNOWN: Catalog values do not establish application suitability or safe operation. [obs-e27c1141cc3fc5b550657ed4100b941d5935d14692bc47f3db8a61e4625012ac]
  - Verify: pressure-temperature derating; seal/medium compatibility; connection standard and mating dimensions; independently verified material/pressure certificates
- V25 / IND-DUTY / NOT_APPLICABLE: Motor electrical comparison is outside this declared valve profile; actuator requirements were not established. [obs-a4c551282bb9ed3619ba61368e4bc50164ccc271b03390507f7a2deb87330c08]
- V25 / IND-PROOF / FAIL_WITH_EVIDENCE: The supplier-stated validity date precedes the capture date; neither certificate authenticity nor actual supplier qualification is established. [obs-9857bd66ff36588c7aa995fa551b6506ad0286a9e7abf5628d515bc2e28e98a1]
- V25 / IND-RFQ / UNKNOWN: The RFQ packet has unresolved buyer inputs or route coverage; no failed inquiry or website defect is asserted. [obs-b0d4708eb875c431466a6156d6f7ea0862f84af983e73316d15af2c7d6762674]

## RFQ preparation (no submission)

- P40: unresolved buyer inputs=destination; product-context GET paths=1
- V25: unresolved buyer inputs=destination; product-context GET paths=1

Exact source quotations, byte positions, HTML-body SHA and capture times are in diagnosis.json -> source_facts; source.json replays the same native EvidencePack.
Hypotheses and recommendations remain HUMAN_REVIEW_REQUIRED. Missing information, unsupported units and unverified engineering/certification remain UNKNOWN.

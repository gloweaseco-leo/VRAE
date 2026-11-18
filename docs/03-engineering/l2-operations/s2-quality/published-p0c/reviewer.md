# S2-C3 PRIVATE unsigned reviewer packet

Inspect original bytes/hash/URL/locator and capture time; scope is not the whole site.
Two real independent reviewers must supply identity, time, bounded verdict, rationale and serious-fact flag.
A third independent person adjudicates disagreement; Owner signs exact rows out of band.
Candidate expectations, names, dates and edited hashes confer no Gold or access authority.

| Unit | Rule / site | Source / time | Candidate (not authority) | Reviewers |
| --- | --- | --- | --- | --- |
| s2-unit-9464f7e606394434341dfa1024939ba18d5529d62822ae8f35e1c9a93258d9e0 | DISC-01 / STATIC | https://example.org/ / 2026-11-10T12:00:00+00:00 | PASS | UNREVIEWED / UNREVIEWED |
| s2-unit-c6f5f539659d233f8255b76bb7df84e9b8058e354520cfef4c08bf60537ad8c7 | DISC-02 / STATIC | https://example.org/category/valves / 2026-11-10T12:00:00+00:00 | PASS | UNREVIEWED / UNREVIEWED |
| s2-unit-9e15fecacd07408899d88d220e9551b982a341638e18c617ac90e8f2125bd885 | CTA-02 / STATIC | https://example.org/products/valve-v1 / 2026-11-10T12:00:00+00:00 | PASS | UNREVIEWED / UNREVIEWED |
| s2-unit-b5417e609c36aa3d48f5d6cb75be85acf0811388d631889825fcf479ca2ae7d4 | DISC-01 / CMS | https://example.org/ / 2026-11-10T12:00:00+00:00 | PASS | UNREVIEWED / UNREVIEWED |
| s2-unit-c7dbca337b05c60c2a0c15025efa19a94223cb5290c77996979ef864aae67d62 | DISC-02 / CMS | https://example.org/category/valves / 2026-11-10T12:00:00+00:00 | PASS | UNREVIEWED / UNREVIEWED |
| s2-unit-38e662cef1d5ed0e2b2a35e2f5694320b0091c30b8752fdd2d13330a70f08057 | CTA-02 / CMS | https://example.org/products/valve-v1 / 2026-11-10T12:00:00+00:00 | FAIL_WITH_EVIDENCE | UNREVIEWED / UNREVIEWED |
| s2-unit-a9c49e56ce98aa9fa6f157bb6a62fa5a32fd5245640c21cb10a702a06431762f | DISC-01 / SPA | https://example.org/ / 2026-11-10T12:00:00+00:00 | UNKNOWN | UNREVIEWED / UNREVIEWED |
| s2-unit-da5484c988d2c88fb688514169514bb69fb49e087dce3eed6e38f78eb67473eb | DISC-02 / SPA | None / 2026-11-10T12:00:00+00:00 | UNKNOWN | UNREVIEWED / UNREVIEWED |
| s2-unit-1a8c75924fb1ef905397c3a349db14afe2c0348a07c29b673a76d1ddbb3de965 | CTA-02 / SPA | None / 2026-11-10T12:00:00+00:00 | UNKNOWN | UNREVIEWED / UNREVIEWED |
| s2-unit-025f582bb3f8c64218ccf9dfbf41c3dd154150746f01c25eefbee490cfbb1494 | DISC-01 / MULTI_SKU | https://example.org/ / 2026-11-10T12:00:00+00:00 | PASS | UNREVIEWED / UNREVIEWED |
| s2-unit-920e74623ddf89391db9f9955da41f3173493f682482bd3cbfb1daad982315ce | DISC-02 / MULTI_SKU | https://example.org/category/valves / 2026-11-10T12:00:00+00:00 | UNKNOWN | UNREVIEWED / UNREVIEWED |
| s2-unit-45d3780328462f3562e1fc1e82712501bbea13864e97dc15274693a64f6c87dc | DISC-02 / MULTI_SKU | https://example.org/category/valves / 2026-11-10T12:00:00+00:00 | PASS | UNREVIEWED / UNREVIEWED |
| s2-unit-321906a5d2d03d37c8e58338aad8f7c853292daae4457fb3ab7a159b4056f9a6 | CTA-02 / MULTI_SKU | https://example.org/products/pump-p40 / 2026-11-10T12:00:00+00:00 | ACCESS_BLOCKED | UNREVIEWED / UNREVIEWED |
| s2-unit-1a66a4e542e19ce0ae958622387d24a47ba02c93cc02d48d804f0b7ca420ec1c | CTA-02 / MULTI_SKU | https://example.org/products/valve-v1 / 2026-11-10T12:00:00+00:00 | UNKNOWN | UNREVIEWED / UNREVIEWED |
| s2-unit-3595a5fc4d3bd087dff038611dfe29b40b724d65fcf1210f828f8b3c4f2f38f5 | DISC-01 / MULTILINGUAL | https://example.org/ / 2026-11-10T12:00:00+00:00 | PASS | UNREVIEWED / UNREVIEWED |
| s2-unit-1b5231737b6fcf5726bb6926cd4870b2d51dd1b205a830fbe87e3fed3d49981d | DISC-02 / MULTILINGUAL | https://example.org/category/valves / 2026-11-10T12:00:00+00:00 | PASS | UNREVIEWED / UNREVIEWED |
| s2-unit-b716dd1160af64a8815d7b6b286ddbb23e043b20fb32208c904d9a9a8dae823b | CTA-02 / MULTILINGUAL | https://example.org/products/valve-v1 / 2026-11-10T12:00:00+00:00 | PASS | UNREVIEWED / UNREVIEWED |
| s2-unit-5ebf52d8145ed25a31e8d1716fd481d118376c79a2a9b7ea07fe2328c124b623 | DISC-01 / MULTI_SKU | https://example.org/ / 2026-11-10T12:00:00+00:00 | PASS | UNREVIEWED / UNREVIEWED |
| s2-unit-2173650e8b76b3f8e76653598057d4bbf5ac5cf60162bd657b8f55449870105f | DISC-02 / MULTI_SKU | https://example.org/category/valves / 2026-11-10T12:00:00+00:00 | PASS | UNREVIEWED / UNREVIEWED |
| s2-unit-a4941fcefadbd2827dcb7d04c676fd69ebaedd40e74b42209df3c49b3045c5bf | DISC-02 / MULTI_SKU | https://example.org/category/valves / 2026-11-10T12:00:00+00:00 | PASS | UNREVIEWED / UNREVIEWED |
| s2-unit-b19b4366ce9d697304e6ba378d15d55efc9f3007a630c5c511aabded06c4232d | CTA-02 / MULTI_SKU | https://example.org/products/pump-p40 / 2026-11-10T12:00:00+00:00 | PASS | UNREVIEWED / UNREVIEWED |
| s2-unit-d588f39b1e56f14cd2d9b1b30120362d0d86e9d7a2f641fa83a4d3ec36e80f5b | CTA-02 / MULTI_SKU | https://example.org/products/valve-v1 / 2026-11-10T12:00:00+00:00 | PASS | UNREVIEWED / UNREVIEWED |
| s2-unit-c8a323caa414bac6321515c673565d1d7a9a88667745f15839b756dbadb77aa6 | IND-DUTY / INDUSTRIAL_MULTI_SKU | https://example.org/products/pump-p40 / 2026-11-15T12:00:00+00:00 | FAIL_WITH_EVIDENCE | UNREVIEWED / UNREVIEWED |
| s2-unit-be7618afd61558e33b903a6ea12aff7268897f60c0f9d9616391aea03c11ecc0 | IND-SELECTION / INDUSTRIAL_MULTI_SKU | None / 2026-11-15T12:00:00+00:00 | UNKNOWN | UNREVIEWED / UNREVIEWED |
| s2-unit-e81359765bc4898b302136070a3e8fcdc7e9f641a20d02b9c4e9e002cd42e385 | IND-SELECTION / INDUSTRIAL_MULTI_SKU | None / 2026-11-15T12:00:00+00:00 | UNKNOWN | UNREVIEWED / UNREVIEWED |
| s2-unit-20c99f912823261c935771b601220e623955ca4973be0013e4f1b6a7beede850 | IND-DUTY / INDUSTRIAL_MULTI_SKU | https://example.org/products/pump-p40 / 2026-11-15T12:00:00+00:00 | PASS | UNREVIEWED / UNREVIEWED |
| s2-unit-4f888373ca0144a317a9f1a5e64886bb6056cb12cdbe38d33c1878f373e2a4fe | IND-SPEC / INDUSTRIAL_MULTI_SKU | https://example.org/products/pump-p40 / 2026-11-15T12:00:00+00:00 | UNKNOWN | UNREVIEWED / UNREVIEWED |
| s2-unit-c8f16bf80333a2eca72b6c031cbaa0dc056f6a2a64ecfa05882c3b45e36dba75 | IND-PROOF / INDUSTRIAL_MULTI_SKU | https://example.org/products/supplier-proof / 2026-11-15T12:00:00+00:00 | FAIL_WITH_EVIDENCE | UNREVIEWED / UNREVIEWED |
| s2-unit-0cdce9e8b6f7750fb127e5e92a9116806b4d4123e10023859b296c23bf26d5ed | IND-PROOF / INDUSTRIAL_MULTI_SKU | https://example.org/products/supplier-proof / 2026-11-15T12:00:00+00:00 | PASS | UNREVIEWED / UNREVIEWED |
| s2-unit-e1e195b2b3483c4dda3ab1b3d681aa62c4ef1e92cd631ae5cc2b41f3cb135794 | IND-RFQ / INDUSTRIAL_MULTI_SKU | https://example.org/products/rfq-guide / 2026-11-15T12:00:00+00:00 | UNKNOWN | UNREVIEWED / UNREVIEWED |
| s2-unit-24fdf066793326008f0cfe251d8513d10c38168aed62d20e91f6ab9dfa19ccc5 | IND-FIT / INDUSTRIAL_MULTI_SKU | https://example.org/products/pump-p40 / 2026-11-15T12:00:00+00:00 | UNKNOWN | UNREVIEWED / UNREVIEWED |
| s2-unit-a8177fa3d4d7a1a560186930a89a790eb072996804f8d38b65b3f16a2e259197 | IND-DUTY / INDUSTRIAL_MULTI_SKU | https://example.org/products/valve-v25 / 2026-11-15T12:00:00+00:00 | NOT_APPLICABLE | UNREVIEWED / UNREVIEWED |

## DISC-01 / s2_static
Native result: PASS. This captured static homepage nav href reached a captured HTTP 200 category-path page.
Candidate rationale (NOT human authority): Static nav href, captured category HTTP200.
Native observation present: True
Scope: {"anchor_index": 0, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/", "target_url": "https://example.org/category/valves"}
Original pack: ep-2840e3699275dd7cfd54dbed7c72acb6eb078d592fce1e404edc3ae8c1082a06
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## DISC-02 / s2_static
Native result: PASS. This captured static href reached HTTP 200 at the required target path role.
Candidate rationale (NOT human authority): Static product href, captured product HTTP200.
Native observation present: True
Scope: {"anchor_index": 0, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/category/valves", "target_url": "https://example.org/products/valve-v1"}
Original pack: ep-2840e3699275dd7cfd54dbed7c72acb6eb078d592fce1e404edc3ae8c1082a06
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## CTA-02 / s2_static
Native result: PASS. This captured static href reached HTTP 200 at the required target path role.
Candidate rationale (NOT human authority): Read-only contact href HTTP200; no delivery claim.
Native observation present: True
Scope: {"anchor_index": 0, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/products/valve-v1", "target_url": "https://example.org/contact"}
Original pack: ep-2840e3699275dd7cfd54dbed7c72acb6eb078d592fce1e404edc3ae8c1082a06
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## DISC-01 / s2_cms
Native result: PASS. This captured static homepage nav href reached a captured HTTP 200 category-path page.
Candidate rationale (NOT human authority): Static nav href, captured category HTTP200.
Native observation present: True
Scope: {"anchor_index": 0, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/", "target_url": "https://example.org/category/valves"}
Original pack: ep-6bb60b3eefb865c88ca36ee196b4f28b09456ecda8a0440b2149cabd723b6985
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## DISC-02 / s2_cms
Native result: PASS. This captured static href reached HTTP 200 at the required target path role.
Candidate rationale (NOT human authority): Static product href, captured product HTTP200.
Native observation present: True
Scope: {"anchor_index": 0, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/category/valves", "target_url": "https://example.org/products/valve-v1"}
Original pack: ep-6bb60b3eefb865c88ca36ee196b4f28b09456ecda8a0440b2149cabd723b6985
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## CTA-02 / s2_cms
Native result: FAIL_WITH_EVIDENCE. This captured static href returned HTTP 404 or 410 at capture time.
Candidate rationale (NOT human authority): Captured CMS contact href returns404; no delivery inference.
Native observation present: True
Scope: {"anchor_index": 0, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/products/valve-v1", "target_url": "https://example.org/contact"}
Original pack: ep-6bb60b3eefb865c88ca36ee196b4f28b09456ecda8a0440b2149cabd723b6985
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## DISC-01 / s2_spa
Native result: UNKNOWN. Insufficient evidence for this bounded rule judgment.
Candidate rationale (NOT human authority): No supported static nav anchor.
Native observation present: True
Scope: {"anchor_index": null, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/", "target_url": null}
Original pack: ep-02be735e349081633b0a515b003dc8ccf8a767d826b09baa15230c370015b6d2
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## DISC-02 / s2_spa
Native result: UNKNOWN. Insufficient evidence for this bounded static path step.
Candidate rationale (NOT human authority): No captured category source.
Native observation present: True
Scope: {"anchor_index": null, "source_observed_at": null, "source_url": null, "target_url": null}
Original pack: ep-02be735e349081633b0a515b003dc8ccf8a767d826b09baa15230c370015b6d2
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## CTA-02 / s2_spa
Native result: UNKNOWN. Insufficient evidence for this bounded static path step.
Candidate rationale (NOT human authority): No captured product source.
Native observation present: True
Scope: {"anchor_index": null, "source_observed_at": null, "source_url": null, "target_url": null}
Original pack: ep-02be735e349081633b0a515b003dc8ccf8a767d826b09baa15230c370015b6d2
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## DISC-01 / s2_skus
Native result: PASS. This captured static homepage nav href reached a captured HTTP 200 category-path page.
Candidate rationale (NOT human authority): Static nav href, captured category HTTP200.
Native observation present: True
Scope: {"anchor_index": 0, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/", "target_url": "https://example.org/category/valves"}
Original pack: ep-05ff6809b372bb6db9d1288962f76346bb6f50e10221f3cf0db278c70bd3dbcf
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## DISC-02 / s2_skus
Native result: UNKNOWN. Insufficient evidence for this bounded static path step.
Candidate rationale (NOT human authority): 403 on selected RFQ stops the bounded capture before the other SKU.
Native observation present: True
Scope: {"anchor_index": 0, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/category/valves", "target_url": "https://example.org/products/valve-v1"}
Original pack: ep-05ff6809b372bb6db9d1288962f76346bb6f50e10221f3cf0db278c70bd3dbcf
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## DISC-02 / s2_skus
Native result: PASS. This captured static href reached HTTP 200 at the required target path role.
Candidate rationale (NOT human authority): Second captured SKU path only.
Native observation present: True
Scope: {"anchor_index": 1, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/category/valves", "target_url": "https://example.org/products/pump-p40"}
Original pack: ep-05ff6809b372bb6db9d1288962f76346bb6f50e10221f3cf0db278c70bd3dbcf
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## CTA-02 / s2_skus
Native result: ACCESS_BLOCKED. Access was blocked for this path step; no website defect is asserted.
Candidate rationale (NOT human authority): Captured403 is not business failure.
Native observation present: True
Scope: {"anchor_index": 0, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/products/pump-p40", "target_url": "https://example.org/rfq"}
Original pack: ep-05ff6809b372bb6db9d1288962f76346bb6f50e10221f3cf0db278c70bd3dbcf
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## CTA-02 / s2_skus
Native result: UNKNOWN. No native observation exists for this planned scope; it remains an uncovered unit.
Candidate rationale (NOT human authority): Other SKU was not visited; authored scope is retained unobserved, not TN.
Native observation present: False
Scope: {"anchor_index": 0, "source_observed_at": null, "source_url": "https://example.org/products/valve-v1", "target_url": "https://example.org/contact"}
Original pack: ep-05ff6809b372bb6db9d1288962f76346bb6f50e10221f3cf0db278c70bd3dbcf
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## DISC-01 / s2_languages
Native result: PASS. This captured static homepage nav href reached a captured HTTP 200 category-path page.
Candidate rationale (NOT human authority): Static nav href, captured category HTTP200.
Native observation present: True
Scope: {"anchor_index": 0, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/", "target_url": "https://example.org/category/valves"}
Original pack: ep-dca44aac7aff53680b182eff0c47fbacc5da2c8ccb7f19621d8cac38f5cbb66c
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## DISC-02 / s2_languages
Native result: PASS. This captured static href reached HTTP 200 at the required target path role.
Candidate rationale (NOT human authority): Static product href, captured product HTTP200.
Native observation present: True
Scope: {"anchor_index": 0, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/category/valves", "target_url": "https://example.org/products/valve-v1"}
Original pack: ep-dca44aac7aff53680b182eff0c47fbacc5da2c8ccb7f19621d8cac38f5cbb66c
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## CTA-02 / s2_languages
Native result: PASS. This captured static href reached HTTP 200 at the required target path role.
Candidate rationale (NOT human authority): Read-only contact href HTTP200; no delivery claim.
Native observation present: True
Scope: {"anchor_index": 0, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/products/valve-v1", "target_url": "https://example.org/contact"}
Original pack: ep-dca44aac7aff53680b182eff0c47fbacc5da2c8ccb7f19621d8cac38f5cbb66c
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## DISC-01 / s2_skus_complete
Native result: PASS. This captured static homepage nav href reached a captured HTTP 200 category-path page.
Candidate rationale (NOT human authority): Static nav href, captured category HTTP200.
Native observation present: True
Scope: {"anchor_index": 0, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/", "target_url": "https://example.org/category/valves"}
Original pack: ep-648c9f897e1475052972222cbbfd9850712606024b9e5191fc9ab631d8d2466c
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## DISC-02 / s2_skus_complete
Native result: PASS. This captured static href reached HTTP 200 at the required target path role.
Candidate rationale (NOT human authority): Captured200 in this complete bounded fixture; no inquiry submitted.
Native observation present: True
Scope: {"anchor_index": 0, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/category/valves", "target_url": "https://example.org/products/valve-v1"}
Original pack: ep-648c9f897e1475052972222cbbfd9850712606024b9e5191fc9ab631d8d2466c
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## DISC-02 / s2_skus_complete
Native result: PASS. This captured static href reached HTTP 200 at the required target path role.
Candidate rationale (NOT human authority): Second captured SKU path only.
Native observation present: True
Scope: {"anchor_index": 1, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/category/valves", "target_url": "https://example.org/products/pump-p40"}
Original pack: ep-648c9f897e1475052972222cbbfd9850712606024b9e5191fc9ab631d8d2466c
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## CTA-02 / s2_skus_complete
Native result: PASS. This captured static href reached HTTP 200 at the required target path role.
Candidate rationale (NOT human authority): Captured200 in this complete bounded fixture; no inquiry submitted.
Native observation present: True
Scope: {"anchor_index": 0, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/products/pump-p40", "target_url": "https://example.org/rfq"}
Original pack: ep-648c9f897e1475052972222cbbfd9850712606024b9e5191fc9ab631d8d2466c
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## CTA-02 / s2_skus_complete
Native result: PASS. This captured static href reached HTTP 200 at the required target path role.
Candidate rationale (NOT human authority): Captured200 in this complete bounded fixture; no inquiry submitted.
Native observation present: True
Scope: {"anchor_index": 0, "source_observed_at": "2026-11-10T12:00:00+00:00", "source_url": "https://example.org/products/valve-v1", "target_url": "https://example.org/contact"}
Original pack: ep-648c9f897e1475052972222cbbfd9850712606024b9e5191fc9ab631d8d2466c
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## IND-DUTY / s2_duty_conflict
Native result: FAIL_WITH_EVIDENCE. Source-listed pressure 10 bar does not meet the configured scalar comparison to scenario 18 bar; this is not engineering fit confirmation.
Candidate rationale (NOT human authority): Declared10bar vs requested18bar; engineering fit UNKNOWN.
Native observation present: True
Scope: {"assessment_index": 6, "attribute": "pressure", "model": "P40", "source_observed_at": "2026-11-15T12:00:00+00:00"}
Original pack: ep-61eaeb390872727ca104b61ef35558ce5ea53720b3d84e3a6b6706bdab7982cb
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## IND-SELECTION / s2_model_collision
Native result: UNKNOWN. Product identity or configured family applicability is unresolved.
Candidate rationale (NOT human authority): Two source records useP40; identity unresolved.
Native observation present: True
Scope: {"assessment_index": 0, "attribute": null, "model": "P40", "source_observed_at": null}
Original pack: ep-4397422cdd5eeb0fb73e3a2e4dd3e0c8e5555b2e9855b6ce3817e278a16a47a3
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## IND-SELECTION / s2_model_collision
Native result: UNKNOWN. Product identity or configured family applicability is unresolved.
Candidate rationale (NOT human authority): Two source records useP40; identity unresolved.
Native observation present: True
Scope: {"assessment_index": 1, "attribute": null, "model": "P40", "source_observed_at": null}
Original pack: ep-4397422cdd5eeb0fb73e3a2e4dd3e0c8e5555b2e9855b6ce3817e278a16a47a3
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## IND-DUTY / s2_unit_conversion
Native result: PASS. Source-listed flow 200 L/min meets the configured scalar comparison to scenario 10 m3/h; this is not engineering fit confirmation.
Candidate rationale (NOT human authority): 200L/min=12m3/h meets declared10m3/h only.
Native observation present: True
Scope: {"assessment_index": 2, "attribute": "flow", "model": "P40", "source_observed_at": "2026-11-15T12:00:00+00:00"}
Original pack: ep-0732889382631f8aef92094d169b852ad56a1dd29083249f5177f7d8cde1045f
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## IND-SPEC / s2_pdf_unparsed
Native result: UNKNOWN. Some configured procurement attributes were not unambiguously usable; this does not establish absence.
Candidate rationale (NOT human authority): Power absent in parsed table; unparsed PDF is not proof of absence.
Native observation present: True
Scope: {"assessment_index": 1, "attribute": null, "model": "P40", "source_observed_at": "2026-11-15T12:00:00+00:00"}
Original pack: ep-7f642bd2f099e57c188b26cab2311bf7de6102ebadde6f5ca3e9243d40736dd1
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## IND-PROOF / s2_certificate_claim
Native result: FAIL_WITH_EVIDENCE. The supplier-stated validity date precedes the capture date; neither certificate authenticity nor actual supplier qualification is established.
Candidate rationale (NOT human authority): Source date precedes capture; independent authenticity UNKNOWN.
Native observation present: True
Scope: {"assessment_index": 17, "attribute": null, "model": "P40", "source_observed_at": "2026-11-15T12:00:00+00:00"}
Original pack: ep-05a56cdbfc9e1ca55fdf120a9a1525c99019d71d96b568b65d92a81756b0084b
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## IND-PROOF / s2_certificate_current_claim
Native result: PASS. A supplier-stated validity date is not earlier than capture; authenticity remains UNKNOWN.
Candidate rationale (NOT human authority): Source date later than capture; NOT authenticated qualification.
Native observation present: True
Scope: {"assessment_index": 17, "attribute": null, "model": "P40", "source_observed_at": "2026-11-15T12:00:00+00:00"}
Original pack: ep-26e487fefb33d273031b7aafb37ac7ef01c4574614c2eb324c638f53e0be75d3
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## IND-RFQ / s2_buyer_input_gap
Native result: UNKNOWN. The RFQ packet has unresolved buyer inputs or route coverage; no failed inquiry or website defect is asserted.
Candidate rationale (NOT human authority): Destination buyer input missing; no form submitted.
Native observation present: True
Scope: {"assessment_index": 10, "attribute": null, "model": "P40", "source_observed_at": "2026-11-15T12:00:00+00:00"}
Original pack: ep-5f6e3983a70bf0d3c1942eaf5bae9390761d8319dbb993e6331fe61f9fd48a4e
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## IND-FIT / s2_engineering_fit_unknown
Native result: UNKNOWN. Catalog values do not establish application suitability or safe operation.
Candidate rationale (NOT human authority): Catalog scalar values do not establish engineering suitability.
Native observation present: True
Scope: {"assessment_index": 16, "attribute": null, "model": "P40", "source_observed_at": "2026-11-15T12:00:00+00:00"}
Original pack: ep-1f2eb0214baea162ace00294830ae377c9828b6012f87cc1dd9982477e5c9c23
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

## IND-DUTY / s2_motor_not_applicable
Native result: NOT_APPLICABLE. Motor electrical comparison is outside this declared valve profile; actuator requirements were not established.
Candidate rationale (NOT human authority): Declared valve profile excludes motor comparison.
Native observation present: True
Scope: {"assessment_index": 16, "attribute": "motor_electrical", "model": "V25", "source_observed_at": "2026-11-15T12:00:00+00:00"}
Original pack: ep-49aa099b4f399978ef24404a856620ff9c428cccd0a33b5f342315ba8a715b21
Two independent inspections: UNREVIEWED / UNREVIEWED; no identity or date supplied.

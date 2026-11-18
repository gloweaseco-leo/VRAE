# C1-P1 Batch2: configured technical and declaration candidates

Authority: [Owner Batch2 CODE GO](https://github.com/gloweaseco-leo/VRAE/issues/118#issuecomment-6965467885).
Exact base: accepted main `cb86cdb1b57962aa89fa2ef4465131219c8c45e9`.
One Draft covers the shared IndustryPack/source adapter and INFO-02/TRUST-02/TRUST-03.
Chrome diagnostics in Issue126 are independent. No C2 Draft source is consumed.

## Buyer output and limits

The saved synthetic P40/V25 archive produces source-local parameter coverage
with stated R1 revision and water/temperature conditions. A P80 counterfactual
with 200 L/min is supported as a declared pump table, using the existing unit
mapping (12 m3/h); neither model identity nor engineering fit is authenticated.
Unsupported families/units, ambiguous model/revision associations, PDF/curve-only
attributes and unretained material stay UNKNOWN. Missing buyer duty is never a
website fault. The six original industrial rules remain their original system.

The declared certificate's 2025 date precedes capture. TRUST-02 records the
issuer/reference/model/date context and requires human review; it does not say
the certificate is genuine, expired, invalid, compliant, or evidence of supplier
qualification. Explicit case and factory statement contexts follow the same
source-only method, with separately configured date/issuer/reference labels.

Two identity pages declaring the same configured identifier namespace and
identifier can be compared for trimmed decoded name/address/email/telephone
strings. A changed address produces an UNKNOWN conflict candidate with both
original byte citations. Equal names with different/missing identifiers, an
unconfigured namespace or incomplete record stay UNKNOWN. No company alias
matching, legal-entity authentication, contact ownership or entity merge occurs.
PASS means the configured source strings matched, not verified supplier identity.

`example.json` and `example-pack.json` retain actual projection/source bytes;
`conflict-example*.json` retain the changed-address counterfactual. `record.py`
replays saved packs without recollecting or overwriting them.

## Single versioned configuration and entry point

`vrae.industry.l2_v1.load()` remains 1.0.0. Additive `load_s2()` returns 1.1.0 of
the same IndustryPack, inheriting the exact original families, units, labels and
six industrial rules. `s2-1.1.0.json` pins both canonical parent documents and adds
revision/conditions, proof contexts, source-declared identity keys and explicit
applicability profiles. The existing quantity/product-family helpers and strict
static HTML parser are reused; there is no second engineering/fit engine.

P40/V25 are fixtures, not an allowlist. Other model strings require a unique,
explicit source-declared supported family/model record and its own revision,
conditions and configured fields. No fields are combined across models or
different revisions. Unsupported/ambiguous scope does not prove NOT_APPLICABLE.

The only public evaluation/replay composition remains:

```python
config = load_s2(tenant_id=server_tenant, profile_id=server_selected_profile)
held = IndustryPins(config['industry_ref'], server_tenant,
                    version='1.1.0', profile_id=server_selected_profile)
out = evaluate_s2(pack, expected_pack_ref=held_pack_ref, trusted_scope=server_scope,
                  projection_version=INDUSTRIAL_PROJECTION_VERSION,
                  industry_pins=held)
verify_s2_projection(out, pack, expected_pack_ref=held_pack_ref,
    trusted_scope=server_scope, industry_pins=held,
    expected_projection_ref=held_projection_ref,
    expected_projection_version=INDUSTRIAL_PROJECTION_VERSION)
```

`INDUSTRIAL_PROJECTION_VERSION` is `s2-projection-1.2.0`. P0 remains the default;
Batch1 1.1.0 stays byte-identical to its pinned accepted-source oracle. Pins and
profile selection must be independently held from authenticated server task
configuration, not inferred from page text, projection fields, or untrusted
client profile choices. Configuration pin matching is consistency, not current
access authorization. Missing pins yields three UNKNOWN rows. Wrong tenant,
version/profile or ref is rejected with `S2_INDUSTRY_CONFIGURATION`.

## DTO and rule semantics

`industrial_projection` records configuration/source/rule versions, selected
profile, parent/ref, source coverage and `rows`. Each row carries a validated
Observation candidate, reason/model, source-page pointers, citations and details.
Citations contain real ev/source/snapshot refs, original source locator/path,
content SHA256, UTF-8 byte range and exact raw element quote. Metadata-only or
blocked records do not gain ev-refs. Scope and full output are replayed from the
original pinned pack; rehashing a forged citation/configuration is insufficient.

| Rule | PASS subset | UNKNOWN/BLOCKED | Explicit NOT_APPLICABLE |
| --- | --- | --- | --- |
| INFO-02 | One unique declared product record, configured family attributes/units, revision and specification conditions, all source-local. | Missing/duplicate aliases, wrong units/dimensions, duplicate model records, unsupported family, PDF/chart-only or unretained sources. Blocked source record type remains undetermined. | `pump-only` explicitly excludes source-declared valve family; actual family citation and configuration locator are retained. |
| TRUST-02 | Declared model-linked certificate/case/factory kind with configured issuer/reference/exact ISO date and original object/model citation. Date relation to capture is context only. | Missing/ambiguous kind/fields/date, wrong model, ambiguous product association. Blocked sources remain ACCESS_BLOCKED without asserting that their record type was proof. | `technical-only` excludes the rule; `pump-only` excludes proof application to a source-declared valve. |
| TRUST-03 | Exactly two source identity tables with the same supported declared namespace/identifier and all configured strings matching. | Cited literal differences are UNKNOWN human-review candidates; missing/different IDs, unconfigured namespace, missing fields or record-count ambiguity remain UNKNOWN. | `technical-only` explicitly excludes this rule. |

Configuration exclusions have independent content-addressed refs and locators.
No source text can self-declare applicability for these rules. No FAIL_WITH_EVIDENCE
is emitted in this version. Each PASS is a narrow source-presence/string check;
there is no overall health, engineering, authenticity, compliance or completeness
assertion. Source parser bounds remain 131072 bytes, 2048 nodes/32 nesting depth,
one record table and at most 128 rows; unsupported structure/presentation is UNKNOWN.

## Admission, regression and evidence

Output remains `s2p-` read-only candidates. Original RuleExecution/FindingPackage/
Report/Guard admission is unchanged and rejects this envelope. There is no fact
promotion bridge in this Draft. Any future bridge requires its own safety contract
and Owner review. Browser v1 still produces only its accepted read-only candidates.

The original default CI inventory stays exactly 2564. New tests use the mandatory
explicit S2 entry alongside P0/Batch1; local native validation also runs the
original IndustryPack cases. Frozen original blobs remain:

- execution.py: `c183970fd90ec69729221a4174c38d193f4b054b`
- evidence/pack.py: `8d45d5882103323e62bc4bd61a4379899e759966`

`runtime/initial-red-311.*` preserves the first 42-case RED (29 failures/13 fixture
errors before load_s2/IndustryPins existed). Counterexamples expanded the new suite
to 54 cases. Further raw JUnit/logs and hashes are in `runtime/` and `receipt.json`.
The final Draft head's natural CI is reported on the PR, without discarding RED.
No old Guard, SourcePolicy, Worker, SQL/RLS, lease, original inventory or C2/C3
modules are changed. Models/real external sites/production outbound: zero.
Real human Gold remains 0/26; no precision or S2 EXIT is claimed. Draft only;
no merge, deployment or production operation is performed.

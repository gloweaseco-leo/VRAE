# Contract V1 / RA-0

JSON Schema 2020-12 is authoritative for structural shape. Python pure domain functions enforce tenant, idempotency, versions, authorization, evidence references, budgeting and business transitions. Nullable costs are unknown, not zero. Audit completion, report approval, sharing and inquiry are separate facts. Opaque reference strings are not legal-entity identities. All fixtures are synthetic. The OpenAPI spec has no live implementation in RA-0.

## RA-0F boundary and draft compatibility change

Validate JSON shape first, then the relevant domain operation. Schema-valid documents can
still be expired, cross-tenant, cross-run or reference nonexistent objects. A schema PASS
does not validate a natural-language claim. `AIInterpretation.status=VALIDATED` means only
the structural/reference candidate status in RA-0; semantic support is a RA-3 gate.

`ReportVersion.audit_mode` is now required. The unpublished draft V1 contract retains
`schema_version=1.0`; old draft fixtures/producers must be updated before contract freeze.
No deployed consumer or stored production report exists in this phase.

`approve_version` now takes scoped Finding records instead of bare ID sets; `check_share`
requires the same resolved records. `content_hash` is SHA-256 over UTF-8 canonical JSON:
`{"report": <all report fields except content_hash/status/approved_by/approved_at>,
"findings": <complete finding records in finding_ids order>}`. Serialization uses sorted
keys, separators `(',', ':')`, `ensure_ascii=False`, `allow_nan=False`. Changed finding
text, references, rule version, report metadata or audit mode invalidates the old approval.
This binds the RA-0 manifest, not a future HTML/PDF or model output; RA-3 must extend the
versioned content manifest before adding rendered content. Referenced findings must have
passed the evidence graph checks before approval; hashes do not prove factual truth.

Bare-ID `validate_ai_references` is a low-level set check only. Use
`validate_ai_scoped_references` for tenant/run-scoped records; it additionally refuses
unresolved observation references, duplicate IDs and unobserved evidence. This still
requires trusted, graph-validated records and cannot authenticate source bytes.

`validate_existing_grant` is only a time/revocation predicate, never a report access
decision. Reading a shared report requires `check_share`, a trusted latest-version
lookup, token possession/subject authentication and persisted revocation state (RA-4).
Actors, `receipt_verified`, `qualification_confirmed`, audit modes and resolved records
are trusted adapter inputs, not authenticated credentials. RA-0 does not verify VF
receipts, role membership, human identity, source ownership or semantic truth. E3's
`verified_by` must equal the confirming Owner's actor ID; service roles cannot confirm E3.

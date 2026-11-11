# RA-2C-0: one private, verified diagnostic issue

Baseline main `70fa445ab094b01f3e84c50030c19d6c79f4cae3`. Builder
`ra2c0-1.0.0` consumes only a complete caller-pinned `ra2b1-1.0.0`
RuleExecution and caller-pinned EvidencePack. It does not consume detached
Observations or change accepted rule semantics, schemas or frozen documents.

## Actual diagnostic result

`python scripts/verify_ra2c0.py` independently replays the sealed offline industrial
fixture: HOME → CATEGORY → PRODUCT are positive captured steps; the product's
`/contact` href returned 404, generating **one** INQUIRE OBSERVATION Finding;
`/rfq` returned 403, generating UNKNOWN rather than a site defect. The other
13 existing unknown rule results remain explicit unknown items, not new rule
implementations. No issue padding, severity guessing, recommendation, Hypothesis,
revenue claim, approval or public report.

## Mandatory full provenance

`build_findings(pack, execution, expected_pack_ref=trusted_pack_ref,
expected_execution_ref=trusted_execution_ref,
expected_evaluator_version='ra2b1-1.0.0')` verifies the entire execution before
mapping anything. The immutable FindingPackage embeds that complete execution,
the original coverage/scope/version pins, and each selected row with its source
href, original locators/time and **separate target source/snapshot/status/error/
redirect trace**. 404/410 bodies are not retained: no body-content claim is made.
A naked Finding record is insufficient target-response proof; future consumers
must preserve the bound response-metadata edge and verify the whole package.

Finding.evidence_ids use the **original native Evidence IDs**, as the existing
RA-0 guard requires. Each objective row provides an exact `guard_bridge` from
EvidencePack evidence_ref → source/JSON pointer → native Evidence ID / native
snapshot ID, with the original Evidence and snapshot plus the explicitly adapted
guard Observation. Its ID, tenant/run, result and version are unchanged; only
evidence IDs are mapped. `validate_evidence_graph` runs unmodified on those
original records and the mapped Finding. The source HTML bridge alone never
proves the target failure; that edge is established by full execution replay.

UNKNOWN/BLOCKED findings have empty fact IDs. Their RA-0 guard arguments use an
explicit deterministic **UNKNOWN_RUN_CONTEXT scope projection**, not a fabricated
captured Snapshot/Evidence domain record; no native or observed evidence ID is
invented. The full original Observation/outcome/gap/coverage stays in the package.
This also handles Browser-only inputs without inferring hrefs from text.

PASS rows remain `checked_positive_paths`, never defects. NOT_APPLICABLE is refused
because the accepted evaluator has no independent applicability proof. Severity
is always null. All packages are private, NOT_APPROVED and shareable=false; these
flags are replay-validated, not an implemented human-review/share workflow.

## Independent replay and identity

`FindingPackage.load(..., expected_package_ref=trusted_package_ref, ...)` replays
the embedded execution against the caller's trusted pack/execution/evaluator pins,
rebuilds all Findings/bridges/coverage and compares canonical bytes. Recomputing
a wrapper hash cannot authorize a changed status, trace, href, native mapping,
statement, severity, coverage, privacy or approval. Unsupported/old evaluator
versions and duplicate observations are refused. The original RA-2A/B0/B1 fixtures
and original tests remain unchanged and replayable.

Frozen canonical bytes with detached document copies provide deterministic
content-addressed package/Finding identities; changed inputs produce new refs.
No update/persistence service. Bounds: <=1024 consumed rows, <=256 Findings,
<=512 positive rows, <=8 MB execution input and package; excess is rejected,
never silently called complete.

## Limits

Only offline synthetic consistency for observed static href/HTTP response scope.
Not signed authenticity/current authorization, semantic product/company identity,
rendered visibility, form delivery, whole-site quality, ROI, RA-2 stage completion
or production readiness. URLs/metadata are private and may contain PII; no public
output/share interface exists. No new rules, collector, AI, CRM, DB/API/UI/infra,
real website collection, approval/reporting, RA-2D or later-stage implementation.

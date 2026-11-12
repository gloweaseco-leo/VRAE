# RA-3D D1/D2 offline source delivery

Draft PR #58, Issue #57. Accepted main: e40201bf399cc8c5d11a708fcbe33c31f01e67b2.
Final functional source: 190c17d3651e5de9070df0709b2177a6ea3c345b. A subsequent
evidence-only commit freezes this dossier for final hosted CI. Exact final HEAD,
latest main, actual merge-ref/ordered parents and all four job/artifact links will
be recorded in the PR final receipt under FINAL_CI_RECEIPT_POLICY.md. No later
functional source change is allowed without another complete affected test run.

## Actual local results

| Stage | Python 3.11.15 | Python 3.13.13 |
| --- | --- | --- |
| D1 accepted native 404/200 public build/load/render replay | PASS | PASS |
| Final 127 dedicated reviewing cases | 127 PASS / 0 FAIL / 0 ERROR / 0 SKIP / 0 XFAIL | 127 PASS / 0 FAIL / 0 ERROR / 0 SKIP / 0 XFAIL |
| Final compile, whole vrae/tests ruff, whole vrae mypy, pip check | all exit 0 | all exit 0 |
| Four executable synthetic review paths + eight actual refusal probes | all exit 0 | all exit 0 |
| Initial 6c6275f local full attempt | INTERRUPTED, exit 4294967295 | INTERRUPTED, exit 4294967295 |

Complete final default full regression is required in both new real hosted Python
jobs plus original isolated HTTP on final HEAD/main. No completed local full JUnit
is claimed for the interrupted attempts. Original initial dedicated 93/123-case
JUnit and first real 4/4 CI are retained; they do not certify the final revision.
See ANOMALIES.md for the independently reproduced and corrected bool/int defect.

The final native-derived paths and receipts compare EXACTLY across both runtimes.
404 target: 5705ac9e45e5118bc162bdece42f040a61360cf090b09500f7e9de5c89a9d256.
200 target: c309bb1878103fdcb71200de644a685a52a04ab38d29325571cbc3a7f2bb4050.
The 404 path has one actual source-supported issue; original native H0 is
fed173bd07ea8f3d7bca2a35146fd811371f3147877e205a361606bdf9ec6ccd.
The 200 path has zero issues/native=null, only SIMULATED_INTERNAL_SCOPE_ACK.
Original native payload, exact HTML, original Guard and source bytes remain
unchanged before/after all synthetic decisions. No real reviewer is impersonated.

Negative checks cover original-source/quote/ByteRange tampering, true evidence ID
with fake claim/fact/Guard, outer hash recomputation, modified HTML/CSS/footer/H0,
cross-tenant/unassigned/unverified/model/worker/service actor, absent source/object/
policy/clock, duplicated/missing/foreign dispositions and sections, unsupported
prose, strict JSON and metadata types, coverage escalation, stale version/CAS,
competing proposed actions, idempotency conflict and old-version reactivation.
Reasons containing instructions remain inert data. Machine hypotheses never
become facts. Real production review authentication always refuses.

## Preservation and reproducibility

SOURCE_FREEZE.json records exact new source/input Git blobs and SHA-256, the
unchanged main blob/mode count and deterministic dual-runtime comparison. Only
three authorized NEW trees are added. No pre-existing file is modified: reporting,
RA3A/B, Guard/rules/evidence, old tests/Gold/QA histories, native schemas/OpenAPI,
CI, Docker, dependencies and Codex-2 worktrees/branches remain unchanged.

Raw local stdout/stderr/JUnit/commands/scenarios are sealed in raw-local-evidence.zip
with RAW_LOCAL_MANIFEST.json; hashes refer to original byte members. To replay:

    python docs/03-engineering/ra3d-d1d2-offline/regress.py --targeted
    python -m pytest -q

The first command records local dedicated gates with JUnit. The second is the
unchanged complete default command used in both hosted Python jobs; kernel HTTP
and browser security cases run in the original hosted isolated jobs.

## Limits and remaining risks

- Policy/object refs and actors are explicitly TEST_ONLY. Actual current policy,
  immutable storage and verified natural-person/session/task authority do not
  exist here. The production port is unimplemented and always denies.
- In-memory sequential interleaving is not actual simultaneous concurrency,
  thread safety, persistent CAS, transaction, audit, outbox or restart recovery.
  The synthetic UTC high-water is lost on restart. Receipts grant no authority.
- No approve_version/check_share call, native approval, durable ReviewDecision,
  APPROVED ReportVersion, ShareGrant, customer access, DB, API, UI or deployment.
- A01–A48 mapping preserves full future real-auth/DB/UI/production cases as
  NOT_RUN/BLOCKED. Passing offline subsets do not turn them production PASS.
- Evidence binding proves captured content consistency, not real factory identity,
  certification, ranking, lost revenue or commercial causality. Human Gold stays
  0/26; accuracy and reviewer understanding are not evaluated.
- Complete replay memo assumes accepted engine/schema code is fixed by D1. It
  caches immutable bytes only, not identity/clock/latest/authorization/decisions.
- Real models, paid calls, live sites, customer report sends, D3/RA4 production
  development and external sharing remain NO_GO.

Keep Draft. No self merge or deployment. Await independent Owner acceptance.

# C3 L2 task intake v1

Accepted integration baseline: c96c4a8f9cc8dc95e05224ca45efdc2bbe90fd17.
Owner directive: Issue96 comment6911360229. PR109 is merged; its FINAL PASS is
not complete L2 E2E. PR110/111 implementations are not imported on this branch.

`L2Tasks` composes original TaskClient.create/status/read and
SignedGeneratedReader. Server-provisioned RegisteredSource pins the native
source archive and provenance bundle. APP202 yields the actual TaskHandle;
PENDING and TEST_ONLY_DONE are actual queue states, never depth claims.
`read_worker` requires original signed JWT/nonce/job assignment and low-role
reader. It replays the actual result pack and requires its tenant/run to match
the task, and all retained URL/final URL/status/body SHA plus robots identity to
match the provisioned original source. Fresh capture run/timestamps remain
untouched. A signed snapshot is NOT current review authority.

The disposable bootstrap registers a new source `l2-industrial-native-v1`;
accepted-404/200 are unchanged. Original legacy admission requires a source
reference, so public accepted builders produce a zero-issue source-bound
coverage preview, replayed with frozen_reference. It contains no L2 diagnosis
and no native report approval. Full eight-page bytes enter the existing
immutable m1_inputs table. No Worker result is seeded, no raw table grant,
SQL definition, RLS, Worker processing or original identity rule is changed.
The C3 supervisor accepts this one explicit additional source only from its
trusted TEST_ONLY bootstrap state; absent it, original M3 behavior is unchanged.

Run the actual intake with native Python3.11 or3.13:

```
python integration/l2_ops/verify_worker.py --label l2intake311 --minor 3.11
```

This reuses GeneratedRun's PG16/API/independent Worker lifecycle, UID10003
TaskClient over loopback HTTP, original low-role signed result reader and owned
cleanup. It creates a real APP202 and verifies the new Worker pack has eight
pages. Output truthfully remains WORKER_EVIDENCE_VERIFIED_DEEP_ANALYSIS_PENDING.
No new SSR or review-storage engine is created. Source SHA is fixed before run;
stdout is metadata only; raw failures and ephemeral profiles stay private.

Next composition, only after Owner merges C1/C2: native C1 diagnose/verify with
held industry ref against this exact Worker pack, C2 report/version/receipt and
blueprint against the same result, then current-reader-bound C3 Brief. Keep the
original signed current-version lock through Brief COMMIT. Never attach a
standalone example, extend TTL, accept browser JSON as authority, or relabel
M1 DONE as a completed deep report. Full browser review, restart/readback and
same-task business receipt remain required before claiming L2 E2E.

Brief rendering shows supplied proposals in the business view and retains the
intact blueprint and all task/version pins in collapsed verification details.
Missing human labor, rates, consultation and customer confirmation stay unknown;
automated timing is not human labor and no E2/E3 is created.

## First native RED and precise correction

abfa00a895d90e4bb51a805a0654487ee5c0c179, intake311a: original PG bootstrap,
new source INSERT and independent API/Worker startup passed. Real TaskClient
create was denied; raw stderr/stdout are preserved privately, public JSON keeps
all case results and successful owned cleanup. No Worker result was generated.
Root cause: supervisor extended consumer allowlist but original dependency
provisioner still built API config.sources from only the two accepted legacy
fixtures. Original API's fixed-source gate therefore cannot admit the new ref.
Corrected only C3 trusted configuration: the new source's exact registered
reference SHA/policy tuple is passed to the existing private APP config, with
original fields/owner/mode retained. New tests deny foreign tenant/role/kind,
policy/version, bad hash and unexpected existing-source catalog. Old API,
identity, TTL, SQL/RLS and Worker implementation are unchanged. This is ordinary
integration correction, not a permission expansion or random retry.

Operator entry: `python scripts/beta_internal.py l2 worker-intake --label NAME
--minor 3.11` (or3.13). This intake intentionally exits after owned cleanup;
complete L2/report/review mode is pending accepted C1/C2 composition.

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

Second native RED ef81136 (intake311b) stopped before API startup: the provisioner
had already made APP config UID10001/0600. Container root intentionally has no
DAC override, so writing it as root raised PermissionError. Cleanup passed;
raw supervisor log remains private. Correction writes the already-provisioned
file as its original UID10001 owner before spawning API. The helper checks exact
path, ownership/modes, original config equality plus only the pinned extra
source, and original validate_binding. No chmod/chown, new capability, database
permission or authentication relaxation is introduced.

## Hosted CI filesystem RED

First natural CI on ac2605dd1f5cf45fef1000cccd39a081e29621ed, run43839480982,
retained both original artifacts: 311 id14212551587 ZIP SHA256
3741e4553e3711423efee08409b58113807f61ac39e9e9a8678398db06257d77;
313 id14211823912 SHA256
b8c6e68d456f9d186169b78a9c3cdaf021daffa6100561a5fcc14834f5e2fca0.
Both 78-check suites/restart passed; actual intake stopped before APP202 at
API/Worker startup, and cleanup passed. No same-HEAD workflow rerun.

The restricted original native.spawn was reproduced on actual Linux with an
UID1001/GID1001/0755 evidence directory: container root has no DAC override and
cannot create /evidence/app-0.log. Windows Desktop bind behavior did not expose
this POSIX difference. The hosted private supervisor file was not part of the
public first artifact; its exact exception text was not observed. The Linux
reproducer and original spawn code establish the concrete filesystem defect;
new-HEAD hosted execution must confirm resolution, not presumed pass.

The correction applies only to the fresh L2-owned /evidence mount when the
trusted POSIX host supplies its real UID/GID: supervisor UID0 owns it, the host
primary group retains access, mode0770 denies other UIDs. Native child groups
remain cleared; APP config stays UID10001/0600. No new capability/DAC override,
old directory, SQL, role/RLS or identity rule changes. An actual no-network Linux
preflight now reproduces the original denial and verifies supervisor writes,
host-UID read/control writes, UID10003 refusal and unchanged private APP owner.
The Windows path is unchanged. Hosted ownership metadata and supervisor-log SHA
are retained in the new public proof; raw private traces are never published.

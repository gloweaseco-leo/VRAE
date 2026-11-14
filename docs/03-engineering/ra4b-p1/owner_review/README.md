# User-authorized refresh to accepted B3-P0 main

**Current state: required local gates PASS; conditional corrective delivery GO.**
The source-bound native results and preserved historical STOP are in `final/`.
Hosted results and independent Owner acceptance remain separate gates.

The user explicitly authorized ordinary merging accepted main `ae2505f74f7a81d7a563c05d1a811aaa526c2839`
and one fresh full ordinary run per minor on this new source, plus necessary
real compatibility gates. Default expectation is 2,448 PASS /25 existing
isolated SKIP; expected hosted gates are 18. Existing RA1B full16 evidence is
rebound to unchanged protected source without a redundant invocation.
CBC results stay source-bound in the retained earlier cohort below.

# Owner-bounded correction of the first hosted RED

Current authority: [Owner comment 6867683511](https://github.com/gloweaseco-leo/VRAE/pull/83#issuecomment-6867683511).
The earlier [diagnostic authorization](https://github.com/gloweaseco-leo/VRAE/pull/83#issuecomment-6856220858)
and every recorded RED remain part of the history.
Baseline HEAD: `ae628003b4aa9f18054cb79fba5db60fefb02b3d`.
Original hosted results and historical RED remain unchanged. This directory is
diagnostic and privacy evidence; it does not declare final acceptance.

**Previous CBC cohort: native ordinary, PG16 and runtime PASS; source handoff before C3.**
Accepted main `cbcdb6f62d402861e8a12392f53061109a4a7d8b` was ordinarily merged
as `c69cc15e29ca0ad874afc0750120dfbe00263e1c`, with ordered parents
`ed50a972f59bb64258459eba7b4cf989f2903ac6` and that accepted main. All
non-B4 paths equal accepted main. The 22 accepted B5A boundary cases change
the ordinary expectation to 2,443 PASS and 25 original isolated SKIP.

Owner permits the single preserved original full16 result to be interpreted
under the scoped malicious `memory` ruling: that browser's OOMKilled flag
remains true. Its original Worker result passed; this does not excuse OOM in
other cases, Worker OOM, a security escape or host damage. Protected RA1B
source and pins are unchanged. No additional full16 invocation is planned.
This is a PASS candidate, pending the remaining gates and independent Owner
review; earlier intermittent `escape`, `infinite` and `resources` failures
retain UNKNOWN cause.

One fresh native full ordinary run per minor is required on the final source,
followed by fresh genuine PG16, runtime and compatibility gates. Native JUnit
must survive complete owned cleanup and independently match SHA/CRC and test
IDs. Any actual failure stops delivery. After every authorized gate and the
complete provenance audit passes, the existing Draft PR may receive one
fast-forward corrective push and its first genuine corrected hosted CI.
No additional Owner confirmation is needed between passed gates.

`diagnosis/LOCAL_STOP_RECEIPT.json` preserves the earlier `infinite` client
timeout124 and later independently observed native Worker exit0 at about
42.36 seconds. They remain distinct facts, and that earlier gate remains RED.
`diagnosis/EVIDENCE_EXPORT_LOSS.json` preserves the later tmpfs export loss;
stdout was not used to manufacture its missing native XML. Subsequent native
persistent-volume results are recorded separately and cannot relabel either
historical failure.

## Proven failure and narrow repair

Exactly one targeted Linux diagnostic ran per minor, using the original pinned
images, unchanged ordinary test selection, source-volume isolation, zero
capabilities, read-only root, no network, and original resource bounds.
Both collected 2,446 cases: 2,421 native passing calls and 25 original isolated
skips. Pytest nevertheless exited 1: JUnit could not write `/evidence/tests.xml`.
The original checker then encountered the same `PermissionError` writing its
stdout log. The native evidence directory was owned by UID/GID 1001 with mode
0755; container UID 0 had group 0 and no capabilities. No failed assertion,
classification failure, OOM, or source mutation was observed.

`diagnosis/DIAGNOSIS_RECEIPT.json` records the actual counts, exit codes,
memory/time, cleanup and private raw hashes. Replacing only the diagnostic
caller's outer traceback frame with the original published command's native
frame produces **both exact original hosted stderr SHA-256 values**. Python
3.13's source/caret frame is rendered by its native traceback formatter using
the command's AST positions. This corroboration is explicitly distinguished
from downloading the unavailable original raw hosted stderr.

The repair grants the container the fresh output directory's own group and
sets only that newly created B4 output directory to mode 0770. It adds no
capabilities, database grants, source permissions or network access. A native
Linux UID/GID 1001 output-volume fixture checks the actual permission boundary
in the subsequent complete local ordinary regressions. An early exclusive
create/remove probe classifies output failures before running the test suite.
Real nonzero exits and exceptions remain failures.

The first corrected full ordinary invocations both returned native exit 0,
but their tmpfs output disappeared before post-exit export. Their actual
bounded counts and container/cleanup receipts are preserved in
`diagnosis/EVIDENCE_EXPORT_LOSS.json`; missing native JUnit is not fabricated.
The fixture now uses a native persistent output volume. A separate initializer
owns only that empty volume, sets UID/GID 1001 and 0770, and verifies a tiny
native file can be exported after exit before the full suite starts. Its sole
CHOWN capability is absent from the actual zero-capability test container.

No application, Worker business logic, SQL migration, RLS, frozen test,
dependency lock, or timeout is changed by the B4 repair itself. A separate
ordinary merge incorporates accepted main `221637a6ecfd61011d3d7fc9de473758899b4664`:
Owner independently accepted PR86's sole change, the standard CI timeout from
12 to 25 minutes. No other workflow bytes differ. The old 12-minute RED is
preserved. Local ordinary replicas began before this workflow-only merge;
the final seal must identify this exact non-executable-input difference.

## Public evidence boundary

`privacy/BASELINE_PATH_SHA_SIZE.json` inventories all 1,553 baseline evidence
files, including 28 dumps, 148 byte objects and 645 logs.
`privacy/PROVENANCE_AUDIT.json` records independent graph regeneration, offline
PG16 dump expansion, every expanded COPY row's semantic review, generated
proposal/receipt checks and reserved example-domain identity checks. Synthetic
business payloads are distinguished from real, nonsecret execution metadata.
Known private credential fingerprints and secret patterns were also checked;
pattern matching alone was not used as provenance proof.

Original raw baseline files are preserved pending Owner's archive decision.
No additional raw dump, byte graph or long log is proposed for publication.
New raw diagnostics and acceptance outputs stay in ignored `.runtime/`.
The B4 publisher emits curated metadata, SHA/size receipts and sanitized native
JUnit preserving every case outcome. It drops raw assertion details, machine
labels and parameter values. Failure-stage JUnit is clearly marked as harness
evidence, never as a substitute for the ordinary suite. Missing gates, native
failures, actual stage failures, secret matches and missing cleanup remain
nonzero publication failures. Formatter component cases are not presented as
PG, HTTP or Worker acceptance tests.

`diagnosis/ADDITIONAL_LOCAL_RED.json` preserves an additional failed complete
local browser invocation: the `escape` worker reached the existing timeout
while both full ordinary replicas were running. Its native assertion failed;
process exit and exact owned cleanup were verified. CPU contention is only a
hypothesis, not a proven root cause. One complete unchanged browser supervisor
after the owned heavy labs finish is recorded separately; no individual case
retry, timeout extension, test edit or relabeling of this RED is used.

## Remaining acceptance boundary

Only complete fresh dual-minor local gates can authorize the one corrective
push specified by Owner. The existing Draft PR remains TEST_ONLY and requires
independent Owner acceptance. The unchanged original contracts3.13 12-minute
cancellation remains historical RED. The next genuine hosted revision uses
the separately accepted main's 25-minute gate. Any repeat cancellation must
STOP with prior-main timing/runner comparisons; no further timeout change or
blind rerun is authorized. No merge, deployment or real approval is authorized.

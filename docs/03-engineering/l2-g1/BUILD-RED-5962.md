# Single private review of the original build RED

Owner comment6995355794; affected HEAD5962e6e9c46ff8eb20b452a37d9299af47b0a21d.
Original run44422804743, Python3.13 Job135219854546, attempt1 remains RED.
No same-SHA rerun, timeout extension, registry substitution or old gate change.

## Observed primary evidence

- The raw Job log records Docker build exit1 in unit_lab.py before ordinary
  business assertions. The later privacy publication correctly fails closed;
  the old runtime step never runs after the failed unit-build step.
- The existing publisher enumerates `ci-unit-313/build.stderr.log` as1,720 bytes,
  SHA256 `88827dff58f18874cae2a6adac01357b6369769018904098d10f9050352bbde2`.
  Build stdout is0 bytes with the standard empty-file SHA256.
- The original stderr bytes are **not present** in the downloaded curated ZIP.
  The existing policy explicitly leaves raw errors in the ephemeral runner or
  local private storage. The completed hosted runner is not accessible through
  the provided GitHub API. The ZIP's publication.json and native harness XML
  therefore establish missing/failed gates, not a network/registry error cause.
- Curated artifact14481864230 was downloaded once and its server digest and ZIP
  CRC verified: `sha256:917f8f81033d0cdd2b7ae8a1bed739e141d1d20fb3bc1b45ece70d360d5da5b3`.
- The already-performed independent local build used unchanged original Dockerfile,
  all three original locks and the same exact public ECR Python3.13 base digest.
  It exited0; its original stderr has SHA256
  `5f973ac5e4080e37cdd20e46e0f0a496c47b6c2d39102afdb6bc380457bebfd6`.
  Inspection shows dependency layers were **CACHED**. This does not reproduce a
  clean hosted runner pull, and cannot prove that the CI failure was external.
  Its uniquely labeled diagnostic image was removed; no existing image tag or
  other user's resources were deleted.

## Falsifiable decision

`CAUSE_UNDETERMINED_ORIGINAL_STDERR_NOT_RETAINED`.

No evidence currently distinguishes hosted environment, registry response,
builder parameters or a specific build-source problem. It would be false to
label this `EXTERNAL_INFRASTRUCTURE_CONFIRMED`. The specific absent evidence is
the1,720 bytes matching the original stderr digest above. If recovered privately,
that text can confirm or falsify this decision without publishing its secrets.
Do not weaken the original publication boundary to obtain it.

Affected capability: ordinary frozen Review127/QA118 regression and the later
original RA4B runtime/cleanup checks lack completed evidence **for that Job on
5962e6e**. It is not an application assertion failure, and the unavailable proof
is not replaced by local build success or by the independent G1 workflow.

The new normal merge of accepted main is required by the Owner and preserves
5962e6e as a parent. A new exact HEAD's natural CI is new integration evidence;
it never changes the retained old RED into a pass. Until those checks and Owner
review complete, there is no all-green or G1 final acceptance claim.

# Exact final-head evidence protocol

Freeze all SQL/runtime/tests/fixtures and local dual-Python PG JUnit, catalog,
backup/restore/restart and teardown evidence before the final CI push. Preserve
all original accepted main blobs/modes; normal-merge newer accepted main only.
No rebase, force push, hidden case exclusions, skip/xfail or oracle changes.

Require original four jobs SUCCESS plus both new real PostgreSQL 16 hosted jobs
SUCCESS on final HEAD + current accepted main. Read every original checkout log,
Git merge-ref object with ordered main/head parents, actual 127 D1/D2 and 118
RA3C V2 call reports, raw PG 54-call receipt/catalog/JUnit and backup/restart/
teardown artifacts. Retain failed/intermediate stages with exact SHA labels.

After that final CI completes, raw final logs/metadata/downloaded artifacts and
receipt audits go in this authorized evidence tree's post-ci/<final-head>/.
Keep them intentionally uncommitted, as in the Owner-accepted PR58 protocol, so
embedding a receipt does not change the very HEAD it certifies. Update Draft PR
body/comment with exact HEAD/main/merge parents, counts, original links, hashes,
limits and all relevant exceptions. No commit solely to embed its own final CI.

Keep Draft, no self merge/deploy. Await separate Owner RA4A_P1_FINAL_PASS. Do not
infer full RA4A EXIT, authenticated humans, object bytes or customer authority
from any SQL row/hash/test role. Production ports remain unimplemented/denying.

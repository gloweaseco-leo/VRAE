# Exact-blob continuation of PR114

Authority: [Owner independent review and L3 continuation](https://github.com/gloweaseco-leo/VRAE/pull/114#issuecomment-6920145471).
This addendum follows the original `0bdb41d` evidence. Earlier README, receipts,
30/36 CI outcome, six RED jobs and all original source history remain intact;
their statements describe that earlier HEAD, not the continuation outcome.

## Narrow change

`integration/ra4c_b5a/publication.py` now permits exactly the original path
`vrae/evidence/pack.py` when its HEAD Git blob is
`8d45d5882103323e62bc4bd61a4379899e759966` and Git reports no staged or
unstaged changes to that path. Wrong committed bytes or a dirty approved file
fail closed. No path pattern or additional runtime exception is introduced.
The reviewed pack bytes themselves have not changed.

Original ENTRY, all five approved document blob/clean-worktree checks and
runtime/identity/SQL pins remain unchanged. The original
`accepted_files_modified` list still reports the pack path; compatibility does
not hide its modification. Original frozen tests and all timeouts remain intact.

The new isolated `tests/evidence_perf/freeze_cases.py` uses disposable actual Git
histories, the exact approved pack bytes and the actual five approved document
blobs. It covers success/audit inclusion, a different committed pack blob,
staged/unstaged/deleted pack, unlisted original runtime/identity/SQL/document
paths (including a similarly prefixed pack filename), and both committed and
dirty tampering of every one of the five documents. No approved runtime blob
is substituted with a fixture hash. The old six publication freeze cases also
run unchanged alongside the 35 pack-consistency cases.

## Prior RED evidence and bounded continuation

The archived original hosted logs and digest-verified safe artifacts were
reviewed. B4 3.11 exposes the original PG Docker startup command's 30-second
TimeoutExpired and cleanup. B3 3.13 publishes summary/source only; B7 3.13 and
B5B 3.11 publish curated XML status and private original XML hashes, without
exception bodies. Those private originals were not uploaded into the available
archives and cannot be reconstructed from their hashes. No private hosted
runtime directories are present in this independent worktree. Their first
exception/root cause remains UNKNOWN; no environment or regression attribution
is inferred from the opposite minor's success.

Owner permits one new-HEAD natural full CI with unchanged isolation/timeout
standards. If a suite still fails, only one controlled local diagnosis directed
at its first root cause is allowed; no indiscriminate rerun or historical
diagnostic authorization is reused. Raw XML, credentials, URLs and bodies stay
private. Only bounded exception category/stage, code-impact evidence and
original hashes may be published. An unresolved substantive safety RED leaves
this PR Draft/STOP.

Original 35-case performance safety and ABBA comparison remain explicit in the
new-HEAD workflow. The new 27-case exact-blob suite gets separate native JUnit.
Actual B5A PG/security/browser and safe publication must run through the original
workflow; entry acceptance alone is not a PASS.

Real P40 APP202/PG16/30-second Worker commit and signed read remain C3's task.
C3 must not copy unmerged PR114 source into formal PR112 integration; normal
sync follows Owner merge. This continuation does not change that contract or
claim that the offline performance fixture performed a live commit.

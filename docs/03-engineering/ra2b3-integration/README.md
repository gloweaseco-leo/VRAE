# PR #20 latest-main integration

Owner instruction: https://github.com/gloweaseco-leo/VRAE/pull/20#issuecomment-6793977003

The original worktree and branch were clean at recovery, with HEAD
`6ab0f4195cf96bfca458557b3fa36ae64f4ab0b4`. After fetching origin,
`git merge --no-edit origin/main` merged Owner-accepted main
`1f88cc4148d2e905c387af82f5943683d3507a72` without conflicts, producing
`3f72385201a092f2dd290684780de257f5d55f64` (parents: original HEAD, accepted main).
No implementation, workflow, sealed fixture, historical evidence or benchmark
file was edited during integration. Only this separate evidence directory is added.

`regress.py` records both local interpreter runs against the merge commit.
Each run checks compileall, Ruff, mypy, 54 dedicated INFO-01 tests, full pytest,
pip check, and RA-2A/B0/B1/B2/C0/B3/D0 offline replays. The D0 replay uses no
write flags. All 13 command exits must be zero in each summary. The 25 existing
host skips require disposable Linux isolation labs; hosted CI supplies those gates.

The final evidence commit changes documentation only; the tested implementation
is the merge commit above. Hosted CI must run against the final exact PR HEAD
and a checkout merge ref containing accepted main. The final SHA, checkout SHA,
four job URLs and results are reported in the original PR after CI completes.
PR remains Draft for Owner final acceptance; no automatic merge or further scope.

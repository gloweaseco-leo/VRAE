# Owner-required latest-main integration only

Owner checkpoint: PR58 issuecomment-6824511332. This closes only the remaining
latest-main gate; it does not redevelop or expand the accepted D1/D2 kernel.

Original QA HEAD c849d3d01a2af976bfe0cdef4fabb7f840bfbd37 had a clean tracked tree.
Its 17 intentionally untracked post-CI receipt files were hashed first and left
in place. Fetched origin/main was independently asserted equal to Owner's
a185f9ce7e67904f2c0aef854716ca9844144592. Ordinary
`git merge --no-edit origin/main` completed without conflicts, rebase, cherry-pick
or force. Worktree merge 06b57a8f7139bc0211d192883aaba66c2184e9fb has ordered parents
c849d3d01a2af976bfe0cdef4fabb7f840bfbd37 and
a185f9ce7e67904f2c0aef854716ca9844144592.

MERGE_SCOPE.json proves all 3069 latest-main blobs/modes and all 101 previous
Issue57-owned blobs/modes unchanged. In particular all 13 D1/D2 source/input blobs
are identical; frozen-set SHA remains
0933f8f4c27dd60b6ac44d6d19a811e5ce73f2976aabb96242f5ba080f7a702a.
The three approved PR56 changes to its existing docs UI come from accepted main;
there is no local edit to them. No source, test, Guard, renderer, schema, CI,
dependency, Docker, original QA oracle or historical dossier is modified here.

This new evidence-only directory is committed before fresh final CI. After that
commit, leave the exact final HEAD fixed. New full raw logs, metadata, security ZIP,
immutable scope proof and dual-Python read-only 404/200 replay outputs live under
post-ci/<new-final-head>/ per the previously committed FINAL_CI_RECEIPT_POLICY.md.
Do not overwrite or relabel old HEAD/JUnit/CI receipts.

Use the original verify_ci.py to inspect the actual four new jobs, checkout
merge-ref ordered parents, 127 real D1/D2 call reports, 13 source hashes and
kernel/browser lifecycle artifact. In addition, verify_v2.py inspects the
unchanged QA transport's actual 64 primary +54 denial call reports in both Python
and isolated HTTP, frozen V2 SHA/profile and the 24 actual HTTP network negatives.
Read-only scenarios.py replays accepted 404/200 bytes through native public
build/load/render and verifies simulated results against the prior frozen paths.
No new test oracle, simulation behavior or functionality is added.

Keep Draft, auto-merge disabled; wait for separate Owner FINAL PASS. Do not start
RA4A until PR58 is approved under its next work-package authorization. Do not
modify Codex2 Issue60/RA4C0 branches. Authenticated review, durable decisions,
models/paid calls/live sites, sharing, customer delivery and deployment remain NO_GO.

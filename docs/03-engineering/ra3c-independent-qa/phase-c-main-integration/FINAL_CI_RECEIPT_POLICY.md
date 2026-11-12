# Final exact-HEAD CI receipt

All local source/replay/JUnit/browser/initial-failure/real-Docker evidence is sealed and committed before the final four hosted jobs are requested. The final QA HEAD is then held fixed.

The **final** four original hosted job logs, merge-ref object/parents, source/118-case receipts and security evidence are read after those jobs finish. Their authoritative GitHub run/job links and decoded-log SHA256 are submitted in the final PR48 comment, bound to that exact final HEAD. Complete local copies are retained in the Codex1-exclusive QA docs `final-ci-<head>/` folder. They are deliberately not followed by another branch commit: doing so would change the very HEAD whose four jobs were verified. This external receipt is distinct from earlier already-committed source/CI artifacts and is plainly identified, not silently labeled as pre-existing in the checked-out commit.

No code, frozen fixture, source assertion, workflow or branch HEAD may change between final CI request and final receipt. If it changes or main advances, verify the new pair with genuinely new jobs. Keep Draft and wait separate Owner PR48_FINAL_PASS; no merge/auto-merge.

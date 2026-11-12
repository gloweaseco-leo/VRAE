# Exact candidate feature CI audit

Source: GitHub Actions run [43168905209](https://github.com/gloweaseco-leo/VRAE/actions/runs/43168905209), head `e2f9466f06bb3e7afbaf2e55575562d9d6fb453e`.

All four original job conclusions are SUCCESS: [Python 3.11](https://github.com/gloweaseco-leo/VRAE/actions/runs/43168905209/job/131017194941), [Python 3.13](https://github.com/gloweaseco-leo/VRAE/actions/runs/43168905209/job/131017194929), [isolated HTTP](https://github.com/gloweaseco-leo/VRAE/actions/runs/43168905209/job/131017194677), [isolated browser](https://github.com/gloweaseco-leo/VRAE/actions/runs/43168905209/job/131017194980).

Every retained checkout log independently prints actual checked-out merge commit `f476078717985e68d34177106e161cffe90eb967`. The fetched merge object has ordered parents `60dbe1e1acfc84ad0849e84f3abe3712ad8ebccd` (main), `e2f9466f06bb3e7afbaf2e55575562d9d6fb453e` (feature). All four log messages also identify both parent SHAs. This is feature CI proof at the final candidate plus latest main, not proof that the independent QA branch has already completed later Phase C integration.

Both domain jobs report 1943 passed / 25 existing environment-dependent skips. The isolated HTTP job reports 1967 passed / 1 browser-container skip and records real socket/TLS/DNS/egress evidence, including zero bait connections and absence of external routes. The isolated-browser lifecycle job completes actual container start/config/log/final-state commands and uploads synthetic security evidence artifact `13920849360`; its original command log is preserved rather than replaced with local host results.

`run.json` and `jobs.json` retain connector-returned GitHub metadata. The four numbered `.log` files retain the connector-decoded log text (LF text representation, not a claim of binary identity with GitHub's ZIP archive). Node.js action deprecation warnings remain visible. No local host skip has been silently counted as a security pass, and no candidate screenshot is used as Codex-1's independent visual evidence.

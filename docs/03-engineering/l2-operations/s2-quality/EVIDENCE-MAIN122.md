# C3-P0 accepted-main combination evidence

Owner ruling: PR123 comment 6953131190. This is combination validation only, not full S2 P2.

- Accepted main: `94a58b9867d96f104941874e07a2c4a4c84ec27f` (Owner-merged PR122).
- Exact local execution merge: `9884552cff58df308cd6d11d89734478be7b5db4`.
- Merge parents: `de00615975d03ef680b65d846265313103644738`, then accepted main.
- Native Python 3.11 and 3.13: each 131 passed, zero failures/errors/skips; full export, independent replay, read-only intake and legacy 26 completed.
- Old human Gold 0/26; new human Gold 0/32. Quality remains NOT_EVALUABLE. No reviewer identity, score or signature generated.
- All previous RED and evidence retained. Original S0, Gold verifier/samples, pack/Guard/Worker/SQL/SSR unchanged.
- No PG/Worker/model/external website or deployment started. Test-source transport remains offline synthetic; package dependency/CI GitHub traffic is separate.
- [Raw native ZIP and hash manifest](published-main122/manifest.json), [merge/frozen audit](published-main122/merge-and-frozen-audit.json), [3.11 JUnit](published-main122/native-311.xml), [3.13 JUnit](published-main122/native-313.xml).

## CI trigger coverage

The accepted C2 workflow is path-filtered to C2 files; the C3-only PR diff does not select it.
A new C3-owned `s2-c3-accepted-c2.yml` invokes the exact accepted C2 test and Chrome entry points on the PR head, for both Python minors.
It preserves the original C2 workflow, source, lock, timeouts, browser request denial and artifact content.
This is a CI coverage change, not a new browser or report engine.
The post-local seal adds only this CI entry and evidence; Python/runtime executable diff from the local execution SHA is empty.
Natural CI outcomes, each run/job attempt and official artifacts are supplied in the PR receipt after all runs reach terminal state.
No claim is made that local-only collection executes the original full default inventory, or that synthetic statistics measure human precision.

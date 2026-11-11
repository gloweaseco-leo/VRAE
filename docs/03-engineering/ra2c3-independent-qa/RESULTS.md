# Actual results and open gate

Test source frozen at commit `5dcb09526c1dc08a2d7060866ab96bdfc3fe017d` before
candidate inspection; test file SHA-256:
`2c35973cd9e811961a8e68109e37a1db2d00908fabdaeb565f5c2331118fb110`.
Baseline source is `4b5ebe689f048ba20d38354ae7c03d4bbaf37c6a`.

| Runtime | Actual exit | Passed | Failed | Setup errors | Skipped |
| --- | --- | --- | --- | --- | --- |
| Python 3.11.15 | 1 | 23 | 1 | 115 | 0 |
| Python 3.13.13 | 1 | 23 | 1 | 115 | 0 |

Raw commands, UTC timestamps, input hashes, JUnit and stdout are in
`runs/baseline-311/` and `runs/baseline-313/`. This is a pre-implementation
expected RED: baseline rejects `ra2c3-1.0.0` with `FINDING_INTEGRITY`.
The 115 prerequisite errors are **not** evidence that mutation defenses passed.
The 23 passes establish the accepted evaluator's independent 18-case status
oracle, two separate positive/broken-contact comparisons (404 and 410), and
three byte/pin-compatible historical C0/C1/C2 replays.

## Exact candidate result

Codex-1 Draft [PR #36](https://github.com/gloweaseco-leo/VRAE/pull/36), functional
HEAD `995325203be1385b98cc888f8b2dd7cc9e85ddcf`, base equal to the accepted baseline.
The unchanged frozen source above ran in isolated archive tree
`3bfac9b70354ca7f1465060f0c469927b5c81211`, overlaid only with the three owned
test/input files. Both interpreters imported the archived builder, verified by
the recorded import probe. All original archive file hashes remained unchanged.

| Runtime | Actual exit | Passed | Failed / errors | Skipped |
| --- | --- | --- | --- | --- |
| Python 3.11.15 | 0 | 139 | 0 / 0 | 0 |
| Python 3.13.13 | 0 | 139 | 0 / 0 | 0 |

See `runs/candidate-9953252-311/`, `runs/candidate-9953252-313/` and the full
candidate archive manifest under `runs/candidate-995325203be1385b98cc888f8b2dd7cc9e85ddcf/`.
`scenario-refs.json` additionally records independent positive/404/410/403/500
pack, execution and package refs, group counts, privacy and genuine defect edges.
Run metadata pins QA checkout `8c1397f16001335a2cee8f015cd43f5c7b14c2ac`; the
test and both input hashes match the initial contract commit exactly. No test
assertions changed after candidate discovery. No candidate defect was exposed
by this matrix, so no production fix or repair/retest cycle was necessary.
GitHub's exact functional HEAD was read again after these runs and was unchanged.
Any later functional HEAD requires a fresh run; this result does not extend to it.

Four real hosted candidate CI jobs were independently read back as successful
for the same HEAD (raw job metadata saved as `hosted-ci.json`):

- [contracts-domain 3.11](https://github.com/gloweaseco-leo/VRAE/actions/runs/43041192668/job/130593114081)
- [contracts-domain 3.13](https://github.com/gloweaseco-leo/VRAE/actions/runs/43041192668/job/130593114125)
- [isolated-http](https://github.com/gloweaseco-leo/VRAE/actions/runs/43041192668/job/130593114287)
- [isolated-browser](https://github.com/gloweaseco-leo/VRAE/actions/runs/43041192668/job/130593113730)

These are PR #36 CI results, distinct from this baseline-based QA PR's expected
RED main-suite jobs. No workflow was changed or disabled. The independent run
is a Codex-2 bounded engineering result, not Owner FINAL PASS. It cannot
authenticate companies, credentials, factory existence, contact effectiveness
or commercial reputation. Historical scope limitations and lack of human Gold
acceptance remain; RA-3/4/5/6 stay frozen.

The Owner's clarification resolves the earlier contradictory same-pack wording:
TRUST PASS and CTA-02 CONTACT 404/410 defect use separate independently pinned
packs. Genuine captured 404/410 remains a CTA defect and TRUST UNKNOWN.

At the initial post-freeze PR discovery, GitHub returned no open PR. Candidate
HEAD validation was subsequently completed above; this QA branch stays Draft
and must not be merged while main lacks C3 compatibility. Owner coordinates
whether and when the separate QA tests are integrated.

Tooling note: the first GitHub comment read was blocked by sandbox networking;
the escalated read succeeded. An exploratory inline Python pin extraction had
a quoting error and was replaced by the checked-in baseline-only extraction
script. Neither was counted as a passing test. Ruff E4/E7/E9/F passed for the
owned test and helper scripts before the contract commit.

The supplementary scenario-record command initially could not import the
archived tests because sandbox access to the temporary directory was denied.
The same command succeeded with approved access. This was a record-generation
environment error, not a test failure; the already recorded 139/139 candidate
runs had successfully accessed and hashed that archive.

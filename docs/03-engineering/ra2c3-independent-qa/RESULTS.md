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

No candidate vulnerability or C3 engineering PASS can be claimed yet. The new
builder must first successfully build/load/verify real positive evidence, then
all frozen adversarial tests must execute against its exact final functional
HEAD. Revisions require another exact-HEAD run of unchanged QA source. A green
run covers this bounded synthetic matrix only; it cannot authenticate companies,
credentials, factory existence, contact effectiveness or commercial reputation.

The Owner's clarification resolves the earlier contradictory same-pack wording:
TRUST PASS and CTA-02 CONTACT 404/410 defect use separate independently pinned
packs. Genuine captured 404/410 remains a CTA defect and TRUST UNKNOWN.

At the initial post-freeze PR discovery, GitHub returned no open PR. Candidate
HEAD validation remains pending; this QA branch must stay Draft and must not be
merged while main lacks C3 compatibility. There is no Owner FINAL PASS claim.

Tooling note: the first GitHub comment read was blocked by sandbox networking;
the escalated read succeeded. An exploratory inline Python pin extraction had
a quoting error and was replaced by the checked-in baseline-only extraction
script. Neither was counted as a passing test. Ruff E4/E7/E9/F passed for the
owned test and helper scripts before the contract commit.

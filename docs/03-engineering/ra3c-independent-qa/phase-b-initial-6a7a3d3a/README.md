# Exact-SHA Phase-B attempt — QA integration NOT_READY

Functional candidate formally identified by PR #47 body:
`6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2`.
Frozen QA source/input commit: `fa645b58549dfd21a6b80656d403f672b790acd8`.
Read-only preflight submission: `3ee9314c1d24f49d6fa75386220a876846e7f8c2`.
The exact candidate was checked out in a new detached worktree
`.worktrees/ra3c-qa-phaseb-6a7a3d3a`. Only the three frozen QA test/case/input
paths were overlaid; no candidate file was edited and no push was made there.
Both runtime results enumerate all three exact Git blobs and verify all **1,506
candidate blobs unchanged** before and after execution.

| Actual frozen-suite attempt | Python 3.11.15 | Python 3.13.13 |
| --- | --- | --- |
| Collected cases | 64 | 64 |
| Fixture setup errors | 64 QA_MAPPING_NOT_BOUND | 64 QA_MAPPING_NOT_BOUND |
| Passed / assertion failures / skipped | 0 / 0 / 0 | 0 / 0 / 0 |
| Substantive business cases executed | 0 | 0 |
| Confirmed production defects from this pytest attempt | 0 | 0 |

Unlike Phase A, reporting **exists and imports** on this exact candidate. The
deliberately unbound adapter stops at fixture setup. These are QA mapping errors,
not old missing-module errors, real business failures or GREEN. Complete JUnit,
commands, raw logs and byte SHA are in py311/py313. No failing assertion was
skipped, xfailed, weakened or made to pass by a fake adapter.

The eight concrete input/representation gaps are in
`../adapter-preflight-v1/REPORT.md` and submitted to Owner at
[PR48 comment 6815044983](https://github.com/gloweaseco-leo/VRAE/pull/48#issuecomment-6815044983).
Their resolution needs Owner contract adjudication; the original frozen assertions,
14 scenarios and 11 original freeze-added blobs remain unchanged. No production
fix is inferred from the mapping errors and none is made by Codex-1.

## Supplemental real browser evidence — separate from the frozen 64

While awaiting adjudication, independently render the exact candidate's own
404/200 demonstration HTML locally. This is **not** our 14-scenario output and
cannot substitute for F01–F08 or prove independent input/Guard acceptance.
No Codex-2 screenshots are reused. `prepare_ui_supplement.py` reads exact Git
objects, independently recomputes full draft/editorial hashes and verifies exact
HTML bytes against the native HTML SHA. The actual retained HTML is unchanged.

`ui-supplement-r3` is the current observation set: Chrome 156 via private CDP
pipe, fresh profile, sandbox retained, 375px mobile/touch emulation and 1280px
desktop. Four actual captures, **18 real mouse evidence clicks**; quoted source
matches companion document on each click. Observed target-page external requests
and runtime exceptions are both zero. This is target-page interception evidence,
not a kernel egress certification or independent original-source/Guard replay.
Commands and driver SHA are in browser-observations.json. DNS resolution is
disabled, HTTP(S)/WS/FTP blocked and Fetch admits only the exact local file.

| Current supplemental view | Width / client / scroll | Body | Privacy label | Actual clicks |
| --- | --- | --- | --- | --- |
| 404 mobile | 375 / 375 / 375 | 14px | **11px** | 6 |
| 404 desktop | 1280 / 1265 / 1265 | 14px | 12px | 6 |
| 200 mobile | 375 / 375 / 375 | 14px | **11px** | 3 |
| 200 desktop | 1280 / 1265 / 1265 | 14px | 12px | 3 |

All four private labels were above fold, with one main heading and no horizontal
overflow. The mobile label misses the frozen F04 >=12px independent heuristic.
This is a measured supplemental UI acceptance gap, not an assertion that the
unbound 64-case suite ran substantively, nor a general accessibility verdict.
The 200 case correctly has no four-layer issue card; that absence is not a defect.

### QA reading observations, not customer approval

Images were actually inspected at both desktop/mobile layouts and mobile source
expansion. Desktop gives a clear single issue, exact captured HTTP404, source URL
and capture time, then visibly provisional impact/action/recheck. The proposal
“是否影响实际询盘，仍需人工核实” preserves uncertainty; the next conversation
“先核实范围，再明确改造动作” stays within candidate Rebuild discussion without
promising delivery or conversion. The 200 preview says “0 项可报告问题” and
explicitly distinguishes scoped coverage from whole-site health. It does not pad
three defects or present source self-description as company certification.

The phone view wraps the issue and evidence without horizontal overflow, with
visible synthetic/private status, but its 11px privacy text misses the existing
12px QA gate. Five stacked buyer-task cards also move the actual finding further
down the page: a possible usability improvement for a busy manufacturer, not a
proven sales or conversion effect. The evidence expansion exposes the original
anchor quote and references as text; this browser check compares displayed quote
with the companion report, **not** a fresh independent source replay.

No report approval, customer reaction, source authenticity guarantee, commercial
ROI, Human Gold result or overall visual PASS is inferred. Current overall gate:
**QA_MAPPING_NOT_BOUND / frozen-case VISUAL_NOT_VERIFIED / CUSTOMER_SHARE_NO_GO**.

## Preserved exceptions and reproduction

- Initial worktree overlay was attempted before checkout completed. Git refused
  with active index.lock. The checkout was allowed to finish, clean state was
  confirmed and overlay retried. No lock was removed; no source deletion/edit
  occurred. Transient incomplete-index status was not treated as real changes.
- First local browser run failed with permission-denied GPU/network subprocess
  exits in the command sandbox. Original empty capture/error and Chromium stderr
  remain in ui-supplement; no screenshot/PASS is fabricated for that run. The
  exact original driver is retained as capture_ui_supplement.v1.mjs.
- Authorized outside-command-sandbox retry r2 produced genuine narrow desktop
  views, including width375, but did not set mobile emulation. Its evidence and
  exact v2 driver remain. r3 separately sets real mobile/touch emulation for375;
  r3 is the current observation set. Neither retry changes report bytes, business
  inputs, browser's own sandbox or frozen assertions.

To reproduce the measured font gap on unchanged actual candidate 404 HTML:

```javascript
// At 375px with mobile emulation, read-only CDP Runtime.evaluate:
getComputedStyle(document.querySelector('.private-bar')).fontSize // "11px"
```

The candidate renderer's mobile CSS supplies this rule; desktop reports12px.
Codex-2 owns any production fix and must submit a new exact final SHA. If the
12px frozen heuristic is contested, Owner must adjudicate; Codex-1 will not
silently lower it. Driver protocol reference:
[Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/).

Keep PR #48 Draft. No edits/pushes to PR47, self-merge, real source/model call,
customer report/share, spend, RA3D or deployment.

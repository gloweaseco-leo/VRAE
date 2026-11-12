# OWNER_ADJUDICATED_RA3C_QA_V2 — final exact-candidate evidence

Against formally released feature `e2f9466f06bb3e7afbaf2e55575562d9d6fb453e`, Python **3.11.15** and **3.13.13** each actually pass the same **64 business goals plus 54 explicit rejection controls**, with zero V2 failures/errors/skips/xfails. This is bounded V2 acceptance evidence for Owner review. It does not turn the historical V1 GREEN or grant customer/report/share approval.

Authority: [Owner adjudication](https://github.com/gloweaseco-leo/VRAE/pull/48#issuecomment-6815825564). [Complete test-function diff](V1_TO_V2_FUNCTION.diff), [mapping/change manifest](V1_TO_V2_CHANGES.json), [frozen source manifest](FREEZE_V2.json), [remaining risks](REMAINING_RISKS.md).

## Exact identities and source preservation

- Original V1 source freeze: `fa645b58549dfd21a6b80656d403f672b790acd8`; original evidence HEAD: `61b9173a32789185bd7fcaf750adb6118ec4bc43`. All **1560** original tree blobs remain unchanged, including original 64 tests, 14 inputs, setup RED, 11/53 RED, JUnit, archives, original screenshots and authoring records.
- New V2 source freeze: `00655091ac06ede0a26233feb6ff75da9fe642bb`; all **23** initial V2 blobs remain unchanged. The original 64 case descriptors/IDs/business goals are exact copies. All 53 original invalid requests are explicit controls, plus one independently pinned source-incomplete M08 control.
- Final feature / externally held candidate and metadata binding: `e2f9466f06bb3e7afbaf2e55575562d9d6fb453e` / `f6956dd7d62f86d611f2164197c5436e43876764`. Reporting `ra3c-1.0.0`, renderer `ra3c-html-1.0.2`. External pins were committed before feature execution; no attacked document supplies trusted pins.
- Isolated workspace: `D:/Projects/VRAE/.worktrees/ra3c-qa-v2-e2f9466f06bb`, detached exact feature SHA. No push/commit to the candidate or Codex2 branch. All **1611** native candidate blobs remain unchanged before/after all runs. All **152** existing `vrae/` and `tests/` blobs from accepted main `60dbe1e1acfc84ad0849e84f3abe3712ad8ebccd` are unchanged in the feature. QA overlays add only Codex1-owned files.
- [Complete source/helper/input hashes](runs/e2f9466f06bb3e7afbaf2e55575562d9d6fb453e/SOURCE_HASHES.json) distinguish canonical Git bytes from Windows worktree bytes. V2 test Git blob `43992a9084ee5f2c6bbd6f6b051a986da5c9a20c`, canonical Git SHA-256 `9e60d3e307d3a4726adca62b79319b6a85f11a65453390b68a5003bd6a643e62`, actual executed CRLF-source SHA-256 `5cf88a5b331c57c0f6e19240e353ef1d55314c58481a3c4d9265eb45804246fe`.

## Actual executions and historical RED

Counts below apply **independently to each Python version**. No original source, discovery rule or CI config was rewritten, and no skip/xfail was added to V1/V2.

| Group | PASS | FAIL | ERROR | SKIP/XFAIL | Raw pytest exit |
| --- | ---: | ---: | ---: | --- | ---: |
| V2-only, 64 primary goals +54 denials | 118 | 0 | 0 | 0 /0 | 0 |
| V2 groups inside full run | 118 | 0 | 0 | 0 /0 | part of combined run |
| Unchanged accepted regression | 1943 | 0 | 0 | 25 existing host/container skips /0 | part of combined run |
| Original V1, replayed against new candidate | 11 | 53 | 0 | 0 /0 | part of combined run |
| Complete combined run, 2150 collected nodes | 2072 | 53 | 0 | 25 /0 | **1** |

Every combined-run failure is original V1: **52 `REPORT_UNSUPPORTED_PROSE`**, **1 `REPORT_GUARD_NOT_VALIDATED`**. There are no additional failures or setup errors. The original first-round 6a7a3d3a 11/53 evidence and JUnit remain at their original paths, independent of this new replay. V1 is executable historical RED, not a positive business gate or a hidden expected-failure marker.

- Python3.11: [V2 JUnit](runs/e2f9466f06bb3e7afbaf2e55575562d9d6fb453e/py311/v2/junit.xml), SHA-256 `15f6e26c13e39d80832d4664d5f357dbf59fa677c120eccd46def0cb72adc69c`; [full JUnit](runs/e2f9466f06bb3e7afbaf2e55575562d9d6fb453e/py311/full/junit.xml), SHA-256 `e7e44df8dd408d54e417dc8f072a8efd7a0d2a29a27845544410d788ef3d25c2`.
- Python3.13: [V2 JUnit](runs/e2f9466f06bb3e7afbaf2e55575562d9d6fb453e/py313/v2/junit.xml), SHA-256 `f77046eae8caa093072edb1edfa48dd944ebc2904137d117a05990e057cadd25`; [full JUnit](runs/e2f9466f06bb3e7afbaf2e55575562d9d6fb453e/py313/full/junit.xml), SHA-256 `4b397a186cdfa9ac839f89fb9d1db27f8f14a8525ae7c6a543ef235295cab377`.

Each adjacent `results.json` records actual command, cwd, Python, timings, original return code, every node, properties and source proof; `stdout.log` preserves raw output. Both V2-only runs started after the completed browser dossier was committed. Combined runs and two earlier dossier invocation failures are retained in the [anomaly record](runs/e2f9466f06bb3e7afbaf2e55575562d9d6fb453e/EXECUTION_ANOMALIES.md). Final source lint also passes E4/E7/E9/F.

## Source authenticity and business interpretation

All original 14 synthetic sources are unchanged. The new explicit admissible requests were authored from those independently captured EvidencePack/Findings/Guard contracts, without copying Codex2 tests or reports. Original unsupported strings/NOT_RUN remain unchanged negative inputs. Separately held exact safe proposal vocabulary is only a proposal and keeps `HUMAN_REVIEW_REQUIRED`. No runtime adapter repairs strings, source refs, scope, approval or absent fields.

Actual public build/load/render ran in both Python versions, with byte/ref-identical output. Every displayed Claim's citation quote independently resolves to exact original EvidencePack byte offsets and externally held Guard binding/status. A genuine evidence ID does not establish certification, SEO rank, revenue, loss or commercial causality. Four genuine-ID hostile profiles require both a real benign report and actual rejected attack. M08 fully bound duplicate target yields one issue; incomplete bindings reject. M03–M06 exercise native HTML bytes, nested evidence, actual Claim pointers and structural absence of score fields. All 64 primary cases completed without using the optional defensive-refusal early return as report success.

The actual one-issue report gives a manufacturing buyer a concrete product-to-contact HTTP404 path, source time and quote, then separates possible buyer friction, a proposed repair and a recheck method. It does not claim lost sales. The zero-issue report retains coverage and evidence limits, expressly avoiding a claim of full-site health or completed enquiry verification. This supports a bounded next-step discussion; synthetic reading is not measured customer value.

## Independent real browser evidence

Codex1 generated its own native reports and launched its own Chromium, fresh profile, actual 375px mobile/touch and1280px desktop. No Codex2 screenshot is substituted. [Original observations](runs/e2f9466f06bb3e7afbaf2e55575562d9d6fb453e/browser/browser-observations.json), [source-bound reading memo](runs/e2f9466f06bb3e7afbaf2e55575562d9d6fb453e/independent-reading-memo-v2.json), [dossier](runs/e2f9466f06bb3e7afbaf2e55575562d9d6fb453e/observations.json).

- Four actual views, **18 actual internal evidence mouse clicks**, matching displayed native quotes plus independent original byte replay; zero observed page external requests and zero page exceptions.
- Privacy banner **12px** at both widths, above fold; body14px; no horizontal overflow. One-issue view has four visible business layers. Exact report HTML SHA-256: one issue `7627007e307840a80cc8168028bfd565a8215bf7b51a03961dbc8548362a5380`, zero issues `935219243ed47d652590be2f05fdeae5d509579832b654626ac2f659f480f523`.
- [375 one issue](runs/e2f9466f06bb3e7afbaf2e55575562d9d6fb453e/browser/contact-404-375.png), [1280 one issue](runs/e2f9466f06bb3e7afbaf2e55575562d9d6fb453e/browser/contact-404-1280.png), [375 zero issues](runs/e2f9466f06bb3e7afbaf2e55575562d9d6fb453e/browser/contact-200-375.png), [1280 zero issues](runs/e2f9466f06bb3e7afbaf2e55575562d9d6fb453e/browser/contact-200-1280.png), [expanded mobile source](runs/e2f9466f06bb3e7afbaf2e55575562d9d6fb453e/browser/contact-404-375-first-evidence.png).

Original Windows Chromium sandbox-access/network-service restart warnings remain in stderr. Page observations are not a claim of clean browser-process logs or kernel egress isolation. All reading notes explicitly deny customer/report/human approval.

## Hosted CI and sealed evidence

[Feature workflow43168905209](https://github.com/gloweaseco-leo/VRAE/actions/runs/43168905209): **four actual SUCCESS**. Four complete checkout logs show merge-ref `f476078717985e68d34177106e161cffe90eb967`, with ordered parents main `60dbe1e1acfc84ad0849e84f3abe3712ad8ebccd` and feature `e2f9466f06bb3e7afbaf2e55575562d9d6fb453e`. [Full CI audit and original job links](runs/e2f9466f06bb3e7afbaf2e55575562d9d6fb453e/candidate-ci/AUDIT.md) includes real isolated HTTP/browser evidence and retained warnings. This is feature CI, not later QA/main Phase C CI.

[SUMMARY.json](runs/e2f9466f06bb3e7afbaf2e55575562d9d6fb453e/SUMMARY.json) records exact counts/hashes/blob invariance. [RAW_MANIFEST.json](runs/e2f9466f06bb3e7afbaf2e55575562d9d6fb453e/RAW_MANIFEST.json) lists **53 raw evidence members** with individual hashes; [raw-v2-evidence.zip](runs/e2f9466f06bb3e7afbaf2e55575562d9d6fb453e/raw-v2-evidence.zip), 1,874,547 bytes, SHA-256 **`3f4278c360d172ffef550ef122bd7d6c2a002b0f247d6237e99e3ac3e490ed13`**. Exact original bytes are inside the ZIP; Git text normalization is separately identified in source hashes.

## Owner decision boundary

No new confirmed production defect was found in the covered V2 domain; the independently reproduced prior mobile11px defect is now12px. Human Gold0/26 remains `QUALITY_GATE_NOT_EVALUABLE`, free prose/commercial ROI is unproven, and three distinct real-defect positive reports are outside these independent source fixtures. Existing container skips need separate real CI. The original discoverable V1 RED will require Owner-approved treatment during later QA/main CI integration; it has not been hidden here.

Keep PR #48 Draft and stop for Owner FINAL PASS. No merge, Codex2 production edit, real source/model call, paid call, customer share, deployment or RA3D production work occurred. Phase C integration/four new QA CI are not declared complete.

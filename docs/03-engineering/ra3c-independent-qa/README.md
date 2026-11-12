# RA3C independent product QA — Phase A, CUSTOMER_SHARE_NO_GO

Owner authority: Issue #46. Accepted baseline:
`2429be6dc5d7dcb48221ab179f063b93ce4b1956`.
Dedicated worktree `.worktrees/ra3c-independent-qa`, branch
`test/ra3c-independent-product-acceptance`, Draft PR #48.
Frozen test/input source commit:
`fa645b58549dfd21a6b80656d403f672b790acd8`.
No candidate RA3C implementation, test, fixture or screenshot was inspected before
this source commit. No production/source/previous test/CI file was changed.

## Product judgement

**Current delivery conclusion: NO-GO.** Accepted main cannot yet produce the
RA3C private one-page report. A genuine captured broken PRODUCT → CONTACT edge
can support a useful repair discussion: identify the exact recorded path/status,
explain a possible inquiry obstacle as a hypothesis, propose scoped link/page
repair for review, and repeat a bounded read-only capture to verify the result.
It cannot prove manufacturer legitimacy, certification, SEO position, lost sales,
delivered inquiries or a client case. The source's own claims remain untrusted.

A 200/blocked/unknown capture should communicate precisely what was checked,
what remains unknown and why no defect was verified. Its usefulness depends on
clarity and restraint. One static broken contact path gives one real issue; it
does not justify a three-item sales narrative. These independently authored
captures currently exercise 0/1 distinct genuine defect, plus duplicate-edge
dedupe and padded-four-item tampering. They do not establish a three-distinct-
issue positive case or broader rule coverage.

The candidate still needs actual private HTML, independently bound editorial
integrity, original evidence navigation, concise Chinese four-layer explanation,
375px/1280px readability, legible private status and substantive local business
reading. No screenshot or customer response exists here. **VISUAL_NOT_VERIFIED**.
Human Gold remains 0/26, OWNER_AUTHORIZED_GOLD_DEFERRED,
QUALITY_GATE_NOT_EVALUABLE. No E2/E3 opportunity, commercial ROI or customer
approval has been inferred from synthetic QA.

## Independent freeze and actual evidence

[MATRIX.md](MATRIX.md) and the cases fixture define 64 cases: T12/B10/C8/D12/E14/F8.
14 local route scenarios yield 18 independently pinned accepted-source guard
contexts. [INPUT_PREPARATION.json](INPUT_PREPARATION.json) records their literal
refs and outcomes. Fixtures contain small hand-authored routes, not copied
candidate fixtures. Public-looking example.org URLs are synthetic keys resolved
only by a fixed in-memory DNS/transport; no real source is fetched.

[FREEZE.json](FREEZE.json) pins nine source/protocol files by Git blob and SHA256
and enumerates all **1,400 unchanged accepted baseline blobs**, including RA3A,
RA3B V1 RED/adjudicated V2, historical evidence, security and Gold files. Git LF
content SHA and original Windows working-copy SHA are separately labelled;
line-ending conversion is not a claim of identical raw Windows bytes.

Phase-A dual Python runs are recorded in `phase-a/py311` and `phase-a/py313`:
raw commands/exit codes, logs and complete JUnit. New tests collect normally;
their module fixture imports the absent `vrae.reporting`. Each runtime reports
**64 errors, 0 failures, 0 passed, 0 skipped**: prerequisite setup RED, not 64
executed business failures and not a reporting PASS. No temporary module,
skip/xfail or candidate-ready claim hides it. Full combined-suite PASS is not
claimed. Accepted-controls JUnit and RA3A/B native replay logs are separate.
The selected accepted controls actually report **681 passed, 0 failed, 0 errors,
0 skipped on each Python**, including frozen RA3B independent V2 and RA2C3
independent adversarial QA plus domain/contracts/RA0F/collection security. These
are compatibility results, not RA3C business assertions executed successfully.

The source-freeze hosted run [43154291249](https://github.com/gloweaseco-leo/VRAE/actions/runs/43154291249)
is also authentic RED: contracts-domain 3.11/3.13 each **1,872 passed, 25 existing
environment skips, 64 reporting setup errors**; isolated HTTP **1,896 passed,
1 existing environment skip, 64 reporting setup errors**; isolated-browser
**SUCCESS**, with actual synthetic security artifact 13914594969. Existing
environment skips were not added or altered by this QA. Four complete decoded
checkout/job logs and metadata are in `phase-a/ci-source-freeze`. All four checked
out merge-ref `b4244c3ec8f417efebd20c0791dff96742b9bac3`, with exact parents
accepted main `2429be6dc5d7dcb48221ab179f063b93ce4b1956` and source freeze
`fa645b58549dfd21a6b80656d403f672b790acd8`. This is not four SUCCESS or an RA3C
visual test. Later evidence-only commit HEADs are separately identified in the PR.

Reproduce from the frozen source with either installed Python 3.11/3.13:

```powershell
python -m pytest -q tests/reporting/test_ra3c_independent_acceptance.py --junitxml=red.xml
python docs/03-engineering/ra3c-independent-qa/audit_inputs.py
python docs/03-engineering/ra3c-independent-qa/freeze_sources.py
```

The versioned Phase-A runner refuses to overwrite existing evidence. Its expected
RED returncode does not turn pytest into GREEN. Exact test execution SHA is stored
in each results.json; subsequent docs/evidence commits must preserve frozen blobs.

## Limits, next gate and anomaly record

- Candidate API is uninspected and adapter **NOT_BOUND**. The independent
  [SUBJECT_PROTOCOL.md](SUBJECT_PROTOCOL.md) specifies audited transport/extraction;
  a different legitimate API/serialization may require QA mapping review. It must
  not be mislabeled as a production failure or patched with expected-value data.
  Oracle contradictions go to Owner; frozen assertions stay unchanged.
- Hostile-input safe public refusal is allowed for designated malicious source/
  fabricated-claim cases, recorded as DEFENSIVE_REFUSAL_NOT_VISUAL_PASS. Normal
  truthful 0/1-issue cases require real output, preventing reject-everything PASS.
- Browser metrics/dossiers require genuine exact-HTML captures and manual image/
  log inspection. The test cannot authenticate an operator's subjective review
  by checking JSON alone. Cached browser files are not execution evidence.
- Full suite, all historical replays and four SUCCESS hosted jobs on final
  functional/main integration are Phase C gates. Phase A hosted failures caused
  by absent reporting remain truthful; no old CI is reused as new acceptance.
- During pre-freeze QA authoring, the input-audit helper initially read a
  nonexistent guard `statement` field. It was corrected to resolve the actual
  original interpretation by claim pointer, before the frozen source commit.
  Conditional native ReportVersion checks and recommendation language were
  clarified against Issues #45/#46, without candidate inspection. Routine path
  discovery misses and Windows LF/CRLF notices do not change production files.

Phase B starts only with an exact final functional SHA released under the Owner
protocol: detached no-push workspace, only frozen QA overlays, separately audited
adapter, both Python runtimes, actual browser evidence and reproducible genuine
defects to Codex-2. No editing their source/branch. Phase C follows actual Owner
functional merge, normal integration and all final CI/replays. Keep Draft and
wait for independent Owner acceptance; no self-merge or RA3D.

No live model/site/provider, payment, customer communication/share, external
report, deployment or change to accepted historical artifacts was authorized.

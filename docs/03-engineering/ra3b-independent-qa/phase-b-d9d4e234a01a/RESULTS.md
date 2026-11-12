# Phase B actual result: 223 passed / 1 failed on both Python versions

Authority: [Owner Phase B GO](https://github.com/gloweaseco-leo/VRAE/pull/44#issuecomment-6811678438).
This authorization supersedes the earlier ready-notification wait. No further
Codex-2 notification was required. Phase B executed the frozen candidate QA only;
full-main integration/new four-success hosted CI remain later Owner gates.

## Exact source, freeze and execution scope

- Functional candidate HEAD: `d9d4e234a01a27a4543404b7060c8867e60d0309`.
- Frozen QA HEAD: `8b961b72ce544251e6f28177cc0ea183f7486af0`.
- Test source freeze: `68336821bb2b8c919b0d04bd86400c165329d9a6`.
- Test Git blob: `e2f188fe234db3131d6ea1604b05d25f4ffd8e61`.
- Test SHA256: `74d595b26f3ba570029194966902568e0365d104eb53e8056741087427892209`.
- Input Git blob: `7fa3a75e3001ad9c95abee2aff66a2b73a32e740`.
- Input SHA256: `7a8c8177b1ef2bc7baa15628d621b5c2a89ae4ac0b50a589553d961c10282428`.
- Detached candidate worktree:
  `D:/Projects/VRAE/.worktrees/ra3b-qa-candidate-d9d4e234a01a`.
- Only two untracked overlay files: frozen independent test and input JSON.
  Before/after snapshots verify exact Git and raw-byte identity and zero candidate
  tracked-source changes. Actual guard/test/input import paths are recorded.
- No Codex-2 branch/worktree/code/fixtures were modified. No frozen assertions,
  helper functions, parameterization or inputs changed; no skip/xfail or stub.

The original QA worktree remains separate. Evidence additions here do not change
which QA HEAD/source bytes were executed. Earlier prerequisite RED, sample/freeze
amendments, raw archive and baseline hosted CI records remain untouched.

## Actual counts, not planned-case claims

| Runtime / authoritative record | Collected | Passed | Failed | Errors | Skipped | xfail / xpass | pytest exit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Python 3.11.15, `python311/` | 224 | 223 | 1 | 0 | 0 | 0 / 0 | 1 |
| Python 3.13.13, `python313-rerun/` | 224 | 223 | 1 | 0 | 0 | 0 / 0 | 1 |

JUnit, stdout/stderr, commands, import paths, timestamps, original candidate tree,
and before/after overlay hashes are in each runtime directory and `index.json`.
The **authoritative raw bytes** are also preserved losslessly in
`phase-b-raw.zip`: index lists every ZIP member's byte size/SHA256 and the
archive SHA256. Existing Git text normalization changes CRLF in some readable
text copies; those paths are explicitly listed in the index. ZIP members retain
the exact original bytes and were reread/hash-verified. No repository settings
were changed to hide this distinction.
Actual commands, run from the detached candidate root:

```text
D:/Projects/VRAE/.venv/ra1a311/Scripts/python.exe -m pytest -q tests/interpretation/test_ra3b_independent_adversarial.py --tb=short --junitxml=D:/Projects/VRAE/.worktrees/ra3b-independent-qa/.venv/ra3b-independent/phase-b/python311/qa.xml
D:/Projects/VRAE/.venv/ra1a313/Scripts/python.exe -m pytest -q tests/interpretation/test_ra3b_independent_adversarial.py --tb=short --junitxml=D:/Projects/VRAE/.worktrees/ra3b-independent-qa/.venv/ra3b-independent/phase-b/python313-rerun/qa.xml
```

The unamended suite is **RED**, not 224 PASS and not full acceptance. No case was
removed from the denominator. The additional first Python 3.13 run also has 224
JUnit cases / 223 passed / 1 failed; its external recorder failed after writing
pytest files, before persisting pytest returncode/summary. Raw files and the
transcribed terminal exception remain in `python313-first-recorder-error/`.
The full unchanged suite was rerun, not a subset, to capture authoritative exit
code and pre/post integrity. No result from that first run was discarded.

## The single failure is an objectively contradictory no-op oracle

Identical node on both versions:

```text
tests/interpretation/test_ra3b_independent_adversarial.py::test_fact_tamper_even_with_recomputed_hashes[True-fact_ref]
```

The frozen test chooses `part='fact_ref'`, temporarily assigns
`'forged-codex1'`, then calls its own `rehash()` helper. That helper computes
`fact_ref` over all fact fields **excluding fact_ref**, so it restores the exact
original valid fact ref. It subsequently recomputes the binding ref, also
restoring the original value. No other field was changed. The validator receives
the exact original legal binding, interpretation, source pack, package and pins.

Frozen logic, with no production modification:

```python
args = qa.proposal()
before = canonical(args[1][0])
args[1][0]['fact']['fact_ref'] = 'forged-codex1'
qa.rehash(args[1][0])
after = canonical(args[1][0])
assert before == after  # Proven byte equality, not merely matching checksums.
result = qa.run(args)
```

Independent reproduction on **both** runtimes proves:

- Entire original and restored binding bytes are equal.
- Binding SHA256 before and after:
  `f8601b836adabd15649683572a225d97242c496041a4c838d2705b2cf4d061bf`.
- Temporary mutated bytes SHA256 (before helper restores):
  `fbcaa3fe2a9a8fdc861a907937da54d1f345ea6f3282237622c5b005d673c685`.
- Original/restored fact ref:
  `cf-33c84c85a4252c33a9673f271f220a676dc00af814c9f1cbb44d7847a6b87762`.
- Original/restored binding ref:
  `cb-8a3fac29fd29eca4149861e4910670f8cb293fde7f72845a4cca02c57e91f299`.
- Actual status: `SOURCE_FACT_BINDING_VERIFIED`, reason `LITERAL_ONLY`;
  `approval_status=NOT_APPROVED`, `shareable=false`, `semantic_approval=false`.

The source is a narrow legitimate captured element, not a fabricated credential,
ranking or business-loss claim. Expecting REJECTED for this fully restored input
contradicts the suite's positive literal-source controls and deterministic replay
oracle. By contrast, the `False-fact_ref` case, whose forged ref is not restored,
passes its expected rejection. Other genuine fact mutations with recomputed
hashes also pass their rejection checks.

Reproduction source is `reproduce_noop.py.txt`; actual stdout, stderr and command
records are under `repro-python311/` and `repro-python313/`. Run the reproduction
script by its absolute QA evidence path **from the detached candidate root**; it
adds that root to import search paths and imports the frozen QA module unchanged.

**Classification: test-oracle contradiction requiring Owner adjudication; no
confirmed implementation defect from this failure.** No production fix is
requested merely to reject a legitimate original input. Findings and minimal
reproduction are submitted to #42 and #44. Frozen assertions are NOT adjusted,
not even to remove this apparent no-op case; await Owner discussion first.

## Observed coverage and risks

All remaining 223 frozen cases pass on both runtimes, including objective false
legal registration/certification/factory ownership, SEO rank, conversion/revenue
and causal assertions with genuine evidence IDs; per-claim mismatches; cross-pack
and tenant/policy scope; bytes/locator/target-response tampering and rehash;
UNKNOWN/BLOCKED abstention; prompt/output injection and fake approval/shareable;
mandatory human-review ceiling for prose. JUnit retains every individual result.

This finite synthetic result is not universal semantic entailment proof, external
source authentication, current SourcePolicy permission, customer readiness,
security certification or real business outcome validation. Hypotheses and
recommendations remain HUMAN_REVIEW_REQUIRED; literal source checks do not grant
report/share authority. Human Gold is deferred 0/26, quality N/A.

## Recorder/setup exceptions retained

1. Initial sandbox GitHub access was denied; approved-environment retry read the
   Owner authorization and fetched the exact source. No stale source was tested.
2. The previously frozen setup helper initially copied all 16 exclusive QA paths.
   Full Owner instructions require only test+JSON overlay. All extra QA docs were
   moved out before test execution, retained under ignored bootstrap evidence;
   both actual runtime integrity snapshots prove exactly the permitted two files.
3. While first Python 3.13 pytest ran, Codex-1 created an untracked evidence helper
   in the original QA documentation directory. The external recorder's original-
   QA clean assertion then failed after pytest completed. Helper moved to ignored
   storage; complete unchanged Python 3.13 suite rerun. This is a recorder error,
   not a candidate failure or suppressed test. Initial pytest files preserved.
4. First external reproduction invocation used script-directory import search and
   could not resolve candidate interpretation. Added explicit candidate cwd to
   that **new reproduction recorder**, not to frozen tests or production. Actual
   full-suite runs already verified correct imports; both final reproduction
   outputs independently pin the candidate module path.

**STOP: Draft #44 retained. Independent suite is RED pending Owner oracle
adjudication; no FINAL PASS claimed. Do not merge functional main/QA branch or
run new combined-main gates without the later authorization. No self-merge,
model/provider/paid call, live site, external customer report, deployment, RA3C/D.**

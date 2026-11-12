# OWNER_ADJUDICATED_QA_V2

Authority: [Owner final oracle adjudication](https://github.com/gloweaseco-leo/VRAE/pull/44#issuecomment-6812189251).
Decision: TEST_ORACLE_CONTRADICTION_CONFIRMED,
IMPLEMENTATION_DEFECT_NOT_DEMONSTRATED. This repair is not an implementation
change or Owner FINAL PASS.

Only node
`test_fact_tamper_even_with_recomputed_hashes[True-fact_ref]` is changed.
The V1 test repaired its own forged fact_ref, restoring the legal original input.
V2 retains `fact_ref='forged-codex1'` and recalculates **only binding_ref** over
the enclosing binding excluding binding_ref. Before validation it asserts that
the forged inner ref remains and canonical full binding bytes differ from the
original legal binding bytes. The expected rejection is unchanged.

Other 223 parameter cases retain their original logic, inputs and acceptance
criteria. AST comparison confirms every node outside the one function and all
decorators/parameter lists are identical. The new branch is selected only for
`part == 'fact_ref' and rehash_attack`; `False-fact_ref` remains unrehashed and
all other rehash cases still use the same unmodified helper. Planned count 224,
14 synthetic scenarios, no skip/xfail, no copied developer tests or stubs.

Historical records are append-only:

- Original source is independently saved as `original-test.py.txt` with Git blob
  `e2f188fe234db3131d6ea1604b05d25f4ffd8e61`, also retained in original QA
  `8b961b72ce544251e6f28177cc0ea183f7486af0` and original source freeze.
- Original freeze manifest is copied unchanged to `original-FREEZE.json`; original
  `FREEZE.json`, `FREEZE-v1.json`, matrix, inputs and all old evidence remain intact.
- V1 actual 223/1 JUnit/raw SHA/reproductions remain under
  `../phase-b-d9d4e234a01a/`; they are not relabeled or replaced with V2 GREEN.
- V2 source snapshot: `v2-test.py.txt`; exact old/new patch: `v1-v2.patch`;
  `diff-proof.json` and `case-inventory.json` preserve scope and source hashes.
- Versioned `manifest.json` pins the V2 source commit and all input/source blobs
  before candidate execution. It supplements, not overwrites, original manifests.

Candidate remains exactly `d9d4e234a01a27a4543404b7060c8867e60d0309`.
A **new detached worktree** preserves the original V1 overlay separately; only
the V2 test and unchanged independent input JSON are overlaid. Record actual
guard/test imports, all candidate/overlay SHA checks before/after, full 224-case
pytest output/JUnit/exit on both 3.11 and 3.13, plus explicit malformed-inner-ref
and valid-outer-wrapper proof. Raw bytes are archived losslessly when complete.

Report INDEPENDENT_QA_V2_CANDIDATE_GREEN only if both actual runs collect/pass
224, zero failure/error/skip/xfail/xpass, exit 0. Otherwise preserve actual RED and
report any genuine issue without editing Codex-2 code. Full main integration and
new combined four-success hosted CI remain later Owner gates after functional
acceptance/merge, not a claim of this isolated retest.

Finite synthetic checks do not prove universal semantics, external legal/company
authenticity, ranking/revenue/causality or current authorization. Source binding
does not approve prose, reports or sharing; HUMAN_REVIEW_REQUIRED remains. Gold
0/26 deferred is quality N/A. No model/provider/paid call, real site, customer
report/share, deployment, RA3C/D or self-merge. Draft only; STOP for Owner review.

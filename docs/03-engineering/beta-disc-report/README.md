# DISC private report v1

S1 of Issue94 / Issue97, based on accepted main
`447005b2951f43e8d8643632d663de268f278329`. This is an offline synthetic
engineering route. It does not approve a report, share it, or change Beta EXIT.
B1/B2 remain 2/7; Human Gold remains 0/26; G1/G2/G3 remain NO-GO.

Owner comment 6886105818 subsequently authorized the exact additive B4 host
inventory correction described in the historical L3 receipt. The manifest
`exact-test-ids.json` preserves 2473 IDs collected in the clean accepted-baseline
worktree and pins the 46 new IDs plus their test-source hash. Its hash is fixed
independently in the host acceptance step. No unknown additions, duplicate IDs
or new skips are accepted. All original QA/Review/skip/XML/cleanup invariants
remain independent. The protected container checker and workflows are unchanged.

## Explicit version route

Use `vrae.interpretation.disc_report_v1` and
`vrae.reporting.disc_report_v1`; the legacy public APIs retain their versions.
The caller must independently hold all source, execution, package, scope, Guard,
metadata, renderer and report pins. A proposal cannot supply its own authority.

The evidence chain is the existing EvidencePack → explicit `ra2b6-1.0.0`
RuleExecution → `ra2c3-1.0.0` FindingPackage → `ra3b-disc-1.0.0`
GuardResult → `ra3c-disc-1.0.0` ReportDraft. The new Guard admits only the two
additional DISC static-href / same-pack HTTP 404 or 410 facts. It independently
replays the existing package and verifies exact UTF-8 source bytes and bindings.
Hypotheses and recommendations remain HUMAN_REVIEW_REQUIRED.

The versioned report uses the accepted native contracts, evidence graph,
ReportVersion validation, metadata rules, immutable draft envelope, CSS,
escaping and evidence renderer. Its version-specific projection and presentation
live in the new directory because the frozen QA pins the complete legacy
`draft.py` and `renderer.py` sources. Those two legacy files and all frozen tests
remain unchanged. The only protected-source difference is the explicit Guard
version branch; its original public route retains its original behavior.

At most three independently bound issues are shown. Missing sources/targets,
blocked access and UNKNOWN do not become negative facts. Static path roles do
not prove product identity, browser visibility/clicks, rankings or business loss.
INFO/TRUST/SEO remain narrow positive source facts; ten disabled rules remain
UNKNOWN. The default evaluator remains `ra2b0-1.0.0`.

## Local reproduction

From this worktree, with the locked development dependencies installed:

```powershell
$env:PYTHONPATH='.'
python -m integration.beta_disc_report
python -m pytest -q --junitxml=docs/03-engineering/beta-disc-report/.runtime/full.xml
node docs/03-engineering/beta-disc-report/browser-test.mjs
```

Run Python acceptance separately with 3.11 and 3.13. Set `RA3C_CHROMIUM` to a
local Chromium executable if the documented Windows default is unavailable.
The browser uses local files, CSP denying external resources, a CDP URL
blocklist and a loopback blackhole proxy. It tests 1280/375/320 widths, actual
evidence-anchor clicks, escaped content, inactive actions, and one-page printing.
The script closes its own browser in `finally`.

Eight private HTML files and complete replay inputs are generated under
`.runtime/previews/`. Open `disc-01-404.html` or `disc-02-404.html` locally;
200/403 counterparts demonstrate zero issues. All raw capture objects, Guard
bundles, private HTML, screenshots and native XML stay in ignored `.runtime/`.
Only sanitized identifiers, counts and hashes belong in the public receipt.

The first route attempt hit the frozen source fingerprint at collection; its
native XML and source diff remain in `.runtime/`. That fingerprint was not
changed or bypassed. Interrupted exploratory runs are not acceptance evidence.
The initial dedicated run also found two test-only accesses to a nonexistent
`source_pins` output key after successful legacy hash replay; these were corrected
to the existing `pins` contract. No historical failure is relabeled PASS.

## Remaining gates

Publish a Draft PR only after local acceptance and publication checks pass,
then inspect natural GitHub CI at its actual source and merge ref. Owner alone
accepts and merges. S2 requires S1 Owner merge and a new precise Owner entry
before reopening the paused Issue90 worktree. No unmerged sibling code, SQL,
Worker, migration, role/ACL, frozen assertion or existing workflow is imported
or changed here.

# Actual development records and final-gate distinction

No original core, contract, QA44, frozen fixture, Gold, dependency or CI assertion changed.

1. Initial dedicated reporting suite: one newly written test passed a dict to the
   EvidencePack storage constructor whose object parameter is a tuple. Corrected
   that test construction only; next dedicated run 68 passed. Later two meaningful
   cases added (actual active source tags and immutable version-two replay), for 70.
   Original dedicated JUnit records remain in `development-reporting-raw.zip`.
2. Initial local CDP attach in sandbox timed out; explicitly permitted local Chromium
   run succeeded. All browsing is local file/CDP with blocked egress, not a real site.
3. Genuine print REDs: initial layout inherited mobile styles at A4 width, then card
   stacking, then zero-summary spacing, then multi-issue header/card density overflowed.
   The exact one-page assertion was kept. Old caller pins and rendering snapshots
   are retained in baseline JSON and `layout-history.zip`; real diagnostic PDF/geometry
   in `ui/print-red-*`. Raw source/Guard SHA and issue counts unchanged throughout.
4. An early full Python311 run was started before rendering froze. It correctly
   failed eight fixed-render-ref tests after layout/pins changed in that development
   session; it is not evidence of the frozen renderer passing. It also exposed the
   unchanged source-scanning test's Windows default GBK decoding of new Chinese
   UTF-8 source (`UnicodeDecodeError`). Actual total: **9 failed / 1933 passed /25 skipped**.
   All 18 RA2-through-RA3C fixed verifiers and both Gold demonstrations subsequently
   returned their expected exits, including forged Gold refusal exit 1.
5. Development processes without explicit UTF-8 are kept separately (`python311`,
   `python311-final`, `python313-final` archives). The latter directory names are
   historical recorder labels, **not the final gates**. Redundant-process cancellation
   returned a host Stop-Process error, so no cancellation success was assumed.
   Final runs use **python311-utf8-final / python313-utf8-final**, fresh basetemp/JUnit,
   `PYTHONUTF8=1`, unchanged tests and exactly frozen functional source. This is a
   process encoding configuration, not exclusion or assertion relaxation.
   Both non-UTF8 frozen-code runs finished with **1 failed /1941 passed /25 skipped**;
   the sole failure is the same GBK decoding error, all 70 reporting cases passed.
6. First genuine hosted run **43152015757** tested functional HEAD
   `d238e8e4b3ec97787ec0016f7669aba7af04c6cd` against accepted QA44 main
   `2429be6dc5d7dcb48221ab179f063b93ce4b1956`. All four actual checkout logs show
   `fa92a4e7a23ea510cb8198a92fa37f61564efdec`; GitHub commit parents are exactly
   base + head, with resulting tree equal to head. Both Python jobs 1942 passed/25
   host skips; isolated HTTP 1966 passed/1 browser-only skip. Browser original
   245 command exits, 16 worker lifecycles, explicit worker-kill 137 and 48 negative
   absence/cleanup exit-1 probes independently checked. Raw logs/artifact and original
   server digest are recorded, not inferred from a green badge.
7. Read-only GitHub API attempts inside sandbox were socket-denied; permitted retries
   fetched original metadata/logs/artifact. Neither network refusal nor local encoding
   error was relabeled a functional success. Final hosted validation follows the last
   evidence/docs-only commit, with exact SHA/run refs in Draft PR #47. That final raw
   record stays under ignored `.checks/ci-<run>/` so recording it cannot move tested HEAD.

Human Gold 0/26, no statistical quality assertion. Internal candidate status requires
Owner independent business/UI/source acceptance and never grants customer approval.

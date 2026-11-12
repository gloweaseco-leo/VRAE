# Frozen-code latest-main local results

Both actual completed runs use the functional source from
`d238e8e4b3ec97787ec0016f7669aba7af04c6cd`, based on accepted QA44 main
`2429be6dc5d7dcb48221ab179f063b93ce4b1956`. Subsequent commits add only owned
evidence/recorder/docs. Original core, QA44 and reporting functional/test blobs unchanged.

| Runtime | Full actual result | Reporting | QA44 frozen | Prior independent QA | Commands |
| --- | --- | --- | --- | --- | --- |
| Python 3.11.15 | 1942 passed /25 host skips /0 failures /0 errors | 70 passed | 224 passed | 139 passed | 25/25 expected exits |
| Python 3.13.13 | 1942 passed /25 host skips /0 failures /0 errors | 70 passed | 224 passed | 139 passed | 25/25 expected exits |

The 25 original host skips require disposable HTTP/browser containers; original hosted
jobs execute those security cases. No reporting or frozen QA skip/xfail. Full JUnit
and exact skip names/reasons in [3.11](local/python311-utf8-final/summary.json) /
[3.13](local/python313-utf8-final/summary.json); full XMLs adjacent. Raw 25-command
logs and JUnit ZIPs have per-entry bytes/SHA in archive-index.json. Original GBK/development
REDs remain separately archived and are not included in these green totals.

Each runtime actually ran compile/Ruff/mypy/full pytest/pip, every 18 sealed RA2A,
B0-B6/B6-execution/C0-C3/D0-D1/RA3A/RA3B/RA3C verifier, simulated-Gold expected success
and forged-Gold expected refusal exit 1. Process UTF-8 mode fixes Windows source
decoding only; no original policy, test, fixture or assertion changed.

Actual local Chromium: 12 views, 72 original evidence-link clicks, zero external
requests/runtime exceptions, 6 exact one-page A4 PDFs, desktop/mobile screenshots.
Final artifact-index.json independently binds preview HTML, JSON, screenshots/PDFs
and local records; browser HTML/PDF hashes were compared again after both runs.

First hosted functional run [43152015757](https://github.com/gloweaseco-leo/VRAE/actions/runs/43152015757)
has four real successes, checkout fa92a4e7a23ea510cb8198a92fa37f61564efdec with exact
base+head parents and head-identical tree. See ci-functional/proof.json and security-proof.json,
functional-ci-raw.zip. Browser 245 commands/16 worker lifecycles, worker-kill 137,
48 negative exit-1 probes retain original meanings. Final HEAD's new four hosted checks
and exact checkout/parents are independently recorded in Draft PR #47 after the
last evidence commit; those raw files remain in ignored .checks/ci-<run> to avoid moving
the tested HEAD.

Private synthetic engineering candidate only. Human Gold 0/26, quality N/A. No actual
customer report, approval/share, live model/site, deployment or RA3D. STOP Owner review.

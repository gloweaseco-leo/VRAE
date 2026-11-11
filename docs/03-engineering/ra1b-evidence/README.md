# RA-1B evidence index

- `python-311-summary.json`, `python-313-summary.json`: exact full-gate commands,
  exits, versions and source hashes. Full command output is in the archive's final-311/313.
- `browser-summary.json`: final 16-scenario supervisor commands, durations and exits.
- `browser-events.jsonl`: final actual attack/resource/network records, including zero bait/writes.
- `sandbox-attestation.log`: actual Chromium internal namespace/PID/network/seccomp report and argv.
- `kernel-denial.log`: direct TCP/UDP socket EPERM, readonly root and tmpfs quota results.
- `http-regression.log`: full original RA-1A isolated suite plus new ordinary tests.
- `evidence-raw.zip`: complete raw subdirectories, including first-failure experiments,
  intermediate fixes and final browser-acceptance. No historical failure was removed.
- `archive-index.json`: SHA-256 per archive member and for the archive itself.

Cleanup checks deliberately use `docker inspect` after deletion; exit1 means expected absence.
Worker SIGKILL deliberately returns137; it is not counted as a successful pytest invocation.
Early revocation-labelled experiments used cancellation or an insufficient trigger window;
only the final suite's actual POLICY_REVOKED plus action-trigger assertions establish revocation.
No remote company data or production secrets are present; sites/certificates are synthetic.

Hosted CI: run42966852022 at implementation474ef34, merge ref32f6b7e.
`ci-first.json` records actual jobs/steps; `hosted-311.log`, `hosted-313.log`,
`hosted-http.log`, `hosted-browser.log` are full logs retrieved from GitHub.
All four jobs succeeded. Hosted files supplement the historical local archive index.

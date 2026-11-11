# RA-2A synthetic evidence

The baseline is main f70ecffc2465807f34cb82d84f663508fe6db465 (Issue7).
All sources are offline synthetic data. No site requests or model calls occur.

- ../ra2a-red.log: initial missing EvidencePack module, exit2 (collection error, not an assertion result).
- ../ra2a-red-locator.log: actual provenance admission failure, 1 failed / 29 passed / exit1.
  The legacy CaptureBundle verifier permits free-text locators. RA-2A must narrow
  them to the actual HTTP producer's whole-response locator before admitting evidence.
  Source modules were not changed; the negative assertion remains in test_pack.py.
- python311/ and python313/: all five full-gate commands, versions, source hashes,
  counts and exit codes, produced by the existing verify_ra1a.py runner.
- acceptance311/ and acceptance313/: final source, 472 passed / 0 failed / 25 skips,
  all five commands exit0. acceptance-evidence.log: 47 EvidencePack tests passed.
  final-python311/313 retain the earlier content-verification-field iteration.
- tests/fixtures/evidence/combined.json: replayable synthetic HTTP+browser pack,
  including base64 private objects and its pinned expected identity.

Final commit CI run/jobs and raw logs are recorded in the Draft PR after execution;
they are not claimed successful in advance. Original HTTP and Chromium CI are unchanged.
PowerShell redirect logs were normalized from UTF-16 to UTF-8 for review;
failure messages, assertions and counts were not removed.

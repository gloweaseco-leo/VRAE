# First natural CI RED and bounded correction

Original HEAD: 99be37c689baa96ec34d0664687affbec08409eb.
Original run: https://github.com/gloweaseco-leo/VRAE/actions/runs/44105652721 (attempt1).

- Both native suites and mypy/ruff passed. Python3.11 browser step passed.
- Both artifact uploads failed: upload-artifact excluded hidden `.runtime` files.
  Fix: include-hidden-files=true with the same explicit XML/JSON/PNG/log allowlist;
  Chrome profiles remain excluded.
- Python3.13 browser step reported `dedicated-chrome-exited=false`. The old
  finally assertion may mask an earlier error; **original primary cause UNKNOWN**.
  It is not evidence of completed 24-case verification on that runner.
- Correction records any primary error and partial measurements before cleanup;
  websocket close rejects pending calls; a dedicated Linux process group permits
  bounded TERM/KILL of only that spawned group if Browser.close does not exit.
  Process exit assertion is retained. No page/business assertion is relaxed.
- Corrected Windows Chrome actually completed 24 combinations, all46 assertions,
  exited0 via Browser.close. Local original screenshots remain in ignored
  `.runtime/p0-cleanup-fixed-05/`; browser.json/cleanup copied here. Linux fix is
  pending a new natural CI at the changed SHA, not assumed proven by Windows.

`ci-99be37c-red.log` is the UTF-8 decoded gh --log-failed output, not a claim of
byte-identical GitHub archive. Original run/RED remains available unchanged.

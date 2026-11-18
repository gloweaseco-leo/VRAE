# e956 Windows 3.11 RED: receipt-only causal correction
This retains the actual e956 first attempt. e956 hosted Linux: 20/20 workflows, 44/44 jobs, attempt1 only; both real-combination artifacts independently verify 49 Chrome assertions, 50 JUnit including completion, 19 native checks, 13 PNG, same-task bindings, 22/7 A4 pages, restart and cleanup. Windows3.13 also passed49. Windows3.11 passed36 business assertions including Controlled review and real PG Brief COMMIT, then failed during the next login before A4/restart. Its public RED export is preserved byte-for-byte in e956-windows311-public-red.zip.

## Observed cause boundary
The original HTTP relay wrote kind=Empty. Its existing replies.get timeout is25s, unchanged. The later browser error is BROWSER_EVALUATION_FAILED at login-page. Node stderr and original SSR stderr were empty, Chrome exited gracefully0 and owned cleanup completed. The original private marker has no initiating-request timestamp/duration, so the exact request and unique root cause cannot be retroactively proved. No sleep/native-crash attribution is invented.

## C3 causal change
The added receipt path was calling binding.read(source.read()) and read_buyer, replaying the same current source/candidate merely to emit audit metadata after business operations. It now stores only the accepted builder's generated ref/version/model/snapshot/rule/result metadata during signed binding. Receipt reads deserialize a defensive copy. Original Workbench.handle/current/report/source/candidate verification and original Brief COMMIT readers/fences remain live and unchanged; the C3 subclass adds storage only, overriding no accepted method. Initial selection reads the accepted constructor output; the original enable_buyer_cards still performs source/projection verification before building.

Regression explicitly denies current candidate verification after the receipt exists: receipt metadata remains detached, but the actual source page returns403. Cache mutation cannot alter the next receipt. It grants no authority. No original guard, identity, SQL/RLS, Worker30s lease, HTTP25s, Chrome/CDP or lifecycle budget changed.

The new finite failure receipt also exports only an allowlisted observed HTTP exception class plus private marker SHA, not message/URL/token/HTML/traceback. The own artifact uploader includes the already-manifested control dotfile; its directory is the secret-scanned public export and remaining private paths are exact native/probe filenames, never a private-directory glob.

## Validation
New related native suite: Python3.11 23/23, Python3.13 23/23, zero skip/fail/error. Ruff/mypy/JS/diff checks pass. Raw prior RED, Linux successes and private original logs remain separate. A new committed executable SHA must perform fresh actual dual-version flows and natural CI before final engineering judgment. This is a causal code correction, not a retry of e956 or reuse of its successful evidence. Human Gold remains separate0/26,0/32,0/14; no full quality PASS.

## Internal operator entry
Use the configured matching Python minor (3.11 or3.13); Docker must be running. No external-site target is admitted in this stage.
1. Build the accepted prerequisite: python integration/l2_ops/build_image.py --python 3.11
2. Start: python scripts/beta_internal.py l2 app-start --run UNIQUE_LABEL --minor 3.11
3. Status: python scripts/beta_internal.py l2 app-status --run UNIQUE_LABEL
4. After M3_READY, open: python scripts/beta_internal.py l2 app-open --run UNIQUE_LABEL
5. Select the controlled P40/V25 L2 source, submit a new task, wait for the actual Worker, open that task's native report and original signed review. Read the five-source page/two limited P40 cards and original bytes; return to the professional report/seven-package blueprint, record a Controlled internal decision and save the internal Brief. UNKNOWN stays UNKNOWN.
6. Stop via python scripts/beta_internal.py l2 app-stop --run UNIQUE_LABEL, then wait for app-status CLOSED. Do not prune or delete historical dumps.
Finite QA (with matching native interpreter): python -m integration.l2_ops.s2_acceptance_runtime --run UNIQUE_LABEL --minor 3.11; performs the actual restart/reauth/denials and exact owned cleanup.

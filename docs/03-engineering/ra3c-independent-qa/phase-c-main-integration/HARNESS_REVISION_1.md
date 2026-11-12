# Mechanical QA harness corrections; frozen business source unchanged

Initial Phase C source `b74318110ba14a23e6db6af393d4f8226ed33443` actually executed V2 on Python3.11/3.13:118 PASS each, standard JUnit saved. The new orchestration runner then exited1 because its stdout proof check could not find `OWNER_RA3C_V2_ACTUAL_CALL_REPORTS`. Pytest captured the module-finalizer receipt despite the118-report assertion succeeding; the original JUnit did not fail. Historical/default steps were **not executed by that aborted runner**. Those original source/run records remain intact.

Revision1 changes only log visibility: temporarily disable pytest capture around printing the read-only teardown receipt, then restore capture. The new shim pins the revised transport SHA256. No frozen V2 source/fixture/assertion, source data, proposal, Guard, browser judgement or expected result changes. Original V1/default selection configuration is unchanged.

Correction to progress comment6819278471: first hosted Python jobs contain the actual64+54 collection receipt and ordinary2061 PASS/25 SKIP, but the individual-call receipt was captured rather than visible in stdout. The new revision makes that additional proof visible; the previous first3/4 CI is never presented as final GREEN.

Separate old-engine replay preparation stopped at the exact Git-blob assertion before executing any old engine. Unqualified `git archive` inherited Windows CRLF export behavior. `prior-export-v0-diagnostic/` retains the reproduced original archive and byte comparison: first differing file is `contracts/v1/AIInterpretation.schema.json`, differing only by CRLF. Revision1 explicitly supplies `git -c core.autocrlf=false -c core.eol=lf archive`; the strict original blob assertion remains unchanged. This corrects export mechanics, not an old production engine or its tests.

Both runtimes already completed19 earlier replay commands (including expected forged-Gold exit1) and all8 current sealed RA3C native build/load replays on sourceb743181. Their actual records remain, independent of the unexecuted old-engine step. New source revisions use new output directories rather than overwriting failed/partial attempts.

The proposed Docker QA-resource extension remains unapplied pending the narrow additional Owner authorization. No missing-resource bypass, skip, xfail, source rewrite or inherited-CI claim is introduced.

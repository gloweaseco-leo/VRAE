# S2-CI-D0: independent Chrome startup evidence

Owner scope: [issue 126](https://github.com/gloweaseco-leo/VRAE/issues/126).
Base: `cb86cdb1b57962aa89fa2ef4465131219c8c45e9`. PR124 and PR123 remain Draft/HOLD.
The independent startup scenario does not launch the application, connect to
PostgreSQL or load pages. The single supervised scenario below runs the unchanged
original PG+application suite. Neither changes the original acceptance criteria
or navigates to third parties.
No D1 fix is proposed: the historical cause remains UNKNOWN.

## Owner-requested equivalence correction and single supervised attempt

The first HEAD `1dfbc1c` used stdout `ignore` instead of the original stdout
`pipe`, and executed a realpath instead of the requested path. Its 19 green
workflows are historical results of that non-equivalent diagnostic; the earlier
claim of fully preserved spawn options was incorrect. They do not establish
causal equivalence or resolve the original REDs.

The revision restores the complete original `{windowsHide:true,
stdio:['ignore','pipe','pipe']}` options, including the **unread stdout pipe**.
It does not drain stdout, preserving the original potential backpressure.
Tests compare the observer's complete options with both pinned source literals;
a large synthetic stdout write proves that unread-pipe behavior remains intact.
Stderr fingerprinting remains unchanged; neither stream's text is published.
The requested executable is now the actual spawn argument. Its separately
resolved path and hash are recorded without assuming symlink equivalence.
A directory-symlink test exercises a requested path that differs from realpath.

Exactly one additional CI job, with no Python matrix or retry, runs
`supervisor.py` around the original RA4C3 PG+Chrome suite using its unchanged
`python -B -m integration.ra4c3.run_suite <fresh-owned-output> --browser` command.
All original stages, flags, 20s gate, conditions and cleanup remain in place.
The supervisor is not launched locally. An exclusive claim plus fresh output
requirement rejects a second invocation in that workspace. Its outer 40-minute
suite bound does not change the original Chrome's 20-second gate.

The passive supervisor only follows its own verified process descendants. It
samples original browser Node/Chrome PID/PPID/start identity, original Chrome
argument equality, actual executable hash, and the owned temporary
DevToolsActivePort file's first publication time and port. It never connects to
Chrome, injects a hook, changes original pipes, or reads private HTTP/profile
content. Only the bounded DevToolsActivePort protocol file is read; its UUID is
discarded. Original suite stdout/stderr are hashed and counted, not published.

**Observation gaps are deliberate:** passive sampling cannot obtain the
descendant's original exit/close callbacks or original timer callback. Those
fields remain null. First-seen +20s is labelled a sampling reference, never the
actual gate event. A DevToolsActivePort file does not prove a listener. Missing
samples do not prove exit. Polling also adds work, so equivalence to a historical
runner is unproved. The final receipt chooses outcome 2 (valid observations,
cause UNKNOWN) only when actual original Chrome arguments are observed equal;
otherwise outcome 3 (equivalence unproved, HOLD). Neither outcome proposes D1.
There is no extra diagnostic iteration after this bounded attempt.

## Contract and observation boundaries

`run.mjs` verifies both original Git blob fingerprints before extracting their
literal Chrome argument arrays. The sole parameter is a fresh profile created
by this tool. Every original flag, `about:blank`, spawn option, and the original
20,000/30,000ms endpoint deadline is preserved. The original source, B5A ENTRY,
allowlists, publication guards, and all existing workflows remain unchanged.
`observer.test.mjs` checks the two extracted argument arrays for exact equality,
rejects source drift and a 60s deadline, and exercises real synthetic child processes.
Python independently verifies the Git source fingerprints and observed receipts.

The diagnostic observes spawn/error/exit/signal/close using monotonic elapsed
times. Startup classification is fixed **before** cleanup, so diagnostic SIGTERM
cannot become evidence of an early startup exit. A timeout with an observed live
owned child is `NO_ENDPOINT_WITH_ALIVE_PROCESS`; missing liveness is UNKNOWN.
Successful publication is `ENDPOINT_AVAILABLE`; a separate boolean describes
the bounded TCP connection to that exact loopback endpoint. An endpoint does not
prove successful CDP or application assertions. A bounded `Browser.getVersion`
request to the owned endpoint retains only its public numeric version; null
means unobserved. No other CDP command is issued.

Stderr is streamed into byte count/SHA256; only a bounded in-memory tail is used
to recognize the original loopback endpoint regex. Raw stderr, endpoint UUID,
HTTP responses, environment values, cookies, keys and page data are never saved.
Only the tool's own temporary profile directory and its DevToolsActivePort file
existence are inspected, without reading file contents. Linux process observation
walks only `/proc/<owned-child>/task/<owned-child>/children`, with a 128-process
bound, and records PID/PPID/state. No machine-wide process or port enumeration.
Windows process-tree observation is explicitly null. The launch file is hashed;
on Linux the live owned child's actual `/proc/<pid>/exe` is also hashed when
accessible, distinguishing a shell launcher from Chrome itself. Unknown binary
identity after early exit is not inferred from the launcher hash.

After the startup decision, bounded observation/connection and cleanup follow.
SIGTERM is followed by SIGKILL if necessary, with separate observed close state.
An unobserved close fails the diagnostic. Child close alone does **not** prove
every Chrome descendant exited; the receipt makes no such claim. Cleanup only
signals the Node-owned child and removes the exact temporary directory created
by `mkdtemp`. The original scripts' cleanup and protective failures are untouched.

Because this launches a separate process and does not reproduce PG/application
load, its result cannot establish the cause of an original failure, or replace an
original suite's RED. No old HEAD is rerun. Original CI on this new PR runs
naturally under existing triggers, without edits to their success criteria.

## Reproduce

Node 22+ and Git, no packages required:

```sh
node --test integration/s2_chrome_diagnostic/observer.test.mjs
python integration/s2_chrome_diagnostic/verify.py
RA4C0_CHROMIUM=/usr/bin/google-chrome node integration/s2_chrome_diagnostic/run.mjs integration/s2_chrome_diagnostic/output/linux
python integration/s2_chrome_diagnostic/verify.py integration/s2_chrome_diagnostic/output/linux/startup.json
```

The independent workflow runs the controls and real Linux Chrome scenario with
Python 3.11 and 3.13, then uploads only the structured startup receipt. A Chrome
failure remains a failing diagnostic job, with its receipt still uploaded.
The Python receipt verifier rejects false promotion of a timeout result.
The initial local Windows controls were 8/8; real Chrome had both endpoints available and TCP
connected within original deadlines, actual close observed. This is neither a
Linux runner reproduction nor a resolution of the old failures.

## Original official failures

`historical-artifacts.json` records ZIP digest, CRC verification and member hashes
from a fresh authenticated read of the original artifacts. `audit_history.py`
reproduces this read-only audit using `gh api`; it does not rerun workflows.
It never writes the raw archives or their private contents. For RA4C3 only the
specified current-run browser directory is selected, excluding historical runs.
The hash manifest is recorded separately from the six browser evidence files.

| Original RED | Official job | Official artifact | ZIP SHA256 |
| --- | --- | --- | --- |
| PR123 RA4C3 3.13 | [134182924667](https://github.com/gloweaseco-leo/VRAE/actions/runs/44124070028/job/134182924667) | [14346573399](https://github.com/gloweaseco-leo/VRAE/actions/runs/44124070028/artifacts/14346573399) | `a3f5975965d20eeac8e152407513119158f2819a5e20405d93ff76d1b9f5898a` |
| PR124 RA4C3 3.11 | [134461535003](https://github.com/gloweaseco-leo/VRAE/actions/runs/44202972104/job/134461535003) | [14383001827](https://github.com/gloweaseco-leo/VRAE/actions/runs/44202972104/artifacts/14383001827) | `775eba78173216248ede00d01c5ec1785668f930dcde895360d92421a06b9775` |
| PR124 B5B 3.11 | [134461535216](https://github.com/gloweaseco-leo/VRAE/actions/runs/44202972396/job/134461535216) | [14383155835](https://github.com/gloweaseco-leo/VRAE/actions/runs/44202972396/artifacts/14383155835) | `fdcbd8861ef6dfe7dc82db5c637eb049f1d3af29ec164cb306670bcb825ae9fd` |

All three retain UNKNOWN. Empty stderr in PR123 does not prove crash or liveness;
191 stderr bytes in PR124 RA4C3 do not establish a DBus cause. No runner slowness,
resource pressure, port conflict, crash, or application bug has been proved.
If further evidence requires changes to frozen sources, stop that path for an
Owner decision on a new interface. Neither timeout extension nor same-HEAD
rerun followed by a green result is a causal fix.

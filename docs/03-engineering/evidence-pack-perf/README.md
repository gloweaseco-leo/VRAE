# EvidencePack same-instance consistency optimization

Authority: [Owner L3 ruling](https://github.com/gloweaseco-leo/VRAE/issues/94#issuecomment-6918212841).
Base: `6b2a2dfff8d6de2cf16c2509e9cdcf30a2267d83`. Independent branch
`codex1/evidence-pack-perf`. Only previously existing runtime file changed:
`vrae/evidence/pack.py`. Original tests, schemas, lease, mandatory precommit
replay, Guard, source policy, identity and database contracts remain unchanged.

## Verification model

The first successful verification still runs the complete original schema,
`_project`, source bundle verification, retained object hashes, scope/reference
checks and canonical projection comparison. The private slot records only
that consistency result. It neither authorizes access nor proves provenance.

Reuse requires the exact EvidencePack class, exact immutable primitive field
types, identical payload/blob tuple objects, the same live owner (weak reference)
and process ID, identical contents and paths of all three native schemas, and
identical scope/limitations/viewport configuration. Schema files are read on
every verification; size and timestamps do not substitute for content. Schemas
with nonlocal reference graphs never qualify. Each call checks its supplied
expected reference independently. Failed checks discard the prior proof.

New construction/load, copy/deepcopy/replace, pickle reconstruction and process
boundaries require full verification. Subclass inputs retain the old complete
verification path and cannot receive a reusable proof. Public document/object
views remain detached/read-only. No instance-external cache exists. Python
private slots are an implementation boundary, not a sandbox against arbitrary
code execution inside the trusted process.

## Reproduction

Use each supported Python minor, from this worktree:

```text
python -m pytest -q tests/evidence_perf/instance_cases.py --junitxml=<new-output>/safety.xml
python -m integration.evidence_perf.compare --out <fresh-output-directory>
python -m pytest -q tests/evidence tests/collection tests/rules tests/findings tests/interpretation tests/reporting tests/browser --junitxml=<new-output>/native.xml
```

The comparator copies the same tracked native code/contracts/fixtures into two
isolated trees; only baseline `pack.py` comes from the accepted base. Four fresh
processes execute ABBA order. It rejects any input digest, original producer
source/report/HTML/binding SHA, complete industrial diagnosis SHA or assessment
semantics difference. The original producer and mandatory precommit replay run
unchanged; complete native industry diagnosis and export verification also run.
Metrics report real phase wall time, process CPU, full `_project` calls, verify
calls/time and OS peak resident memory. They are not cProfile cumulative times
and not a latency SLA on a shared Windows host.

Eight P40/V25 HTML bodies are byte-identical to the accepted offline industrial
fixture. The original Collector captures them under tenant-test/run/policy
configured before capture, with a compatible synthetic robots response. No
external socket is opened. The consistency fixture uses a 30-second context;
its fixed time does **not** demonstrate a live lease, PG commit or signed read.
The unmerged PR112 task launcher is not imported. C3 must perform the final
real original Worker P40/V25 dual-version PG16/30-second commit and signed-read
trial. This PR cannot claim that item PASS.

Local ABBA comparison (two fresh runs per variant, shared Windows host):

| Python | Original build + mandatory replay wall | Candidate wall | Original CPU | Candidate CPU |
| --- | --- | --- | --- | --- |
| 3.11.15 | 51.68–55.23 s | 5.25–6.02 s | 45.28–45.41 s | 4.73–5.16 s |
| 3.13.13 | 50.61–59.44 s | 7.52–8.04 s | 44.05–47.63 s | 5.53–5.66 s |

All eight complete executions match every compared input/output/diagnosis
digest and assessment semantic. M1 build plus mandatory replay still makes
861 `verify` calls; `_project` calls decline from 862 to 3 (including the
unconditional build projection). The replay phase performs one full projection
on its newly loaded pack. Separate industry pack construction performs two;
its subsequent diagnosis/export reuse consistency only on that exact instance.
OS peak working-set measurements remain approximately 50–52 MB across variants;
raw bytes and all phase metrics are in `comparison-311.json` and
`comparison-313.json`. No cProfile or live PG claim is included in these numbers.

## Preserved blockers and development failures

Local Python 3.11.15 and 3.13.13 each pass all 35 new safety cases and
1656 original native cases. Each original suite skips the same 25 cases that
require disposable firewall/Chromium containers; they remain mandatory in the
unchanged real HTTP/browser CI jobs. Exact JUnit hashes and matching test-ID
hashes are recorded in `local-receipt.json`; skipped cases are not claimed PASS.

The old B5A source protector is intentionally unchanged. Its original
`integration/ra4c_b5a/publication.py:65` assertion `ACCEPTED_SOURCE_CHANGED`
rejects this protected source modification. Actual CI failure must be retained;
Owner must separately approve an exact new blob before compatibility work.
No broad whitelist or gate relaxation belongs in this PR.

First new-suite run: 29 PASS / 3 FAIL. The new temporary-schema fixture replaced
the original `$defs`, losing `#/$defs/id`; fixed by appending its unused external
reference definition. Original assertions/schemas were untouched. Raw r1 JUnit
is retained under ignored `.runtime/cache-311-r1.xml`.

First candidate benchmark smoke reached the end of all diagnostic phases but
failed Windows memory sampling (`ctypes.ArgumentError`, handle converted to
32-bit int). Fixed only the new sampler's explicit HANDLE argument declaration.
That incomplete run is not performance evidence. No security RED has been
discarded or rerun as a passing result.

Local raw JUnit/logs and copied benchmark trees stay in ignored `.runtime/`;
bounded summary receipts and exact source diff are published separately. CI
uploads its actual fresh-run JUnit and synthetic benchmark JSON/log artifacts.

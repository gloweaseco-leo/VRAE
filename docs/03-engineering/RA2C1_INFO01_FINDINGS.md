# RA-2C-1: explicitly versioned private product evidence

Issue #23. Base: Owner-accepted main `acc5f7594dd5b96b1fda41dcf743f6c27bbac611`.
Independent worktree `D:/Projects/VRAE-Codex2/.worktrees/ra2c1`, branch
`feat/ra2c1-info01-finding-integration`. Draft for Owner independent acceptance.

During final CI verification, main advanced to Owner-accepted RA-2D-1 engineering
merge `8f91dfd1783fa66c4827a6d2073c6237516de902` (Owner acceptance on PR #22).
It was merged without conflicts at `d802c9ee2e209054217f6ee653f3427aceeb1ce9`.
No Codex 1 file was edited. Initial dual-interpreter evidence is preserved at the
original paths; final integrated runs are recorded separately under
`ra2c1-evidence/latest-main/`, adding the read-only RA-2D-1 replay. The initial
4/4 CI run 43012977480 is historical, not the latest-main integration gate.

## Version and trust boundary

`build_findings`, `FindingPackage.load` and `FindingPackage.verify` accept
`expected_builder_version='ra2c1-1.0.0'` only when explicitly supplied. That
version requires `expected_evaluator_version='ra2b3-1.0.0'`. Omission retains
`ra2c0-1.0.0` / `ra2b1-1.0.0`, including exact historical document hashes and
load/verify behavior. No version is inferred from untrusted input or auto-upgraded.
Callers must supply their trusted pack/execution pins and, for load/verify, package
pin. Self-reported refs are not an authorization source or a signature.

Before projection, the unchanged complete execution verifier independently
replays against the caller-pinned EvidencePack. The builder then projects the
verified execution into immutable canonical bytes with detached document copies.
Loading replays the complete projection and compares canonical bytes; recomputed
wrapper hashes cannot bless fabricated evidence, scope, versions or approval.
Existing 8,000,000-byte input/output limits and aggregate row limits remain.

## Positive evidence and bounded defects

Only INFO-01 PASS is retained in the new `checked_product_facts` group, separate
from `checked_positive_paths`. It contains the complete original Observation and
provenance, execution locator, h1/TH/TD text and paired field indices, source and
snapshot refs, original evidence IDs, URL/time, body hashes, source pointers,
element path/line/column/opening tag, response metadata and coverage disclaimer.
The full pinned RuleExecution and pack ref remain inseparable package context.

Product text is observed in captured static HTML. It proves neither parameter
truth, completeness, authenticity, SKU identity, rendered visibility, comprehension
nor engineering fit. INFO-01 PASS creates no Finding. INFO-01 UNKNOWN and
ACCESS_BLOCKED produce only UNKNOWN records with empty fact IDs and original
scope/coverage. No INFO-01 FAIL or independently justified NOT_APPLICABLE exists.
Other unknowns likewise do not establish website defects or inflate problem counts.

Only DISC-01/02/CTA-02 replay-proven 404/410 static href failures create factual
Finding records, with null severity. The unchanged native RA-0 ID bridge and
inseparable source href + target source/snapshot/status/error/redirect metadata
remain required. A naked Finding does not prove a target response. No revenue,
quality score or whole-site conclusion is inferred. Every package remains private,
NOT_APPROVED and non-shareable, with no publishing or approval API.

## Fixed synthetic industrial demonstration

`python scripts/verify_ra2c1.py` replays the separately sealed
`tests/findings/fixtures/info01-private-package.json`, reproduces the same fixed
synthetic transport inputs, and independently checks citations against raw HTML
lines. It makes no real DNS/HTTP/model requests and writes nothing by default.
Explicit `--write-example` only creates this new example, never a historical file.

Name: `SV-40 flanged isolation valve`, source line 3, column 0.
Parameters: Body material = Stainless steel 316L; Nominal pressure = PN 40
(4.0 MPa); Nominal diameter = DN 50. Pressure TD starts at line 6, column 29.
Only the separate product-to-`/contact` href returning 404 creates one INQUIRE
Finding. `/rfq` is capture-blocked (403); remaining unsupported checks stay UNKNOWN.
Two discovery paths are checked positives, one product page is positive source text.
Collector limits and original policy are retained in the sealed pack; the fixture
uses the existing bounded L0 collector with fixed DNS/transport and GET requests.

Pins:

- Pack: `ep-3291e934f77bf97e5c7cb9c7089f5629a40efe58771427c893d81106dbc93329`
- Execution: `rx-3d0c95f66fbc231b95054d4621c78282de36c137bb60bdd67ac99c42ae5c84b3`
- Package: `fp-4fcb355d8015fbbbd1236465989c4bd144fc45f567a56d4457dbb0cd09ff368a`

## Verification and scope

Dedicated tests cover explicit dispatch; original byte identity; product
name/value/coordinates/ref/hash/URL/time fabrication; unknown/empty/duplicate/
variant/missing raw/403/WAF/robots; spoofed target 404 and metadata removal;
resealed execution and package forgery; privacy, approval, scope, version pins,
immutability/detachment and aggregate bytes. The red log records the new builder
keyword being unsupported before implementation. Raw green/full regressions and
all accepted offline RA-2A/B0/B1/B2/B3/C0/D0 replays are in `ra2c1-evidence/`.
Run `python docs/03-engineering/ra2c1-evidence/regress.py` with Python 3.11/3.13.
Local isolation skips require the real hosted HTTP/browser labs; final exact HEAD,
checkout merge SHA, counts, four CI links and artifact are reported in the Draft PR.

Only minimal findings adapter code, dedicated tests, a new synthetic replay/demo
and these limited docs change. No rules/extractor, contracts, schemas, policies,
collection/browser/security, dependencies, CI/infra, frozen roadmap or old fixtures
change. Codex 1 benchmark/Gold files and denominator remain untouched. No RA-3,
live-site diagnosis, model, report/share feature, deployment or self-merge.

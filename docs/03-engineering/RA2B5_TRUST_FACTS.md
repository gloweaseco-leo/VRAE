# RA-2B-5: public self-description and contact source evidence

Issue #27. Development base Owner-accepted main
`214321551034a98239cc6a6586ec9d788ba3769a`. Independent worktree
`D:/Projects/VRAE-Codex2/.worktrees/ra2b5`, branch `feat/ra2b5-trust-facts`.
Offline synthetic evidence prerequisite only; Draft for Owner independent audit.

## Capability and explicit exclusions

`vrae.rules.trust_facts.extract(pack, expected_pack_ref=caller_trusted_ref)` is an
independent, explicitly invoked extractor `ra2b5-trust-facts-1.0.0`.
`verify_facts(output, pack, expected_pack_ref=caller_trusted_ref)` independently
replays the complete output from retained bytes, not just its `tf-` content hash.
Pack pin must be separately trusted, not accepted from an untrusted document.
Output is detached ordinary JSON data with a deterministic content-addressed ref;
editing it cannot pass full replay. No disk persistence or network action is implicit.

It only records what captured HOME/ABOUT/CONTACT static HTML explicitly says.
No Observation, Finding, company rating, defect, trustworthy/untrustworthy result,
legal identity certification, registration/factory/certificate/export capability,
contact ownership, current authorization or valid inquiry is inferred. A missing
description or certificate is not a company defect or evidence of fraud.
`trust01_enabled` stays false and `trust01_result` stays UNKNOWN. Existing rules,
catalog, enabled-state dispatch, FindingBuilder and all historical refs stay intact.

## Deliberately small structural subset

- Plain-text `itemprop="name"` within one explicit `itemscope` Organization
  (`https://schema.org/Organization` or http equivalent), using the nearest scope.
- Plain TH/TD pairs under a balanced table row with an exact name label:
  Company name / Organization name / Legal name / Brand name, or
  公司名称 / 企业名称 / 组织名称 / 法定名称 / 品牌名称. Even “Legal name” is just a label the
  source uses, not legal verification. Repeated equal name strings do not certify
  the same legal entity; different declared strings remain unresolved.
- Plain P children after an exact first H1/H2/H3 heading of a SECTION: About us,
  About the company, Company profile, Company overview, 关于我们, 公司简介, 企业简介.
- Plain ADDRESS text, without validating what the address or contact string means.
- Plain A text plus literal href: same-origin HTTP(S) CONTACT-path role, restricted
  `mailto:` or `tel:` literal. URL roles are the existing path heuristics, not semantic
  identity resolution. Non-contact ordinary navigation is not contact evidence.

Original decoded text keeps whitespace and entities' decoded characters; the
exact `raw_element` preserves the original entity spelling/markup too. Every
citation includes the original response hash, source/snapshot/evidence ref and
source JSON pointer, requested/final URL, captured_at, element path, original
opening tag and line/column. Lines are one-based; columns are zero-based Unicode
character offsets. Path indices count all sibling elements, not XPath tag indices.
Complete original body bytes remain available in the pinned EvidencePack.

Balanced UTF-8 subset only: at most 131072 source bytes, 2048 elements, 32 levels,
128 selected facts per page and 8000000 serialized output/replay bytes. Nested
rich text in selected leaves, DL, unlabeled prose/h1, logos/images, JSON-LD,
scripts/style/template/noscript/forms/frames/base, duplicate attributes and
presentation attributes are unsupported; these gaps are UNKNOWN, never absence
or fraud claims. No fuzzy NLP, domain-to-company inference or live lookup is used.

## Status and target-edge semantics

Per page, EXTRACTED means supported source-text facts were retained; it may be
only a static link. UNKNOWN means unsupported/ambiguous/missing raw/incomplete
capture, with empty fact evidence IDs. ACCESS_BLOCKED preserves captured
403/WAF/robots state, also with empty fact IDs. Multiple explicit name strings
across eligible pages, multiple Organization scopes, or an unresolved name scope
leave the overall scope UNKNOWN. Available different-name citations remain
context only in UNKNOWN rows with empty evidence_ids; they are not resolved identities.

Overall EXTRACTED requires one distinct supported declared name string (trimmed,
case-folded exact equality only) plus an observed supported static contact href.
It does not assert the pages belong to a verified legal entity. Independent gaps
or blocked pages retain their own status and coverage; known text on another page
does not turn them positive. Overall ACCESS_BLOCKED requires all selected captured
pages to be blocked; mixed/gapped scope otherwise remains UNKNOWN unless the
bounded name-plus-literal-link condition is independently satisfied. Inventory-only
pages remain explicitly NOT_VISITED in coverage and `unvisited_candidates`.
Browser DOM/screenshots never substitute for retained original HTTP text.

Each selected HTTP href stores `target_responses` separately: source page locator,
source/snapshot/evidence refs, full normalized snapshot, requested/final URLs,
capture time, HTTP status/error and complete redirect trace. These metadata are
independently bound to the pack and full replay. Missing HTTP targets and mailto/tel
literals have no response edge; they say only that a static href was present.
A 200, 403, 404, 410 or 500 target never becomes a reachability, deliverability,
valid-inquiry or company-quality judgment in this module. Even a broken target
does not negate the fact that the original page contained that literal link.

## Runnable fixed synthetic review preparation

`python scripts/verify_ra2b5.py` loads the separate sealed
`tests/rules/fixtures/trust-source-facts.json`, verifies all three pack pins and
facts refs, reproduces the same fixed transport inputs, and checks original lines,
raw element slices and body hashes without using the extractor's parser.
Default replay writes nothing. Explicit `--write-examples` writes only this new
fixture, never historical examples. No real DNS/HTTP/model request occurs.

1. Fictional Heshan Meridian Valve Works: explicit ABOUT name (line 3, column 0),
   Company profile source paragraph, CONTACT label/address, email/telephone and
   ABOUT→CONTACT href (line 8, column 0, `/html[1]/main[1]/a[3]`). EXTRACTED
   self-declaration only; original source says it makes industrial isolation valves
   and actuator assemblies, which this module does not verify.
2. Fictional Qinglan Precision Drives / Harbor Motion Export Group: conflicting
   company/brand label strings and drivetrain supplier prose. UNKNOWN; no attempt
   to decide the actual company, resolve brands to legal entities, or rate trust.
3. Fictional Beilin Automation Components: JS-only profile/contact rendering.
   UNKNOWN; page title/domain is not promoted to an organization name.

The sealed fixture contains every original input byte, pin and output. The raw
replay log lists facts/locators/response edges and their limits. Separate tests cover
403/WAF/robots, no raw/no structure, unvisited or error pages, cross-site pack
rejection, Unicode/entities, bad/redirected targets, hostile hrefs, ambiguous scopes,
parser/output bounds and rehashed text/href/locator/hash/time/scope/metadata forgery.

## Verification and stopping point

Initial red records the actual missing-module failure before implementation.
The new dedicated suite has 90 tests. Full regressions and all accepted
RA-2A/B0/B1/B2/B3/C0/C1/D0/D1 replays plus B5 use
`python docs/03-engineering/ra2b5-evidence/regress.py <new-log-directory>`.
Run Python 3.11 and 3.13 serially. Original logs, interpreter, imported source path,
source HEAD, command and exit codes are preserved. Windows temp/schema read
failures, if any, are recorded as failures; no old tests/schema are changed.
Final exact-head 3.11/3.13/isolated-http/isolated-browser CI links, actual counts
and accepted main/checkout merge SHA are recorded in the Draft PR.

Only this module, dedicated tests/trust fixtures, a separate sealed replay/script
and limited B5 docs/evidence change. No execution.py, rules __init__, readiness,
SEO-01/Codex 1 files, FindingBuilder, Gold, catalogs, policies, collector/browser,
contracts/schemas, security labs, CI, infra, dependencies or frozen roadmap change.
Enabling TRUST-01 still requires a separately Owner-approved adapter/version and
status/coverage contract, independent audit and integration tests. This evidence
module supplies none of that activation or identity verification authorization.
No self-merge, RA-3, real-site diagnosis, public report or deployment.

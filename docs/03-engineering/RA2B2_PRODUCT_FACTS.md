# RA-2B-2 product information evidence prerequisite

Issue #14; isolated worktree `D:/Projects/VRAE-Codex2`, branch
`feat/ra2b2-product-facts`. Fetched baseline main:
`70fa445ab094b01f3e84c50030c19d6c79f4cae3`. No Codex 1 code is included.

**PREREQUISITE / PRODUCT FACTS ONLY / NOT RULE-ENABLED.** Owner acceptance pending.
No Observation, Finding or diagnostic PASS/FAIL is generated. INFO-01 remains
disabled and UNKNOWN in both existing evaluator versions.

## Useful bounded capability

`vrae.rules.product_facts.extract(pack, expected_pack_ref=trusted_pin)` verifies
the existing EvidencePack before resolving retained original UTF-8 HTTP HTML.
Requested and final product roles use the existing URL heuristic; this does not
establish a SKU or semantic product identity. `EXTRACTED` means source text was
retained and located, not that INFO-01 passed. It does not establish rendered
visibility, authenticity, engineering suitability, completeness or business value.

The supported subset is balanced HTML, exactly one plain-text nonempty h1, and
table rows with exactly one plain-text th followed by one plain-text td. Explicit
tbody/thead/tfoot are supported. DL, rich cell markup, nested tables, scripts,
templates, forms, variant controls, hidden/style attributes, malformed markup,
oversized documents (>128 KiB), >2048 elements, >32 nesting and >128 rows are
outside the supported scope. No generic NLP, keyword product classifier, network
client or new framework is introduced.

Every name, label and value preserves decoded text including whitespace, source
and snapshot refs, EvidencePack evidence_ref, source JSON pointer, original
document SHA256, requested/final URL and capture time. Element locators use
one-based line, zero-based character column and a structural path whose bracket
index is **ordinal among all element siblings**, not XPath same-tag indexing.
`start_tag` retains the exact original opening tag. HTML entities are decoded in
text; original entity spelling remains in the pinned raw bytes.

## Unknown and blocked boundaries

Empty static cells retain exact empty value citations with `EMPTY_STATIC_VALUE`
and UNKNOWN. Repeated labels, even equal-valued ones, retain separate citations
with `DUPLICATE_LABEL`; no variant association is inferred. Missing fields/raw,
unvisited pages, unsupported input, incomplete responses and ambiguous names
remain UNKNOWN. Existing capture-classified WAF/403/robots snapshots return
ACCESS_BLOCKED. No product pages yields an empty pages list with original coverage
and INFO-01 UNKNOWN. Unvisited inventory remains visible in coverage.

**No safe INFO-01 FAIL is enabled.** An empty static cell proves only that the
captured original cell contains no text. Required-field applicability, complete
dynamic/variant state, separately supplied PDFs and rendered context are not
established. Owner-approved applicability and a versioned evaluator integration
are still needed. Script-free source is not proof that no dynamic variant exists.

## Reproducible evidence and review

Five new fictional industrial valve HTML fixtures cover a named component with
material/pressure/diameter, an empty pressure cell, conflicting pressure labels,
variant selection, and separately available parameters. Values are plausible
sample page text, not certified physical properties. Tests additionally cover
missing raw, unvisited, WAF, robots, HTTP 403/500, malformed/unsupported markup,
UTF-8/entities, old pins, tenant/run changes, corrupted blobs, duplicate snapshots
and forged output text/positions/refs/scope/enabled flag after resealing.

`python scripts/verify_ra2b2.py` loads the committed synthetic pack and trusted pin
from `ra2b2-evidence/product-facts.json`. Default replay is offline; regeneration
requires explicit `--write-example`. It independently checks original source lines
without using the extractor parser. This is an independent code path, **not a
second human or Owner acceptance**. `verify_facts` also replays and compares the
complete extraction; recomputing an output hash cannot authorize fabricated facts.

Example: `Nominal pressure` → `PN 40 (4.0 MPa)` occurs in fixture line 10;
th column 4, td column 29. Full pack/source/snapshot/evidence IDs and exact paths
are committed in `ra2b2-evidence/product-facts.json` and replay output.

Original red log records 26 pass / 2 fail: the reused journey helper blocked a
contact target rather than the product source. The independent product helper
fixed that test setup; `green.txt` records 30 passing tests before the added UTF-8
and existing-rule isolation checks. No production behavior was relaxed to pass.

Full unchanged CI-equivalent local checks and legacy RA-2A/2B-0/2B-1 replay run via
`python docs/03-engineering/ra2b2-evidence/regress.py` in separate 3.11/3.13 virtual
environments. Raw logs and commands are retained per interpreter. Host pytest
intentionally skips the existing disposable Linux firewall lab tests; the hosted
isolated-http and isolated-browser jobs must supply those actual checks. Hosted
four-job status and final exact head SHA are reported with the Draft PR delivery.

No shared schema, dispatcher, readiness, journey, collector, browser, security,
frozen document, infrastructure or workflow file is changed. No RA-2D/RA-3,
integration of unaccepted code, deployment or merge is authorized by this PR.

# Private synthetic evidence review — 26 UNREVIEWED units

Inspect original sample bodies and response metadata BEFORE considering the candidate expectation.
Fill reviewer.csv / review-input.json separately; no Gold approval is created by editing a name or flag.
Full href locators, traces, evidence refs and blank human fields are in reviewer.csv and packet.json.

| # | Site / rule@version | Source → target | HTTP / observed / candidate | Human verdict / rationale / identity / time / conflict / Owner ref |
| --- | --- | --- | --- | --- |
| 1 | static_catalog / DISC-01@1.0.0 | https://example.org/ → https://example.org/category/valves | 200 / PASS / PASS | UNREVIEWED — all human fields blank |
| 2 | static_catalog / DISC-02@1.0.0 | https://example.org/category/valves → https://example.org/products/valve-v1 | 200 / PASS / PASS | UNREVIEWED — all human fields blank |
| 3 | static_catalog / CTA-02@1.0.0 | https://example.org/products/valve-v1 → https://example.org/contact | 200 / PASS / PASS | UNREVIEWED — all human fields blank |
| 4 | mixed_broken_paths / DISC-01@1.0.0 | https://example.org/ → https://example.org/category/missing | 404 / FAIL_WITH_EVIDENCE / FAIL_WITH_EVIDENCE | UNREVIEWED — all human fields blank |
| 5 | mixed_broken_paths / DISC-01@1.0.0 | https://example.org/ → https://example.org/category/valves | 200 / PASS / PASS | UNREVIEWED — all human fields blank |
| 6 | mixed_broken_paths / DISC-02@1.0.0 | https://example.org/category/missing → (no supported href observed) | N/A / UNKNOWN / UNKNOWN | UNREVIEWED — all human fields blank |
| 7 | mixed_broken_paths / DISC-02@1.0.0 | https://example.org/category/valves → https://example.org/products/gone | 410 / FAIL_WITH_EVIDENCE / FAIL_WITH_EVIDENCE | UNREVIEWED — all human fields blank |
| 8 | mixed_broken_paths / DISC-02@1.0.0 | https://example.org/category/valves → https://example.org/products/valve-v1 | 200 / PASS / PASS | UNREVIEWED — all human fields blank |
| 9 | mixed_broken_paths / CTA-02@1.0.0 | https://example.org/products/gone → (no supported href observed) | N/A / UNKNOWN / UNKNOWN | UNREVIEWED — all human fields blank |
| 10 | mixed_broken_paths / CTA-02@1.0.0 | https://example.org/products/valve-v1 → https://example.org/contact | 404 / FAIL_WITH_EVIDENCE / FAIL_WITH_EVIDENCE | UNREVIEWED — all human fields blank |
| 11 | mixed_broken_paths / CTA-02@1.0.0 | https://example.org/products/valve-v1 → https://example.org/rfq | 403 / ACCESS_BLOCKED / ACCESS_BLOCKED | UNREVIEWED — all human fields blank |
| 12 | spa_navigation / DISC-01@1.0.0 | https://example.org/ → (no supported href observed) | N/A / UNKNOWN / UNKNOWN | UNREVIEWED — all human fields blank |
| 13 | spa_navigation / DISC-02@1.0.0 | (source not captured) → (no supported href observed) | N/A / UNKNOWN / UNKNOWN | UNREVIEWED — all human fields blank |
| 14 | spa_navigation / CTA-02@1.0.0 | (source not captured) → (no supported href observed) | N/A / UNKNOWN / UNKNOWN | UNREVIEWED — all human fields blank |
| 15 | waf_challenge / DISC-01@1.0.0 | https://example.org/ → (no supported href observed) | N/A / ACCESS_BLOCKED / ACCESS_BLOCKED | UNREVIEWED — all human fields blank |
| 16 | waf_challenge / DISC-02@1.0.0 | (source not captured) → (no supported href observed) | N/A / UNKNOWN / UNKNOWN | UNREVIEWED — all human fields blank |
| 17 | waf_challenge / CTA-02@1.0.0 | (source not captured) → (no supported href observed) | N/A / UNKNOWN / UNKNOWN | UNREVIEWED — all human fields blank |
| 18 | robots_denied / DISC-01@1.0.0 | https://example.org/ → (no supported href observed) | N/A / ACCESS_BLOCKED / ACCESS_BLOCKED | UNREVIEWED — all human fields blank |
| 19 | robots_denied / DISC-02@1.0.0 | (source not captured) → (no supported href observed) | N/A / UNKNOWN / UNKNOWN | UNREVIEWED — all human fields blank |
| 20 | robots_denied / CTA-02@1.0.0 | (source not captured) → (no supported href observed) | N/A / UNKNOWN / UNKNOWN | UNREVIEWED — all human fields blank |
| 21 | redirect_budget / DISC-01@1.0.0 | https://example.org/ → https://example.org/category/moved | 200 / PASS / PASS | UNREVIEWED — all human fields blank |
| 22 | redirect_budget / DISC-02@1.0.0 | https://example.org/category/moved → https://example.org/products/valve-v1 | N/A / UNKNOWN / UNKNOWN | UNREVIEWED — all human fields blank |
| 23 | redirect_budget / CTA-02@1.0.0 | (source not captured) → (no supported href observed) | N/A / UNKNOWN / UNKNOWN | UNREVIEWED — all human fields blank |
| 24 | unretained_html / DISC-01@1.0.0 | https://example.org/ → (no supported href observed) | N/A / UNKNOWN / UNKNOWN | UNREVIEWED — all human fields blank |
| 25 | unretained_html / DISC-02@1.0.0 | https://example.org/category/valves → (no supported href observed) | N/A / UNKNOWN / UNKNOWN | UNREVIEWED — all human fields blank |
| 26 | unretained_html / CTA-02@1.0.0 | https://example.org/products/valve-v1 → (no supported href observed) | N/A / UNKNOWN / UNKNOWN | UNREVIEWED — all human fields blank |

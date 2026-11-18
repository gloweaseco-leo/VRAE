"""Authored S2-C3 scopes/expectations, never a new rule evaluator or human Gold."""

from copy import deepcopy
from tests.benchmark.scenarios import scenarios, route, label, HOME, CATEGORY, PRODUCT, CONTACT
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parents[1] / "fixtures/industry/l2-industrial-v1"

VERSION = "s2-c3-quality-1.0.0"
BASELINE = "84276325befdcf858852a1ec791e8b0695a515eb"


def sites():
    base = scenarios()[0]
    result = []
    for name, kind in (
        ("s2_static", "STATIC"),
        ("s2_cms", "CMS"),
        ("s2_spa", "SPA"),
        ("s2_skus", "MULTI_SKU"),
        ("s2_languages", "MULTILINGUAL"),
    ):
        case = deepcopy(base)
        case.update(
            site_id=name, site_type=kind, representation="SYNTHETIC_RECORDED_HTML_NOT_LIVE_" + kind
        )
        case["selected_roles"] = [
            dict(role=role, url="https://example.org" + url, selection="SELECTED", applicable=True)
            for role, url in (
                ("HOME", HOME),
                ("CATEGORY", CATEGORY),
                ("PRODUCT", PRODUCT),
                ("CONTACT", CONTACT),
            )
        ]
        if kind == "CMS":
            case["routes"][0]["body"] = (
                '<meta name="generator" content="Synthetic CMS">' + case["routes"][0]["body"]
            )
            case["routes"][3]["status"] = 404
            case["labels"][2].update(
                expected="FAIL_WITH_EVIDENCE",
                rationale="Captured CMS contact href returns404; no delivery inference.",
            )
        elif kind == "SPA":
            case.update(
                routes=deepcopy(scenarios()[2]["routes"]), labels=deepcopy(scenarios()[2]["labels"])
            )
        elif kind == "MULTI_SKU":
            extra = "/products/pump-p40"
            case["routes"][1]["body"] = (
                '<h1>Valves and pumps</h1><a href="'
                + PRODUCT
                + '">Valve V1</a><a href="'
                + extra
                + '">Pump P40</a>'
            )
            case["routes"] += [
                route(extra, '<h1>P40</h1><a href="/rfq">RFQ</a>'),
                route("/rfq", "blocked", 403),
            ]
            case["labels"][1].update(
                expected="UNKNOWN",
                rationale="403 on selected RFQ stops the bounded capture before the other SKU.",
            )
            case["labels"][2].update(
                expected="UNKNOWN",
                rationale="Other SKU was not visited; authored scope is retained unobserved, not TN.",
            )
            case["labels"] += [
                label("DISC-02", CATEGORY, extra, "PASS", 1, "Second captured SKU path only."),
                label(
                    "CTA-02",
                    extra,
                    "/rfq",
                    "ACCESS_BLOCKED",
                    0,
                    "Captured403 is not business failure.",
                ),
            ]
            case["selected_roles"] += [
                dict(
                    role="PRODUCT_SECOND",
                    url="https://example.org" + extra,
                    selection="SELECTED",
                    applicable=True,
                ),
                dict(
                    role="RFQ", url="https://example.org/rfq", selection="SELECTED", applicable=True
                ),
            ]
        elif kind == "MULTILINGUAL":
            case["routes"][0]["body"] = (
                '<html lang="en"><h1>Industrial components</h1><section lang="de">Industrieventile und technische Daten</section><section lang="zh">&#24037;&#19994;&#27893;&#38400;</section><nav><a href="'
                + CATEGORY
                + '">Components</a></nav></html>'
            )
            case["selected_roles"] += [
                dict(
                    role="DE_PRODUCT",
                    url="https://example.org/de/products/valve-v1",
                    selection="SELECTED",
                    applicable=True,
                ),
                dict(
                    role="JP_PRODUCT",
                    url="https://example.org/ja/products/valve-v1",
                    selection="UNSELECTED",
                    applicable=True,
                ),
            ]
        result.append(case)
    complete = deepcopy(next(c for c in result if c["site_id"] == "s2_skus"))
    complete["site_id"] = "s2_skus_complete"
    for r in complete["routes"]:
        if r["url"] == "https://example.org/rfq":
            r.update(
                status=200,
                body='<html><h1>RFQ fields</h1><form method="post" action="/send"></form></html>',
            )
    for index in (1, 2, 4):
        complete["labels"][index].update(
            expected="PASS",
            rationale="Captured200 in this complete bounded fixture; no inquiry submitted.",
        )
    result.append(complete)
    return result


def industrial_cases():
    """Each selector and expectation is authored independently of diagnose()."""
    pump = (DIRECTORY / "pump.html").read_bytes()
    valve = (DIRECTORY / "valve.html").read_bytes()
    proof = (DIRECTORY / "proof.html").read_bytes()

    def case(name, rule, model, expected, reason, overrides=None, attribute=None):
        return dict(
            site_id=name,
            site_type="INDUSTRIAL_MULTI_SKU",
            source_origin="SYNTHETIC_OFFLINE",
            overrides=overrides or {},
            rule=rule,
            model=model,
            attribute=attribute,
            expected=expected,
            rationale=reason,
        )

    return [
        case(
            "s2_duty_conflict",
            "IND-DUTY",
            "P40",
            "FAIL_WITH_EVIDENCE",
            "Declared10bar vs requested18bar; engineering fit UNKNOWN.",
            attribute="pressure",
        ),
        case(
            "s2_model_collision",
            "IND-SELECTION",
            "P40",
            "UNKNOWN",
            "Two source records useP40; identity unresolved.",
            {"/products/valve-v25": valve.replace(b"<td>V25</td>", b"<td>P40</td>")},
        ),
        case(
            "s2_unit_conversion",
            "IND-DUTY",
            "P40",
            "PASS",
            "200L/min=12m3/h meets declared10m3/h only.",
            {"/products/pump-p40": pump.replace(b"12 m3/h", b"200 L/min")},
            attribute="flow",
        ),
        case(
            "s2_pdf_unparsed",
            "IND-SPEC",
            "P40",
            "UNKNOWN",
            "Power absent in parsed table; unparsed PDF is not proof of absence.",
            {
                "/products/pump-p40": pump.replace(
                    b"<tr><th>Motor power</th><td>2.2 kW</td></tr>", b""
                ).replace(b"<nav>", b'<a href="/p40.pdf">Datasheet not parsed</a><nav>')
            },
        ),
        case(
            "s2_certificate_claim",
            "IND-PROOF",
            "P40",
            "FAIL_WITH_EVIDENCE",
            "Source date precedes capture; independent authenticity UNKNOWN.",
        ),
        case(
            "s2_certificate_current_claim",
            "IND-PROOF",
            "P40",
            "PASS",
            "Source date later than capture; NOT authenticated qualification.",
            {"/products/supplier-proof": proof.replace(b"2025-12-31", b"2027-12-31")},
        ),
        case(
            "s2_buyer_input_gap",
            "IND-RFQ",
            "P40",
            "UNKNOWN",
            "Destination buyer input missing; no form submitted.",
        ),
        case(
            "s2_engineering_fit_unknown",
            "IND-FIT",
            "P40",
            "UNKNOWN",
            "Catalog scalar values do not establish engineering suitability.",
        ),
        case(
            "s2_motor_not_applicable",
            "IND-DUTY",
            "V25",
            "NOT_APPLICABLE",
            "Declared valve profile excludes motor comparison.",
            attribute="motor_electrical",
        ),
    ]

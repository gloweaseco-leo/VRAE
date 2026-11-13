"""Bounded receipts for the unchanged accepted local regression suites."""

import argparse
import json
import re
import xml.etree.ElementTree as ET

from .publication import OWN, RUNTIME, public_junit, scan, sha


def main():
    parser = argparse.ArgumentParser()
    for name in ("minor", "legacy", "review", "final"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--identity")
    parser.add_argument("--browser-run")
    args = parser.parse_args()
    assert args.minor in ("311", "313")
    assert all(re.fullmatch(r"[a-z0-9-]{3,48}", x) for x in (args.legacy, args.review, args.final))
    c3 = RUNTIME / args.legacy / "c3/evidence/full"
    review = RUNTIME / args.review
    identity = RUNTIME / (args.identity or args.review)
    assert re.fullmatch(r"[a-z0-9-]{3,48}", identity.name)
    out = OWN / "evidence" / ("legacy-" + args.minor)
    out.mkdir(parents=True, exist_ok=False)
    facts = []
    expected = {
        "p1-v1": 54,
        "p1-v2": 54,
        "p2a": 86,
        "pure": 35,
        "c3": 29,
        "p2b1": 131,
        "b2-pure": 73,
        "b2-pg": 30,
    }
    commands = json.loads((c3 / "commands.json").read_text())
    commands += [
        c for c in json.loads((review / "receipt.json").read_text()) if c["stage"] == "p2b1"
    ]
    commands += [
        c
        for c in json.loads((identity / "receipt.json").read_text())
        if c["stage"] in ("b2-pure", "b2-pg")
    ]
    counts = {}
    for stage in ["p1-v1", "p1-v2", "p2a", "pure", "c3", "full", "p2b1", "b2-pure", "b2-pg"]:
        item = next(c for c in commands if c["stage"] == stage)
        assert item["returncode"] == 0, "ACCEPTED_STAGE_RED_" + stage
        if stage != "full":
            assert not item.get("red"), "ACCEPTED_STAGE_RED_" + stage
        assert stage == "full" or item["tests"] == expected[stage], "ORIGINAL_COUNT_DRIFT_" + stage
        parent = (
            c3
            if stage in ("p1-v1", "p1-v2", "p2a", "pure", "c3", "full")
            else review
            if stage == "p2b1"
            else identity
        )
        raw = (parent / stage / "raw-junit.xml").read_bytes()
        cases = ET.fromstring(raw).findall(".//testcase")
        assert len(cases) == item["tests"] and all(
            not any(c.find(k) is not None for k in ("failure", "error")) for c in cases
        )
        skipped = [c for c in cases if c.find("skipped") is not None]
        if stage == "full":
            # Unchanged default markers require separate disposable kernel and
            # sandboxed-browser containers. Preserve native XML skip records;
            # do not lift these guards on the host or count them as passes.
            assert len(cases) == 2468 and len(skipped) == 25
            assert all(
                c.get("classname")
                in ("tests.browser.test_isolated_browser", "tests.collection.test_isolated")
                for c in skipped
            )
        else:
            assert not skipped
        safe = ET.fromstring(public_junit(raw))
        safe.set("name", "Accepted unchanged " + stage)
        for c in safe.findall("testcase"):
            c.set("classname", "accepted_" + stage)
        ET.ElementTree(safe).write(
            out / (stage + "-status.xml"), encoding="utf-8", xml_declaration=True
        )
        facts.append(
            {
                **{k: v for k, v in item.items() if k != "red"},
                "passed": len(cases) - len(skipped),
                "host_isolation_skips": len(skipped),
                "native_junit_sha256": sha(raw),
            }
        )
        if stage == "full":
            for prefix in (
                "tests.reviewing",
                "tests.reporting",
                "tests.reporting.test_ra3c_owner_adjudicated_v2",
                "tests.identity",
                "tests.operator_console",
            ):
                counts[prefix] = sum(c.get("classname", "").startswith(prefix) for c in cases)
    assert (
        counts["tests.reviewing"] == 127
        and counts["tests.reporting.test_ra3c_owner_adjudicated_v2"] == 118
    ), "REVIEW_QA_COUNT_DRIFT"
    if args.browser_run:
        assert re.fullmatch(r"[a-z0-9-]{3,48}", args.browser_run)
        browser_root = RUNTIME / args.browser_run
        assert json.loads((browser_root / "receipt.json").read_text())["returncode"] == 0
        browsers = list(browser_root.glob("evidence/browser-*/receipt.json"))
    else:
        assert next(c for c in commands if c["stage"] == "browser")["returncode"] == 0
        browsers = list(c3.parent.glob("browser-*/receipt.json"))
    assert len(browsers) == 1
    browser = json.loads(browsers[0].read_text())
    assert browser["assertions"] == browser["passed"] and browser["assertions"] > 0
    catalog = json.loads((review / "p2b1/p2b1-catalog-and-calls.json").read_text())
    bounded_catalog = {
        k: catalog[k]
        for k in (
            "server",
            "roles",
            "tables",
            "policies",
            "grants",
            "functions",
            "migrations",
            "schema_sha256",
        )
    }
    (out / "actual-pg-role-rls-acl-catalog.json").write_text(
        json.dumps(bounded_catalog, indent=2), encoding="utf-8"
    )
    final = OWN / "evidence" / args.final
    assert (final / "publication.json").is_file()
    assert json.loads((final / "security-receipt.json").read_text())["tests"] == 57
    proof = {
        "status": "ACCEPTED_HOST_PG_AND_C3_REGRESSIONS_PASS",
        "minor": args.minor,
        "stages": facts,
        "full_test_groups": counts,
        "c3_actual_browser": {
            "assertions": browser["assertions"],
            "passed": browser["passed"],
            "screenshots": len(browser["screenshots"]),
            "protected_receipt_sha256": sha(browsers[0].read_bytes()),
        },
        "b5a_final_evidence": args.final,
        "accepted_test_assertions_modified": False,
        "unchanged_host_skips_require_separate_isolated_gates": 25,
    }
    (out / "summary.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
    (out / "publication.json").write_text(json.dumps(scan(out), indent=2), encoding="utf-8")
    print(
        json.dumps({"status": proof["status"], "minor": args.minor, "full_groups": counts}),
        flush=True,
    )


if __name__ == "__main__":
    main()

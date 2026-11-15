"""Run actual SourcePolicy/Collector/rules/Guard/report, no network transport."""
import asyncio
from datetime import datetime, timezone
import base64
import json
import time
from pathlib import Path
from tests.collection.test_pipeline import FixedDNS, SyntheticTransport
from tests.collection.test_security import access
from tests.reporting.synthetic import HOME, PRODUCT, DECLARATION, proposal_bundle, source_pins
from vrae.collection.collector import Collector
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Limits
from vrae.evidence import build_pack
from vrae.findings import build_findings
from vrae.rules import execute
from vrae.reporting import build_draft, render
from vrae.reporting.common import VERSION, digest
from vrae.reporting.renderer import RENDERER_VERSION

def run(folder):
    records = []
    for case in ("404", "200", "disc-404"):
        begin = time.monotonic()
        code = 200 if case == "200" else 404
        routes = {
            "/": (200, HOME),
            "/category/motion": (404 if case == "disc-404" else 200,
                "<html>Not found</html>" if case == "disc-404" else
                '<html><a href="/products/hm-40">HM-40</a></html>'),
            "/products/hm-40": (200, PRODUCT.replace("LINKS", '<a href="/contact">Contact team</a>')),
            "/contact": (code, "<html><body>"+DECLARATION+"</body></html>"),
            "/robots.txt": (200, "User-agent: *\nDisallow:\n"),
        }
        transport = SyntheticTransport({"https://example.org"+u: (status,
            {"content-type": "text/plain" if u == "/robots.txt" else "text/html"}, text.encode())
            for u, (status, text) in routes.items()})
        source = asyncio.run(Collector(SafeFetcher(FixedDNS(), transport)).capture(
            "run-beta-"+case, access(), limits=Limits(max_pages=8, interval_seconds=0.01),
            retain_raw_html=True))
        assert transport.calls and all(c[1] == "GET" for c in transport.calls)
        pack = build_pack([source])
        execution = execute(pack, expected_pack_ref=pack.ref, evaluator_version="ra2b6-1.0.0")
        enabled = [r["rule_id"] for r in execution["executions"] if r["enabled"]]
        assert set(enabled) == {"DISC-01","DISC-02","CTA-02","INFO-01","TRUST-01","SEO-01"}
        package = build_findings(pack, execution, expected_pack_ref=pack.ref,
            expected_execution_ref=execution["execution_ref"],
            expected_builder_version="ra2c3-1.0.0", expected_evaluator_version="ra2b6-1.0.0")
        guards = proposal_bundle(pack, package)
        metadata = {"report_id":"report-beta-"+case,"version":1,
            "created_at":datetime.now(timezone.utc).isoformat(),"created_by":"beta-test-only",
            "mode":"SYNTHETIC_PRIVATE_PREVIEW","finding_selection":None}
        pins = {**source_pins(pack, package),
            "expected_guard_refs":[g["guard"]["guard_ref"] for g in guards],
            "expected_metadata_sha256":digest(metadata),"expected_reporting_version":VERSION,
            "expected_renderer_version":RENDERER_VERSION}
        if case == 'disc-404':
            from .accepted_chain import build as disc_build
            guards,pins,draft,html = disc_build(pack,package,metadata)
        else:
            draft = build_draft(pack, package, guards, metadata, **pins)
            html = render(draft.document, draft.html_bytes, pack, package, guards, metadata,
                expected_draft_ref=draft.ref, **pins)
        from .accepted_chain import delivery_denials
        denial = delivery_denials(draft)
        assert draft.document["approval_status"] == "NOT_APPROVED" and not draft.document["shareable"]
        assert len(draft.document["issues"]) == (1 if case in ("404","disc-404") else 0)
        if case == "disc-404":
            assert draft.document["unsupported_rule_findings"] == 0
        dest = Path(folder)/case
        dest.mkdir(parents=True)
        bundle = {"pack":pack.document,"objects_base64":{k:base64.b64encode(v).decode()
            for k,v in pack.objects.items()},"package":package.document,"guard_inputs":guards,
            "metadata":metadata,"pins":pins}
        (dest/"source.json").write_text(json.dumps(bundle,sort_keys=True))
        (dest/"draft.json").write_text(json.dumps(draft.document,sort_keys=True))
        (dest/"report.html").write_bytes(html)
        failures = [{"rule":r["rule_id"],"observation_id":o["observation"]["observation_id"]}
            for r in execution["executions"] for o in r["observations"]
            if o["observation"]["result"] == "FAIL_WITH_EVIDENCE"]
        records.append({"case":case,"run_id":pack.document["run_id"],"pack_ref":pack.ref,
            "execution_ref":execution["execution_ref"],"package_ref":package.ref,"draft_ref":draft.ref,
            "enabled_rules":enabled,"disabled_rules":len(execution["executions"])-len(enabled),
            "finding_failures":failures,"report_issues":len(draft.document["issues"]),
            "unsupported_rule_findings":draft.document["unsupported_rule_findings"],
            "html_sha256":draft.document["html_sha256"],"seconds":round(time.monotonic()-begin,3),
            "execution":"LIVE_OFFLINE_COLLECTOR_NOT_PRECOMPUTED_REPORT",
            "reporting_version":pins["expected_reporting_version"],"B6_delivery":denial,
            "worker_connection":"BLOCKED_NO_ACCEPTED_PROCESSING_BRIDGE"})
    return records

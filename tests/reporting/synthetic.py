"""Read accepted fixed captures; new detached captures use only synthetic transport."""
import asyncio
import base64
import json
from pathlib import Path

from tests.collection.test_pipeline import FixedDNS, SyntheticTransport
from tests.collection.test_security import access
from vrae.collection.collector import Collector
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Limits
from vrae.evidence import EvidencePack, build_pack
from vrae.findings import FindingPackage, build_findings
from vrae.interpretation import binding, catalog, validate
from vrae.reporting.common import VERSION, digest
from vrae.reporting.editorial import PROPOSALS
from vrae.reporting.renderer import RENDERER_VERSION
from vrae.rules import execute

ROOT = Path(__file__).resolve().parents[2]
DECLARATION = ('<table><tr><th>Company name</th><td>Harbor Synthetic Motion Parts</td></tr></table>'
    '<section><h2>Company profile</h2><p>We supply industrial motion components.</p></section>'
    '<a href="mailto:team@synthetic.example">Contact sales</a>')
HOME = ('<html>\n<head><title>Harbor industrial motion components</title>'
        '<link rel="canonical" href="/"></head><body>\n' + DECLARATION +
        '\n<nav><a href="/category/motion">Components</a></nav></body></html>')
PRODUCT = ('<html><body>\n<h1>HM-40 linear actuator component</h1>\n'
           '<table><tr><th>Body material</th><td>Stainless steel</td></tr>'
           '<tr><th>Nominal size</th><td>DN 40</td></tr></table>\nLINKS\n</body></html>')


def base_pins(pack, execution):
    return {'expected_pack_ref': pack.ref, 'expected_execution_ref': execution['execution_ref'],
            'expected_builder_version': 'ra2c3-1.0.0', 'expected_evaluator_version': 'ra2b6-1.0.0'}


def accepted_source(status):
    data = json.loads((ROOT / 'tests/interpretation/fixtures/fixed-replay.json').read_text(encoding='utf-8'))
    case = next(c for c in data['cases'] if c['status'] == status)
    p = case['pins']
    pack = EvidencePack.load(case['pack'], {k: base64.b64decode(v, validate=True)
        for k, v in case['objects_base64'].items()}, expected_ref=p['expected_pack_ref'])
    package = FindingPackage.load(case['package'], pack,
        **{k: v for k, v in p.items() if k not in ('expected_scope', 'expected_guard_version')})
    return pack, package


def new_source(mode=403, *, contacts=1, product=PRODUCT, retained=True, home=HOME):
    status = mode if isinstance(mode, int) else 200
    if mode == 'unretained':
        retained = False
    if mode == 'waf':
        home = '<html><body>Verify you are human</body></html>'
    urls = ['/contact' + ('/' + str(i + 1) if contacts > 1 else '') for i in range(contacts)]
    links = ''.join(f'<a href="{u}">Contact team</a>' for u in urls)
    robots = 'User-agent: *\nDisallow: /contact\n' if mode == 'robots' else 'User-agent: *\nDisallow:\n'
    routes = {'/': (200, home), '/category/motion': (200,
              '<html><a href="/products/hm-40">HM-40</a></html>'),
              '/products/hm-40': (200, product.replace('LINKS', links)),
              '/robots.txt': (200, robots),
              **{u: (status, '<html><body>' + DECLARATION + '</body></html>') for u in urls}}
    transport = SyntheticTransport({'https://example.org' + path: (code,
        {'content-type': 'text/plain' if path == '/robots.txt' else 'text/html'}, text.encode())
        for path, (code, text) in routes.items()})
    source = asyncio.run(Collector(SafeFetcher(FixedDNS(), transport)).capture(
        'run-ra3c-' + str(mode) + '-' + str(contacts), access(),
        limits=Limits(max_pages=8, interval_seconds=0.01), retain_raw_html=retained))
    assert all(call[1] == 'GET' for call in transport.calls)
    pack = build_pack([source])
    execution = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b6-1.0.0')
    package = build_findings(pack, execution, **base_pins(pack, execution))
    return pack, package


def source_pins(pack, package):
    return {**base_pins(pack, package.document['rule_execution']), 'expected_package_ref': package.ref,
            'expected_guard_version': 'ra3b-1.0.0',
            'expected_scope': {k: pack.document[k] for k in ('tenant_id', 'run_id', 'policy_id', 'policy_version')}}


def proposal_bundle(pack, package):
    pins = source_pins(pack, package)
    cat = catalog(pack, package, **pins)
    facts = [f for f in cat['facts'] if f['proof_kind'] == 'CAPTURED_CTA_HTTP_FAILURE']
    for rule in ('INFO-01', 'TRUST-01', 'SEO-01'):
        selected = next((f for f in cat['facts'] if f['rule_id'] == rule), None)
        if selected:
            facts.append(selected)
    known_oid = next(r['observations'][0]['observation']['observation_id'] for r in
                     package.document['rule_execution']['executions'] if r['observations'])
    i = {'schema_version': '1.0', **{k: pins['expected_scope'][k] for k in ('tenant_id', 'run_id')},
         'interpretation_id': 'ra3c-synthetic-proposals', 'observation_ids': sorted(
             {f['observation_id'] for f in facts}) or [known_oid],
         'evidence_ids': sorted({f['source']['citation']['evidence_ref'] for f in facts}),
         'hypotheses': [], 'recommendations': [], 'missing_information': [], 'model_id': None,
         'input_tokens': None, 'output_tokens': None, 'status': 'VALIDATED'}
    bindings = []

    def add(text, kind, fact):
        field = 'recommendations' if kind == 'RECOMMENDATION' else 'hypotheses'
        pointer = f'/{field}/{len(i[field])}'
        i[field].append(text)
        bindings.append(binding(pointer=pointer, text=text, claim_type=kind, fact=fact, context=cat['context']))

    duplicate_objectives = []
    for fact in facts:
        if fact['statement'] in i['hypotheses']:
            duplicate_objectives.append(fact)
        else:
            add(fact['statement'], 'OBJECTIVE_SOURCE_FACT', fact)
    # Frozen AIInterpretation disallows duplicate strings. Use separate guard
    # envelopes per defect for repeated cautious review copy, never change schema.
    bundles = []
    objective = {'interpretation': i, 'bindings': bindings,
                 'guard': validate(i, bindings, pack, package, **pins).document}
    bundles.append(objective)
    for index, fact in enumerate(duplicate_objectives):
        j = {**i, 'interpretation_id': 'ra3c-duplicate-source-' + str(index),
             'observation_ids': [fact['observation_id']],
             'evidence_ids': [fact['source']['citation']['evidence_ref']],
             'hypotheses': [fact['statement']], 'recommendations': [], 'missing_information': []}
        bs = [binding(pointer='/hypotheses/0', text=fact['statement'], claim_type='OBJECTIVE_SOURCE_FACT',
                      fact=fact, context=cat['context'])]
        bundles.append({'interpretation': j, 'bindings': bs,
                        'guard': validate(j, bs, pack, package, **pins).document})
    for index, fact in enumerate(f for f in facts if f['proof_kind'] == 'CAPTURED_CTA_HTTP_FAILURE'):
        j = {**i, 'interpretation_id': 'ra3c-proposals-' + str(index),
             'observation_ids': [fact['observation_id']],
             'evidence_ids': [fact['source']['citation']['evidence_ref']],
             'hypotheses': [], 'recommendations': [], 'missing_information': []}
        bs = []
        for kind, text in PROPOSALS.values():
            field = 'recommendations' if kind == 'RECOMMENDATION' else 'hypotheses'
            pointer = f'/{field}/{len(j[field])}'
            j[field].append(text)
            bs.append(binding(pointer=pointer, text=text, claim_type=kind, fact=fact, context=cat['context']))
        bundles.append({'interpretation': j, 'bindings': bs,
                        'guard': validate(j, bs, pack, package, **pins).document})
    return bundles


def inputs(mode=404, *, use_accepted=True, **kwargs):
    pack, package = accepted_source(mode) if use_accepted and mode in (200, 404, 410) and not kwargs else new_source(mode, **kwargs)
    bundles = proposal_bundle(pack, package)
    metadata = {'report_id': 'report-ra3c-' + str(mode), 'version': 1,
                'created_at': '2026-11-12T02:30:00Z', 'created_by': 'offline-review-operator',
                'mode': 'SYNTHETIC_PRIVATE_PREVIEW', 'finding_selection': None}
    pins = {**source_pins(pack, package), 'expected_guard_refs': [b['guard']['guard_ref'] for b in bundles],
            'expected_metadata_sha256': digest(metadata), 'expected_reporting_version': VERSION,
            'expected_renderer_version': RENDERER_VERSION}
    return pack, package, bundles, metadata, pins

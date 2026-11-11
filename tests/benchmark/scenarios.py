"""Authored inputs/expectations, independent of rule evaluator output."""
import asyncio
from copy import deepcopy

from tests.collection.test_pipeline import FixedDNS, SyntheticTransport
from tests.collection.test_security import fixture, NOW
from vrae.collection.collector import Collector
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Limits
from vrae.collection.policy import SourceAccess

ORIGIN = 'https://example.org'
HOME, CATEGORY, PRODUCT, CONTACT = '/', '/category/valves', '/products/valve-v1', '/contact'


def route(path, body, status=200, headers=None):
    return {'url': ORIGIN + path, 'status': status,
            'headers': headers or {'content-type': 'text/html'}, 'body': body}


def label(rule, source, target, expected, anchor=None, rationale=''):
    return {'status': 'CANDIDATE', 'rule_id': rule, 'rule_version': '1.0.0',
        'source_url': ORIGIN + source if source is not None else None,
        'target_url': ORIGIN + target if target is not None else None,
        'source_observed_at': NOW.isoformat() if source is not None else None,
        'anchor_index': anchor, 'expected': expected,
        'scope': 'ONE_CAPTURED_HREF_OR_EXPLICIT_EVIDENCE_GAP', 'rationale': rationale,
        'reviewer': None, 'reviewed_at': None, 'adjudication': None,
        'conflict_resolution': None, 'owner_approval_reference': None}


def scenarios():
    normal = [route(HOME, '<html><nav><a href="/category/valves">Valve components</a></nav></html>'),
        route(CATEGORY, '<html><h1>Valve components</h1><a href="/products/valve-v1">Valve V1</a></html>'),
        route(PRODUCT, '<html><h1>Industrial valve V1</h1><a href="/contact">Contact</a></html>'),
        route(CONTACT, '<html><h1>Contact</h1><form method="post" action="/send"></form></html>')]
    good = [label('DISC-01', HOME, CATEGORY, 'PASS', 0, 'Static nav href, captured category HTTP200.'),
        label('DISC-02', CATEGORY, PRODUCT, 'PASS', 0, 'Static product href, captured product HTTP200.'),
        label('CTA-02', PRODUCT, CONTACT, 'PASS', 0, 'Read-only contact href HTTP200; no delivery claim.')]
    cases = [{'site_id': 'static_catalog', 'site_type': 'STATIC_CATALOG', 'routes': deepcopy(normal),
              'labels': good, 'max_pages': 8, 'retain_raw_html': True,
              'annotation': 'Fully retained static industrial catalog; all three path steps reachable.'}]
    mixed = [route(HOME, '<html><nav><a href="/category/missing">Old catalog</a><a href="/category/valves">Valves</a></nav></html>'),
        route('/category/missing', '<html>404</html>', 404),
        route(CATEGORY, '<html><a href="/products/gone">Retired part</a><a href="/products/valve-v1">Valve V1</a></html>'),
        route('/products/gone', '<html>410</html>', 410),
        route(PRODUCT, '<html><a href="/contact">Contact</a><a href="/rfq">RFQ</a></html>'),
        route(CONTACT, '<html>404</html>', 404), route('/rfq', 'blocked', 403)]
    cases.append({'site_id': 'mixed_broken_paths', 'site_type': 'MIXED_BROKEN_PATHS', 'routes': mixed,
        'max_pages': 8, 'retain_raw_html': True,
        'annotation': 'Three independently captured broken hrefs (404/410), two good edges and a separate 403. Never a whole-site defect.',
        'labels': [label('DISC-01', HOME, '/category/missing', 'FAIL_WITH_EVIDENCE', 0, 'Captured 404 for this href only.'),
            label('DISC-01', HOME, CATEGORY, 'PASS', 1, 'Other homepage category href is reachable.'),
            label('DISC-02', '/category/missing', None, 'UNKNOWN', rationale='404 category has no retained observed source body.'),
            label('DISC-02', CATEGORY, '/products/gone', 'FAIL_WITH_EVIDENCE', 0, 'Captured 410 for retired product href.'),
            label('DISC-02', CATEGORY, PRODUCT, 'PASS', 1, 'Separate product href is reachable.'),
            label('CTA-02', '/products/gone', None, 'UNKNOWN', rationale='No observed product body after 410.'),
            label('CTA-02', PRODUCT, CONTACT, 'FAIL_WITH_EVIDENCE', 0, 'Contact target captured 404, no inbox claim.'),
            label('CTA-02', PRODUCT, '/rfq', 'ACCESS_BLOCKED', 1, '403 is an access boundary, never a site-quality failure.')]})
    cases.append({'site_id': 'spa_navigation', 'site_type': 'JS_ONLY_NAVIGATION', 'max_pages': 8,
        'retain_raw_html': True, 'routes': [route(HOME,
            '<html><div id="app"></div><script>window.catalogRoute="/category/valves";</script></html>')],
        'annotation': 'Application shell and JS route string; static evaluator cannot observe the menu or infer missing products.',
        'labels': [label('DISC-01', HOME, None, 'UNKNOWN', rationale='No supported static nav anchor.'),
                   label('DISC-02', None, None, 'UNKNOWN', rationale='No captured category source.'),
                   label('CTA-02', None, None, 'UNKNOWN', rationale='No captured product source.')]})
    for site_id, blocked_route, annotation in [
        ('waf_challenge', route(HOME, '<html>Verify you are human</html>'), 'HTTP200 WAF challenge is not an observed business homepage.'),
        ('robots_denied', route('/robots.txt', 'User-agent: *\nDisallow: /\n',
                               headers={'content-type': 'text/plain'}), 'Robots denial prevents page inspection; no absence claim.')]:
        cases.append({'site_id': site_id, 'site_type': 'ACCESS_BOUNDARY', 'routes': [blocked_route],
            'max_pages': 8, 'retain_raw_html': True, 'annotation': annotation,
            'labels': [label('DISC-01', HOME, None, 'ACCESS_BLOCKED', rationale=annotation),
                       label('DISC-02', None, None, 'UNKNOWN', rationale='No inspected category source.'),
                       label('CTA-02', None, None, 'UNKNOWN', rationale='No inspected product source.')]})
    cases.append({'site_id': 'redirect_budget', 'site_type': 'REDIRECT_AND_COVERAGE_LIMIT', 'max_pages': 2,
        'retain_raw_html': True, 'annotation': 'Captured same-role redirect; page budget stops before product. No mobile observation is available.',
        'routes': [route(HOME, '<html><nav><a href="/category/moved">Catalog</a></nav></html>'),
            route('/category/moved', '', 302, {'location': CATEGORY}), deepcopy(normal[1])],
        'labels': [label('DISC-01', HOME, '/category/moved', 'PASS', 0, '302 then category HTTP200 captured.'),
            label('DISC-02', '/category/moved', PRODUCT, 'UNKNOWN', 0, 'Original href observed; target not visited within page budget.'),
            label('CTA-02', None, None, 'UNKNOWN', rationale='No captured product source; mobile layout not evaluated.')]})
    cases.append({'site_id': 'unretained_html', 'site_type': 'RAW_HTML_NOT_RETAINED', 'max_pages': 8,
        'retain_raw_html': False, 'routes': deepcopy(normal),
        'annotation': 'Same complete observed responses but raw HTML deliberately not retained; hashes do not reconstruct href text.',
        'labels': [label('DISC-01', HOME, None, 'UNKNOWN', rationale='No retained homepage original text.'),
            label('DISC-02', CATEGORY, None, 'UNKNOWN', rationale='No retained category original text.'),
            label('CTA-02', PRODUCT, None, 'UNKNOWN', rationale='No retained product original text.')]})
    for case in cases:
        if not any(r['url'] == ORIGIN + '/robots.txt' for r in case['routes']):
            case['routes'].append(route('/robots.txt', 'User-agent: *\nDisallow:\n',
                                        headers={'content-type': 'text/plain'}))
    return cases


class StrictSyntheticTransport(SyntheticTransport):
    async def exchange(self, url, method, ip, budget, max_bytes):
        if url not in self.routes:
            raise AssertionError('UNDECLARED_BENCHMARK_REQUEST')
        return await super().exchange(url, method, ip, budget, max_bytes)


def capture(case):
    routes = {r['url']: (r['status'], r['headers'], r['body'].encode('utf-8')) for r in case['routes']}
    routes.setdefault(ORIGIN + '/robots.txt', (200, {'content-type': 'text/plain'}, b'User-agent: *\nDisallow:\n'))
    request, policy = fixture('AuditRequest'), fixture('SourcePolicy')
    access = SourceAccess(request, lambda: policy, terms_reference='benchmark-synthetic', now=lambda: NOW)
    transport = StrictSyntheticTransport(routes)
    bundle = asyncio.run(Collector(SafeFetcher(FixedDNS(), transport)).capture(
        'run-bench-' + case['site_id'], access,
        limits=Limits(max_pages=case['max_pages'], interval_seconds=0.01),
        retain_raw_html=case['retain_raw_html']))
    assert all(call[1] == 'GET' for call in transport.calls)
    return bundle

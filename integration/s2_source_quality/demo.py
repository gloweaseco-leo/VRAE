"""Offline business examples and real loopback HTTP using the original signed server."""
import json
import re
import sys
import threading
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener

from apps.operator_console.b5a_http import server
from integration.s2_source_quality.fixture import application, prepared
from integration.s2_source_quality.workbench import render
from vrae.rules.s2.source_quality import evaluate_source_quality, verify_source_quality


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else 'local'
    if not re.fullmatch('[a-z0-9-]{3,48}', label):
        raise ValueError('OWNED_LABEL_REQUIRED')
    out = Path(__file__).resolve().parent / '.runtime' / label
    out.mkdir(parents=True, exist_ok=False)
    summary = []
    scenarios = [(s, {}) for s in ('static', 'cms', 'spa', 'multi-sku', 'multilingual',
                                  'ambiguous', 'no-images', 'hostile')]
    scenarios += [('blocked', {'status': 403}), ('missing', {'status': 404}),
                  ('unretained', {'retain': False}), ('image-200', {'resource_status': 200})]
    for name, options in scenarios:
        pack, parent, held = prepared(name, **options)
        value = evaluate_source_quality(pack, parent, held=held)
        verify_source_quality(value, pack, parent, held=held, expected_quality_ref=value['quality_ref'])
        # Full retained bundle makes each byte citation independently replayable.
        (out / (name+'-pack.json')).write_text(json.dumps(pack.document, ensure_ascii=False), encoding='utf-8')
        (out / (name+'.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        (out / (name+'.html')).write_text('<!doctype html><meta charset="utf-8">'+render(value, '/controlled-demo'), encoding='utf-8')
        summary.append({'scenario': name, 'quality_ref': value['quality_ref'], 'parent_ref': held.parent_ref,
                        'coverage': value['coverage'], 'states': [r['state'] for r in value['rows']]})
    issuer, _, ledger, app, _, _, rid = application(out)
    original = ledger.source.read().payload
    http = server(app)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    results = {}
    try:
        origin = app.origin
        for subject, expected in [('reviewer-demo', 200), ('other-tenant', 403), ('recipient-a', 403)]:
            opener = build_opener(HTTPCookieProcessor(CookieJar()), NoRedirect())
            entry = origin+'/b5a/l2/'
            html = opener.open(entry, timeout=20).read().decode()
            csrf = re.search(r'name="_csrf" value="([A-Za-z0-9_-]+)"', html)[1]
            challenge = json.loads(opener.open(Request(entry+'challenge', data=urlencode({'_csrf': csrf}).encode(),
                headers={'Origin': origin, 'Content-Type': 'application/x-www-form-urlencoded'}), timeout=20).read())
            try:
                opener.open(Request(entry+'session', data=b'{}', headers={'Origin': origin,
                    'Content-Type': 'application/json', 'Authorization': issuer.token(subject, challenge['nonce']),
                    'X-L2-Nonce': challenge['nonce'], 'X-L2-CSRF': challenge['csrf']}), timeout=20).close()
                raise RuntimeError('ORIGINAL_SESSION_REDIRECT_REQUIRED')
            except HTTPError as exc:
                assert exc.code == 303
                exc.close()
            path = origin+'/b5a/l2/r/'+rid+'/source-quality'
            try:
                response = opener.open(path, timeout=20)
                code, body = response.status, response.read()
                response.close()
            except HTTPError as exc:
                code, body = exc.code, exc.read()
                exc.close()
            assert code == expected
            if code == 200:
                assert b'data-rule="INFO-03"' in body and b'HTTP 200' in body
                (out/'signed-http.html').write_bytes(body)
                cite = opener.open(path+'/cite/0/0', timeout=20).read()
                assert b'&lt;html' in cite
            else:
                assert b'quality-clue' not in body
            results[subject] = code
        assert ledger.source.read().payload == original
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=10)
    assert not thread.is_alive()
    result = {'source_mode': 'OFFLINE_SYNTHETIC', 'network': 'LOOPBACK_ORIGINAL_SERVER_ONLY',
              'model_calls': 0, 'paid_calls': 0, 'real_customer_sources': 0,
              'quality': 'NOT_EVALUABLE', 'gold': 0, 'http': results, 'server_closed': True,
              'original_report_unchanged': True, 'scenarios': summary}
    (out/'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'scenarios': len(summary), 'signed_http': results, 'server_closed': True}))


if __name__ == '__main__':
    main()

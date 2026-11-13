"""Explicit TEST_ONLY loopback harness, not a production server/auth adapter.

python -B -m apps.operator_console.preview --test-only --synthetic-fixtures
No real actor context, arbitrary URL, mutation, storage or external connection.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets

from .fixtures import make_fixture
from .interface import ConsoleInterface, Response
from .contracts import ConsoleError
from .proposals import ProposalPreview, BODY_LIMIT, CONTENT_TYPE
from . import views
from .proposal_views import composer


def serve(*, test_only=False, synthetic_fixtures=False, host='127.0.0.1', port=0, pg_read_profile=None, audit_sink=None):
    if test_only is not True or synthetic_fixtures is not True or host != '127.0.0.1':
        raise ValueError('TEST_ONLY_LOOPBACK_REQUIRED')
    if pg_read_profile is None:
        service, context = make_fixture()
    else:
        from .pg_read import make_pg_fixture
        service,context=make_pg_fixture(pg_read_profile,test_only=test_only,
            synthetic_fixtures=synthetic_fixtures,audit_sink=audit_sink)
    prefix = '/__fixture__/' + secrets.token_urlsafe(24) + '/'
    proposals = ProposalPreview(service,context,test_only=test_only,synthetic_fixtures=synthetic_fixtures)
    interface = ConsoleInterface(service,prefix=prefix,proposal_preview=proposals)

    class Handler(BaseHTTPRequestHandler):
        def handle_read(self):
            expected_host = f'127.0.0.1:{self.server.server_port}'
            origin = self.headers.get('Origin')
            if (self.headers.get('Host') != expected_host
                    or (origin is not None and origin != 'http://'+expected_host)
                    or not self.path.startswith(prefix)
                    or self.headers.get('Sec-Fetch-Site') in ('cross-site','same-site')
                    or len(self.headers.get_all('Host', [])) != 1):
                response = Response(403,b'UNAUTHORIZED','text/plain; charset=utf-8')
            elif self.command == 'POST' and self.path.split('?',1)[0].endswith('/proposal-preview'):
                self.close_connection = True
                length = self.headers.get('Content-Length','')
                if (origin != 'http://'+expected_host or len(self.headers.get_all('Origin',[])) != 1
                        or self.headers.get('Cookie') is not None
                        or self.headers.get('Authorization') is not None
                        or self.headers.get('Transfer-Encoding') is not None
                        or len(self.headers.get_all('Content-Length',[])) != 1
                        or len(self.headers.get_all('Content-Type',[])) != 1
                        or not length.isascii() or not length.isdigit() or len(length) > 6
                        or int(length) > BODY_LIMIT or self.headers.get('Content-Type') != CONTENT_TYPE):
                    response = Response(403,b'UNAUTHORIZED','text/plain; charset=utf-8')
                else:
                    self.connection.settimeout(3)
                    try:
                        raw = self.rfile.read(int(length))
                        if len(raw) != int(length):
                            raise ValueError('INCOMPLETE_BODY')
                        with service.request(context):
                            result = proposals.post(context,self.path,raw,CONTENT_TYPE,prefix=prefix)
                            response = Response(200,composer(prefix,*result).encode('utf-8'))
                    except ConsoleError as exc:
                        code = str(exc)
                        status = 503 if code=='DB_UNAVAILABLE' else 403 if code == 'UNAUTHORIZED' else 501 if code == 'NOT_IMPLEMENTED' else 409 if code in ('STALE_VERSION','SOURCE_INTEGRITY','NOT_READY') else 400
                        response = Response(status,views.error(prefix,code).encode('utf-8'))
                    except (ValueError, UnicodeError, TypeError, TimeoutError):
                        response = Response(400,b'INVALID_INPUT','text/plain; charset=utf-8')
            else:
                response = interface.dispatch(context,self.command,self.path)
            if pg_read_profile is not None and response.content_type.startswith('text/html'):
                marker='<section class="notice pg-mode"><strong>PG16 TEST_ONLY · 数据库原文字节只读模式</strong><p>合成来源，不代表真实网站许可、身份认证或人工审批。</p></section>'
                response=Response(response.status,response.body.replace(b'<main id="main" tabindex="-1">',
                    b'<main id="main" tabindex="-1">'+marker.encode('utf-8')),response.content_type)
            self.send_response(response.status)
            self.send_header('Content-Type',response.content_type)
            self.send_header('Content-Length',str(len(response.body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            # Chromium suppresses Origin to "null" on POST under no-referrer.
            # Keep exact Origin enforcement; only the local form pages use
            # same-origin (never send any referrer across origins).
            form_page = self.path.split('?',1)[0].endswith(('/proposal','/proposal-preview'))
            self.send_header('Referrer-Policy','same-origin' if form_page and response.status == 200 else 'no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'; connect-src 'none'")
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(response.body)

        do_GET = handle_read
        do_HEAD = handle_read
        do_POST = handle_read
        do_PUT = handle_read
        do_DELETE = handle_read
        do_PATCH = handle_read
        do_OPTIONS = handle_read

        def log_message(self, fmt, *args):
            # Avoid leaking the launch-only fixture path into access logs.
            pass

    server = ThreadingHTTPServer((host,port),Handler)
    print(json.dumps({'mode':'PG16_TEST_ONLY_READ' if pg_read_profile is not None else 'SYNTHETIC_TEST_ONLY',
        'url':f'http://127.0.0.1:{server.server_port}{prefix}'}),flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test-only',action='store_true')
    parser.add_argument('--synthetic-fixtures',action='store_true')
    parser.add_argument('--pg-read-profile',type=str)
    args = parser.parse_args()
    serve(test_only=args.test_only,synthetic_fixtures=args.synthetic_fixtures,pg_read_profile=args.pg_read_profile)

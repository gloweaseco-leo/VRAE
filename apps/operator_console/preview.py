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


def serve(*, test_only=False, synthetic_fixtures=False, host='127.0.0.1', port=0):
    if test_only is not True or synthetic_fixtures is not True or host != '127.0.0.1':
        raise ValueError('TEST_ONLY_LOOPBACK_REQUIRED')
    service, context = make_fixture()
    prefix = '/__fixture__/' + secrets.token_urlsafe(24) + '/'
    interface = ConsoleInterface(service,prefix=prefix)

    class Handler(BaseHTTPRequestHandler):
        def handle_read(self):
            expected_host = f'127.0.0.1:{self.server.server_port}'
            origin = self.headers.get('Origin')
            if (self.headers.get('Host') != expected_host
                    or (origin is not None and origin != 'http://'+expected_host)
                    or not self.path.startswith(prefix)
                    or self.headers.get('Sec-Fetch-Site') in ('cross-site','same-site')):
                response = Response(403,b'UNAUTHORIZED','text/plain; charset=utf-8')
            else:
                response = interface.dispatch(context,self.command,self.path)
            self.send_response(response.status)
            self.send_header('Content-Type',response.content_type)
            self.send_header('Content-Length',str(len(response.body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
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
    print(json.dumps({'mode':'SYNTHETIC_TEST_ONLY','url':f'http://127.0.0.1:{server.server_port}{prefix}'}),flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test-only',action='store_true')
    parser.add_argument('--synthetic-fixtures',action='store_true')
    args = parser.parse_args()
    serve(test_only=args.test_only,synthetic_fixtures=args.synthetic_fixtures)

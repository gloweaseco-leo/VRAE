"""Test-only stdio HTTP relay into the ONE real B5B SSR inside network-none PG.

Receives Reviewer provisioning/public keys and a separate HTTP service bearer.
Optional native runtime receives only the separate C3 Brief namespace credential.
No signer, APP/Worker database credential or admin state. Does not log request
headers/body/cookies. Real host Chrome talks
to a finite loopback transport relay; all auth/mutations execute in original SSR.
"""

import base64
import http.client
import json
import secrets
import sys
import threading
from contextlib import closing

from apps.operator_console.b5a_http import Application as Base, server
from apps.operator_console.b5a_sessions import SessionStore
from apps.operator_console.b5p0_http import RehearsalApplication
from apps.operator_console.b5p0_journal import Journal
from apps.operator_console.b5b_http import Application
from apps.operator_console.b5b_m2_profile import provision
from vrae.b6_p0.reader import PrivateHandoffReader


def main():
    config = json.loads(sys.stdin.readline())
    generated = provision(config['profile'])
    deep = None
    if config.get('deep') is not None:
        from apps.operator_console.l2_profile import provision as provision_deep
        deep = provision_deep(config['deep'])
    anchor = generated.sessions.reader.anchor
    legacy = SessionStore(anchor=anchor, bindings={}, readers={})
    app = Application(RehearsalApplication(Base(legacy, {}), {},
        Journal('/tmp/m2-empty-legacy.sqlite'), key_secret=secrets.token_bytes(32)),
        PrivateHandoffReader(legacy, {}), generated=generated, deep=deep)
    if config.get('native') is not None:
        if deep is not None:
            raise ValueError('L2_NATIVE_CANNOT_MOUNT_AUTHORED_FALLBACK')
        from integration.l2_ops.native_runtime import provision as provision_native
        provision_native(app, config['native'])
    http_server = server(app)
    port = http_server.server_address[1]
    app.origin = config['origin']
    thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    thread.start()
    print(json.dumps({'ready': True}), flush=True)
    try:
        for line in sys.stdin:
            request = json.loads(line)
            if request.get('stop') is True:
                break
            with closing(http.client.HTTPConnection('127.0.0.1', port, timeout=30)) as c:
                c.request(request['method'], request['path'], base64.b64decode(request['body']), request['headers'])
                response = c.getresponse()
                print(json.dumps({'status': response.status, 'body': base64.b64encode(response.read()).decode(),
                    'headers': response.getheaders()}), flush=True)
    finally:
        http_server.shutdown()
        http_server.server_close()
        thread.join(timeout=5)


if __name__ == '__main__':
    main()

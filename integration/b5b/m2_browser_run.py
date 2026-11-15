"""Host Chrome -> loopback stdio relay -> real single SSR/PG16, no mock data."""

import base64
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading
import time

from tests.identity.issuer import Issuer, ISSUER, AUDIENCE
from vrae.application.ra4b_p2.m1.reader import JobAssignment

ROOT = Path(__file__).resolve().parents[2]


def run(out, ident, image):
    out = Path(out)
    folder = out / 'browser'
    folder.mkdir(exist_ok=False)
    proof = json.loads((out / 'm2-restart-proof.json').read_bytes())
    reviewers = json.loads((out / 'private-m2-reviewers.json').read_bytes())
    issuer = Issuer()
    now = int(time.time())
    role = 'p2b1_test_a_reviewer'
    profile = {
        'version': 'M2_SYNTHETIC_REVIEWER_1',
        'anchor': {'issuer': ISSUER, 'audience': AUDIENCE, 'jwks': json.loads(issuer.jwks()), 'expires': now + 1800},
        'assignments': [asdict(JobAssignment(ISSUER, 'synthetic-reviewer-1', role,
            'tenant-test', proof[case]['result']['job_id'], now + 1800)) for case in ('404', '200')],
        'reviewers': {role: {'password': reviewers[role]}},
        'tasks': {case: {'tenant': 'tenant-test', 'job_id': proof[case]['result']['job_id']} for case in ('404', '200')},
    }
    bridge = node = None
    http = thread = None
    lock = threading.Lock()
    observations = []
    try:
        class Relay(BaseHTTPRequestHandler):
            def respond(self):
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 <= size <= 24576:
                        self.send_error(413)
                        return
                    body = self.rfile.read(size)
                    with lock:
                        bridge.stdin.write(json.dumps({'method': self.command, 'path': self.path,
                            'headers': dict(self.headers), 'body': base64.b64encode(body).decode()}) + '\n')
                        bridge.stdin.flush()
                        reply = json.loads(bridge.stdout.readline())
                    raw = base64.b64decode(reply['body'])
                    self.send_response_only(reply['status'])
                    for key, value in reply['headers']:
                        self.send_header(key, value)
                    self.end_headers()
                    self.wfile.write(raw)
                    observations.append({'path': self.path, 'status': reply['status']})
                except Exception:
                    self.close_connection = True

            do_GET = do_POST = do_HEAD = respond

            def log_message(self, *args):
                pass

        http = ThreadingHTTPServer(('127.0.0.1', 0), Relay)
        origin = 'http://127.0.0.1:' + str(http.server_port)
        args = ['docker', 'run', '--rm', '-i', '--name', ident + '-client',
            '--label', 'vrae.b5b.m2=' + ident, '--network', 'container:' + ident + '-pg',
            '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--user', '10003:10003', '--memory', '768m', '--pids-limit', '128',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=128m', '--mount',
            'type=volume,src=' + ident + '-source,dst=/work,readonly', image,
            'python', '-B', '-m', 'integration.b5b.m2_bridge']
        with (folder / 'private-bridge.stderr.log').open('wb') as errors:
            bridge = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=errors, text=True, encoding='utf-8')
            bridge.stdin.write(json.dumps({'profile': profile, 'origin': origin}) + '\n')
            bridge.stdin.flush()
            assert json.loads(bridge.stdout.readline()) == {'ready': True}
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()
            env = dict(os.environ)
            env['B5P0_CHROMIUM'] = os.environ.get('B5B_CHROMIUM',
                'C:/Program Files/Google/Chrome/Application/chrome.exe')
            with (folder / 'private-node.stderr.log').open('wb') as node_errors:
                node = subprocess.Popen(['node', 'integration/b5b/m2_browser.mjs'], cwd=ROOT,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=node_errors,
                    text=True, encoding='utf-8', env=env)
                node.stdin.write(json.dumps({'type': 'init', 'base': origin + '/b5a/m2/',
                    'output': str(folder), 'private': str(folder),
                    'pins': {case: proof[case]['result'] for case in ('404', '200')}}) + '\n')
                node.stdin.flush()
                done = None
                for line in node.stdout:
                    msg = json.loads(line)
                    if msg.get('kind') == 'done':
                        done = msg
                        break
                    if msg.get('kind') != 'sign':
                        raise RuntimeError('M2_UNKNOWN_BROWSER_RPC')
                    current = int(time.time())
                    value = issuer.token({'iat': current, 'nbf': current, 'exp': current + 90, 'nonce': msg['nonce']})
                    node.stdin.write(json.dumps({'id': msg['id'], 'result': value}) + '\n')
                    node.stdin.flush()
                node.wait(timeout=30)
                assert done and done['pass'] and node.returncode == 0, 'M2_REAL_BROWSER_RED'
                return done
    finally:
        if node is not None and node.poll() is None:
            node.terminate()
            node.wait(timeout=15)
        if http:
            if thread is not None:
                http.shutdown()
                thread.join(timeout=5)
            http.server_close()
        if bridge is not None and bridge.poll() is None:
            bridge.stdin.write('{"stop":true}\n')
            bridge.stdin.flush()
            bridge.wait(timeout=30)
        (folder / 'http-observations.json').write_text(json.dumps(observations, indent=2))
        (folder / 'transport-cleanup.json').write_text(json.dumps({
            'node_exited': node is None or node.poll() is not None,
            'bridge_exited': bridge is None or bridge.poll() is not None,
            'http_thread_exited': thread is None or not thread.is_alive(),
            'reviewer_only_ssr_uid': 10003, 'signing_key_outside_ssr': True,
            'pg_network': 'NONE', 'transport': 'LOOPBACK_HTTP_STDIO_REAL_SSR',
        }, indent=2))

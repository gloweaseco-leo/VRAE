"""Host Chrome -> same SSR -> accepted TaskClient/APP -> real independent Worker."""
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
        'task_journal': '/state/tasks.sqlite',
    }
    bridge = backend = node = None
    http = thread = None
    streams = []
    serial = 0
    lock = threading.Lock()
    observations, workers, restarts, secret_values = [], [], [], list(reviewers.values())

    def docker(*args):
        result = subprocess.run(['docker', *args], capture_output=True, timeout=60)
        if result.returncode:
            (folder/'private-control.stderr.log').write_bytes(result.stderr)
            (folder/'private-control.stdout.log').write_bytes(result.stdout)
        assert result.returncode == 0, 'M2_OWNED_CONTROL_FAILED'
        return result

    def spawn(args, label):
        nonlocal serial
        serial += 1
        errors = (folder / ('private-' + label + '-' + str(serial) + '.stderr.log')).open('wb')
        streams.append(errors)
        return subprocess.Popen(args, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=errors, text=True, encoding='utf-8')

    def start_backend():
        nonlocal backend
        args = ['docker', 'run', '--rm', '-i', '--name', ident + '-backend',
            '--label', 'vrae.b5b.m2=' + ident, '--network', 'container:' + ident + '-pg',
            '--read-only', '--cap-drop', 'ALL', '--cap-add', 'SETUID', '--cap-add', 'SETGID',
            '--cap-add', 'CHOWN', '--security-opt', 'no-new-privileges',
            '--memory', '768m', '--pids-limit', '128', '--tmpfs', '/tmp:rw,nosuid,nodev,size=128m',
            '--mount', 'type=volume,src=' + ident + '-source,dst=/work,readonly',
            '--mount', 'type=bind,src=' + str(out/'private-restart-state.json') + ',dst=/run/m1-state.json,readonly',
            image, 'python', '-B', '-m', 'integration.b5b.m2_backend']
        backend = spawn(args, 'backend')
        ready = json.loads(backend.stdout.readline())
        assert ready['ready'] is True
        secret_values.append(ready['api_bearer'])
        scan = folder / 'private-browser-credential-scan-values.json'
        scan.write_text(json.dumps(secret_values))
        scan.chmod(0o600)
        profile['task_endpoint'] = {'bearer': ready['api_bearer'], 'tenant_id':'tenant-test',
                                    'source_refs':['accepted-404', 'accepted-200']}

    def start_bridge():
        nonlocal bridge
        args = ['docker', 'run', '--rm', '-i', '--name', ident + '-client',
            '--label', 'vrae.b5b.m2=' + ident, '--network', 'container:' + ident + '-pg',
            '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--user', '10003:10003', '--memory', '768m', '--pids-limit', '128',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=128m', '--mount',
            'type=volume,src=' + ident + '-source,dst=/work,readonly', '--mount',
            'type=volume,src=' + ident + '-routing,dst=/state',
            image, 'python', '-B', '-m', 'integration.b5b.m2_bridge']
        bridge = spawn(args, 'bridge')
        bridge.stdin.write(json.dumps({'profile': profile, 'origin': origin}) + '\n')
        bridge.stdin.flush()
        assert json.loads(bridge.stdout.readline()) == {'ready':True}

    def stop(p):
        if p is not None and p.poll() is None:
            p.stdin.write('{"stop":true}\n')
            p.stdin.flush()
            p.wait(timeout=30)
        assert p is None or p.poll() is not None

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
                    # Check before forwarding bytes to the real browser; never
                    # inject a private API/DB secret into a browser assertion.
                    wire = raw + json.dumps(reply['headers']).encode()
                    assert not any(value.encode() in wire for value in secret_values), 'M2_SECRET_IN_BROWSER_RESPONSE'
                    self.send_response_only(reply['status'])
                    for key, value in reply['headers']:
                        self.send_header(key, value)
                    self.end_headers()
                    self.wfile.write(raw)
                    observations.append({'path':self.path, 'status':reply['status']})
                except Exception:
                    self.close_connection = True
            do_GET = do_POST = do_HEAD = respond
            def log_message(self, *args):
                pass

        http = ThreadingHTTPServer(('127.0.0.1', 0), Relay)
        origin = 'http://127.0.0.1:' + str(http.server_port)
        docker('run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
               '--cap-add', 'CHOWN', '--mount', 'type=volume,src=' + ident + '-routing,dst=/state',
               image, 'python', '-c', "import os;os.chmod('/state',0o700);os.chown('/state',10003,10003)")
        start_backend()
        start_bridge()
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        env = dict(os.environ)
        env['B5P0_CHROMIUM'] = os.environ.get('B5B_CHROMIUM', 'C:/Program Files/Google/Chrome/Application/chrome.exe')
        errors = (folder/'private-node.stderr.log').open('wb')
        streams.append(errors)
        node = subprocess.Popen(['node','integration/b5b/m2_browser.mjs'], cwd=ROOT,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, text=True, encoding='utf-8', env=env)
        node.stdin.write(json.dumps({'type':'init','base':origin+'/b5a/m2/','output':str(folder),
            'private':str(folder),'bootstrap_pins':{case:proof[case]['result'] for case in ('404','200')}})+'\n')
        node.stdin.flush()
        done = None
        for line in node.stdout:
            msg = json.loads(line)
            if msg.get('kind') == 'done':
                done = msg
                break
            if msg['kind'] == 'sign':
                current = int(time.time())
                value = issuer.token({'iat':current,'nbf':current,'exp':current+90,'nonce':msg['nonce']})
            elif msg['kind'] == 'worker':
                backend.stdin.write('{"worker":true}\n')
                backend.stdin.flush()
                value = json.loads(backend.stdout.readline())
                workers.append(value)
            elif msg['kind'] == 'restart':
                with lock:
                    stop(bridge)
                    stop(backend)
                    docker('restart', ident+'-pg')
                    deadline = time.monotonic()+60
                    while subprocess.run(['docker','exec',ident+'-pg','pg_isready','-q'],capture_output=True).returncode:
                        assert time.monotonic()<deadline
                        time.sleep(.25)
                    issuer = Issuer()
                    profile['anchor']['jwks'] = json.loads(issuer.jwks())
                    start_backend()
                    start_bridge()
                value = {'actual_pg_restart':True,'ssr_process_restarted':True,
                         'app_process_restarted':True,'routing_volume_preserved':True,'new_issuer_key':True}
                restarts.append(value)
            else:
                raise RuntimeError('M2_UNKNOWN_BROWSER_RPC')
            node.stdin.write(json.dumps({'id':msg['id'],'result':value})+'\n')
            node.stdin.flush()
        node.wait(timeout=30)
        assert done and done['pass'] and node.returncode==0, 'M2_REAL_BROWSER_RED'
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
        stop(bridge)
        stop(backend)
        for stream in streams:
            stream.close()
        (folder/'worker-results.json').write_text(json.dumps(workers,indent=2))
        (folder/'actual-restarts.json').write_text(json.dumps(restarts,indent=2))
        (folder/'http-observations.json').write_text(json.dumps(observations,indent=2))
        (folder/'transport-cleanup.json').write_text(json.dumps({
            'node_exited':node is None or node.poll() is not None,
            'bridge_exited':bridge is None or bridge.poll() is not None,
            'backend_exited':backend is None or backend.poll() is not None,
            'http_thread_exited':thread is None or not thread.is_alive(),
            'reviewer_only_ssr_uid':10003,'app_uid':10001,'worker_uid':10002,
            'signing_key_outside_ssr':True,'pg_network':'NONE','transport':'LOOPBACK_HTTP_STDIO_REAL_SSR',
            'credential_free_browser_responses_verified':True,'responses_checked':len(observations),
        },indent=2))

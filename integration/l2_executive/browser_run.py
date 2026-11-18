"""Focused real-browser run with real PG, original signed C2 and detached M1.

Uses the existing C3 component fixture without claiming APP202/Worker E2E.
The independent synthetic receiver runs in another process and holds its key.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import urllib.request

from apps.operator_console.b5a_http import server
from vrae.l2_ops.briefs import BriefService
from vrae.l2_ops.intake import SyntheticIntake, SyntheticReceiver
from integration.l2_ops.runtime_tests.test_pg import native_business_app

ROOT = Path(__file__).resolve().parents[2]


def run(database, native_result, native_source, reviewed, monkeypatch, tmp_path):
    app, path, _, reader, _, pg = native_business_app(
        database, native_result, native_source, reviewed, monkeypatch, tmp_path, seconds=300)
    out = Path(os.environ.get('S4_OUTPUT', str(tmp_path/'browser')))
    out.mkdir(parents=True, exist_ok=False)
    http = server(app)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    signer = browser = None
    service = BriefService(reader)
    with reader.current() as current:
        brief_ref = 'rb-'+current.review['receipt_ref']
    try:
        signer = subprocess.Popen([sys.executable, '-B', '-m', 'integration.l2_executive.receiver'], cwd=ROOT,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, encoding='utf-8')
        public = json.loads(signer.stdout.readline())['public_key']
        app.native_business.intake = SyntheticIntake(SyntheticReceiver(bytes.fromhex(public)))
        # Exercise the original HTTP/PG read independently before CDP so a
        # renderer/navigation failure cannot be mislabelled as a PG failure.
        request = urllib.request.Request(app.origin+path, headers={'Cookie': 'b5a_l2_session='+reviewed[1]})
        with urllib.request.urlopen(request, timeout=10) as response:
            assert response.status == 200 and 'VF 内部接单准备' in response.read().decode()
        with (out/'browser-stderr.txt').open('w', encoding='utf-8') as errors:
            browser = subprocess.Popen(['node', 'integration/l2_executive/browser.mjs'], cwd=ROOT,
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
                                       text=True, encoding='utf-8')
            config = {'origin': app.origin, 'reportId': reviewed[2], 'session': reviewed[1], 'out': str(out)}
            browser.stdin.write(json.dumps(config)+'\n')
            browser.stdin.flush()
            done = None
            for line in browser.stdout:
                message = json.loads(line)
                if message['kind'] == 'done':
                    done = message
                    break
                assert message['kind'] == 'receiver'
                adapter = app.native_business.intake
                row = adapter.current(service, pg, brief_ref)
                receipt = {**{k: row[k] for k in ('scope_sha256', 'brief_sha256', 'attempt', 'nonce')},
                           'state': message['state']}
                signer.stdin.write(json.dumps(receipt)+'\n')
                signer.stdin.flush()
                signature = bytes.fromhex(json.loads(signer.stdout.readline())['signature'])
                result = adapter.receive(service, pg, brief_ref, receipt, signature)
                browser.stdin.write(json.dumps({'state': result['state']})+'\n')
                browser.stdin.flush()
            browser.wait(timeout=15)
            assert browser.returncode == 0 and done is not None, 'S4_REAL_BROWSER_RED; see browser-stderr.txt'
        # The exact PG document is unchanged after every receipt simulation.
        document = service.load_current(pg, brief_ref)
        assert not document['customer_approval'] and not document['external_delivery_allowed']
        files = ['vrae/l2/executive.py', 'apps/operator_console/l2_executive_views.py',
                 'apps/operator_console/l2_http.py', 'apps/operator_console/l2_views.py',
                 'apps/operator_console/l2.css', 'vrae/l2_ops/intake.py', 'vrae/l2_ops/intake_panel.py',
                 'integration/l2_ops/native_business.py', 'integration/l2_executive/browser.mjs',
                 'integration/l2_executive/receiver.py', 'integration/l2_executive/browser_run.py']
        source = {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  'scope': 'C1_C2_REAL_PG_SIGNED_SSR_DETACHED_TASK_NOT_WORKER_E2E',
                  'source_hashes': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},
                  'report_version': native_source[0].read().version,
                  'display_hash': native_source[0].read().display_hash,
                  'brief_sha256': document['content_sha256'], 'receiver_separate_process': True,
                  'result': done}
        (out/'source.json').write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        for process in (browser, signer):
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=15)
        http.shutdown()
        http.server_close()
        thread.join(timeout=5)
        (out/'cleanup.json').write_text(json.dumps({'http_thread_exited': not thread.is_alive(),
            'receiver_exited': signer is None or signer.poll() is not None,
            'browser_controller_exited': browser is None or browser.poll() is not None}), encoding='utf-8')

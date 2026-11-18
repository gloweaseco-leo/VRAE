"""Live loopback acceptance: original signed HTTP, SSR, review ledger and Chrome.

The signer stays in this parent; the HTTP child receives only public JWKS.
All remote-looking fixture URLs use the accepted in-memory saved-source transport.
"""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, build_opener, Request
from urllib.error import HTTPError

from integration.l2.support import Issuer, people
from .fixture import source_binding
from integration.s2_cta.candidate import Receipt, context, sha

ROOT = Path(__file__).resolve().parents[2]
OWN = Path(__file__).resolve().parent


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    label = sys.argv[1]
    if not re.fullmatch('[a-z0-9-]{3,48}', label):
        raise ValueError('OWNED_LABEL_REQUIRED')
    out = OWN/'.runtime'/label
    out.mkdir(parents=True, exist_ok=False)
    binding = source_binding()
    report = binding.source.read()
    after = datetime.now(timezone.utc).isoformat()
    subprocess.run(['node','integration/s2_cta/capture.mjs',str(out/'cta')],cwd=ROOT,check=True,timeout=180)
    before = datetime.now(timezone.utc).isoformat()
    cta_config = {'directory':str(out/'cta'),'expected_sha256':sha((out/'cta/receipt.json').read_bytes()),
                  'held_context':context(binding,report),'observed_after':after,'observed_before':before}
    binding.cta = Receipt(**cta_config)
    cta = binding.cta.read(binding,report)
    rid = report.version['report_id']
    issuer = Issuer()
    config = {'directory': {'issuer': issuer.issuer, 'audience': issuer.audience, 'jwks': issuer.jwks,
                           'people': [asdict(replace(person, report_ids=(rid,))) for person in people()],
                           'expires': int(time.time())+3600, 'mode': 'CONTROLLED'}, 'cta':cta_config}
    profile, ready = out/'public-profile.json', out/'ready.json'
    profile.write_text(json.dumps(config), encoding='utf-8')
    server_process = browser = None
    streams = []
    started = time.monotonic()
    files = ['workbench.py','buyer_cards.py','fixture.py','server.py','lab.py','browser.mjs','test_workbench.py','test_buyer_cards.py']
    source_hashes = {name:hashlib.sha256((OWN/name).read_bytes()).hexdigest() for name in files}
    cta_hashes = {name:hashlib.sha256((ROOT/'integration/s2_cta'/name).read_bytes()).hexdigest()
                  for name in ('capture.mjs','candidate.py','views.py','test_candidate.py')}
    try:
        errors = (out/'private-server.stderr').open('wb')
        streams.append(errors)
        server_process = subprocess.Popen([sys.executable, '-B', '-m', 'integration.s2_buyer_workbench.server',
                                           str(profile), str(ready)], cwd=ROOT, stdout=subprocess.PIPE, stderr=errors)
        while not ready.exists():
            if server_process.poll() is not None or time.monotonic()-started > 120:
                raise RuntimeError('CONTROLLED_SERVER_START_FAILED')
            time.sleep(0.1)
        actual = json.loads(ready.read_text())
        assert actual['reportId'] == rid and actual['displayHash'] == report.display_hash
        assert actual['buyerCandidateRef'] == binding.expected_buyer_ref
        assert actual['ctaAvailable'] is True

        def login(subject):
            if subject not in {person.subject for person in people()}:
                raise ValueError('CONTROLLED_SUBJECT_REQUIRED')
            jar = CookieJar()
            opener = build_opener(HTTPCookieProcessor(jar), NoRedirect())
            origin = actual['origin']
            entry = origin+'/b5a/l2/'
            html = opener.open(entry, timeout=30).read().decode()
            csrf = re.search(r'name="_csrf" value="([A-Za-z0-9_-]+)"', html)[1]
            req = Request(entry+'challenge', data=urlencode({'_csrf': csrf}).encode(),
                          headers={'Origin': origin, 'Content-Type':'application/x-www-form-urlencoded'})
            challenge = json.loads(opener.open(req, timeout=30).read())
            req = Request(entry+'session', data=b'{}', headers={'Origin': origin, 'Content-Type':'application/json',
                          'Authorization':issuer.token(subject, challenge['nonce']),
                          'X-L2-Nonce':challenge['nonce'], 'X-L2-CSRF':challenge['csrf']})
            try:
                opener.open(req, timeout=30).close()
                raise RuntimeError('ORIGINAL_SESSION_REDIRECT_REQUIRED')
            except HTTPError as response:
                if response.code != 303:
                    raise
                response.close()
            cookie = next(cookie for cookie in jar if cookie.name == 'b5a_l2_session')
            if not cookie.has_nonstandard_attr('HttpOnly'):
                raise RuntimeError('ORIGINAL_HTTPONLY_COOKIE_REQUIRED')
            return cookie.value

        errors = (out/'private-browser.stderr').open('wb')
        streams.append(errors)
        browser = subprocess.Popen(['node', 'integration/s2_buyer_workbench/browser.mjs'], cwd=ROOT,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
                                   text=True, encoding='utf-8', env=dict(os.environ))
        browser.stdin.write(json.dumps({**actual, 'out':str(out)})+'\n')
        browser.stdin.flush()
        done = None
        for line in browser.stdout:
            message = json.loads(line)
            if message['kind'] == 'done':
                done = message
                break
            if message['kind'] != 'login':
                raise ValueError('CONTROLLED_BROWSER_COMMAND_REQUIRED')
            browser.stdin.write(json.dumps({'session': login(message['subject'])})+'\n')
            browser.stdin.flush()
        code = browser.wait(timeout=15)
        if code != 0 or done is None:
            raise RuntimeError('CONTROLLED_BROWSER_RED')
        if source_hashes != {name:hashlib.sha256((OWN/name).read_bytes()).hexdigest() for name in files}:
            raise RuntimeError('SOURCE_CHANGED_DURING_LIVE_RUN')
        if cta_hashes != {name:hashlib.sha256((ROOT/'integration/s2_cta'/name).read_bytes()).hexdigest() for name in cta_hashes}:
            raise RuntimeError('CTA_SOURCE_CHANGED_DURING_LIVE_RUN')
        receipt = {'acceptedMain':'6a15ab4514d24c60b4d03d4ec795f6e3bcd435c3',
                   'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
                   'composition':'Original B5B Application / DeepConsole / Directory / Ledger',
                   'signerOutsideHttpChild':True,'sourceAccessMode':'OFFLINE_SYNTHETIC',
                   'reportId':rid,'displayHash':report.display_hash,'packRef':binding.pack.ref,
                   'projectionRef':binding.expected_ref,'projectionVersion':json.loads(binding.payload)['projection_version'],
                   'buyerCandidateRef':binding.expected_buyer_ref,'buyerCandidateAuthority':'READ_ONLY_REVIEW_CANDIDATE',
                   'buyerCandidatePins':asdict(binding.buyer_pins),
                   'reportVersionId':report.version['report_version_id'],
                   'reportContentHash':report.version['content_hash'],
                   'sourceHashes':source_hashes,
                   'ctaSourceHashes':cta_hashes,'ctaReceiptSha256':cta_config['expected_sha256'],
                   'ctaContext':cta_config['held_context'],'ctaRecords':len(cta['records']),
                   'browser':done,'formalHumanReview':False,'externalDelivery':False}
        (out/'source.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps({'result':'PASS','checks':done['checks'],'screenshots':done['shots'],'out':str(out)}))
    finally:
        for process in (browser, server_process):
            if process is not None and process.poll() is None:
                if process is browser:
                    try:
                        browser.stdin.write('{"error":"PARENT_CLOSING"}\n')
                        browser.stdin.close()
                        browser.wait(timeout=10)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
                if process.poll() is not None:
                    continue
                process.terminate()
                process.wait(timeout=15)
        for stream in streams:
            stream.close()
        (out/'process-cleanup.json').write_text(json.dumps({
            'serverExitObserved':server_process is not None and server_process.poll() is not None,
            'browserNodeExitObserved':browser is not None and browser.poll() is not None})+'\n')


if __name__ == '__main__':
    main()

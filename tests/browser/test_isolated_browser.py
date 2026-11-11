"""Actual sandboxed Chromium in a separate no-network container, driven over IPC."""
import asyncio
import json
import os

import pytest
import dns.rdatatype

from vrae.browser.broker import ResourceBroker
from vrae.browser.cdp import CDP
from vrae.browser.controller import BrowserController
from vrae.collection.errors import CollectionError
from vrae.collection.limits import Budget, Limits
from vrae.collection.policy import SourceAccess
from tests.collection.test_isolated import lab, fetcher
from tests.collection.test_security import fixture, NOW

pytestmark = pytest.mark.skipif(os.environ.get('VRAE_BROWSER_LAB') != '1',
                              reason='Requires separate sandboxed Chromium and Worker containers')

ATTACKS = {
    'readonly': "console.log('TRIGGER:readonly'); document.body.innerHTML += '<h1>Rendered</h1>';",
    'writes': """console.log('TRIGGER:writes');
      console.log('ATTEMPT:fetch-post');fetch('/mutate',{method:'POST',body:'x'}).catch(()=>{});
      console.log('ATTEMPT:xhr-put');let x=new XMLHttpRequest();x.open('PUT','/mutate');x.send('x');
      console.log('ATTEMPT:beacon');navigator.sendBeacon('/mutate','x');
      let f=document.createElement('form');f.method='POST';f.action='/mutate';
      document.body.append(f);console.log('ATTEMPT:form');f.submit();""",
    'private': """console.log('TRIGGER:private');
      for(let h of ['127.0.0.1','169.254.169.254','10.77.0.2','[::1]'])
        fetch('http://'+h+'/bait').catch(()=>{});""",
    'resources': """console.log('TRIGGER:resources');
      for(let [tag,attr,url] of [['img','src','https://evil.test/img'],
        ['iframe','src','https://evil.test/frame'],['script','src','https://evil.test/code']]){
        let e=document.createElement(tag);e[attr]=url;document.body.append(e)}
      let s=document.createElement('style');s.textContent='@import url(https://evil.test/style); @font-face{font-family:x;src:url(https://evil.test/font)}body{font-family:x}';document.head.append(s);""",
    'channels': """console.log('TRIGGER:channels');
      console.log('ATTEMPT:websocket');try{new WebSocket('wss://factory.test/socket')}catch(e){}
      console.log('ATTEMPT:service-worker');navigator.serviceWorker.register('/sw.js').catch(()=>{});
      console.log('ATTEMPT:webrtc');try{let p=new RTCPeerConnection({iceServers:[{urls:'stun:169.254.169.254:3478'}]});
        p.createDataChannel('x');p.createOffer().then(o=>p.setLocalDescription(o));}catch(e){}""",
    'escape': """console.log('TRIGGER:escape');window.open('https://evil.test/popup');
      let a=document.createElement('a');a.href='/download';a.download='evil.txt';document.body.append(a);a.click();
      let f=document.createElement('iframe');f.src='file:///etc/passwd';document.body.append(f);""",
    'storage': """console.log('TRIGGER:storage');console.log('STATE:'+document.cookie+':'+localStorage.getItem('secret'));
      document.cookie='secret=synthetic';localStorage.setItem('secret','synthetic');
      indexedDB.databases().then(d=>{console.log('IDB:'+d.length);indexedDB.open('synthetic')});""",
    'redirect': "console.log('TRIGGER:redirect');fetch('/redirect').catch(()=>{});",
    'redirect_private': "console.log('TRIGGER:redirect_private');fetch('/redirect').catch(()=>{});",
    'rebinding': "console.log('TRIGGER:rebinding');fetch('/rebind').catch(()=>{});",
    'infinite': "console.log('TRIGGER:infinite');while(true){}",
    'memory': "console.log('TRIGGER:memory');let blocks=[];for(;;)blocks.push(new Uint8Array(16*1024*1024).fill(7));",
    'revocation': "console.log('TRIGGER:revocation');setInterval(()=>fetch('/ping').catch(()=>{}),20);",
    'sigkill': "console.log('TRIGGER:sigkill');while(true){}",
    'worker_kill': "console.log('TRIGGER:worker_kill');while(true){}",
    'crash': "console.log('TRIGGER:crash');while(true){}",
}


def test_real_chromium_synthetic_case():
    scenario = os.environ['VRAE_BROWSER_CASE']
    assert scenario in ATTACKS
    async def run():
        mutations = []
        source = ('<html><head><link rel="icon" href="/icon"></head><body><h1>Synthetic</h1><script>'
                  + ATTACKS[scenario] + '</script></body></html>').encode()
        async def handler(target, writer):
            # The bait has an actual in-memory mutation path. The browser must
            # never reach it with a write method; do not merely report a constant 0.
            method = requests[-1].split(b' ', 1)[0]
            if method not in (b'GET', b'HEAD'):
                mutations.append((method.decode('ascii'), target.decode('ascii')))
            if target == b'/robots.txt':
                body, mime = b'User-agent: *\nDisallow:\n', b'text/plain'
            elif target == b'/redirect':
                location = b'http://169.254.169.254/bait' if scenario == 'redirect_private' else b'https://evil.test/bait'
                writer.write(b'HTTP/1.1 302 Found\r\nLocation: '+location+b'\r\nContent-Length: 0\r\n\r\n')
                await writer.drain()
                return
            elif target == b'/icon':
                body, mime = b'not-an-image', b'image/png'
            elif target == b'/ping':
                body, mime = b'ok', b'text/plain'
            else:
                body, mime = source, b'text/html'
            writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: '+mime+b'\r\nContent-Length: '+
                         str(len(body)).encode()+b'\r\n\r\n'+body)
            await writer.drain()
        def answer(kind, count):
            if kind != dns.rdatatype.A:
                return []
            return ['127.0.0.1'] if scenario == 'rebinding' and count >= 5 else ['93.184.216.20']
        async with lab(handler=handler, answer=answer) as (requests, sni, bait, dns_server):
            cdp = await CDP.connect()
            request, policy = fixture('AuditRequest'), fixture('SourcePolicy')
            request['site_url'] = 'https://factory.test/'
            policy['permitted_hosts'] = ['factory.test']
            a = SourceAccess(request, lambda: policy, terms_reference='synthetic-terms', now=lambda: NOW)
            budget = Budget(Limits(interval_seconds=0.01, task_seconds=18), a)
            broker = ResourceBroker(fetcher(), budget, ['https://factory.test/'])
            controller = BrowserController(cdp, broker)
            action_started = asyncio.Event()
            async def cancel_after_trigger():
                while budget.clock() < budget.deadline:
                    if any('TRIGGER:' + scenario in str(e) for e in controller.events):
                        action_started.set()
                        if scenario == 'revocation':
                            policy['revoked_at'] = NOW.isoformat()
                        elif scenario in ('sigkill', 'worker_kill'):
                            print('PRE_KILL_COUNTERS ' + json.dumps({'bait': len(bait), 'writes': len(mutations)}), flush=True)
                            print('KILL_READY', flush=True)
                        elif scenario == 'crash':
                            try:
                                await cdp.call('Browser.crash')
                            except CollectionError:
                                pass
                        return
                    await asyncio.sleep(0.02)
            cancellation = (asyncio.create_task(cancel_after_trigger())
                            if scenario in ('revocation', 'sigkill', 'worker_kill', 'crash') else None)
            try:
                if scenario == 'revocation':
                    # Deliberately slow startup: a test monitor must not silently
                    # expire before untrusted code has actually run.
                    await asyncio.sleep(5)
                bundle = await controller.capture('run-browser-synthetic')
                bundle.verify()
                print('OBSERVATION ' + json.dumps(bundle.manifest), flush=True)
                assert len(bundle.manifest['observations']) == 2
                if scenario == 'readonly':
                    assert all(o['dom_ref'] and o['screenshot_ref'] for o in bundle.manifest['observations'])
            except CollectionError as exc:
                print('BROWSER_TERMINATION ' + exc.code, flush=True)
                assert scenario in ('infinite', 'memory', 'revocation', 'sigkill', 'worker_kill', 'crash')
                if scenario == 'revocation':
                    assert exc.code == 'POLICY_REVOKED'
            finally:
                if cancellation:
                    cancellation.cancel()
                    await asyncio.gather(cancellation, return_exceptions=True)
            assert any('TRIGGER:' + scenario in str(e) for e in controller.events), controller.events
            if scenario in ('revocation', 'sigkill', 'worker_kill', 'crash'):
                assert action_started.is_set(), 'Termination action never triggered; cannot claim containment PASS'
            if scenario == 'revocation':
                assert policy['revoked_at'] == NOW.isoformat()
            for marker in ({'writes': ['fetch-post', 'xhr-put', 'beacon', 'form'],
                            'channels': ['websocket', 'service-worker', 'webrtc']}.get(scenario, [])):
                assert any('ATTEMPT:' + marker in str(e) for e in controller.events), marker
            if scenario == 'storage':
                states = [str(e) for e in controller.events if 'STATE:' in str(e)]
                assert len(states) == 2 and all('STATE::null' in s for s in states), states
                databases = [str(e) for e in controller.events if 'IDB:' in str(e)]
                assert len(databases) == 2 and all('IDB:0' in s for s in databases), databases
            assert not bait
            assert not mutations
            assert all(r.startswith(b'GET ') or r.startswith(b'HEAD ') for r in requests)
            assert not any(b'/mutate' in r.split(b'\r\n',1)[0] for r in requests)
            if scenario == 'rebinding':
                assert any(r['error'] == 'SSRF_BLOCKED' for r in broker.trace)
            print('ATTACK_EVIDENCE ' + json.dumps({'scenario': scenario, 'triggered': controller.events,
                'broker': broker.trace, 'unauthorized_connections': len(bait), 'writes': len(mutations)}), flush=True)
    asyncio.run(run())

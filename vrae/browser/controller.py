"""Trusted controller. All page resource bytes come from ResourceBroker."""
import asyncio
import base64
import json

from vrae.collection.errors import CollectionError
from vrae.collection.manifest import sha256
from .observation import VIEWPORTS, seal

DOM_SCRIPT = """(() => ({title:document.title.slice(0,256), url:location.href,
  elements:Array.from(document.querySelectorAll('h1,h2,a,button,input,img')).slice(0,128).map(e=>{
    const r=e.getBoundingClientRect();return {tag:e.tagName,visible:r.width>0&&r.height>0,
    text:(e.textContent||'').slice(0,160)}})}))()"""


class BrowserController:
    def __init__(self, cdp, broker):
        self.cdp, self.broker = cdp, broker
        self.events: list[dict] = []

    async def sandbox(self):
        target = (await self.cdp.call('Target.createTarget', {'url': 'chrome://sandbox'}))['targetId']
        session = (await self.cdp.call('Target.attachToTarget', {'targetId': target, 'flatten': True}))['sessionId']
        for _ in range(30):
            result = await self.cdp.call('Runtime.evaluate', {'expression': 'document.body.innerText',
                'returnByValue': True}, session)
            value = result.get('result', {}).get('value', '')
            if 'Seccomp-BPF sandbox' in value:
                break
            await asyncio.sleep(0.05)
        for label, expected in (('Layer 1 Sandbox', 'Namespace'), ('PID namespaces', 'Yes'),
                                ('Network namespaces', 'Yes'), ('Seccomp-BPF sandbox', 'Yes')):
            if label + '\t' + expected not in value:
                raise CollectionError('EVIDENCE_INSUFFICIENT')
        await self.cdp.call('Target.closeTarget', {'targetId': target})
        return value

    async def capture(self, run_id):
        if not isinstance(run_id, str) or not run_id or len(run_id) > 128:
            raise CollectionError('INPUT_INVALID')
        self.broker.budget.run_id = run_id
        async def execute():
            await self.sandbox()
            version = await self.cdp.call('Browser.getVersion')
            await self.cdp.call('Browser.setDownloadBehavior', {'behavior': 'deny'})
            observations, objects = [], {}
            for url in self.broker.urls:
                for viewport in VIEWPORTS:
                    item, saved = await self.observe(url, viewport)
                    observations.append(item)
                    objects.update(saved)
            return seal(self.broker, run_id, version['product'], observations, objects)
        try:
            return await self.broker.budget.run(execute())
        finally:
            await self.cdp.close()

    async def observe(self, url, viewport):
        self.broker.budget.check()
        context = (await self.cdp.call('Target.createBrowserContext', {'disposeOnDetach': True}))['browserContextId']
        target = (await self.cdp.call('Target.createTarget', {'url': 'about:blank', 'browserContextId': context}))['targetId']
        session = (await self.cdp.call('Target.attachToTarget', {'targetId': target, 'flatten': True}))['sessionId']
        errors: list[str] = []
        tasks: set[asyncio.Task] = set()
        loaded = asyncio.Event()
        start = len(self.broker.trace)
        objects = {}
        item = {'url': url, 'viewport': dict(viewport), 'observed_at': self.broker.budget.access.now().isoformat(),
                'status': 'UNKNOWN', 'dom_ref': None, 'screenshot_ref': None, 'errors': errors, 'resources': []}

        def completed(task):
            tasks.discard(task)
            if not task.cancelled() and task.exception() is not None:
                errors.append('RESOURCE_HANDLER_FAILED')

        async def resource(event):
            params = event['params']
            request = params['request']
            try:
                if event.get('sessionId') != session or params.get('resourceType') == 'Document' and request['url'] != url:
                    raise CollectionError('SOURCE_NOT_ALLOWED')
                result = await self.broker.read(request['url'], request['method'], params['resourceType'])
                await self.cdp.call('Fetch.fulfillRequest', {'requestId': params['requestId'],
                    'responseCode': result['status'], 'responseHeaders': [
                        {'name': k, 'value': v} for k,v in result['headers'].items()],
                    'body': base64.b64encode(result['body']).decode()}, session)
            except CollectionError as exc:
                errors.append(exc.code)
                await self.cdp.call('Fetch.failRequest', {'requestId': params['requestId'],
                                                        'errorReason': 'BlockedByClient'}, session)

        async def events():
            while True:
                event = await self.cdp.events.get()
                method, params = event.get('method'), event.get('params', {})
                if (method == 'Target.attachedToTarget' and event.get('sessionId') == session
                        and params['targetInfo']['targetId'] != target):
                    errors.append('TARGET_BLOCKED')
                    await self.cdp.call('Target.closeTarget', {'targetId': params['targetInfo']['targetId']})
                elif event.get('sessionId') != session:
                    continue
                elif method == 'Fetch.requestPaused':
                    if len(tasks) >= 16:
                        raise CollectionError('LIMIT_EXCEEDED')
                    task = asyncio.create_task(resource(event))
                    tasks.add(task)
                    task.add_done_callback(completed)
                elif method == 'Page.domContentEventFired':
                    loaded.set()
                elif method in ('Network.loadingFailed', 'Network.webSocketCreated', 'Inspector.targetCrashed'):
                    errors.append(method)
                elif method == 'Page.frameNavigated' and params['frame'].get('url') not in (url, 'about:blank'):
                    errors.append('NAVIGATION_BLOCKED')
                    await self.cdp.call('Page.stopLoading', session=session)
                elif method == 'Runtime.consoleAPICalled' and len(self.events) < 128:
                    self.events.append({'method': method, 'values': [str(a.get('value', ''))[:256]
                                                                  for a in params.get('args', [])[:4]]})
                if len(errors) > 128:
                    raise CollectionError('LIMIT_EXCEEDED')

        pump = None
        try:
            for method in ('Page.enable', 'Runtime.enable', 'Network.enable'):
                await self.cdp.call(method, session=session)
            await self.cdp.call('Network.setBypassServiceWorker', {'bypass': True}, session)
            await self.cdp.call('Network.setCacheDisabled', {'cacheDisabled': True}, session)
            await self.cdp.call('Target.setAutoAttach', {'autoAttach': True, 'waitForDebuggerOnStart': True,
                                                       'flatten': True}, session)
            await self.cdp.call('Emulation.setDeviceMetricsOverride', {
                'width': viewport['width'], 'height': viewport['height'],
                'deviceScaleFactor': 1, 'mobile': viewport['mobile']}, session)
            await self.cdp.call('Fetch.enable', {'patterns': [{'urlPattern': '*', 'requestStage': 'Request'}]}, session)
            pump = asyncio.create_task(events())
            await self.cdp.call('Page.navigate', {'url': url}, session)
            await asyncio.wait_for(loaded.wait(), 8)
            await asyncio.sleep(0.4)
            if pump.done():
                await pump
            if tasks:
                await asyncio.wait_for(asyncio.gather(*list(tasks)), 8)
            result = await self.cdp.call('Runtime.evaluate', {'expression': DOM_SCRIPT,
                'returnByValue': True, 'timeout': 1000}, session)
            dom = result.get('result', {}).get('value')
            if not isinstance(dom, dict) or dom.get('url') != url:
                raise CollectionError('EVIDENCE_INSUFFICIENT')
            data = json.dumps(dom, ensure_ascii=False).encode()
            if len(data) > 65536:
                raise CollectionError('LIMIT_EXCEEDED')
            screen = await self.cdp.call('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False}, session)
            png = base64.b64decode(screen['data'], validate=True)
            if len(png) > 2_000_000 or not png.startswith(b'\x89PNG\r\n\x1a\n'):
                raise CollectionError('LIMIT_EXCEEDED')
            self.broker.budget.check()
            for field, body in (('dom_ref', data), ('screenshot_ref', png)):
                item[field] = sha256(body)
                objects[item[field]] = body
            item['status'] = 'OBSERVED' if not errors else 'ACCESS_BLOCKED'
        except (CollectionError, TimeoutError) as exc:
            errors.append(exc.code if isinstance(exc, CollectionError) else 'TIMEOUT')
        finally:
            if pump:
                pump.cancel()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*list(tasks), *([pump] if pump else []), return_exceptions=True)
            await self.cdp.call('Target.disposeBrowserContext', {'browserContextId': context})
        item['resources'] = self.broker.trace[start:]
        return item, objects

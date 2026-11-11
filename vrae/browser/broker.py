"""Trusted read-only resource policy. Browser-reported URLs are never trusted."""
import asyncio
from urllib.parse import urlsplit

from vrae.collection.errors import CollectionError
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Budget
from vrae.collection.manifest import sha256
from vrae.collection.robots import RobotsRules

MIMES = {
    'Document': {'text/html', 'application/xhtml+xml'},
    'Script': {'text/javascript', 'application/javascript', 'application/x-javascript'},
    'Stylesheet': {'text/css'},
    'Image': {'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/svg+xml'},
    'Font': {'font/woff', 'font/woff2', 'application/font-woff'},
    'Fetch': {'application/json', 'text/plain'},
    'XHR': {'application/json', 'text/plain'},
}
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self'; font-src 'self'; connect-src 'self'; frame-src 'none'; worker-src 'none'; "
       "object-src 'none'; form-action 'none'; base-uri 'none'; "
       "sandbox allow-scripts allow-same-origin")


class ResourceBroker:
    def __init__(self, fetcher: SafeFetcher, budget: Budget, approved_urls: list[str]):
        self.fetcher, self.budget = fetcher, budget
        if budget.access.audit['audit_mode'] != 'L1' or not 1 <= len(approved_urls) <= 3:
            raise CollectionError('SOURCE_NOT_ALLOWED')
        self.urls = tuple(budget.access.check(u) for u in approved_urls)
        if len(set(self.urls)) != len(self.urls):
            raise CollectionError('INPUT_INVALID')
        self.trace: list[dict] = []
        self.rules: RobotsRules | None = None
        self.lock = asyncio.Lock()

    async def read(self, url: str, method: str, kind: str) -> dict:
        async with self.lock:
            self.budget.check()
            if len(self.trace) >= 128:
                raise CollectionError('LIMIT_EXCEEDED')
            record: dict = {'url': url[:2048], 'method': method[:16], 'resource_type': kind[:32],
                      'outcome': 'UNKNOWN', 'error': None, 'redirect_trace': [], 'sha256': None}
            self.trace.append(record)
            try:
                if method not in ('GET', 'HEAD'):
                    raise CollectionError('METHOD_NOT_ALLOWED')
                if kind not in MIMES or kind == 'Document' and url not in self.urls:
                    raise CollectionError('SOURCE_NOT_ALLOWED')
                url = self.budget.access.check(url)
                if self.rules is None:
                    parts = urlsplit(self.urls[0])
                    robots_url = f'{parts.scheme}://{parts.netloc}/robots.txt'
                    response, _ = await self.fetcher.fetch(robots_url, 'GET', self.budget, max_bytes=65536)
                    if response.url != robots_url:
                        raise CollectionError('REDIRECT_BLOCKED')
                    self.rules = RobotsRules(response)
                    self.budget.interval = max(self.budget.interval, self.rules.delay)
                    self.budget.next_request = max(self.budget.next_request,
                                                   self.budget.clock() + self.rules.delay)

                def allowed(target):
                    if urlsplit(target).scheme != urlsplit(self.urls[0]).scheme:
                        raise CollectionError('REDIRECT_BLOCKED')
                    assert self.rules is not None
                    self.rules.check(target)

                response, trace = await self.fetcher.fetch(url, method, self.budget, allow_url=allowed)
                record['redirect_trace'] = trace
                if response.status in (401, 403, 429, 503):
                    raise CollectionError('ACCESS_BLOCKED')
                if response.status != 200:
                    raise CollectionError('HTTP_ERROR')
                if kind == 'Document' and response.url != url:
                    # Do not render final bytes under an inaccurate original document URL.
                    raise CollectionError('REDIRECT_BLOCKED')
                mime = response.headers.get('content-type', '').split(';')[0].strip().lower()
                if mime not in MIMES[kind]:
                    raise CollectionError('CONTENT_TYPE_INVALID')
                self.budget.check()
                record.update(outcome='FETCHED', sha256=sha256(response.body))
                headers = {'content-type': mime, 'cache-control': 'no-store',
                           'x-content-type-options': 'nosniff', 'content-security-policy': CSP}
                return {'body': response.body, 'status': 200, 'headers': headers}
            except CollectionError as exc:
                record.update(outcome='ACCESS_BLOCKED', error=exc.code)
                raise

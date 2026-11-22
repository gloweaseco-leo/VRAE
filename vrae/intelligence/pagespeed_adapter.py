"""P2 adapter skeleton. Disabled. It does not read secrets or send requests.

Owner has not approved a PageSpeed or other third-party performance call.
Customer URLs must not be handed to this adapter.
"""
ENABLED = False


class PageSpeedAdapter:
    def __init__(self):
        self.enabled = ENABLED

    def measure(self, url):
        raise RuntimeError('PAGESPEED_NOT_APPROVED')

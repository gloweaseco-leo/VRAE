"""No implicit redirect following; each Location passes the full policy again."""
from urllib.parse import urljoin, urlsplit
from .errors import CollectionError
from .policy import SourceAccess

REDIRECT_STATUSES = {301, 302, 303, 307, 308}


def redirect_target(current: str, location: str, access: SourceAccess) -> str:
    if (not location or len(location) > 2048
            or any(ord(c) <= 32 or ord(c) >= 127 for c in location)
            or "\\" in location or "%" in location
            or any(p in (".", "..") for p in urlsplit(location).path.split("/"))):
        raise CollectionError("REDIRECT_BLOCKED")
    candidate = urljoin(current, location)
    if (urlsplit(current).scheme == "https" and urlsplit(candidate).scheme != "https"
            or urlsplit(current).hostname != urlsplit(candidate).hostname):
        raise CollectionError("REDIRECT_BLOCKED")
    return access.check(candidate)

"""Pinned sockets + verified TLS + h11 framing. No proxy, cookies, redirects or retries."""
import asyncio
from dataclasses import dataclass
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit

import h11

from .errors import CollectionError
from .limits import Budget
from .resolver import public_addresses


@dataclass(frozen=True)
class FetchResponse:
    url: str
    status: int
    headers: dict[str, str]
    body: bytes
    peer_ip: str

    def document(self) -> dict:
        from .manifest import sha256
        return {"schema_version": "1.0", "url": self.url, "status": self.status,
                "peer_ip": self.peer_ip, "body_sha256": sha256(self.body),
                "body_bytes": len(self.body), "content_type": self.headers.get("content-type")}


class PinnedTransport:
    def __init__(self, *, cafile: str | None = None):
        # cafile is trusted deployment configuration, never a fetch-request parameter.
        self.tls = ssl.create_default_context(cafile=cafile)
        self.tls.minimum_version = ssl.TLSVersion.TLSv1_2

    async def exchange(self, url: str, method: str, ip: str, budget: Budget,
                       max_bytes: int) -> FetchResponse:
        if method not in ("GET", "HEAD"):
            raise CollectionError("METHOD_NOT_ALLOWED")
        url = budget.access.check(url)
        public_addresses([ip])
        parts = urlsplit(url)
        host = str(parts.hostname)
        port = 443 if parts.scheme == "https" else 80
        if not self.tls.check_hostname or self.tls.verify_mode != ssl.CERT_REQUIRED:
            raise CollectionError("TLS_FAILED")
        family = socket.AF_INET6 if ipaddress.ip_address(ip).version == 6 else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.setblocking(False)
        writer = None
        try:
            async with asyncio.timeout(budget.limits.request_seconds):
                await asyncio.get_running_loop().sock_connect(sock, (ip, port))
                if ipaddress.ip_address(sock.getpeername()[0]) != ipaddress.ip_address(ip):
                    raise CollectionError("SSRF_BLOCKED")
                if parts.scheme == "https":
                    reader, writer = await asyncio.open_connection(
                        sock=sock, ssl=self.tls, server_hostname=host,
                        ssl_handshake_timeout=budget.limits.request_seconds,
                        ssl_shutdown_timeout=0.1, limit=16_384)
                else:
                    reader, writer = await asyncio.open_connection(sock=sock, limit=16_384)
                peer = writer.get_extra_info("peername")[0]
                if ipaddress.ip_address(peer) != ipaddress.ip_address(ip):
                    raise CollectionError("SSRF_BLOCKED")
                # Recheck immediately before writing, after DNS/connect/TLS may have waited.
                budget.check()
                budget.access.check(url)
                connection = h11.Connection(h11.CLIENT, max_incomplete_event_size=16_384)
                request = h11.Request(method=method, target=parts.path or "/", headers=[
                    ("Host", host), ("User-Agent", "VRAE-Audit/1.0"),
                    ("Accept", "text/html,text/plain"), ("Accept-Encoding", "identity"),
                    ("Connection", "close"),
                ])
                writer.write(connection.send(request) or b"")
                writer.write(connection.send(h11.EndOfMessage()) or b"")
                await writer.drain()
                status = 0
                headers: dict[str, str] = {}
                body = bytearray()
                wire_bytes = 0
                informational = 0
                while True:
                    budget.check()
                    event = connection.next_event()
                    if event is h11.NEED_DATA:
                        block = await reader.read(8192)
                        wire_bytes += len(block)
                        # Bound framing overhead as well as decoded chunk payload.
                        if wire_bytes > max_bytes + 65_536:
                            raise CollectionError("LIMIT_EXCEEDED")
                        connection.receive_data(block)
                    elif isinstance(event, h11.InformationalResponse):
                        informational += 1
                        if event.status_code == 101 or informational > 4:
                            raise CollectionError("HTTP_PROTOCOL_ERROR")
                    elif isinstance(event, h11.Response):
                        status = event.status_code
                        if not 200 <= status <= 599:
                            raise CollectionError("HTTP_PROTOCOL_ERROR")
                        if sum(len(k) + len(v) for k, v in event.headers) > 16_384:
                            raise CollectionError("LIMIT_EXCEEDED")
                        for key, value in event.headers:
                            name, text = key.decode("ascii").lower(), value.decode("latin1")
                            if name in {"location", "content-type", "content-length", "content-encoding"}:
                                if name in headers:
                                    raise CollectionError("HTTP_PROTOCOL_ERROR")
                                headers[name] = text
                        if headers.get("content-encoding", "identity").lower() != "identity":
                            raise CollectionError("CONTENT_ENCODING_INVALID")
                        if int(headers.get("content-length", "0")) > max_bytes:
                            raise CollectionError("LIMIT_EXCEEDED")
                    elif isinstance(event, h11.Data):
                        budget.consume(len(event.data))
                        if len(body) + len(event.data) > max_bytes:
                            raise CollectionError("LIMIT_EXCEEDED")
                        body.extend(event.data)
                    elif isinstance(event, h11.EndOfMessage):
                        if not status:
                            raise CollectionError("HTTP_PROTOCOL_ERROR")
                        return FetchResponse(url, status, headers, bytes(body), str(peer))
                    else:
                        raise CollectionError("HTTP_PROTOCOL_ERROR")
        except ssl.SSLError as exc:
            raise CollectionError("TLS_FAILED") from exc
        except TimeoutError as exc:
            raise CollectionError("TIMEOUT") from exc
        except (h11.ProtocolError, UnicodeError) as exc:
            raise CollectionError("HTTP_PROTOCOL_ERROR") from exc
        except OSError as exc:
            raise CollectionError("NETWORK_ERROR") from exc
        finally:
            if writer is not None:
                # Abort, not unbounded TLS close_notify waits on untrusted peers.
                writer.transport.abort()
            sock.close()
